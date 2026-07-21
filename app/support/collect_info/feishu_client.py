"""Feishu OpenAPI client utilities."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import time
from typing import Any, Final, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class TaskMember:
    """A task member payload used by Feishu Task API."""

    id: str
    type: str = "user"
    role: str = "assignee"
    name: Optional[str] = None


@dataclass
class TaskDue:
    """Task due time payload."""

    timestamp: str
    is_all_day: bool = True


@dataclass
class TaskRequest:
    """Task create request payload."""

    summary: str
    description: str
    members: list[TaskMember]
    due: Optional[TaskDue] = None


class FeishuClient:
    """Feishu OpenAPI client.

    Notes:
        The `tenant_access_token` returned by Feishu has an expiration time. This client caches the
        token and refreshes it automatically before it expires.
    """
    
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url: Final[str] = "https://open.feishu.cn/open-apis"
        self._access_token: Optional[str] = None
        self._access_token_expires_at: float | None = None
        self._token_refresh_skew_seconds: Final[int] = 60
    
    def _is_token_valid(self) -> bool:
        """Return whether cached access token exists and is not expired."""
        if not self._access_token or not self._access_token_expires_at:
            return False
        return time.time() < (self._access_token_expires_at - self._token_refresh_skew_seconds)

    async def get_access_token(self, *, force_refresh: bool = False) -> str:
        """Get Feishu tenant access token.

        Args:
            force_refresh: Whether to refresh token even if cached token looks valid.

        Returns:
            Tenant access token string.

        Raises:
            RuntimeError: If token request fails.
        """
        if not force_refresh and self._is_token_valid():
            return self._access_token  # type: ignore[return-value]

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            data = response.json()
            if data.get("code") != 0:
                raise RuntimeError(f"获取token失败: {data}")

            token = data.get("tenant_access_token")
            expires_in = data.get("expire")  # seconds
            if not token or not isinstance(expires_in, int):
                raise RuntimeError(f"获取token失败: 响应缺少tenant_access_token/expire: {data}")

            self._access_token = token
            self._access_token_expires_at = time.time() + expires_in
            return token

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        retry_on_invalid_token: bool = True,
    ) -> dict[str, Any]:
        """Make a Feishu OpenAPI request and return JSON response."""
        token = await self.get_access_token()
        if not token:
            raise RuntimeError("获取token失败: tenant_access_token为空（请检查FEISHU_APP_ID/FEISHU_APP_SECRET）")
        req_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            req_headers.update(headers)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, url, headers=req_headers, params=params, json=json_body)
            try:
                data = response.json()
            except Exception:
                # Some Feishu gateways can return non-JSON on auth/network errors.
                text = response.text
                raise RuntimeError(
                    f"飞书接口返回非JSON: status={response.status_code}, url={url}, body={text[:500]}"
                )

        # 99991663: Invalid access token for authorization
        need_retry = False
        if retry_on_invalid_token:
            if response.status_code in (401, 403):
                need_retry = True
            elif isinstance(data, dict) and data.get("code") == 99991663:
                need_retry = True

        if need_retry:
            token = await self.get_access_token(force_refresh=True)
            if not token:
                raise RuntimeError("获取token失败: tenant_access_token为空（刷新后仍为空）")
            req_headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(method, url, headers=req_headers, params=params, json=json_body)
                try:
                    data = response.json()
                except Exception:
                    text = response.text
                    raise RuntimeError(
                        f"飞书接口重试后仍返回非JSON: status={response.status_code}, url={url}, body={text[:500]}"
                    )

        return data
    
    async def get_bitable_records(
        self,
        app_token: str,
        table_id: str,
        filter_field: str | None = None,
        filter_value: Any = None,
    ) -> list[dict[str, Any]]:
        """Get bitable records with optional filter."""
        
        all_records = []
        page_token = None
        
        # 构建查询条件
        search_body = {
            "page_size": 500,
            "sort": [
                {
                    "field_name": "提交时间",
                    "desc": True
                }
            ]
        }
        
        # 添加过滤条件
        if filter_field and filter_value is not None:
            search_body["filter"] = {
                "conditions": [
                    {
                        "field_name": filter_field,
                        "operator": "is",
                        "value": [filter_value]
                    }
                ],
                "conjunction": "and"
            }
        
        while True:
            if page_token:
                search_body["page_token"] = page_token

            data = await self._request_json(
                "POST",
                f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                headers={"Content-Type": "application/json"},
                json_body=search_body,
            )

            if data.get("code") != 0:
                raise RuntimeError(f"获取记录失败: {data}")

            records = data["data"]["items"]
            all_records.extend(records)

            if not data["data"].get("has_more"):
                break
            page_token = data["data"]["page_token"]
        
        return all_records
    
    async def create_task(self, task_request: TaskRequest) -> Dict[str, Any]:
        """创建飞书任务"""
        
        # 构建成员列表
        members = []
        for member in task_request.members:
            member_data = {
                "id": member.id,
                "type": member.type,
                "role": member.role
            }
            if member.name:
                member_data["name"] = member.name
            members.append(member_data)
        
        payload = {
            "summary": task_request.summary,
            "description": task_request.description,
            "members": members
        }
        
        # 添加截止时间
        if task_request.due:
            payload["due"] = {
                "timestamp": task_request.due.timestamp,
                "is_all_day": task_request.due.is_all_day
            }
        
        data = await self._request_json(
            "POST",
            f"{self.base_url}/task/v2/tasks?user_id_type=user_id",
            headers={"Content-Type": "application/json"},
            json_body=payload,
        )
            
        if data.get("code") != 0:
            raise RuntimeError(f"创建任务失败: {data}")

        return data["data"]
    
    async def get_wiki_node(self, token_value: str, obj_type: str = None) -> Dict[str, Any]:
        """获取飞书wiki节点信息"""
        params = {"token": token_value}
        if obj_type:
            params["obj_type"] = obj_type

        data = await self._request_json(
            "GET",
            f"{self.base_url}/wiki/v2/spaces/get_node",
            params=params,
        )
            
        if data.get("code") != 0:
            raise RuntimeError(f"获取wiki节点失败: {data}")

        return data["data"]["node"]
    
    async def get_bitable_app_token_from_wiki(self, token_value: str) -> str:
        """从wiki token获取多维表格的app_token"""
        node_info = await self.get_wiki_node(token_value, "wiki")
        
        # 检查节点类型是否为多维表格
        if node_info.get("obj_type") != "bitable":
            raise Exception(f"节点类型不是多维表格: {node_info.get('obj_type')}")
        
        # 返回obj_token，这就是多维表格的app_token
        app_token = node_info.get("obj_token")
        if not app_token:
            raise Exception("未找到多维表格的app_token")
        
        return app_token
    
    async def update_bitable_record(self, app_token: str, table_id: str, record_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """更新多维表格记录"""
        payload = {"fields": fields}

        data = await self._request_json(
            "PUT",
            f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            headers={"Content-Type": "application/json"},
            json_body=payload,
        )
            
        if data.get("code") != 0:
            raise RuntimeError(f"更新记录失败: {data}")

        return data["data"]

    async def create_bitable_record(
        self, app_token: str, table_id: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """在多维表格中新增一条记录

        Args:
            app_token: 多维表格 app_token
            table_id: 数据表 table_id
            fields: 字段名到值的映射，字段名需与多维表格列名一致

        Returns:
            新增记录的 data 部分
        """
        payload = {"fields": fields}

        data = await self._request_json(
            "POST",
            f"{self.base_url}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
            headers={"Content-Type": "application/json"},
            json_body=payload,
        )

        if data.get("code") != 0:
            raise RuntimeError(f"新增记录失败: {data}")

        return data["data"]

    async def download_file(self, file_token: str) -> bytes:
        """下载飞书文件"""
        token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f"{self.base_url}/drive/v1/medias/{file_token}/download",
                headers=headers,
            )
            
            if response.status_code != 200:
                # 如果直接下载失败，尝试解析响应
                try:
                    error_data = response.json()
                    raise Exception(f"下载文件失败: {error_data}")
                except:
                    raise Exception(f"下载文件失败: HTTP {response.status_code}")
            
            # 检查响应内容类型
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                # 如果返回的是JSON，说明需要重定向或有错误
                try:
                    json_data = response.json()
                    raise Exception(f"下载返回JSON而非文件: {json_data}")
                except Exception as e:
                    if "Extra data" in str(e):
                        # 可能是JSON解析错误，直接返回内容
                        return response.content
                    raise e
            
            return response.content
    
    async def upload_file_to_task(self, task_guid: str, file_name: str, file_content: bytes) -> Dict[str, Any]:
        """上传文件到任务附件"""
        token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        # 构建multipart/form-data
        files = {
            'file': (file_name, file_content)
        }
        
        data = {
            'resource_type': 'task',
            'resource_id': task_guid
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.base_url}/task/v2/attachments/upload",
                headers=headers,
                files=files,
                data=data,
                params={"user_id_type": "open_id"}
            )
            response_data = response.json()
            
            if response_data.get("code") != 0:
                raise Exception(f"上传任务附件失败: {response_data}")
            
            return response_data["data"]

    async def send_message(self, receive_id: str, msg_type: str, content: str, receive_id_type: str = "chat_id") -> Dict[str, Any]:
        """发送飞书消息"""
        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": content
        }

        data = await self._request_json(
            "POST",
            f"{self.base_url}/im/v1/messages",
            headers={"Content-Type": "application/json"},
            params={"receive_id_type": receive_id_type},
            json_body=payload,
        )
            
        if data.get("code") != 0:
            raise RuntimeError(f"发送消息失败: {data}")

        return data["data"]
    
    async def forward_message(
        self,
        message_id: str,
        receive_id: str,
        receive_id_type: str = "chat_id"
    ) -> Dict[str, Any]:
        """转发消息到指定会话（保持原消息格式）
        
        Args:
            message_id: 原消息ID
            receive_id: 目标会话ID（群ID或用户ID）
            receive_id_type: receive_id类型，可选值: open_id, user_id, union_id, email, chat_id
        
        Returns:
            转发结果
        """
        payload = {
            "receive_id": receive_id
        }

        data = await self._request_json(
            "POST",
            f"{self.base_url}/im/v1/messages/{message_id}/forward",
            headers={"Content-Type": "application/json"},
            params={"receive_id_type": receive_id_type},
            json_body=payload,
        )
            
        if data.get("code") != 0:
            raise RuntimeError(f"转发消息失败: {data}")

        return data["data"]

    async def batch_get_user_id(
        self,
        emails: list[str] | None = None,
        mobiles: list[str] | None = None,
        include_resigned: bool = True,
    ) -> dict[str, Any]:
        """根据手机号或邮箱批量获取用户ID"""
        url = f"{self.base_url}/contact/v3/users/batch_get_id"
        params = {"user_id_type": "user_id"}

        data = {"include_resigned": include_resigned}
        if emails:
            data["emails"] = emails
        if mobiles:
            data["mobiles"] = mobiles

        return await self._request_json(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            params=params,
            json_body=data,
        )


# ==================== 测试脚本 ====================
async def test_get_access_token(client: FeishuClient):
    """测试获取访问令牌"""
    token = await client.get_access_token()
    print(f"✓ 获取token成功: {token[:20]}...")
    return token


async def test_get_bitable_records(client: FeishuClient):
    """测试获取多维表格记录"""
    import os
    app_token = os.getenv("FEISHU_BITABLE_APP_TOKEN")
    table_id = os.getenv("FEISHU_BITABLE_TABLE_ID")
    
    # 测试过滤查询：流程执行状态=1
    records = await client.get_bitable_records(
        app_token, 
        table_id, 
        filter_field="流程执行状态", 
        filter_value=1
    )
    print(f"✓ 获取记录成功，共 {len(records)} 条（已执行流程=1）")
    if records:
        print(f"  第一条记录: {records[0]}")
    return records


async def test_create_task(client: FeishuClient):
    """测试创建飞书任务"""
    import os
    
    # 创建任务成员
    member = TaskMember(
        id=os.getenv("FEISHU_ASSIGNEE_ID", "ou_76ecbc7c133c3b10134a9b368f78421f"),
        name="张明德（明德）"
    )
    
    # 创建截止时间（一天后）
    due_time = TaskDue(
        timestamp=str(int((time.time() + 86400) * 1000))  # 一天后的时间戳（毫秒）
    )
    
    # 创建任务请求
    task_request = TaskRequest(
        summary="测试任务",
        description="这是一个测试任务",
        members=[member],
        due=due_time
    )
    
    result = await client.create_task(task_request)
    print(f"✓ 创建任务成功: {result}")
    return result


async def test_get_wiki_app_token(client: FeishuClient, wiki_token: str):
    """测试获取wiki多维表格app_token"""
    import os
    wiki_token = os.getenv("FEISHU_WIKI_TOKEN", wiki_token)
    
    app_token = await client.get_bitable_app_token_from_wiki(wiki_token)
    print(f"✓ 获取wiki多维表格app_token成功: {app_token}")
    return app_token


async def test_send_message(client: FeishuClient):
    """测试发送飞书消息"""
    import os
    import json
    receive_id = ""
    
    content = json.dumps({"text": "这是一条测试消息"})
    result = await client.send_message(
        receive_id=receive_id,
        msg_type="text",
        content=content
    )
    print(f"✓ 发送消息成功: {result}")
    return result


async def test_batch_get_user_id(client: FeishuClient):
    """测试根据手机号邮箱获取用户ID"""
    result = await client.batch_get_user_id(
        emails=["zhangsan@z.com", "lisi@a.com"],
        mobiles=["13011111111", "13022222222"],
        include_resigned=True
    )
    print(f"✓ 批量获取用户ID成功: {result}")
    return result


async def run_all_tests(client: FeishuClient):
    """运行所有测试"""

    
    try:
        print("\n[1/5] 测试获取访问令牌...")
        await test_get_access_token(client)
    except Exception as e:
        print(f"✗ 失败: {e}")

    try:
        print("\n[3/5] 测试获取wiki多维表格app_token...")
        await test_get_wiki_app_token(client, "EannwwXX5i3tthkmym8cv7bknsB")
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    try:
        print("\n[2/5] 测试获取多维表格记录...")
        await test_get_bitable_records(client)
    except Exception as e:
        print(f"✗ 失败: {e}")
    

    
    try:
        print("\n[4/5] 测试创建任务...")
        # await test_create_task(client)
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    try:
        print("\n[5/5] 测试发送消息...")
        await test_send_message(client)
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    try:
        print("\n[6/6] 测试批量获取用户ID...")
        await test_batch_get_user_id(client)
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    print(f"\n共享的access_token: {client._access_token[:20] if client._access_token else 'None'}...")
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    import asyncio
    import os
    from dotenv import load_dotenv

    load_dotenv()

    print("=" * 50)
    print("开始测试飞书客户端")
    print("=" * 50)

    # 创建单一客户端实例，共享access_token
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    client = FeishuClient(app_id, app_secret)

    print("\n[3/5] 测试获取wiki多维表格app_token...")
    asyncio.run(test_get_wiki_app_token(client, "DTucwES6zi2x10kEp3qckxw4nwf"))
    # asyncio.run(run_all_tests(client))
