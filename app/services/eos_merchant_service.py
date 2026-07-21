"""EOS 商户与网站查询服务。"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx
import requests

from app.utils.eos_client import get_eos_client

logger = logging.getLogger(__name__)

MERCHANT_LIST_URL = "https://test.inflyway.com/paycenter/eos/merchant/list/1/1"
WEBSITE_LIST_URL = (
    "https://test.inflyway.com/paycenter/eos/merchant/website/list/{page}/{page_size}"
)


def fetch_merchant_info(merchant_id: str) -> dict[str, Any]:
    """查询商户详细信息。

    Args:
        merchant_id: 商户 ID（MID）。

    Returns:
        商户信息字典；失败时包含 error 字段。
    """
    if not merchant_id:
        return {"error": "merchant_id 不能为空"}

    try:
        url = f"{MERCHANT_LIST_URL}?merchantId={merchant_id}"
        headers, cookies = get_eos_client().get_request_auth()

        with httpx.Client() as client:
            response = client.get(
                url,
                headers=headers,
                cookies=cookies,
                timeout=10.0,
            )
            response.raise_for_status()
            result = response.json()

        if result.get("success") and result.get("data", {}).get("data"):
            merchant_data = result["data"]["data"][0]
            return {
                "merchant_id": merchant_data.get("merchantId"),
                "txbAccId": merchant_data.get("txbAccId"),
                "merchant_name": merchant_data.get("merchantName"),
                "merchant_en_name": merchant_data.get("merchantEnName"),
                "email": merchant_data.get("email"),
                "status": merchant_data.get("status"),
                "camelpay_status": merchant_data.get("camelpayStatus"),
                "camelpay_mid": merchant_data.get("camelpayMid"),
                "bus_type": merchant_data.get("busType"),
                "margin_rate": merchant_data.get("marginRate"),
                "margin_freeze_period": merchant_data.get("marginFreezePeriod"),
                "integration_mode": merchant_data.get("integrationMode"),
                "create_time": merchant_data.get("createTime"),
                "interfaceSecret": merchant_data.get("interfaceSecret"),
                "publicKey": merchant_data.get("publicKey"),
                "company_id_no": merchant_data.get("companyIdNo"),
                "legal_name": merchant_data.get("legalName"),
                "legal_id_no": merchant_data.get("legalIdNo"),
                "company_register_country": merchant_data.get("companyRegisterCountry"),
            }

        return {"error": "未找到商户信息"}
    except Exception as exc:
        logger.exception("fetch_merchant_info 失败 - merchant_id=%s", merchant_id)
        return {"error": f"获取商户信息失败: {exc}"}


def fetch_merchant_websites(
    txb_acc_id: Optional[str] = None,
    web_site: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """查询商户网站信息列表。

    Args:
        txb_acc_id: 商户账号 ID。
        web_site: 网站地址。
        page: 页码。
        page_size: 每页数量。

    Returns:
        网站查询结果；失败时包含 error 字段。
    """
    url = WEBSITE_LIST_URL.format(page=page, page_size=page_size)
    headers, cookies = get_eos_client().get_request_auth()

    params: dict[str, str] = {}
    if txb_acc_id:
        params["txbAccId"] = txb_acc_id
    if web_site:
        params["webSite"] = web_site

    try:
        response = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=30.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.exception("fetch_merchant_websites 失败 - txb_acc_id=%s", txb_acc_id)
        return {"error": str(exc)}
