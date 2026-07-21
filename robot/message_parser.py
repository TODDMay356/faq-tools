import logging
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)


class MessageParser:
    """
    解析微信消息以提取相关查询。
    """

    def __init__(self, bot_name: str) -> None:
        """
        使用机器人的微信名称初始化MessageParser。

        Args:
            bot_name (str): 机器人的微信名称。
        """
        self.bot_name = bot_name
        self.mention_prefix = f"@{bot_name}"
        logger.info(f"MessageParser已用机器人名称初始化: {bot_name}")

    def extract_query(self, message_text: str) -> Optional[str]:
        """
        从提及机器人的消息中提取查询。

        Args:
            message_text (str): 微信消息的完整文本。

        Returns:
            Optional[str]: 提取的查询字符串，如果未提及机器人
                           或在删除提及后查询为空，则返回None。
        """
        if self.mention_prefix in message_text:
            # 移除提及并去除前导/尾随空格
            query = message_text.replace(self.mention_prefix, "").strip()
            if query:
                logger.debug(f"从消息 '{message_text}' 中提取的查询: '{query}'")
                return query
            else:
                logger.warning(f"机器人被提及，但在消息 '{message_text}' 中未找到查询。")
                return None
        else:
            logger.debug(f"消息 '{message_text}' 中未提及机器人。")
            return None


# 使用设置初始化MessageParser
message_parser = MessageParser(bot_name=settings.BOT_NAME)
