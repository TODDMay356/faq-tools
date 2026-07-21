"""核心配置模块"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from functools import lru_cache

load_dotenv()


class Settings:
    """应用配置"""
    # LLM 配置
    llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    qwen_api_key: str = os.getenv("QWEN_API_KEY", "")
    
    # ChromaDB 配置
    chroma_host: str = os.getenv("CHROMA_HOST", "localhost")
    chroma_port: str = os.getenv("CHROMA_PORT", "8000")
    
    # 嵌入模型配置
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    
    # 向量库集合配置
    default_collection_name: str = os.getenv("COLLECTION_NAME", "FLY_PAY_RAG")

    # EOS 鉴权配置
    eos_base_url: str = os.getenv("EOS_BASE_URL", "https://test.inflyway.com")
    eos_username: str = os.getenv("EOS_USERNAME", "18806669914")
    eos_password: str = os.getenv("EOS_PASSWORD", "123456")
    eos_token_ttl_seconds: int = int(os.getenv("EOS_TOKEN_TTL_SECONDS", "600"))

    # Merchant Trader 鉴权配置
    merchant_trader_base_url: str = os.getenv(
        "MERCHANT_TRADER_BASE_URL", "https://merchanttrader-test.inflyway.com"
    )
    merchant_trader_dhpay_cookie: str = os.getenv("MERCHANT_TRADER_DHPAY_COOKIE", "")
    merchant_trader_jsession_id: str = os.getenv("MERCHANT_TRADER_JSESSIONID", "")
    merchant_trader_file_token: str = os.getenv("MERCHANT_TRADER_FILE_TOKEN", "")

    # Cashier open trace API
    cashier_trace_api_key: str = os.getenv("CASHIER_TRACE_API_KEY", "")
    
    # 数据库配置
    DATABASES = {
        'default': {
            'host': os.getenv('PAYMENT_DB_HOST', 'localhost'),
            'port': int(os.getenv('PAYMENT_DB_PORT', '3306')),
            'user': os.getenv('PAYMENT_DB_USER', 'root'),
            'password': os.getenv('PAYMENT_DB_PASSWORD', ''),
            'database': os.getenv('PAYMENT_DB_NAME', 'payment_db'),
            'charset': 'utf8mb4',
            'max_connections': 20,
            'min_cached': 2,
            'max_cached': 5,
            'max_shared': 3
        },
        # 支付系统数据库
        'payment': {
            'host': os.getenv('PAYMENT_DB_HOST', 'localhost'),
            'port': int(os.getenv('PAYMENT_DB_PORT', '3306')),
            'user': os.getenv('PAYMENT_DB_USER', 'root'),
            'password': os.getenv('PAYMENT_DB_PASSWORD', ''),
            'database': os.getenv('PAYMENT_DB_NAME', 'payment_db'),
            'charset': 'utf8mb4',
            'max_connections': 30,
            'min_cached': 3,
            'max_cached': 8,
            'max_shared': 5
        },
        # # 用户系统数据库
        # 'cashier': {
        #     'host': os.getenv('CASHIER_DB_HOST', 'localhost'),
        #     'port': int(os.getenv('CASHIER_DB_PORT', '3306')),
        #     'user': os.getenv('CASHIER_DB_USER', 'root'),
        #     'password': os.getenv('CASHIER_DB_PASSWORD', ''),
        #     'database': os.getenv('CASHIER_DB_NAME', 'user_db'),
        #     'charset': 'utf8mb4',
        #     'max_connections': 15,
        #     'min_cached': 2,
        #     'max_cached': 5,
        #     'max_shared': 3
        # },
        # # 日志数据库
        # 'log': {
        #     'host': os.getenv('LOG_DB_HOST', 'localhost'),
        #     'port': int(os.getenv('LOG_DB_PORT', '3306')),
        #     'user': os.getenv('LOG_DB_USER', 'root'),
        #     'password': os.getenv('LOG_DB_PASSWORD', ''),
        #     'database': os.getenv('LOG_DB_NAME', 'log_db'),
        #     'charset': 'utf8mb4',
        #     'max_connections': 10,
        #     'min_cached': 1,
        #     'max_cached': 3,
        #     'max_shared': 2
        # }
    }


settings = Settings()


@lru_cache()
def get_llm() -> ChatOpenAI:
    """获取LLM实例（单例）"""
    return ChatOpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    )
