"""支付路由服务单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.eos_payment_route_service import (
    add_payment_routes_for_merchant,
    build_partner_bind_payload,
    extract_website_ids,
)


def test_extract_website_ids() -> None:
    """应正确提取网站 ID。"""
    websites = [
        {"webSiteId": "MWS001"},
        {"id": "MWS002"},
        {"webSiteId": None},
    ]
    assert extract_website_ids(websites) == ["MWS001", "MWS002"]


def test_build_partner_bind_payload_success() -> None:
    """合作伙伴绑定参数应正确组装。"""
    payload = build_partner_bind_payload(
        website={"webSiteId": "MWS001", "billingName": "demo-shop"},
        txb_acc_id="VL001",
        merchant={
            "merchant_en_name": "demo-shop",
            "company_id_no": "91440300MA5FMABC7A",
            "legal_name": "li liu",
            "legal_id_no": "110110199909090091",
            "company_register_country": "CN",
        },
    )

    assert payload is not None
    assert payload["webSiteId"] == "MWS001"
    assert payload["flyLoginId"] == "VL001"
    assert payload["partnerCode"] == "EBANX"
    assert payload["billingName"] == "demo-shop"


def test_build_partner_bind_payload_skip_when_missing_fields() -> None:
    """缺少法人信息时应跳过绑定。"""
    payload = build_partner_bind_payload(
        website={"webSiteId": "MWS001", "billingName": "demo-shop"},
        txb_acc_id="VL001",
        merchant={"merchant_en_name": "demo-shop"},
    )
    assert payload is None


@patch("app.services.eos_payment_route_service.bind_partner_merchant")
@patch("app.services.eos_payment_route_service.add_single_payment_route")
@patch("app.services.eos_payment_route_service.fetch_merchant_websites")
@patch("app.services.eos_payment_route_service.fetch_merchant_info")
def test_add_payment_routes_for_merchant_orchestration(
    fetch_merchant_info_mock: MagicMock,
    fetch_websites_mock: MagicMock,
    add_route_mock: MagicMock,
    bind_partner_mock: MagicMock,
) -> None:
    """应根据 MID 串联查询并批量添加路由。"""
    fetch_merchant_info_mock.return_value = {
        "merchant_id": "MT001",
        "txbAccId": "VL001",
        "merchant_en_name": "demo-shop",
        "company_id_no": "91440300MA5FMABC7A",
        "legal_name": "li liu",
        "legal_id_no": "110110199909090091",
    }
    fetch_websites_mock.return_value = {
        "data": {
            "data": [
                {"webSiteId": "MWS001", "billingName": "demo-shop"},
            ]
        }
    }
    add_route_mock.return_value = {"success": True}
    bind_partner_mock.return_value = {"success": True}

    result = add_payment_routes_for_merchant("MT001")

    assert result["merchant_id"] == "MT001"
    assert result["txb_acc_id"] == "VL001"
    assert result["web_site_ids"] == ["MWS001"]
    assert add_route_mock.call_count == 3
    bind_partner_mock.assert_called_once()
    fetch_merchant_info_mock.assert_called_once_with("MT001")
    fetch_websites_mock.assert_called_once_with(txb_acc_id="VL001")
