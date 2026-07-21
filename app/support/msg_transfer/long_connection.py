"""飞书长连接事件客户端"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Optional

import lark_oapi as lark

from .scheduler import MsgTransferScheduler

logger = logging.getLogger(__name__)


class FeishuLongConnectionClient:
    """基于飞书 SDK 的长连接事件客户端"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        scheduler: Optional[MsgTransferScheduler],
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.scheduler = scheduler
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def _on_message_receive(self, data) -> None:
        """处理 im.message.receive_v1 事件"""
        try:
            payload_str = lark.JSON.marshal(data) or "{}"
            payload = json.loads(payload_str)
            if self._loop is None or self._loop.is_closed():
                logger.warning("事件循环不可用，忽略飞书事件")
                return
            if self.scheduler is None:
                logger.warning("消息转发调度器未就绪，忽略飞书事件")
                return
            event = payload.get("event", {}) if isinstance(payload, dict) else {}
            message = event.get("message", {}) if isinstance(event, dict) else {}
            logger.info(
                "长连接收到事件: message_id=%s chat_id=%s message_type=%s",
                message.get("message_id"),
                message.get("chat_id"),
                message.get("message_type"),
            )
            asyncio.run_coroutine_threadsafe(self.scheduler.handle_event(payload), self._loop)
        except Exception as e:
            logger.error("处理飞书长连接事件失败: %s", e, exc_info=True)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """启动长连接客户端"""
        self._loop = loop

        handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_message_receive)
            .build()
        )
        client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
        )

        self._thread = threading.Thread(
            target=client.start,
            name="feishu-long-connection",
            daemon=True,
        )
        self._thread.start()
        logger.info("飞书长连接客户端已启动")
