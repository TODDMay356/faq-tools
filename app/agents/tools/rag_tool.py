"""RAG 向量检索工具"""
import logging
from langchain.tools import tool
from app.services.rag_service import rag_service
from app.core.config import settings

logger = logging.getLogger(__name__)


@tool(description="从知识库检索相关文档信息，用于回答支付接口、错误码、FAQ等问题。调用时需要提取核心关键词和专业术语，避免使用口语化表达。")
def search_knowledge_base(query: str) -> str:
    """检索知识库获取相关信息
    
    调用建议：
    - 提取用户问题中的核心关键词、错误码、接口名称
    - 使用文档中的专业术语，如"支付网址未备案"而非"网址未备案"
    - 包含相关联的技术术语，如"notify_url"、"备案"、"域名"等
    - 错误现象可添加错误码或HTTP状态码
    
    示例：
    - 用户："网址未备案" → 调用参数："支付网址未备案 notify_url 域名备案"
    - 用户："签名不对" → 调用参数："签名错误 hash 校验失败"
    - 用户："403错误" → 调用参数："403 接口返回 user-agent"
    
    Args:
        query: 优化后的查询关键词（包含专业术语和关联词）
        
    Returns:
        str: 检索到的相关文档内容
    """
    logger.info(f"[Tool] search_knowledge_base 调用 - query: {query}")
    try:
        collection_name = settings.default_collection_name
        answer = rag_service.answer_question(query, collection_name)
        logger.info(f"[Tool] search_knowledge_base 成功 - 返回内容长度: {len(answer)}")
        return answer
    except Exception as e:
        logger.exception(f"[Tool] search_knowledge_base 失败 - error: {e}")
        return f"知识库检索失败: {str(e)}"


