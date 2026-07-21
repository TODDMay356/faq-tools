"""飞书事件订阅回调接口"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/events")
async def feishu_events(request: Request) -> dict[str, Any]:
    """接收飞书应用长事件推送"""
    try:
        body = await request.json()
    except Exception:
        logger.warning("飞书事件回调解析 JSON 失败")
        return {"code": 0, "msg": "ok"}

    event_type = body.get("type")
    if event_type == "url_verification":
        return {"challenge": body.get("challenge", "")}

    scheduler = getattr(request.app.state, "msg_transfer_scheduler", None)
    if not scheduler:
        logger.warning("消息转发调度器未初始化，忽略事件")
        return {"code": 0, "msg": "ok"}

    await scheduler.handle_event(body)
    return {"code": 0, "msg": "ok"}
