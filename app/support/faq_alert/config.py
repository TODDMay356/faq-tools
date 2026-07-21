"""关键词告警配置。

复用 collect_info 模块已有的飞书应用凭证与群/多维表格配置，
未单独配置时自动回退到 FEISHU_* 通用配置，尽量做到「零额外配置即可启用」。
"""
import os
from functools import lru_cache
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split_env(name: str) -> List[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


class FaqAlertSettings:
    """FAQ 关键词告警配置"""

    # 总开关（默认开启，只要配置齐全就生效）
    enabled: bool = os.getenv("FAQ_ALERT_ENABLED", "true").lower() == "true"

    # 飞书应用凭证：优先使用告警专用，未配置则回退通用 FEISHU_*
    feishu_app_id: str = os.getenv("FAQ_ALERT_FEISHU_APP_ID") or os.getenv("FEISHU_APP_ID", "")
    feishu_app_secret: str = os.getenv("FAQ_ALERT_FEISHU_APP_SECRET") or os.getenv("FEISHU_APP_SECRET", "")

    # 告警推送目标群：未配置则回退到 collect_info 的通知群
    target_chat_id: str = os.getenv("FAQ_ALERT_TARGET_CHAT_ID") or os.getenv("FEISHU_GROUP_CHAT_ID", "")

    # @ 人员的 user_id 列表（逗号分隔，可为空）
    mention_user_ids: str = os.getenv("FAQ_ALERT_MENTION_USER_IDS", "")

    # 预置关键词（逗号分隔）。运行时还可通过 keyword_store 动态增删
    keywords: str = os.getenv("FAQ_ALERT_KEYWORDS", "")

    # 多维表格记录：未配置则回退到通用 bitable 配置
    bitable_app_token: str = os.getenv("FAQ_ALERT_BITABLE_APP_TOKEN") or os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
    bitable_table_id: str = os.getenv("FAQ_ALERT_BITABLE_TABLE_ID") or os.getenv("FEISHU_BITABLE_TABLE_ID", "")

    # 多维表格字段名（与飞书表格列名保持一致，支持自定义）
    field_question: str = os.getenv("FAQ_ALERT_FIELD_QUESTION", "问题")
    field_answer: str = os.getenv("FAQ_ALERT_FIELD_ANSWER", "回答")
    field_keyword: str = os.getenv("FAQ_ALERT_FIELD_KEYWORD", "命中关键词")
    field_time: str = os.getenv("FAQ_ALERT_FIELD_TIME", "时间")

    # 同一关键词的去重窗口（秒），窗口内重复命中不再重复推送，默认 0 表示不去重
    dedup_window_seconds: int = int(os.getenv("FAQ_ALERT_DEDUP_WINDOW", "0"))

    def get_env_keywords(self) -> List[str]:
        return _split_env("FAQ_ALERT_KEYWORDS")

    def get_mention_user_list(self) -> List[str]:
        return _split_env("FAQ_ALERT_MENTION_USER_IDS")

    def has_feishu_credentials(self) -> bool:
        return bool(self.feishu_app_id and self.feishu_app_secret)

    def can_push_message(self) -> bool:
        """具备向群推送消息的最小配置"""
        return bool(self.has_feishu_credentials() and self.target_chat_id)

    def can_write_bitable(self) -> bool:
        """具备写入多维表格的最小配置"""
        return bool(self.has_feishu_credentials() and self.bitable_app_token and self.bitable_table_id)


@lru_cache()
def get_faq_alert_settings() -> FaqAlertSettings:
    """获取告警配置实例（单例）"""
    return FaqAlertSettings()
