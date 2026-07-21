"""消息转发配置"""
import os
from typing import List
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()


class MsgTransferSettings:
    """消息转发配置"""
    
    # 消息转发专用飞书应用配置（不与其他模块共用）
    feishu_app_id: str = os.getenv("MSG_TRANSFER_FEISHU_APP_ID", "")
    feishu_app_secret: str = os.getenv("MSG_TRANSFER_FEISHU_APP_SECRET", "")
    
    # 消息源群ID（群A），逗号分隔支持多个
    source_chat_id: str = os.getenv("MSG_TRANSFER_SOURCE_CHAT_ID", "")
    
    # 目标群ID（群B），逗号分隔支持多个
    target_chat_id: str = os.getenv("MSG_TRANSFER_TARGET_CHAT_ID", "")
    
    # 关键词列表（逗号分隔）
    keywords: str = os.getenv("MSG_TRANSFER_KEYWORDS", "")
    
    # @人员ID列表（逗号分隔）
    mention_user_ids: str = os.getenv("MSG_TRANSFER_MENTION_USER_IDS", "")
    
    # 轮询间隔（秒），默认5秒
    poll_interval: int = int(os.getenv("MSG_TRANSFER_POLL_INTERVAL", "5"))

    # 增量轮询单次最多分页数，防止拉取过多历史
    poll_max_pages: int = int(os.getenv("MSG_TRANSFER_POLL_MAX_PAGES", "3"))

    # 增量轮询回溯窗口（秒），略大于 poll_interval 可防止漏消息
    poll_lookback_seconds: int = int(os.getenv("MSG_TRANSFER_POLL_LOOKBACK", "30"))

    # 同一消息最大转发次数，默认3次
    max_forward_count: int = int(os.getenv("MSG_TRANSFER_MAX_COUNT", "3"))
    
    # 转发间隔（秒），用于重复转发时的间隔，默认300秒（5分钟）
    forward_interval: int = int(os.getenv("MSG_TRANSFER_FORWARD_INTERVAL", "300"))
    
    def is_configured(self) -> bool:
        """检查是否已配置所有必需字段"""
        return all([
            self.feishu_app_id,
            self.feishu_app_secret,
            self.get_source_chat_list(),
            self.get_target_chat_list(),
            self.get_keywords_list()
        ])

    def has_long_connection_credentials(self) -> bool:
        """检查是否具备启动长连接所需凭证"""
        return bool(self.feishu_app_id and self.feishu_app_secret)
    
    def get_source_chat_list(self) -> List[str]:
        """获取源群ID列表"""
        if not self.source_chat_id:
            return []
        return [cid.strip() for cid in self.source_chat_id.split(",") if cid.strip()]

    def get_target_chat_list(self) -> List[str]:
        """获取目标群ID列表"""
        if not self.target_chat_id:
            return []
        return [cid.strip() for cid in self.target_chat_id.split(",") if cid.strip()]

    def get_keywords_list(self) -> List[str]:
        """获取关键词列表"""
        if not self.keywords:
            return []
        return [kw.strip() for kw in self.keywords.split(",") if kw.strip()]
    
    def get_mention_user_list(self) -> List[str]:
        """获取@人员ID列表"""
        if not self.mention_user_ids:
            return []
        return [uid.strip() for uid in self.mention_user_ids.split(",") if uid.strip()]


@lru_cache()
def get_msg_transfer_settings() -> MsgTransferSettings:
    """获取消息转发配置实例（单例）"""
    return MsgTransferSettings()
