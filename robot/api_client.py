import logging
from typing import Any, Dict, Optional

import requests

from .config import settings

logger = logging.getLogger(__name__)


class APIClient:
    """
    用于与内部支付API交互的客户端。
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None) -> None:
        """
        使用基础URL和可选的API密钥初始化APIClient。

        Args:
            base_url (str): 内部支付API的基础URL。
            api_key (Optional[str]): 用于认证的API密钥（如果需要）。
        """
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key  # 假设API密钥通过请求头传递

    def _make_request(self, method: str, endpoint: str, **kwargs: Any) -> Dict[str, Any]:
        """
        向指定的API端点发起HTTP请求。

        Args:
            method (str): HTTP方法（例如，“GET”，“POST”）。
            endpoint (str): 相对于基础URL的API端点。
            **kwargs (Any): 传递给requests.request的其他关键字参数。

        Returns:
            Dict[str, Any]: 来自API的JSON响应。

        Raises:
            requests.exceptions.RequestException: 如果请求失败。
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()  # 对于4xx或5xx的错误响应，抛出HTTPError
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"发生HTTP错误: {http_err} - {response.text}")
            raise
        except requests.exceptions.ConnectionError as conn_err:
            logger.error(f"发生连接错误: {conn_err}")
            raise
        except requests.exceptions.Timeout as timeout_err:
            logger.error(f"发生超时错误: {timeout_err}")
            raise
        except requests.exceptions.RequestException as req_err:
            logger.error(f"发生意外请求错误: {req_err}")
            raise

    def get_api_status(self) -> Dict[str, Any]:
        """
        获取API的状态。

        Returns:
            Dict[str, Any]: API状态信息。
        """
        logger.info("正在获取API状态。")
        return self._make_request("GET", "status")

    def query_api_docs(self, query: str) -> Dict[str, Any]:
        """
        根据特定术语查询API文档。

        Args:
            query (str): 文档的搜索词。

        Returns:
            Dict[str, Any]: API文档中的搜索结果。
        """
        logger.info(f"正在查询API文档，搜索词为: {query}")
        return self._make_request("GET", "docs", params={"q": query})

    def get_payment_status(self, order_id: str) -> Dict[str, Any]:
        """
        检索给定订单ID的支付状态。

        Args:
            order_id (str): 要检查的订单ID。

        Returns:
            Dict[str, Any]: 支付状态详情。
        """
        logger.info(f"正在获取订单ID为 {order_id} 的支付状态。")
        return self._make_request("GET", f"payments/{order_id}/status")

    # 根据需要添加更多API方法
    def search_faq(self, question: str) -> Dict[str, Any]:
        """
        在FAQ中搜索给定问题的答案。

        Args:
            question (str): 要在FAQ中搜索的问题。

        Returns:
            Dict[str, Any]: FAQ搜索结果。
        """
        logger.info(f"正在FAQ中搜索问题: {question}")
        return self._make_request("POST", "faq/search", json={"question": question})


# 使用设置初始化API客户端
api_client = APIClient(base_url=settings.API_BASE_URL, api_key=settings.API_KEY)
