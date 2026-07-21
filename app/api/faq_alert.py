"""关键词告警管理接口。

- 查看/新增/删除关键词（新增删除均为运行时生效并持久化）
- 手动测试推送
"""
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.support.faq_alert import get_faq_alert_settings, get_faq_alerter, keyword_store

router = APIRouter()


class KeywordAddRequest(BaseModel):
    keywords: List[str]


class KeywordDeleteRequest(BaseModel):
    keyword: str


class AlertTestRequest(BaseModel):
    question: str
    answer: Optional[str] = ""


@router.get("/keywords")
async def list_keywords():
    """查看当前全部关键词（环境变量预置 + 运行时新增）"""
    settings = get_faq_alert_settings()
    return {
        "enabled": settings.enabled,
        "keywords": keyword_store.list_keywords(),
        "env_keywords": settings.get_env_keywords(),
        "push_ready": settings.can_push_message(),
        "bitable_ready": settings.can_write_bitable(),
    }


@router.post("/keywords")
async def add_keywords(req: KeywordAddRequest):
    """新增关键词（可批量），立即生效并持久化"""
    keywords = keyword_store.add_keywords(req.keywords)
    return {"message": "已新增", "keywords": keywords}


@router.delete("/keywords")
async def delete_keyword(req: KeywordDeleteRequest):
    """删除一个运行时关键词（环境变量预置的无法删除）"""
    keywords = keyword_store.remove_keyword(req.keyword)
    return {"message": "已删除", "keywords": keywords}


@router.post("/test")
async def test_alert(req: AlertTestRequest):
    """手动触发一次关键词检测与推送，用于联调飞书配置"""
    result = await get_faq_alerter().maybe_alert(req.question, req.answer or "")
    if result is None:
        return {"matched": [], "message": "未命中关键词或告警未启用"}
    return result
