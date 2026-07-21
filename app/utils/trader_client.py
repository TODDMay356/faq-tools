"""Merchant Trader HTTP 客户端。"""

from __future__ import annotations

import logging
import threading
from typing import Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)


class TraderClientError(Exception):
    """Merchant Trader 请求失败。"""


class TraderClient:
    """Merchant Trader API 客户端，使用 Cookie 鉴权。"""

    def __init__(
        self,
        base_url: str,
        dhpay_cookie: str,
        jsession_id: str,
        file_token: str,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.dhpay_cookie = dhpay_cookie
        self.jsession_id = jsession_id
        self.file_token = file_token
        self.timeout = timeout

    def get_cookies(self) -> dict[str, str]:
        """获取 Trader 请求 Cookie。"""
        cookies: dict[str, str] = {}
        if self.dhpay_cookie:
            cookies["DHPayCookie"] = self.dhpay_cookie
        if self.jsession_id:
            cookies["JSESSIONID"] = self.jsession_id
        if self.file_token:
            cookies["file_token"] = self.file_token
        return cookies

    def get_headers(self, *, xhr: bool = False) -> dict[str, str]:
        """获取 Trader 请求头。"""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/trader-api/notice/trace-manage/trace-pc.html",
        }
        if xhr:
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Referer"] = f"{self.base_url}/dhpayservice/customer/list/"
        return headers

    def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """发送 POST JSON 请求。"""
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self.get_headers(),
                cookies=self.get_cookies(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.exception("Trader POST 请求失败 - url=%s", url)
            raise TraderClientError(f"Trader POST 请求失败: {exc}") from exc

    def get_json(self, url: str, *, params: dict[str, Any] | None = None, xhr: bool = False) -> Any:
        """发送 GET 请求并解析 JSON。"""
        try:
            response = requests.get(
                url,
                params=params,
                headers=self.get_headers(xhr=xhr),
                cookies=self.get_cookies(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.exception("Trader GET 请求失败 - url=%s", url)
            raise TraderClientError(f"Trader GET 请求失败: {exc}") from exc


_trader_client: TraderClient | None = None
_trader_client_lock = threading.Lock()


def get_trader_client() -> TraderClient:
    """获取全局 Trader 客户端单例。"""
    global _trader_client
    if _trader_client is not None:
        return _trader_client

    with _trader_client_lock:
        if _trader_client is None:
            _trader_client = TraderClient(
                base_url=settings.merchant_trader_base_url,
                dhpay_cookie=settings.merchant_trader_dhpay_cookie,
                jsession_id=settings.merchant_trader_jsession_id,
                file_token=settings.merchant_trader_file_token,
            )
        return _trader_client
