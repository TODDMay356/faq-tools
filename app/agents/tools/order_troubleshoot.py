"""根据订单号排查订单问题的 Agent 工具。"""

from __future__ import annotations

import logging
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from app.services.order_issue_analyzer import troubleshoot_order_issue

logger = logging.getLogger(__name__)


class OrderTroubleshootInput(BaseModel):
    """订单问题排查参数。"""

    order_no: str = Field(description="订单号，例如 224180-1214100_77120")


@tool(
    args_schema=OrderTroubleshootInput,
    description=(
        "根据订单号排查订单问题：查询最近5天订单链路日志（payment/create、api/pay），"
        "获取日志详情，查询商户信息、商户网址、商户路由，"
        "并分析 notify_url 域名、币种支付方式、source 字段、金额格式等问题"
    ),
)
def troubleshoot_order_by_no(order_no: str) -> dict[str, Any]:
    """根据订单号排查商户接口问题。"""
    logger.info("[Tool] troubleshoot_order_by_no 调用 - order_no=%s", order_no)
    try:
        result = troubleshoot_order_issue(order_no, use_llm=True)
        logger.info(
            "[Tool] troubleshoot_order_by_no 完成 - order_no=%s, investigations=%s",
            order_no,
            len(result.get("investigations", [])),
        )
        return result
    except Exception as exc:
        logger.exception("[Tool] troubleshoot_order_by_no 失败 - order_no=%s", order_no)
        return {"error": str(exc)}
