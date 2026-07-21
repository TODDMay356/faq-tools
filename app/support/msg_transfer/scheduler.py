"""消息转发调度器（事件驱动 + 定时轮询）"""
import asyncio
import logging
import time
from typing import Optional

from app.support.collect_info.feishu_client import FeishuClient
from .config import MsgTransferSettings, get_msg_transfer_settings
from .transfer import MsgTransfer

logger = logging.getLogger(__name__)


class MsgTransferScheduler:
    """消息转发调度器（长连接事件 + 定时轮询群消息）"""
    
    def __init__(
        self,
        feishu_app_id: str,
        feishu_app_secret: str,
        source_chat_ids: list,
        target_chat_ids: list,
        keywords: list,
        mention_user_ids: list,
        poll_interval: int = 60,
        max_forward_count: int = 3,
        forward_interval: int = 300,
        poll_max_pages: int = 3,
        poll_lookback_seconds: int = 30,
    ):
        self.feishu_client = FeishuClient(feishu_app_id, feishu_app_secret)
        self.transfer = MsgTransfer(
            feishu_client=self.feishu_client,
            source_chat_ids=source_chat_ids,
            target_chat_ids=target_chat_ids,
            keywords=keywords,
            mention_user_ids=mention_user_ids,
            max_forward_count=max_forward_count,
            forward_interval=forward_interval,
            poll_max_pages=poll_max_pages,
            poll_lookback_seconds=poll_lookback_seconds,
        )
        self.poll_interval = poll_interval
        self.running = False
    
    async def run_once(self) -> int:
        """兼容接口：执行一次轮询检查，返回转发数量"""
        try:
            logger.debug("开始执行兼容轮询检查")
            count = await self.transfer.process_messages()
            if count > 0:
                logger.info(f"本次转发消息 {count} 条")
            return count
        except Exception as e:
            logger.error(f"消息转发检查失败: {e}", exc_info=True)
            return 0
    
    async def start(self) -> None:
        """启动调度器：定时轮询源群消息并转发，同时周期性清理缓存"""
        self.running = True
        logger.info(
            f"消息转发调度器已启动，"
            f"源群: {len(self.transfer.source_chat_ids)} 个, "
            f"目标群: {len(self.transfer.target_chat_ids)} 个, "
            f"关键词: {self.transfer.keywords}, "
            f"轮询间隔: {self.poll_interval}秒"
        )

        last_cache_cleanup = time.time()
        cache_cleanup_interval = 3600

        while self.running:
            await self.run_once()

            now = time.time()
            if now - last_cache_cleanup >= cache_cleanup_interval:
                self.transfer.cleanup_cache(max_age_hours=24)
                last_cache_cleanup = now

            await asyncio.sleep(self.poll_interval)

    async def handle_event(self, event_body: dict) -> bool:
        """处理飞书长事件推送消息"""
        try:
            header = event_body.get("header", {}) or {}
            event = event_body.get("event", {}) or {}
            event_type = header.get("event_type", "") or event.get("type", "")
            message = event.get("message", {}) or {}
            sender = event.get("sender", {}) or {}

            # SDK 长连接场景下 event_type 可能为空；只要包含 message 字段就按消息事件处理
            if event_type and event_type != "im.message.receive_v1":
                logger.debug("忽略非消息事件: %s", event_type)
                return False

            if not message:
                logger.debug("收到事件但无 message 字段，event_type=%s", event_type or "unknown")
                return False

            logger.info(
                "收到飞书消息事件: message_id=%s chat_id=%s message_type=%s",
                message.get("message_id"),
                message.get("chat_id"),
                message.get("message_type"),
            )
            message_payload = dict(message)
            message_payload["sender"] = sender
            forwarded = await self.transfer.process_event_message(message_payload)
            if forwarded:
                logger.info("事件消息转发成功: %s", message.get("message_id"))
            else:
                logger.info("事件消息未触发转发: %s", message.get("message_id"))
            return forwarded
        except Exception as e:
            logger.error(f"处理消息事件失败: {e}", exc_info=True)
            return False
    
    def stop(self) -> None:
        """停止定时任务"""
        self.running = False
        logger.info("消息转发调度器已停止")
    
    @classmethod
    def from_settings(cls, settings: Optional[MsgTransferSettings] = None) -> Optional["MsgTransferScheduler"]:
        """从配置创建调度器实例"""
        if settings is None:
            settings = get_msg_transfer_settings()
        
        if not settings.is_configured():
            logger.warning("消息转发配置不完整，跳过创建调度器")
            return None
        
        return cls(
            feishu_app_id=settings.feishu_app_id,
            feishu_app_secret=settings.feishu_app_secret,
            source_chat_ids=settings.get_source_chat_list(),
            target_chat_ids=settings.get_target_chat_list(),
            keywords=settings.get_keywords_list(),
            mention_user_ids=settings.get_mention_user_list(),
            poll_interval=settings.poll_interval,
            max_forward_count=settings.max_forward_count,
            forward_interval=settings.forward_interval,
            poll_max_pages=settings.poll_max_pages,
            poll_lookback_seconds=settings.poll_lookback_seconds,
        )
