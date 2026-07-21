"""智能体API接口"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.agents.agent import invoke_agent

router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """调用智能体"""
    try:
        result = invoke_agent(request.message)
        # 提取最后一条消息内容
        messages = result.get("messages", [])
        response_text = messages[-1].content if messages else ""
        
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用失败: {str(e)}")
