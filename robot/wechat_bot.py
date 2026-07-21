import logging
import re
from typing import Dict, Any

from wxpy import Bot, Group, Message, TEXT

from .config import settings
from .api_client import api_client
from .message_parser import message_parser
from .response_formatter import response_formatter

# 配置日志
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


class WeChatBot:
    """
    微信机器人，监听群组中的提及消息，查询API并回复。
    """

    def __init__(self) -> None:
        """
        初始化WeChatBot，登录微信并设置消息监听器。
        """
        logger.info("正在初始化WeChatBot...")
        self.bot = Bot(cache_path=True)  # 使用缓存以避免频繁扫描二维码
        self.bot_name = settings.BOT_NAME
        logger.info(f"机器人 '{self.bot_name}' 登录成功。")

        # 为群组消息注册消息处理器
        @self.bot.register(msg_types=TEXT, chats=Group)
        def group_message_handler(msg: Message) -> None:
            """
            处理来自微信群组的传入文本消息。
            """
            self._handle_group_message(msg)

    def _handle_group_message(self, msg: Message) -> None:
        """
        处理群组消息以检查提及并进行回复（如果适用）。

        Args:
            msg (Message): 传入的微信消息对象。
        """
        logger.debug(f"收到来自 {msg.sender.name} 在 {msg.chat.name} 群组中的消息: {msg.text}")

        # 检查消息是否提及机器人
        if re.search(rf"@{re.escape(self.bot_name)}(\s|$)", msg.text):
            logger.info(f"机器人在群组 '{msg.chat.name}' 中被 '{msg.sender.name}' 提及。")
            query = message_parser.extract_query(msg.text)
            if query:
                response_text = self._get_api_response(query)
                # 回复群组，提及原始发件人
                msg.chat.send(f"@{msg.sender.name} {response_text}")
                logger.info(f"已回复 '{msg.sender.name}' 在 '{msg.chat.name}' 群组中的消息。")
            else:
                msg.chat.send(f"@{msg.sender.name} 我收到了您的提及，但未能找到明确的查询。请问有什么可以帮您的吗？")
                logger.warning(f"从消息中未提取到查询: {msg.text}")

    def _get_api_response(self, query: str) -> str:
        """
        根据提取的查询调用内部API并格式化响应。

        Args:
            query (str): 从微信消息中提取的查询。

        Returns:
            str: 包含API响应或错误消息的格式化字符串。
        """
        try:
            # 基本命令解析 - 根据需要扩展此逻辑
            if query.lower() == "status":
                api_resp = api_client.get_api_status()
            elif query.lower().startswith("docs "):
                search_term = query[5:].strip()
                api_resp = api_client.query_api_docs(search_term)
            elif query.lower().startswith("order status "):
                order_id = query[len("order status "):].strip()
                api_resp = api_client.get_payment_status(order_id)
            elif query.lower().startswith("faq "):
                question = query[len("faq "):].strip()
                api_resp = api_client.search_faq(question)
            else:
                # 默认行为: 如果没有匹配到特定命令，则尝试搜索FAQ
                api_resp = api_client.search_faq(query)

            return response_formatter.format_response(api_resp)
        except Exception as e:
            logger.error(f"调用API或格式化查询 '{query}' 的响应时出错: {e}", exc_info=True)
            return "抱歉，我在尝试获取信息时遇到错误。请稍后再试。"

    def run(self) -> None:
        """
        启动机器人并保持运行。
        """
        logger.info("WeChatBot正在运行...")
        self.bot.join()  # 阻塞直到机器人退出或停止


# 在main.py中初始化并运行机器人
