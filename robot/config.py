import os
from dotenv import load_dotenv

# 从.env文件加载环境变量
load_dotenv()

class Config:
    """
    用于加载微信机器人环境变量的配置类。
    """
    BOT_NAME: str = os.getenv("BOT_NAME", "YourBotName")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    API_KEY: str | None = os.getenv("API_KEY")

    def __init__(self) -> None:
        """
        初始化Config类。
        """
        if not self.BOT_NAME:
            raise ValueError("未设置BOT_NAME环境变量。")
        if not self.API_BASE_URL:
            raise ValueError("未设置API_BASE_URL环境变量。")

# 创建配置实例
settings = Config()
