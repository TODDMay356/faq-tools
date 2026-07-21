"""Agent工具模块"""
from .merchant_operation import get_merchant_info
from .payment_order import query_payment_orders
from .rag_tool import search_knowledge_base
from .payment_route import add_payment_route
from .payment_config import get_payment_styles
from .merchant_website import query_merchant_websites
from .order_troubleshoot import troubleshoot_order_by_no

__all__ = [
    "get_merchant_info",
    "query_payment_orders",
    "search_knowledge_base",
    "add_payment_route",
    "get_payment_styles",
    "query_merchant_websites",
    "troubleshoot_order_by_no",
]


def get_all_tools():
    """获取所有工具列表"""
    return [globals()[tool_name] for tool_name in __all__]
