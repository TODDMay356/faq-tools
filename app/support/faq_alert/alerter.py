"""关键词告警执行器。

对外只暴露一个入口 `maybe_alert(question, answer)`：
- 命中关键词 -> 推送飞书群消息（可 @ 人）+ 写多维表格；
- 未命中或未配置 -> 直接返回，不影响问答主流程。

设计原则：任何飞书侧异常都被捕获并记录，绝不向上抛出以免影响用户拿到答案。
"""
from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from typing import Dict, List, Optional

from app.support.collect_info.feishu_client import FeishuClient
from app.support.faq_alert.config import FaqAlertSettings, get_faq_alert_settings
from app.support.faq_alert.keyword_store import keyword_store

logger = logging.getLogger(__name__)


class FaqAlerter:
    """FAQ 关键词告警执行器"""

    def __init__(self, settings: FaqAlertSettings):
        self.settings = settings
        self._feishu: Optional[FeishuClient] = None
        if settings.has_feishu_credentials():
            self._feishu = FeishuClient(settings.feishu_app_id, settings.feishu_app_secret)
        # 关键词 -> 上次推送时间，用于去重窗口
        self._last_alert_time: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # 对外入口
    # ------------------------------------------------------------------ #
    async def maybe_alert(self, question: str, answer: str = "") -> Optional[Dict]:
        """检测关键词并按需告警。

        Returns:
            命中并处理时返回结果摘要 dict；未命中/未启用返回 None。
        """
        if not self.settings.enabled:
            return None

        matched = keyword_store.match(question)
        if not matched:
            return None

        if not self._passes_dedup(matched):
            logger.info("[FAQ告警] 命中关键词 %s 但在去重窗口内，跳过推送", matched)
            return {"matched": matched, "skipped": "dedup"}

        if self._feishu is None:
            logger.warning("[FAQ告警] 命中关键词 %s，但缺少飞书凭证，无法推送", matched)
            return {"matched": matched, "skipped": "no_credentials"}

        logger.info("[FAQ告警] 咨询命中关键词: %s", matched)

        result: Dict[str, object] = {"matched": matched}
        result["message_pushed"] = await self._push_group_message(question, answer, matched)
        result["bitable_written"] = await self._write_bitable(question, answer, matched)
        return result

    # ------------------------------------------------------------------ #
    # 内部实现
    # ------------------------------------------------------------------ #
    def _passes_dedup(self, matched: List[str]) -> bool:
        window = self.settings.dedup_window_seconds
        if window <= 0:
            return True
        now = time.time()
        key = ",".join(sorted(matched))
        last = self._last_alert_time.get(key, 0.0)
        if now - last < window:
            return False
        self._last_alert_time[key] = now
        return True

    def _build_message_text(self, question: str, answer: str, matched: List[str]) -> str:
        mention_prefix = ""
        mention_ids = self.settings.get_mention_user_list()
        if mention_ids:
            mention_prefix = " ".join(f'<at user_id="{uid}"></at>' for uid in mention_ids) + "\n"

        lines = [
            "🔔 关键词咨询提醒",
            f"命中关键词：{', '.join(matched)}",
            f"用户问题：{question}",
        ]
        if answer:
            preview = answer if len(answer) <= 500 else answer[:500] + "…"
            lines.append(f"机器人回答：{preview}")
        return mention_prefix + "\n".join(lines)

    async def _push_group_message(self, question: str, answer: str, matched: List[str]) -> bool:
        if not self.settings.can_push_message():
            logger.warning("[FAQ告警] 推送目标群未配置，跳过群消息")
            return False
        try:
            text = self._build_message_text(question, answer, matched)
            await self._feishu.send_message(  # type: ignore[union-attr]
                receive_id=self.settings.target_chat_id,
                msg_type="text",
                content=json.dumps({"text": text}, ensure_ascii=False),
                receive_id_type="chat_id",
            )
            logger.info("[FAQ告警] 群消息推送成功")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("[FAQ告警] 群消息推送失败: %s", exc, exc_info=True)
            return False

    async def _write_bitable(self, question: str, answer: str, matched: List[str]) -> bool:
        if not self.settings.can_write_bitable():
            logger.info("[FAQ告警] 多维表格未配置，跳过写记录")
            return False
        try:
            s = self.settings
            fields = {
                s.field_question: question,
                s.field_answer: answer,
                s.field_keyword: ", ".join(matched),
                # 飞书日期字段接收毫秒时间戳
                s.field_time: int(time.time() * 1000),
            }
            await self._feishu.create_bitable_record(  # type: ignore[union-attr]
                app_token=s.bitable_app_token,
                table_id=s.bitable_table_id,
                fields=fields,
            )
            logger.info("[FAQ告警] 多维表格记录写入成功")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("[FAQ告警] 多维表格写入失败: %s", exc, exc_info=True)
            return False


@lru_cache()
def get_faq_alerter() -> FaqAlerter:
    """获取告警执行器单例"""
    return FaqAlerter(get_faq_alert_settings())
