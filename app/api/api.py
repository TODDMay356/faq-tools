from fastapi import APIRouter
from app.api import chat, files, faq_alert

api_router = APIRouter()

# 包含聊天路由
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
# 包含文件上传路由
api_router.include_router(files.router, prefix="/files", tags=["Files"])
# 关键词告警管理路由
api_router.include_router(faq_alert.router, prefix="/faq-alert", tags=["FAQ Alert"])
