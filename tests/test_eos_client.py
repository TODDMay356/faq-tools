"""EOS 鉴权客户端单元测试。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from app.utils.eos_client import EosAuthError, EosClient, _build_cookies


def test_build_cookies_merges_session_fields() -> None:
    """登录 cookie 应补齐 EOS 会话字段。"""
    cookies = _build_cookies("session-123", {"foo": "bar"})

    assert cookies["foo"] == "bar"
    assert cookies["camel_token"] == "session-123"
    assert cookies["JSESSIONID"] == "session-123"
    assert cookies["JSESSIONIDS"] == "session-123"
    assert cookies["file_token"] == "session-123"


def test_get_session_uses_cache_within_ttl() -> None:
    """10 分钟有效期内应复用缓存，不重复登录。"""
    client = EosClient(
        base_url="https://test.inflyway.com",
        username="user",
        password="pass",
        token_ttl_seconds=600,
    )

    with patch.object(client, "_login_and_activate") as login_mock:
        login_mock.return_value = type(
            "Session",
            (),
            {
                "session_id": "cached-token",
                "cookies": {"camel_token": "cached-token"},
                "expires_at": time.time() + 600,
                "is_valid": lambda self: True,
            },
        )()

        first = client.get_session()
        second = client.get_session()

    assert first.session_id == "cached-token"
    assert second.session_id == "cached-token"
    login_mock.assert_called_once()


def test_get_session_refreshes_after_cache_cleared() -> None:
    """清空缓存后应重新登录。"""
    client = EosClient(
        base_url="https://test.inflyway.com",
        username="user",
        password="pass",
        token_ttl_seconds=600,
    )

    with patch.object(client, "_login_and_activate") as login_mock:
        login_mock.side_effect = [
            type(
                "Session",
                (),
                {
                    "session_id": "token-1",
                    "cookies": {"camel_token": "token-1"},
                    "expires_at": time.time() + 600,
                    "is_valid": lambda self: True,
                },
            )(),
            type(
                "Session",
                (),
                {
                    "session_id": "token-2",
                    "cookies": {"camel_token": "token-2"},
                    "expires_at": time.time() + 600,
                    "is_valid": lambda self: True,
                },
            )(),
        ]

        first = client.get_session()
        client.clear_cache()
        second = client.get_session()

    assert first.session_id == "token-1"
    assert second.session_id == "token-2"
    assert login_mock.call_count == 2


def test_login_and_activate_reads_session_from_response_body() -> None:
    """camel_token 缺失时应从响应体 msg 兜底。"""
    client = EosClient(
        base_url="https://test.inflyway.com",
        username="user",
        password="pass",
    )

    login_response = MagicMock()
    login_response.headers = {}
    login_response.json.return_value = {"code": 0, "msg": "body-session-id"}

    with (
        patch.object(client, "_login", return_value=login_response),
        patch.object(client, "_check_login") as check_login_mock,
    ):
        session = client._login_and_activate()

    assert session.session_id == "body-session-id"
    check_login_mock.assert_called_once()


def test_login_and_activate_raises_when_login_fails() -> None:
    """登录失败时应抛出 EosAuthError。"""
    client = EosClient(
        base_url="https://test.inflyway.com",
        username="user",
        password="pass",
    )

    login_response = MagicMock()
    login_response.headers = {}
    login_response.json.return_value = {"code": 1, "msg": "invalid credentials"}

    with patch.object(client, "_login", return_value=login_response):
        with pytest.raises(EosAuthError, match="EOS 登录失败"):
            client._login_and_activate()


def test_get_auth_headers_contains_access_token() -> None:
    """请求头应注入 accessToken。"""
    client = EosClient(
        base_url="https://test.inflyway.com",
        username="user",
        password="pass",
    )

    with patch.object(
        client,
        "get_session",
        return_value=type(
            "Session",
            (),
            {
                "session_id": "header-token",
                "cookies": {"camel_token": "header-token"},
                "expires_at": time.time() + 600,
                "is_valid": lambda self: True,
            },
        )(),
    ):
        headers = client.get_auth_headers()

    assert headers["accessToken"] == "header-token"
    assert headers["Accept"] == "application/json, text/plain, */*"
