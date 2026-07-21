"""EOS 鉴权客户端：登录获取 token、激活会话，并缓存 10 分钟。"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
)
TOKEN_TTL_SECONDS = 600


class EosAuthError(Exception):
    """EOS 登录或会话激活失败。"""


@dataclass(frozen=True)
class EosSession:
    """EOS 登录会话。"""

    session_id: str
    cookies: dict[str, str]
    expires_at: float

    def is_valid(self) -> bool:
        """判断会话是否在有效期内。"""
        return bool(self.session_id) and time.time() < self.expires_at


def _parse_set_cookies(response: requests.Response) -> dict[str, str]:
    """从响应头解析 Set-Cookie。"""
    cookie_map: dict[str, str] = {}
    for header_name, header_value in response.headers.items():
        if header_name.lower() != "set-cookie":
            continue
        first_part = header_value.split(";", 1)[0].strip()
        if "=" not in first_part:
            continue
        name, value = first_part.split("=", 1)
        cookie_map[name.strip()] = value.strip()
    return cookie_map


def _build_cookies(session_id: str, cookie_map: dict[str, str]) -> dict[str, str]:
    """合并登录 cookie，并补齐 EOS 会话所需字段。"""
    merged = dict(cookie_map)
    merged["camel_token"] = session_id
    merged["JSESSIONID"] = session_id
    merged["JSESSIONIDS"] = session_id
    merged["file_token"] = session_id
    return merged


class EosClient:
    """EOS 接口鉴权客户端，支持 token 缓存与自动刷新。"""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        token_ttl_seconds: int = TOKEN_TTL_SECONDS,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.token_ttl_seconds = token_ttl_seconds
        self.timeout = timeout
        self._session: EosSession | None = None
        self._lock = threading.Lock()

    def get_session(self, force_refresh: bool = False) -> EosSession:
        """获取有效会话；缓存过期时自动重新登录并激活。

        Args:
            force_refresh: 是否忽略缓存强制重新登录。

        Returns:
            当前有效的 EOS 会话。

        Raises:
            EosAuthError: 登录或激活失败时抛出。
        """
        with self._lock:
            if (
                not force_refresh
                and self._session is not None
                and self._session.is_valid()
            ):
                return self._session

            session = self._login_and_activate()
            self._session = session
            return session

    def get_auth_headers(self, force_refresh: bool = False) -> dict[str, str]:
        """获取带 accessToken 的请求头。"""
        session = self.get_session(force_refresh=force_refresh)
        return {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "accessToken": session.session_id,
            "User-Agent": DEFAULT_USER_AGENT,
        }

    def get_cookies(self, force_refresh: bool = False) -> dict[str, str]:
        """获取 EOS 请求所需 cookie。"""
        session = self.get_session(force_refresh=force_refresh)
        return dict(session.cookies)

    def get_request_auth(
        self, force_refresh: bool = False
    ) -> tuple[dict[str, str], dict[str, str]]:
        """同时返回请求头与 cookie，供业务接口复用。"""
        session = self.get_session(force_refresh=force_refresh)
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "accessToken": session.session_id,
            "User-Agent": DEFAULT_USER_AGENT,
        }
        return headers, dict(session.cookies)

    def clear_cache(self) -> None:
        """清空本地缓存会话。"""
        with self._lock:
            self._session = None

    def _login_and_activate(self) -> EosSession:
        """登录并调用 checkLogin 激活用户。"""
        login_response = self._login()
        cookie_map = _parse_set_cookies(login_response)
        session_id = cookie_map.get("camel_token", "")

        if not session_id:
            session_id = self._extract_session_id_from_body(login_response)

        cookies = _build_cookies(session_id, cookie_map)
        self._check_login(session_id, cookies)

        expires_at = time.time() + self.token_ttl_seconds
        logger.info("EOS 登录成功，sessionId=%s，缓存 %s 秒", session_id, self.token_ttl_seconds)
        return EosSession(session_id=session_id, cookies=cookies, expires_at=expires_at)

    def _login(self) -> requests.Response:
        """调用 EOS 登录接口。"""
        login_url = f"{self.base_url}/eos/login"
        payload = {
            "username": self.username,
            "password": self.password,
            "code": "1",
            "type": "mobile",
            "rurl": "",
        }
        logger.info("开始 EOS 登录: %s", login_url)

        try:
            response = requests.post(login_url, data=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.exception("EOS 登录请求失败")
            raise EosAuthError(f"EOS 登录请求异常: {exc}") from exc

        logger.debug("EOS 登录响应: %s", response.text)
        return response

    def _extract_session_id_from_body(self, response: requests.Response) -> str:
        """从登录响应体 msg 字段兜底提取 sessionId。"""
        try:
            body: dict[str, Any] = response.json()
        except ValueError as exc:
            raise EosAuthError("EOS 登录响应不是合法 JSON") from exc

        if body.get("code") == 0 and body.get("msg"):
            return str(body["msg"])

        raise EosAuthError(f"EOS 登录失败: {body}")

    def _check_login(self, session_id: str, cookies: dict[str, str]) -> None:
        """调用 checkLogin 激活用户会话。"""
        check_url = f"{self.base_url}/eos/checkLogin"
        headers = {
            "accessToken": session_id,
            "Cookie": "; ".join(f"{key}={value}" for key, value in cookies.items()),
            "Accept": "application/json, text/plain, */*",
            "User-Agent": DEFAULT_USER_AGENT,
        }

        try:
            response = requests.get(check_url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            logger.debug("EOS checkLogin 响应: %s", response.text)
        except requests.RequestException as exc:
            logger.exception("EOS checkLogin 调用失败")
            raise EosAuthError(f"EOS 会话激活失败: {exc}") from exc


_eos_client: EosClient | None = None
_eos_client_lock = threading.Lock()


def get_eos_client() -> EosClient:
    """获取全局 EOS 客户端单例。"""
    global _eos_client
    if _eos_client is not None:
        return _eos_client

    with _eos_client_lock:
        if _eos_client is None:
            _eos_client = EosClient(
                base_url=settings.eos_base_url,
                username=settings.eos_username,
                password=settings.eos_password,
                token_ttl_seconds=settings.eos_token_ttl_seconds,
            )
        return _eos_client
