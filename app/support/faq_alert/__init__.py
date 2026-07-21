"""关键词告警模块。

当用户咨询（走 /chat 问答接口）命中配置的关键词时：
1. 向飞书群发送一条告警消息（可 @ 指定人员）；
2. 在飞书多维表格中新增一条记录，便于后续统计与分配。

关键词支持通过环境变量预置，也支持运行时通过 API 动态增删（持久化到本地 JSON）。
"""

from app.support.faq_alert.config import FaqAlertSettings, get_faq_alert_settings
from app.support.faq_alert.keyword_store import KeywordStore, keyword_store
from app.support.faq_alert.alerter import FaqAlerter, get_faq_alerter

__all__ = [
    "FaqAlertSettings",
    "get_faq_alert_settings",
    "KeywordStore",
    "keyword_store",
    "FaqAlerter",
    "get_faq_alerter",
]
