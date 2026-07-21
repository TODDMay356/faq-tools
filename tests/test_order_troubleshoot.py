"""订单排查服务单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.order_issue_analyzer import (
    check_amount_two_decimals,
    check_notify_url_domain,
    check_source_field,
    run_rule_checks,
    troubleshoot_order_issue,
)
from app.services.order_trace_service import (
    _matches_target_url,
    collect_target_trace_details,
    extract_merchant_id,
    extract_request_params,
)


def test_matches_target_url() -> None:
    """应识别目标接口 URL。"""
    assert _matches_target_url(
        "https://payapi-test.inflyway.com/paycenter/api/v2/order/payment/create"
    )
    assert _matches_target_url("https://payapi-test.inflyway.com/paycenter/api/pay")
    assert not _matches_target_url("https://example.com/other")


def test_extract_request_params_from_response_param() -> None:
    """应解析 RESPONSE_PARAM 字段。"""
    detail = {
        "data": {
            "RESPONSE_PARAM": (
                '{"notify_url":"https://shop.example.com/notify",'
                '"source":"S004","amount":"10.00","currency":"USD","payStyleId":"PS0103"}'
            )
        }
    }
    params = extract_request_params(detail)
    assert params["notify_url"] == "https://shop.example.com/notify"
    assert params["source"] == "S004"


def test_extract_merchant_id() -> None:
    """应提取 MID。"""
    detail = {"data": {"merchantId": "MT200010000003605"}}
    params = {"merchant_id": "MT999"}
    assert extract_merchant_id(detail, params) == "MT200010000003605"


def test_check_notify_url_domain_pass() -> None:
    """notify_url 域名一致时应通过。"""
    result = check_notify_url_domain(
        "https://shop.example.com/notify",
        [{"webSite": "https://shop.example.com"}],
    )
    assert result["passed"] is True


def test_check_source_field_fail() -> None:
    """source 非 S004 时应失败。"""
    result = check_source_field("S001")
    assert result["passed"] is False


def test_check_amount_two_decimals() -> None:
    """金额应校验两位小数。"""
    assert check_amount_two_decimals("10.00")["passed"] is True
    assert check_amount_two_decimals("10.0")["passed"] is False
    assert check_amount_two_decimals("10")["passed"] is False


def test_run_rule_checks() -> None:
    """规则检查应覆盖四个核心点。"""
    checks = run_rule_checks(
        {
            "notify_url": "https://shop.example.com/notify",
            "source": "S004",
            "amount": "10.00",
            "currency": "USD",
            "payStyleId": "PS0103",
        },
        [{"webSite": "https://shop.example.com"}],
        [{"currency": "USD", "payStyleId": "PS0103"}],
    )
    assert len(checks) == 4
    assert all(check["passed"] for check in checks)


@patch("app.services.order_issue_analyzer.analyze_with_llm", return_value="诊断完成")
@patch("app.services.order_issue_analyzer.fetch_merchant_route")
@patch("app.services.order_issue_analyzer.fetch_merchant_websites")
@patch("app.services.order_issue_analyzer.fetch_merchant_info")
@patch("app.services.order_issue_analyzer.collect_target_trace_details")
def test_troubleshoot_order_issue_orchestration(
    collect_trace_mock: MagicMock,
    fetch_merchant_info_mock: MagicMock,
    fetch_websites_mock: MagicMock,
    fetch_route_mock: MagicMock,
    llm_mock: MagicMock,
) -> None:
    """应串联日志、商户信息与规则分析。"""
    collect_trace_mock.return_value = {
        "order_no": "ORDER-001",
        "total_logs": 2,
        "matched_logs": 1,
        "trace_details": [
            {
                "log_id": "log-1",
                "url": "https://payapi-test.inflyway.com/paycenter/api/v2/order/payment/create",
                "http_status_code": 200,
                "request_params": {
                    "notify_url": "https://shop.example.com/notify",
                    "source": "S004",
                    "amount": "10.00",
                    "currency": "USD",
                    "payStyleId": "PS0103",
                },
                "merchant_id": "MT001",
            }
        ],
    }
    fetch_merchant_info_mock.return_value = {
        "merchant_id": "MT001",
        "txbAccId": "VL001",
        "email": "merchant@example.com",
    }
    fetch_websites_mock.return_value = {
        "data": {"data": [{"webSite": "https://shop.example.com"}]}
    }
    fetch_route_mock.return_value = {
        "data": [{"currency": "USD", "payStyleId": "PS0103"}]
    }

    result = troubleshoot_order_issue("ORDER-001", use_llm=True)

    assert result["order_no"] == "ORDER-001"
    assert len(result["investigations"]) == 1
    assert result["llm_analysis"] == "诊断完成"
    llm_mock.assert_called_once()


@patch("app.services.order_trace_service.fetch_trace_log_detail")
@patch("app.services.order_trace_service.fetch_trace_logs")
def test_collect_target_trace_details(
    fetch_logs_mock: MagicMock,
    fetch_detail_mock: MagicMock,
) -> None:
    """应筛选目标接口并拉取详情。"""
    fetch_logs_mock.return_value = {
        "data": {
            "list": [
                {
                    "id": "log-1",
                    "url": "https://payapi-test.inflyway.com/paycenter/api/pay",
                },
                {"id": "log-2", "url": "https://example.com/other"},
            ]
        }
    }
    fetch_detail_mock.return_value = {
        "data": {
            "RESPONSE_PARAM": '{"source":"S004","amount":"10.00"}',
            "merchantId": "MT001",
        }
    }

    result = collect_target_trace_details("ORDER-001", client=MagicMock())

    assert result["matched_logs"] == 1
    assert len(result["trace_details"]) == 1
    assert result["trace_details"][0]["merchant_id"] == "MT001"
