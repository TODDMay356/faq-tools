import logging
import sys

from .wechat_bot import WeChatBot
from .config import settings

# 配置日志
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

def main() -> None:
    """
    主函数，用于初始化和运行微信机器人。
    """
    logger.info("正在启动微信API支持机器人...")
    try:
        # 确保存在必要的配置
        if not settings.BOT_NAME or settings.BOT_NAME == "YourBotName":
            logger.error("BOT_NAME未在.env中正确配置。请将其设置为您的机器人微信名称。")
            sys.exit(1)
        if not settings.API_BASE_URL or settings.API_BASE_URL == "http://localhost:8000/api/v1":
            logger.warning("API_BASE_URL未配置。正在使用默认值。请在.env中正确设置。")

        bot = WeChatBot()
        bot.run()
    except ValueError as ve:
        logger.error(f"配置错误: {ve}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"发生未处理的错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
