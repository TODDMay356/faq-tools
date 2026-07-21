"""企微智能机器人回调接口"""
import os
import json
import logging
import hashlib
import base64
from typing import Optional
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse, Response

from app.utils.WXBizJsonMsgCrypt import WXBizJsonMsgCrypt
from app.agents.agent import invoke_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wechat", tags=["wechat"])

# 从环境变量读取配置
TOKEN = os.getenv("WECHAT_TOKEN", "EvO46DbTskSlioVbPwH")
ENCODING_AES_KEY = os.getenv("WECHAT_ENCODING_AES_KEY", "")
RECEIVE_ID = ""  # 智能机器人的 receiveid 是空串


class StreamManager:
    """流式消息管理器"""
    def __init__(self):
        self.streams = {}  # {stream_id: {"content": str, "finish": bool}}
    
    def create_stream(self, stream_id: str, content: str, finish: bool = False):
        """创建或更新流式消息"""
        self.streams[stream_id] = {
            "content": content,
            "finish": finish
        }
    
    def get_stream(self, stream_id: str) -> Optional[dict]:
        """获取流式消息"""
        return self.streams.get(stream_id)


stream_manager = StreamManager()


def make_text_stream(stream_id: str, content: str, finish: bool) -> str:
    """构造文本流式消息"""
    plain = {
        "msgtype": "stream",
        "stream": {
            "id": stream_id,
            "finish": finish,
            "content": content
        }
    }
    return json.dumps(plain, ensure_ascii=False)


def make_image_stream(stream_id: str, image_data: bytes, finish: bool) -> str:
    """构造图片流式消息"""
    image_md5 = hashlib.md5(image_data).hexdigest()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    
    plain = {
        "msgtype": "stream",
        "stream": {
            "id": stream_id,
            "finish": finish,
            "msg_item": [
                {
                    "msgtype": "image",
                    "image": {
                        "base64": image_base64,
                        "md5": image_md5
                    }
                }
            ]
        }
    }
    return json.dumps(plain, ensure_ascii=False)


@router.get("/robot/callback")
async def verify_url(
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...)
):
    """验证URL回调"""
    try:
        wxcpt = WXBizJsonMsgCrypt(TOKEN, ENCODING_AES_KEY, RECEIVE_ID)
        ret, reply_echostr = wxcpt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        
        if ret != 0:
            logger.error(f"验证URL失败，错误码: {ret}")
            return PlainTextResponse("verify fail")
        
        logger.info("URL验证成功")
        return PlainTextResponse(reply_echostr)
    
    except Exception as e:
        logger.error(f"验证URL异常: {e}")
        return PlainTextResponse("verify fail")


@router.post("/robot/callback")
async def handle_callback(
    request: Request,
    msg_signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    """处理企微回调消息"""
    try:
        # 读取POST数据
        post_data = await request.body()
        
        # 解密消息
        wxcpt = WXBizJsonMsgCrypt(TOKEN, ENCODING_AES_KEY, RECEIVE_ID)
        ret, msg = wxcpt.DecryptMsg(post_data, msg_signature, timestamp, nonce)
        
        if ret != 0:
            logger.error(f"解密消息失败，错误码: {ret}")
            raise HTTPException(status_code=400, detail="Decrypt fail")
        
        # 解析消息
        data = json.loads(msg)
        logger.info(f"收到消息: {data}")
        
        msgtype = data.get("msgtype")
        
        # 处理不同类型的消息
        if msgtype == "text":
            # 文本消息
            content = data.get("text", {}).get("content", "")
            response_content = await process_text_message(content)
            
            # 生成stream_id
            import uuid
            stream_id = str(uuid.uuid4())
            
            # 构造流式响应
            stream = make_text_stream(stream_id, response_content, True)
            
        elif msgtype == "stream":
            # 流式消息刷新请求
            stream_id = data.get("stream", {}).get("id", "")
            stream_info = stream_manager.get_stream(stream_id)
            
            if stream_info:
                stream = make_text_stream(
                    stream_id,
                    stream_info["content"],
                    stream_info["finish"]
                )
            else:
                stream = make_text_stream(stream_id, "消息已过期", True)
        
        elif msgtype == "image":
            # 图片消息 - 暂不处理
            logger.warning("暂不支持图片消息")
            return PlainTextResponse("success")
        
        elif msgtype == "mixed":
            # 图文混排消息 - 暂不处理
            logger.warning("暂不支持图文混排消息")
            return PlainTextResponse("success")
        
        elif msgtype == "event":
            # 事件消息 - 暂不处理
            logger.warning(f"收到事件消息: {data}")
            return PlainTextResponse("success")
        
        else:
            logger.warning(f"不支持的消息类型: {msgtype}")
            return PlainTextResponse("success")
        
        # 加密响应
        ret, encrypted_resp = wxcpt.EncryptMsg(stream, nonce, timestamp)
        
        if ret != 0:
            logger.error(f"加密响应失败，错误码: {ret}")
            raise HTTPException(status_code=500, detail="Encrypt fail")
        
        logger.info("消息处理成功")
        return Response(content=encrypted_resp, media_type="application/json")
    
    except Exception as e:
        logger.error(f"处理回调异常: {e}", exc_info=True)
        return PlainTextResponse("success")


async def process_text_message(content: str) -> str:
    """处理文本消息，调用智能体"""
    try:
        result = invoke_agent(content)
        messages = result.get("messages", [])
        response_text = messages[-1].content if messages else "抱歉，我无法处理您的请求"
        return response_text
    except Exception as e:
        logger.error(f"调用智能体失败: {e}")
        return "抱歉，系统出现错误，请稍后再试"
