"""订单链路日志查询服务。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.trader_config import (
    MERCHANT_ROUTE_URL,
    TARGET_TRACE_URLS,
    TRACE_LOG_DETAIL_URL,
    TRACE_LOG_LIST_URL,
)
from app.core.config import settings
from app.utils.trader_client import TraderClient, get_trader_client

logger = logging.getLogger(__name__)


def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """从分页响应中提取记录列表。"""
    data = payload.get("data", payload)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    for key in ("list", "records", "rows", "data", "content"):
        items = data.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _default_time_range(days: int = 5) -> tuple[str, str]:
    """生成默认查询时间范围（最近 N 天，含当天）。"""
    end_time = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    start_time = (end_time - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S")


def _get_trace_open_headers() -> dict[str, str]:
    """获取 open trace 接口请求头。"""
    if not settings.cashier_trace_api_key:
        logger.warning("未配置 CASHIER_TRACE_API_KEY，open trace 接口可能调用失败")

    return {
        "Pragma": "no-cache",
        "x-api-key": settings.cashier_trace_api_key,
        "User-Agent": "Apifox/1.0.0 (https://apifox.com)",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }


def _matches_target_url(url: str) -> bool:
    """判断日志 URL 是否属于目标接口。"""
    normalized = (url or "").strip().rstrip("/")
    for target in TARGET_TRACE_URLS:
        if normalized == target.rstrip("/") or normalized.endswith(urlparse(target).path.rstrip("/")):
            return True
    return False


def _parse_json_field(value: Any) -> dict[str, Any]:
    """解析可能为 JSON 字符串的字段。"""
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"raw": value}


def _pick_field(data: dict[str, Any], *keys: str) -> Any:
    """按多个候选 key 提取字段。"""
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def extract_request_params(log_detail: dict[str, Any]) -> dict[str, Any]:
    """从日志详情提取请求参数。"""
    detail_data = log_detail.get("data", log_detail)
    if not isinstance(detail_data, dict):
        return {}

    response_param = _pick_field(
        detail_data,
        "RESPONSE_PARAM",
        "responseParam",
        "response_param",
        "requestParam",
        "request_param",
        "REQUEST_PARAM",
    )
    request_params = _parse_json_field(response_param)

    if not request_params:
        request_params = _parse_json_field(
            _pick_field(detail_data, "requestBody", "request_body", "body")
        )

    return request_params


def extract_merchant_id(log_detail: dict[str, Any], request_params: dict[str, Any]) -> str | None:
    """从日志详情或请求参数提取 MID。"""
    detail_data = log_detail.get("data", log_detail)
    if isinstance(detail_data, dict):
        merchant_id = _pick_field(
            detail_data,
            "merchantId",
            "merchant_id",
            "mid",
            "MID",
            "merchantNo",
        )
        if merchant_id:
            return str(merchant_id)

    merchant_id = _pick_field(
        request_params,
        "merchant_id",
        "merchantId",
        "mid",
        "MID",
        "merchantNo",
    )
    return str(merchant_id) if merchant_id else None


def fetch_trace_logs(
    order_no: str,
    *,
    page_no: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """查询订单链路日志列表（固定查询最近5天）。"""
    if not order_no:
        return {"error": "order_no 不能为空"}

    start_time, end_time = _default_time_range()

    payload = {
        "traceId": "",
        "url": "",
        "method": "",
        "httpStatusCode": None,
        "transOrderId": "",
        "merchantOrderId": "",
        "invoiceId": "",
        "orderNo": order_no,
        "remark1": "",
        "startTime": start_time,
        "endTime": end_time,
        "pageNo": page_no,
        "pageSize": page_size,
    }
    try:
        response = requests.post(
            TRACE_LOG_LIST_URL,
            json=payload,
            headers=_get_trace_open_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.exception("open trace 日志列表查询失败 - order_no=%s", order_no)
        return {"error": f"open trace 日志列表查询失败: {exc}"}


def fetch_trace_log_detail(
    log_id: str,
) -> dict[str, Any]:
    """查询单条链路日志详情。"""
    if not log_id:
        return {"error": "log_id 不能为空"}

    try:
        response = requests.get(
            f"{TRACE_LOG_DETAIL_URL}/{log_id}",
            headers=_get_trace_open_headers(),
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.exception("open trace 日志详情查询失败 - log_id=%s", log_id)
        return {"error": f"open trace 日志详情查询失败: {exc}"}


def fetch_merchant_route(
    email: str,
    *,
    client: TraderClient | None = None,
) -> dict[str, Any]:
    """根据商户邮箱查询支付路由。"""
    if not email:
        return {"error": "email 不能为空"}

    trader = client or get_trader_client()
    result = trader.get_json(MERCHANT_ROUTE_URL, params={"email": email}, xhr=True)
    return result if isinstance(result, dict) else {"data": result}


def collect_target_trace_details(
    order_no: str,
    *,
    client: TraderClient | None = None,
) -> dict[str, Any]:
    """查询订单日志并返回目标接口详情（固定查询最近5天）。"""
    start_time, end_time = _default_time_range()
    _ = client
    list_result = fetch_trace_logs(order_no)
    if list_result.get("error"):
        return list_result

    records = _extract_records(list_result)
    matched_records = [record for record in records if _matches_target_url(str(record.get("url", "")))]

    details: list[dict[str, Any]] = []
    for record in matched_records:
        log_id = _pick_field(record, "id", "traceId", "trace_id", "logId")
        if not log_id:
            continue
        detail = fetch_trace_log_detail(str(log_id))
        request_params = extract_request_params(detail)
        details.append(
            {
                "log_id": str(log_id),
                "url": record.get("url"),
                "http_status_code": record.get("httpStatusCode") or record.get("http_status_code"),
                "detail": detail,
                "request_params": request_params,
                "merchant_id": extract_merchant_id(detail, request_params),
            }
        )

    return {
        "order_no": order_no,
        "start_time": start_time,
        "end_time": end_time,
        "total_logs": len(records),
        "matched_logs": len(matched_records),
        "trace_details": details,
    }
