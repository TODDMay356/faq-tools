"""EOS 支付路由编排服务。"""

from __future__ import annotations

import logging
from typing import Any

import requests

from app.services.eos_merchant_service import fetch_merchant_info, fetch_merchant_websites
from app.core.eos_config import (
    DEFAULT_PAYMENT_ROUTE_CONFIGS,
    EOS_PAYCENTER_BASE_URL,
    PARTNER_BIND_PARTNER_CODE,
)
from app.utils.eos_client import get_eos_client

logger = logging.getLogger(__name__)

ROUTE_ADD_URL = f"{EOS_PAYCENTER_BASE_URL}/merchant/route/add"
PARTNER_BIND_URL = f"{EOS_PAYCENTER_BASE_URL}/partner/merchant/bind"


def extract_website_items(websites_result: dict[str, Any]) -> list[dict[str, Any]]:
    """从网站查询结果中提取网站列表。"""
    data = websites_result.get("data", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def extract_website_ids(websites: list[dict[str, Any]]) -> list[str]:
    """提取网站 ID 列表。"""
    website_ids: list[str] = []
    for website in websites:
        website_id = website.get("webSiteId") or website.get("id")
        if website_id:
            website_ids.append(str(website_id))
    return website_ids


def post_eos_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """发送 EOS JSON 请求。"""
    headers, cookies = get_eos_client().get_request_auth()
    response = requests.post(url, json=payload, headers=headers, cookies=cookies, timeout=30.0)
    response.raise_for_status()
    return response.json()


def add_single_payment_route(
    *,
    web_site_ids: list[str],
    pay_style_ids: list[str],
    bank_aisle_id: str,
    mid_name: str,
    txb_acc_id: str,
) -> dict[str, Any]:
    """调用单个支付路由添加接口。"""
    payload = {
        "matchMidCurrency": "1",
        "country": ["GLOBAL"],
        "busType": "PCB01",
        "payStyleId": "",
        "webSiteIds": web_site_ids,
        "payStyleIds": pay_style_ids,
        "bankAisleId": bank_aisle_id,
        "midName": mid_name,
        "txbAccId": txb_acc_id,
    }
    logger.info(
        "添加支付路由 - bank_aisle_id=%s, mid_name=%s, web_site_ids=%s",
        bank_aisle_id,
        mid_name,
        web_site_ids,
    )
    return post_eos_json(ROUTE_ADD_URL, payload)


def build_partner_bind_payload(
    *,
    website: dict[str, Any],
    txb_acc_id: str,
    merchant: dict[str, Any],
) -> dict[str, str] | None:
    """构建合作伙伴绑定请求体。"""
    web_site_id = website.get("webSiteId") or website.get("id")
    if not web_site_id:
        return None

    billing_name = (
        website.get("billingName")
        or website.get("billName")
        or merchant.get("merchant_en_name")
        or merchant.get("merchant_name")
        or ""
    )
    company_en_name = merchant.get("merchant_en_name") or billing_name
    company_id_no = merchant.get("company_id_no") or merchant.get("companyIdNo") or ""
    legal_name = merchant.get("legal_name") or merchant.get("legalName") or ""
    legal_id_no = merchant.get("legal_id_no") or merchant.get("legalIdNo") or ""

    if not all([billing_name, company_en_name, company_id_no, legal_name, legal_id_no]):
        logger.warning("跳过合作伙伴绑定，缺少必要字段 - web_site_id=%s", web_site_id)
        return None

    return {
        "webSiteId": str(web_site_id),
        "flyLoginId": txb_acc_id,
        "billingName": str(billing_name),
        "partnerCode": PARTNER_BIND_PARTNER_CODE,
        "companyEnName": str(company_en_name),
        "companyRegisterCountry": str(
            merchant.get("company_register_country")
            or merchant.get("companyRegisterCountry")
            or "CN"
        ),
        "companyIdNo": str(company_id_no),
        "legalName": str(legal_name),
        "legalIdNo": str(legal_id_no),
    }


def bind_partner_merchant(
    *,
    website: dict[str, Any],
    txb_acc_id: str,
    merchant: dict[str, Any],
) -> dict[str, Any] | None:
    """调用合作伙伴商户绑定接口。"""
    payload = build_partner_bind_payload(
        website=website,
        txb_acc_id=txb_acc_id,
        merchant=merchant,
    )
    if payload is None:
        return None

    logger.info(
        "绑定合作伙伴商户 - web_site_id=%s, partner=%s",
        payload["webSiteId"],
        payload["partnerCode"],
    )
    return post_eos_json(PARTNER_BIND_URL, payload)


def add_payment_routes_for_merchant(merchant_id: str) -> dict[str, Any]:
    """根据商户 MID 查询信息并批量添加支付路由。

    Args:
        merchant_id: 商户 ID（MID）。

    Returns:
        包含商户信息、网站信息、路由添加及合作伙伴绑定结果的字典。
    """
    merchant = fetch_merchant_info(merchant_id)
    if merchant.get("error"):
        return merchant

    txb_acc_id = merchant.get("txbAccId")
    if not txb_acc_id:
        return {"error": f"商户 {merchant_id} 未找到 txbAccId"}

    websites_result = fetch_merchant_websites(txb_acc_id=txb_acc_id)
    if websites_result.get("error"):
        return websites_result

    websites = extract_website_items(websites_result)
    web_site_ids = extract_website_ids(websites)
    if not web_site_ids:
        return {"error": f"商户 {merchant_id} 未找到可用网站信息"}

    route_results: list[dict[str, Any]] = []
    for route_config in DEFAULT_PAYMENT_ROUTE_CONFIGS:
        try:
            result = add_single_payment_route(
                web_site_ids=web_site_ids,
                pay_style_ids=list(route_config["pay_style_ids"]),  # type: ignore[arg-type]
                bank_aisle_id=str(route_config["bank_aisle_id"]),
                mid_name=str(route_config["mid_name"]),
                txb_acc_id=txb_acc_id,
            )
            route_results.append(
                {
                    "bank_aisle_id": route_config["bank_aisle_id"],
                    "mid_name": route_config["mid_name"],
                    "success": True,
                    "result": result,
                }
            )
        except Exception as exc:
            logger.exception("添加支付路由失败 - bank_aisle_id=%s", route_config["bank_aisle_id"])
            route_results.append(
                {
                    "bank_aisle_id": route_config["bank_aisle_id"],
                    "mid_name": route_config["mid_name"],
                    "success": False,
                    "error": str(exc),
                }
            )

    partner_bind_results: list[dict[str, Any]] = []
    for website in websites:
        try:
            bind_result = bind_partner_merchant(
                website=website,
                txb_acc_id=txb_acc_id,
                merchant=merchant,
            )
            if bind_result is None:
                partner_bind_results.append(
                    {
                        "web_site_id": website.get("webSiteId") or website.get("id"),
                        "skipped": True,
                        "reason": "缺少合作伙伴绑定必要字段",
                    }
                )
                continue
            partner_bind_results.append(
                {
                    "web_site_id": website.get("webSiteId") or website.get("id"),
                    "success": True,
                    "result": bind_result,
                }
            )
        except Exception as exc:
            logger.exception(
                "合作伙伴绑定失败 - web_site_id=%s",
                website.get("webSiteId") or website.get("id"),
            )
            partner_bind_results.append(
                {
                    "web_site_id": website.get("webSiteId") or website.get("id"),
                    "success": False,
                    "error": str(exc),
                }
            )

    return {
        "merchant_id": merchant_id,
        "txb_acc_id": txb_acc_id,
        "web_site_ids": web_site_ids,
        "merchant": merchant,
        "websites": websites,
        "route_results": route_results,
        "partner_bind_results": partner_bind_results,
    }
