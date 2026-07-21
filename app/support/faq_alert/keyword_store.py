"""关键词存储。

关键词来源两部分并集：
1. 环境变量 FAQ_ALERT_KEYWORDS（预置，只读）；
2. 运行时通过 API 增删的关键词（持久化到 data/faq_alert_keywords.json）。

匹配采用大小写不敏感的子串匹配，与现有 msg_transfer 模块保持一致。
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import List

from app.support.faq_alert.config import get_faq_alert_settings

logger = logging.getLogger(__name__)

# 持久化文件：项目根目录 data/faq_alert_keywords.json
# keyword_store.py -> faq_alert -> support -> app -> 项目根目录
_BASE_DIR = Path(__file__).resolve().parents[3]
_STORE_PATH = _BASE_DIR / "data" / "faq_alert_keywords.json"


class KeywordStore:
    """关键词存储，线程安全"""

    def __init__(self, store_path: Path = _STORE_PATH):
        self._store_path = store_path
        self._lock = threading.Lock()
        self._runtime_keywords: List[str] = self._load()

    def _load(self) -> List[str]:
        try:
            if self._store_path.exists():
                data = json.loads(self._store_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [str(k).strip() for k in data if str(k).strip()]
        except Exception as exc:  # noqa: BLE001
            logger.warning("加载关键词文件失败: %s", exc)
        return []

    def _persist(self) -> None:
        try:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            self._store_path.write_text(
                json.dumps(self._runtime_keywords, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("持久化关键词文件失败: %s", exc)

    def list_keywords(self) -> List[str]:
        """返回环境变量预置 + 运行时关键词的并集（去重，保序）"""
        env_keywords = get_faq_alert_settings().get_env_keywords()
        merged: List[str] = []
        seen = set()
        for kw in env_keywords + self._runtime_keywords:
            low = kw.lower()
            if low not in seen:
                seen.add(low)
                merged.append(kw)
        return merged

    def add_keywords(self, keywords: List[str]) -> List[str]:
        """新增关键词（仅影响运行时集合），返回最新全量列表"""
        with self._lock:
            existing_low = {k.lower() for k in self._runtime_keywords}
            env_low = {k.lower() for k in get_faq_alert_settings().get_env_keywords()}
            for kw in keywords:
                kw = kw.strip()
                if not kw:
                    continue
                low = kw.lower()
                if low in existing_low or low in env_low:
                    continue
                self._runtime_keywords.append(kw)
                existing_low.add(low)
            self._persist()
        return self.list_keywords()

    def remove_keyword(self, keyword: str) -> List[str]:
        """删除一个运行时关键词（环境变量预置的无法删除），返回最新全量列表"""
        target = keyword.strip().lower()
        with self._lock:
            self._runtime_keywords = [
                k for k in self._runtime_keywords if k.lower() != target
            ]
            self._persist()
        return self.list_keywords()

    def match(self, text: str) -> List[str]:
        """返回文本命中的全部关键词（大小写不敏感子串匹配）"""
        if not text:
            return []
        text_low = text.lower()
        return [kw for kw in self.list_keywords() if kw.lower() in text_low]


# 全局单例
keyword_store = KeywordStore()
