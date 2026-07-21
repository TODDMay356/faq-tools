"""消息转发核心逻辑"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MessageRecord:
    """消息记录"""
    message_id: str
    content: str
    sender_id: str
    sender_name: str
    create_time: int
    forward_count: int = 0
    last_forward_time: float = 0.0


class MsgTransfer:
    """消息转发处理器"""
    
    def __init__(
        self,
        feishu_client,
        source_chat_ids: List[str],
        target_chat_ids: List[str],
        keywords: List[str],
        mention_user_ids: List[str],
        max_forward_count: int = 3,
        forward_interval: int = 300,
        poll_max_pages: int = 3,
        poll_lookback_seconds: int = 30,
    ):
        self.feishu_client = feishu_client
        self.source_chat_ids = source_chat_ids
        self.target_chat_ids = target_chat_ids
        self.keywords = keywords
        self.mention_user_ids = mention_user_ids
        self.max_forward_count = max_forward_count
        self.forward_interval = forward_interval
        self.poll_max_pages = poll_max_pages
        self.poll_lookback_seconds = poll_lookback_seconds
        
        # 消息缓存：message_id -> MessageRecord
        self._message_cache: Dict[str, MessageRecord] = {}
        
        # 各源群最后查询的消息时间戳，用于增量查询
        self._last_message_time: Dict[str, int] = {}

    def _extract_text_content(self, content_str: str) -> str:
        """从消息 content 字段中解析文本内容"""
        try:
            content_data = json.loads(content_str or "{}")
            return content_data.get("text", "")
        except json.JSONDecodeError:
            return content_str or ""

    def _extract_message_text(self, msg_type: str, content_str: str) -> str:
        """从各类消息体中提取可用于关键词匹配的文本"""
        if msg_type == "text":
            return self._extract_text_content(content_str)
        # 富文本/卡片等：在原始 JSON 字符串中做关键词匹配
        if msg_type in ("post", "interactive", "share_chat", "merge_forward"):
            return content_str or ""
        return ""
    
    def _match_keywords(self, content: str) -> bool:
        """检查消息内容是否匹配关键词"""
        if not content:
            return False
        content_lower = content.lower()
        for keyword in self.keywords:
            if keyword.lower() in content_lower:
                return True
        return False
    
    def _build_mention_content(self, original_content: str) -> str:
        """构建带@的消息内容"""
        if not self.mention_user_ids:
            return original_content
        
        # 构建@用户列表
        mention_parts = []
        for user_id in self.mention_user_ids:
            mention_parts.append(f"<at user_id=\"{user_id}\"></at>")
        
        mention_str = " ".join(mention_parts)
        return f"{mention_str}\n{original_content}"
    
    async def get_chat_messages(
        self,
        chat_id: str,
        start_time: Optional[int] = None,
        page_size: int = 50,
        max_pages: int = 3,
        recent_only: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """获取群聊消息列表

        Args:
            chat_id: 群聊 ID（oc_ 开头）
            start_time: 起始时间戳（毫秒），用于增量查询；传给飞书 API 时会转为秒
            page_size: 每页消息数量
            max_pages: 最多请求分页数，防止拉取全量历史
            recent_only: 为 True 时仅拉最近一页（降序），用于首次建立水位线

        Returns:
            (消息列表, 实际请求页数)
        """
        token = await self.feishu_client.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        base_params: Dict[str, Any] = {
            "container_id_type": "chat",
            "container_id": chat_id,
            "page_size": page_size,
            "sort_type": "ByCreateTimeDesc" if recent_only else "ByCreateTimeAsc",
        }

        if start_time and not recent_only:
            start_ms = int(start_time)
            start_seconds = start_ms // 1000 + (1 if start_ms > 1_000_000_000_000 else 0)
            base_params["start_time"] = str(start_seconds)

        url = f"{self.feishu_client.base_url}/im/v1/messages"
        all_items: List[Dict[str, Any]] = []
        pages_fetched = 0

        async with httpx.AsyncClient(timeout=30) as client:
            page_token: Optional[str] = None
            while pages_fetched < max_pages:
                params = dict(base_params)
                if page_token:
                    params["page_token"] = page_token

                response = await client.get(url, headers=headers, params=params)
                data = response.json()
                pages_fetched += 1

                if data.get("code") != 0:
                    logger.error("获取消息失败: chat_id=%s response=%s", chat_id, data)
                    break

                resp_data = data.get("data", {}) or {}
                items = resp_data.get("items", []) or []
                all_items.extend(items)

                if not resp_data.get("has_more"):
                    break
                page_token = resp_data.get("page_token")
                if not page_token:
                    break

        return all_items, pages_fetched
    
    async def process_messages(self) -> int:
        """处理消息，返回转发数量"""
        forward_count = 0
        for source_chat_id in self.source_chat_ids:
            forward_count += await self._process_messages_for_chat(source_chat_id)
        return forward_count

    async def _process_messages_for_chat(self, source_chat_id: str) -> int:
        """处理单个源群的消息"""
        try:
            last_time = self._last_message_time.get(source_chat_id, 0)

            if last_time == 0:
                messages, pages = await self.get_chat_messages(
                    source_chat_id,
                    max_pages=1,
                    recent_only=True,
                )
                if messages:
                    max_create_time = max(
                        int(m.get("create_time", 0) or 0) for m in messages
                    )
                    self._last_message_time[source_chat_id] = max_create_time
                logger.info(
                    "源群 %s 首次轮询: 查询 %d 条(%d 页)，已建立水位线，跳过历史转发",
                    source_chat_id[:20],
                    len(messages),
                    pages,
                )
                return 0

            # 略向前回溯，避免轮询间隔内漏消息
            query_start = max(0, last_time - self.poll_lookback_seconds * 1000)
            watermark = last_time

            messages, pages = await self.get_chat_messages(
                source_chat_id,
                start_time=query_start,
                max_pages=self.poll_max_pages,
            )

            if not messages:
                logger.info(
                    "源群 %s 本轮: 查询 0 条(0 页)，无新消息",
                    source_chat_id[:20],
                )
                return 0

            forward_count = 0
            current_time = time.time()
            max_create_time = watermark
            stats = {
                "fetched": len(messages),
                "pages": pages,
                "newer_than_watermark": 0,
                "matchable": 0,
                "keyword_hit": 0,
                "skipped_type": 0,
                "skipped_keyword": 0,
                "skipped_cache": 0,
            }

            messages.sort(key=lambda x: int(x.get("create_time", 0) or 0))

            for msg in messages:
                msg_id = msg.get("message_id")
                msg_type = msg.get("msg_type")
                try:
                    create_time = int(msg.get("create_time", 0) or 0)
                except (TypeError, ValueError):
                    create_time = 0

                max_create_time = max(max_create_time, create_time)

                if create_time <= watermark:
                    continue

                stats["newer_than_watermark"] += 1

                content_str = msg.get("body", {}).get("content", "{}")
                text_content = self._extract_message_text(msg_type, content_str)

                if not text_content and msg_type not in ("text", "post", "interactive"):
                    stats["skipped_type"] += 1
                    continue

                stats["matchable"] += 1

                if not self._match_keywords(text_content):
                    stats["skipped_keyword"] += 1
                    continue

                stats["keyword_hit"] += 1

                if msg_id in self._message_cache:
                    record = self._message_cache[msg_id]

                    if record.forward_count >= self.max_forward_count:
                        stats["skipped_cache"] += 1
                        continue

                    if current_time - record.last_forward_time < self.forward_interval:
                        stats["skipped_cache"] += 1
                        continue

                    if await self._forward_message(record, text_content, msg):
                        forward_count += 1
                else:
                    sender_info = msg.get("sender", {})
                    sender_id = sender_info.get("id", "")

                    record = MessageRecord(
                        message_id=msg_id,
                        content=text_content,
                        sender_id=sender_id,
                        sender_name=sender_info.get("name", "未知用户"),
                        create_time=create_time,
                    )
                    self._message_cache[msg_id] = record

                    if await self._forward_message(record, text_content, msg):
                        forward_count += 1

            self._last_message_time[source_chat_id] = max_create_time

            logger.info(
                "源群 %s 本轮: 查询 %d 条(%d 页), 水位后新消息 %d, 可匹配 %d, "
                "关键词命中 %d, 跳过类型 %d, 跳过关键词 %d, 跳过缓存/间隔 %d, 转发 %d",
                source_chat_id[:20],
                stats["fetched"],
                stats["pages"],
                stats["newer_than_watermark"],
                stats["matchable"],
                stats["keyword_hit"],
                stats["skipped_type"],
                stats["skipped_keyword"],
                stats["skipped_cache"],
                forward_count,
            )
            return forward_count

        except Exception as e:
            logger.error(f"处理源群 {source_chat_id} 消息失败: {e}", exc_info=True)
            return 0

    async def process_event_message(self, event_message: Dict[str, Any]) -> bool:
        """处理飞书事件推送的单条消息"""
        try:
            msg_id = event_message.get("message_id")
            chat_id = event_message.get("chat_id")
            msg_type = event_message.get("message_type")
            create_time_raw = event_message.get("create_time", 0)
            content_str = event_message.get("content", "{}")
            sender_info = event_message.get("sender", {})

            if not msg_id:
                logger.debug("跳过无 message_id 的事件消息")
                return False

            if chat_id not in self.source_chat_ids:
                logger.info(
                    "跳过非源群消息: message_id=%s chat_id=%s expected_chat_ids=%s",
                    msg_id,
                    chat_id,
                    self.source_chat_ids,
                )
                return False

            try:
                create_time = int(create_time_raw)
            except (TypeError, ValueError):
                create_time = 0

            text_content = self._extract_message_text(msg_type or "", content_str)
            if not text_content:
                logger.info("跳过无文本内容消息: message_id=%s msg_type=%s", msg_id, msg_type)
                return False
            if not self._match_keywords(text_content):
                logger.info("关键词不匹配，跳过转发: message_id=%s content=%s", msg_id, text_content[:100])
                return False

            now = time.time()
            if msg_id in self._message_cache:
                record = self._message_cache[msg_id]
                if record.forward_count >= self.max_forward_count:
                    logger.info("达到最大转发次数，跳过: message_id=%s", msg_id)
                    return False
                if now - record.last_forward_time < self.forward_interval:
                    logger.info("未到重复转发间隔，跳过: message_id=%s", msg_id)
                    return False
            else:
                record = MessageRecord(
                    message_id=msg_id,
                    content=text_content,
                    sender_id=sender_info.get("sender_id", {}).get("user_id", ""),
                    sender_name=sender_info.get("sender_id", {}).get("open_id", "未知用户"),
                    create_time=create_time,
                )
                self._message_cache[msg_id] = record

            success = await self._forward_message(
                record=record,
                content=text_content,
                original_msg={"message_id": msg_id},
            )
            return success
        except Exception as e:
            logger.error(f"处理事件消息失败: {e}", exc_info=True)
            return False
    
    async def _forward_message(
        self,
        record: MessageRecord,
        content: str,
        original_msg: Dict[str, Any]
    ) -> bool:
        """转发消息到目标群（保持原消息格式）"""
        try:
            message_id = original_msg.get("message_id")
            
            for target_chat_id in self.target_chat_ids:
                await self.feishu_client.forward_message(
                    message_id=message_id,
                    receive_id=target_chat_id,
                    receive_id_type="chat_id"
                )
            
            record.forward_count += 1
            record.last_forward_time = time.time()
            
            logger.info(
                f"消息转发成功 [ID:{record.message_id}] "
                f"[目标群数:{len(self.target_chat_ids)}] "
                f"[次数:{record.forward_count}/{self.max_forward_count}]"
            )
            
            if self.mention_user_ids:
                await self._send_mention_message()
            
            return True
            
        except Exception as e:
            logger.error(f"转发消息失败: {e}", exc_info=True)
            return False
    
    async def _send_mention_message(self) -> bool:
        """发送@提醒消息"""
        try:
            # 构建@用户列表
            mention_parts = []
            for user_id in self.mention_user_ids:
                mention_parts.append(f"<at user_id=\"{user_id}\"></at>")
            
            mention_str = " ".join(mention_parts)
            content = f"{mention_str} 请关注以上消息"
            
            for target_chat_id in self.target_chat_ids:
                await self.feishu_client.send_message(
                    receive_id=target_chat_id,
                    msg_type="text",
                    content=json.dumps({"text": content}),
                    receive_id_type="chat_id"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"发送@消息失败: {e}", exc_info=True)
            return False
    
    def cleanup_cache(self, max_age_hours: int = 24):
        """清理过期缓存"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        expired_keys = [
            msg_id for msg_id, record in self._message_cache.items()
            if current_time - record.create_time / 1000 > max_age_seconds
        ]
        
        for key in expired_keys:
            del self._message_cache[key]
        
        if expired_keys:
            logger.info(f"清理过期消息缓存: {len(expired_keys)} 条")
