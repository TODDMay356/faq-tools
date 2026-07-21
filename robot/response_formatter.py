import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    将API响应格式化为微信可读的字符串。
    """

    def format_response(self, api_response: Dict[str, Any]) -> str:
        """
        将给定的API响应字典格式化为可读的字符串。

        Args:
            api_response (Dict[str, Any]): 来自API的原始JSON响应。

        Returns:
            str: 适合作为微信消息发送的格式化字符串。
        """
        if not api_response:
            return "抱歉，我无法从API获得有意义的回复。"

        # 根据预期的API响应结构进行示例格式化
        if "status" in api_response and isinstance(api_response["status"], str):
            return f"API状态: {api_response['status'].upper()}"
        elif "docs" in api_response and isinstance(api_response["docs"], list):
            docs_summary = "\n".join([doc.get("title", "N/A") for doc in api_response["docs"][:3]])  # 限制为3个文档
            return f"找到API文档:\n{docs_summary}\n(更多内容可用...)"
        elif "order_status" in api_response and "order_id" in api_response:
            return (
                f"订单ID: {api_response['order_id']}\n"  # noqa: E501
                f"支付状态: {api_response['order_status']}\n"
                f"金额: {api_response.get('amount', 'N/A')}"
            )
        elif "answer" in api_response and isinstance(api_response["answer"], str):
            return f"常见问题解答: {api_response['answer']}"
        elif "error" in api_response and isinstance(api_response["error"], str):
            return f"API错误: {api_response['error']}"
        else:
            logger.warning(f"未知的API响应格式: {api_response}")
            # 未知响应结构的备用方案
            return "从API收到了未知的响应格式。请检查日志。"


# 创建格式化程序实例
response_formatter = ResponseFormatter()
