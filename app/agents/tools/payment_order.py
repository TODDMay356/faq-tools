import logging
from typing import Optional

import requests
from langchain.tools import tool
from pydantic import BaseModel, Field

from app.utils.eos_client import get_eos_client

logger = logging.getLogger(__name__)


class PaymentOrderInput(BaseModel):
    """支付订单查询参数"""
    page: int = Field(default=1, description="页码")
    page_size: int = Field(default=10, description="每页数量")
    payment_order_id: Optional[str] = Field(default=None, description="支付订单号")
    login_id: Optional[str] = Field(default=None, description="登录ID")
    status: Optional[str] = Field(default=None, description="订单状态")
    invoice_id: Optional[str] = Field(default=None, description="商户订单号,当没有指定是什么订单号时优先用这个订单号查询")
    trade_id: Optional[str] = Field(default=None, description="交易ID")
    merchant_name: Optional[str] = Field(default=None, description="商户名称")
    create_time_begin: Optional[int] = Field(default=None, description="创建时间开始（时间戳）")
    create_time_end: Optional[int] = Field(default=None, description="创建时间结束（时间戳）")


@tool(args_schema=PaymentOrderInput, description="查询支付订单列表")
def query_payment_orders(
    page: int = 1,
    page_size: int = 10,
    payment_order_id: Optional[str] = None,
    login_id: Optional[str] = None,
    status: Optional[str] = None,
    invoice_id: Optional[str] = None,
    trade_id: Optional[str] = None,
    merchant_name: Optional[str] = None,
    create_time_begin: Optional[int] = None,
    create_time_end: Optional[int] = None
):
    """查询支付订单列表"""
    logger.info(f"[Tool] query_payment_orders 调用 - invoice_id: {invoice_id}, payment_order_id: {payment_order_id}")
    
    url = f"https://test.inflyway.com/paycenter/eos/payorder/list/{page}/{page_size}"
    headers, cookies = get_eos_client().get_request_auth()
    
    payload = {}
    if payment_order_id:
        payload["paymentOrderId"] = payment_order_id
    if login_id:
        payload["loginId"] = login_id
    if status:
        payload["status"] = status
    if invoice_id:
        payload["invoiceId"] = invoice_id
    if trade_id:
        payload["tradeId"] = trade_id
    if merchant_name:
        payload["merchantName"] = merchant_name
    if create_time_begin:
        payload["createTimeBegin"] = create_time_begin
    if create_time_end:
        payload["createTimeEnd"] = create_time_end
    
    try:
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)
        response.raise_for_status()
        result = response.json()
        logger.info(f"[Tool] query_payment_orders 成功 - 返回数据量: {len(result.get('data', {}).get('data', []))}")
        return result
    except Exception as e:
        logger.exception(f"[Tool] query_payment_orders 失败 - error: {e}")
        return {"error": str(e)}
