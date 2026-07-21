import asyncio
from fastapi import APIRouter, HTTPException
import logging
from app.models.chat import ChatRequest, ChatResponse
from app.agents.agent import invoke_agent
from app.support.faq_alert import get_faq_alerter

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    智能体聊天接口，结合向量检索和工具调用。
    """
    logger = logging.getLogger(__name__)
    logger.info("[Chat][start] question='%s'", (request.question[:200] + "...") if len(request.question) > 200 else request.question)
    try:
        result = invoke_agent(request.question)
        # 提取最后一条消息内容
        messages = result.get("messages", [])
        answer = messages[-1].content if messages else "抱歉，无法生成回答"

        logger.info("[Chat][done] answer_length=%d", len(answer))

        # 关键词告警：命中即推送飞书群 + 写多维表格。
        # 后台执行，不阻塞、不影响本次问答返回；内部已捕获所有异常。
        asyncio.create_task(get_faq_alerter().maybe_alert(request.question, answer))

        return ChatResponse(answer=answer)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Chat][error]: %s", exc)
        raise HTTPException(status_code=500, detail=f"处理失败: {exc}")
