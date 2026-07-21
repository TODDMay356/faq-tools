"""订单问题规则分析与 LLM 诊断。"""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_llm
from app.core.trader_config import REQUIRED_SOURCE_VALUE
from app.services.eos_merchant_service import fetch_merchant_info, fetch_merchant_websites
from app.services.order_trace_service import collect_target_trace_details, fetch_merchant_route

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """你是跨境支付技术支持专家，负责根据订单日志、商户配置和规则检查结果排查商户接口问题。

请基于给定的事实数据输出：
1. 问题摘要（1-3 句）
2. 发现的问题列表（按严重程度排序）
3. 排查建议（可执行步骤）
4. 若未发现明显问题，说明还需人工核查的点

要求：
- 只基于提供的数据分析，不要编造
- 明确指出字段名、实际值、期望值
- 使用中文，结构清晰
"""


def extract_website_items(websites_result: dict[str, Any]) -> list[dict[str, Any]]:
    """从网站查询结果中提取网站列表。"""
    data = websites_result.get("data", {})
    if isinstance(data, dict):
        items = data.get("data", [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _extract_domain(url: str) -> str:
    """提取 URL 域名（小写，不含端口）。"""
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    return host.split(":")[0]


def _normalize_route_items(route_result: dict[str, Any]) -> list[dict[str, Any]]:
    """标准化商户路由列表。"""
    data = route_result.get("data", route_result)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        for key in ("routes", "routeList", "list", "data", "records"):
            items = data.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def _pick_param(request_params: dict[str, Any], *keys: str) -> Any:
    """从请求参数中提取字段。"""
    for key in keys:
        if key in request_params and request_params[key] not in (None, ""):
            return request_params[key]
    return None


def check_notify_url_domain(
    notify_url: str | None,
    websites: list[dict[str, Any]],
) -> dict[str, Any]:
    """检查 notify_url 域名是否与商户网址一致。"""
    if not notify_url:
        return {
            "rule": "notify_url_domain",
            "passed": False,
            "message": "请求参数缺少 notify_url",
            "actual": None,
            "expected": "与商户备案网址域名一致",
        }

    notify_domain = _extract_domain(str(notify_url))
    website_domains = sorted(
        {
            domain
            for website in websites
            for domain in [
                _extract_domain(str(website.get("webSite") or website.get("website") or "")),
                _extract_domain(str(website.get("notifyUrl") or website.get("notify_url") or "")),
            ]
            if domain
        }
    )

    passed = notify_domain in website_domains
    return {
        "rule": "notify_url_domain",
        "passed": passed,
        "message": "notify_url 域名与商户网址一致" if passed else "notify_url 域名与商户网址不一致",
        "actual": notify_domain,
        "expected": website_domains,
    }


def check_source_field(source: Any) -> dict[str, Any]:
    """检查 source 字段是否为 S004。"""
    actual = str(source) if source is not None else ""
    passed = actual == REQUIRED_SOURCE_VALUE
    return {
        "rule": "source_field",
        "passed": passed,
        "message": "source 字段正确" if passed else "source 字段不正确",
        "actual": actual,
        "expected": REQUIRED_SOURCE_VALUE,
    }


def check_amount_two_decimals(amount: Any) -> dict[str, Any]:
    """检查金额是否保留两位小数。"""
    if amount is None or amount == "":
        return {
            "rule": "amount_decimals",
            "passed": False,
            "message": "请求参数缺少 amount",
            "actual": amount,
            "expected": "保留两位小数，例如 10.00",
        }

    amount_str = str(amount).strip()
    passed = bool(re.fullmatch(r"\d+(\.\d{2})", amount_str))
    if not passed and re.fullmatch(r"\d+\.\d+", amount_str):
        return {
            "rule": "amount_decimals",
            "passed": False,
            "message": "金额小数位数不是两位",
            "actual": amount_str,
            "expected": "保留两位小数，例如 10.00",
        }
    if not passed and re.fullmatch(r"\d+", amount_str):
        return {
            "rule": "amount_decimals",
            "passed": False,
            "message": "金额未包含两位小数",
            "actual": amount_str,
            "expected": "保留两位小数，例如 10.00",
        }

    try:
        decimal_amount = Decimal(amount_str)
        passed = decimal_amount == decimal_amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        passed = False

    return {
        "rule": "amount_decimals",
        "passed": passed,
        "message": "金额格式正确" if passed else "金额格式不符合两位小数要求",
        "actual": amount_str,
        "expected": "保留两位小数，例如 10.00",
    }


def check_currency_and_pay_style(
    currency: Any,
    pay_style: Any,
    routes: list[dict[str, Any]],
) -> dict[str, Any]:
    """检查币种和支付方式是否匹配商户路由。"""
    if not routes:
        return {
            "rule": "currency_pay_style_route",
            "passed": False,
            "message": "未查询到商户支付路由，无法校验币种和支付方式",
            "actual": {"currency": currency, "pay_style": pay_style},
            "expected": "商户路由中存在对应币种和支付方式",
        }

    currency_text = str(currency or "").upper()
    pay_style_text = str(pay_style or "").upper()

    route_currencies: set[str] = set()
    route_pay_styles: set[str] = set()
    for route in routes:
        for key in ("currency", "currencyCode", "transCurrency", "settleCurrency"):
            value = route.get(key)
            if value:
                route_currencies.add(str(value).upper())
        for key in ("payStyleId", "payStyle", "pay_style", "payStyleCode"):
            value = route.get(key)
            if value:
                route_pay_styles.add(str(value).upper())

    currency_matched = not currency_text or currency_text in route_currencies
    pay_style_matched = not pay_style_text or pay_style_text in route_pay_styles
    passed = currency_matched and pay_style_matched

    return {
        "rule": "currency_pay_style_route",
        "passed": passed,
        "message": "币种和支付方式与路由匹配" if passed else "币种或支付方式与商户路由不匹配",
        "actual": {"currency": currency_text, "pay_style": pay_style_text},
        "expected": {
            "route_currencies": sorted(route_currencies),
            "route_pay_styles": sorted(route_pay_styles),
        },
    }


def run_rule_checks(
    request_params: dict[str, Any],
    websites: list[dict[str, Any]],
    routes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """执行全部规则检查。"""
    notify_url = _pick_param(request_params, "notify_url", "notifyUrl", "notifyURL")
    source = _pick_param(request_params, "source", "sourceCode", "SOURCE")
    amount = _pick_param(request_params, "amount", "order_amount", "orderAmount", "total_amount")
    currency = _pick_param(request_params, "currency", "currencyCode", "transCurrency")
    pay_style = _pick_param(
        request_params,
        "pay_style_id",
        "payStyleId",
        "pay_style",
        "payStyle",
        "payment_method",
    )

    return [
        check_notify_url_domain(notify_url, websites),
        check_currency_and_pay_style(currency, pay_style, routes),
        check_source_field(source),
        check_amount_two_decimals(amount),
    ]


def analyze_with_llm(context: dict[str, Any]) -> str:
    """调用大模型生成诊断结论。"""
    try:
        llm = get_llm()
        response = llm.invoke(
            [
                SystemMessage(content=ANALYSIS_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "请根据以下排查数据输出诊断结论：\n"
                        f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)}"
                    )
                ),
            ]
        )
        content = response.content
        return content if isinstance(content, str) else str(content)
    except Exception as exc:
        logger.exception("LLM 订单问题分析失败")
        return f"LLM 分析失败: {exc}"


def troubleshoot_order_issue(
    order_no: str,
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """根据订单号排查商户接口问题。

    Args:
        order_no: 订单号。
        use_llm: 是否调用大模型生成诊断结论。

    Returns:
        完整排查结果。
    """
    trace_data = collect_target_trace_details(order_no)
    if trace_data.get("error"):
        return trace_data

    if not trace_data.get("trace_details"):
        return {
            "order_no": order_no,
            "error": "未找到目标接口日志",
            "hint": "请确认订单号是否正确，或扩大查询时间范围",
            "trace_summary": trace_data,
        }

    investigations: list[dict[str, Any]] = []
    for trace_detail in trace_data["trace_details"]:
        merchant_id = trace_detail.get("merchant_id")
        request_params = trace_detail.get("request_params", {})

        merchant_info: dict[str, Any] = {"error": "日志中未提取到 MID"}
        websites_result: dict[str, Any] = {"error": "未查询"}
        merchant_route: dict[str, Any] = {"error": "未查询"}
        websites: list[dict[str, Any]] = []
        routes: list[dict[str, Any]] = []

        if merchant_id:
            merchant_info = fetch_merchant_info(merchant_id)
            txb_acc_id = merchant_info.get("txbAccId")
            email = merchant_info.get("email")
            if txb_acc_id:
                websites_result = fetch_merchant_websites(txb_acc_id=txb_acc_id)
                websites = extract_website_items(websites_result)
            if email:
                merchant_route = fetch_merchant_route(email)
                routes = _normalize_route_items(merchant_route)

        rule_checks = run_rule_checks(request_params, websites, routes)
        investigations.append(
            {
                "log_id": trace_detail.get("log_id"),
                "url": trace_detail.get("url"),
                "http_status_code": trace_detail.get("http_status_code"),
                "merchant_id": merchant_id,
                "request_params": request_params,
                "merchant_info": merchant_info,
                "websites": websites,
                "merchant_route": merchant_route,
                "rule_checks": rule_checks,
                "has_issue": any(not check["passed"] for check in rule_checks),
            }
        )

    result: dict[str, Any] = {
        "order_no": order_no,
        "trace_summary": {
            "total_logs": trace_data.get("total_logs"),
            "matched_logs": trace_data.get("matched_logs"),
            "start_time": trace_data.get("start_time"),
            "end_time": trace_data.get("end_time"),
        },
        "investigations": investigations,
        "failed_rules": [
            check
            for item in investigations
            for check in item.get("rule_checks", [])
            if not check.get("passed")
        ],
    }

    if use_llm:
        result["llm_analysis"] = analyze_with_llm(result)

    return result
