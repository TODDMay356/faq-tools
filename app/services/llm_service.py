from langchain_openai import ChatOpenAI
from app.core.config import settings

class LLMService:
    """
    用于与大语言模型交互的服务。
    """

    def __init__(self):
        self.llm = self._get_llm()

    def _get_llm(self):
        """
        根据配置获取相应的大语言模型实例。
        """
        if settings.llm_provider == "deepseek":
            return ChatOpenAI(
                api_key=settings.deepseek_api_key,
                base_url="https://api.deepseek.com/v1",
                model="deepseek-chat",
            )
        elif settings.llm_provider == "qwen":
            # 假设千问使用与 OpenAI 兼容的 API
            return ChatOpenAI(
                api_key=settings.qwen_api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model="qwen-turbo",
            )
        else:
            raise ValueError(f"不支持的大语言模型提供商: {settings.llm_provider}")

llm_service = LLMService()
