from pydantic import BaseModel

class ChatRequest(BaseModel):
    """
    聊天接口的请求模型。
    """
    question: str

class ChatResponse(BaseModel):
    """
    聊天接口的响应模型。
    """
    answer: str
