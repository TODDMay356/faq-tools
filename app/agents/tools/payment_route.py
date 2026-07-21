"""支付路由 Agent 工具。"""

from __future__ import annotations

import logging
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel, Field

from app.services.eos_payment_route_service import add_payment_routes_for_merchant

logger = logging.getLogger(__name__)


class PaymentRouteInput(BaseModel):
    """添加支付路由参数。"""

    merchant_id: str = Field(description="商户ID（MID），例如 MT200010000003605")


@tool(
    args_schema=PaymentRouteInput,
    description=(
        "根据商户MID自动添加支付路由配置：先查询商户信息获取txbAccId，"
        "再查询商户网站，最后批量添加PPRO/EBANX/ONERWAY路由并绑定EBANX合作伙伴"
    ),
)
def add_payment_route(merchant_id: str) -> dict[str, Any]:
    """根据商户 MID 自动添加支付路由。"""
    logger.info("[Tool] add_payment_route 调用 - merchant_id: %s", merchant_id)
    try:
        result = add_payment_routes_for_merchant(merchant_id)
        logger.info(
            "[Tool] add_payment_route 完成 - merchant_id=%s, routes=%s",
            merchant_id,
            len(result.get("route_results", [])),
        )
        return result
    except Exception as exc:
        logger.exception("[Tool] add_payment_route 失败 - merchant_id=%s", merchant_id)
        return {"error": str(exc)}
