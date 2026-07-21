"""企业微信回调接口"""
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse
import logging
import xml.etree.ElementTree as ET
from typing import Optional
import os
import time

from app.utils.wechat_crypto import WeChatCrypto
from app.agents.agent import invoke_agent

router = APIRouter()
logger = logging.getLogger(__name__)

# 企业微信配置（从环境变量读取）
WECHAT_TOKEN = os.getenv("WECHAT_TOKEN", "EvO46DbTskSlioVbPwH")
WECHAT_ENCODING_AES_KEY = os.getenv("WECHAT_ENCODING_AES_KEY", "")
WECHAT_CORP_ID = os.getenv("WECHAT_CORP_ID", "ww3f1e47a13a33d7a1")

# 初始化加解密工具
crypto = WeChatCrypto(WECHAT_TOKEN, WECHAT_ENCODING_AES_KEY, WECHAT_CORP_ID)


def build_text_response(content: str, to_user: str, from_user: str, timestamp: str) -> str:
    """构建文本响应 XML"""
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{timestamp}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


@router.get("/callback", response_class=PlainTextResponse)
async def wechat_verify(
    msg_signature: str = Query(..., description="企业微信加密签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数"),
    echostr: str = Query(..., description="加密的字符串")
):
    """
    企业微信 URL 验证接口
    
    企业微信会发送 GET 请求验证 URL 有效性
    """
    logger.info("[WeChat] 收到验证请求")
    logger.info(f"  - msg_signature: {msg_signature}")
    logger.info(f"  - timestamp: {timestamp}")
    logger.info(f"  - nonce: {nonce}")
    logger.info(f"  - echostr: {echostr[:50]}...")
    
    try:
        # 1. 验证签名
        if not crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
            logger.error("[WeChat] 签名验证失败")
            raise HTTPException(status_code=403, detail="签名验证失败")
        
        # 2. 解密 echostr
        decrypted_msg, receiveid = crypto.decrypt(echostr)
        
        logger.info(f"[WeChat] 验证成功，receiveid: {receiveid}")
        
        # 3. 返回明文
        return decrypted_msg
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[WeChat] 验证处理异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/callback", response_class=PlainTextResponse)
async def wechat_callback(
    request: Request,
    msg_signature: str = Query(..., description="消息签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数")
):
    """
    企业微信消息回调接口
    
    接收企业微信推送的消息
    """
    logger.info("[WeChat] 收到消息回调")
    
    try:
        # 1. 读取请求体
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"[WeChat] 消息体: {body_str[:200]}...")
        
        # 2. 解析 XML 获取加密消息
        root = ET.fromstring(body_str)
        to_user_name = root.find('ToUserName').text
        encrypt = root.find('Encrypt').text
        agent_id = root.find('AgentID')
        agent_id_text = agent_id.text if agent_id is not None else None
        
        logger.info(f"[WeChat] ToUserName: {to_user_name}, AgentID: {agent_id_text}")
        
        # 3. 验证签名
        if not crypto.verify_signature(msg_signature, timestamp, nonce, encrypt):
            logger.error("[WeChat] 签名验证失败")
            return ""
        
        # 4. 解密消息
        decrypted_msg, receiveid = crypto.decrypt(encrypt)
        logger.info(f"[WeChat] 解密成功, receiveid: {receiveid}")
        logger.info(f"[WeChat] 明文消息: {decrypted_msg[:500]}...")
        
        # 5. 解析明文 XML
        msg_root = ET.fromstring(decrypted_msg)
        msg_type = msg_root.find('MsgType').text
        from_user = msg_root.find('FromUserName').text
        create_time = msg_root.find('CreateTime').text
        
        logger.info(f"[WeChat] 消息类型: {msg_type}, 发送者: {from_user}")
        
        # 6. 处理不同类型的消息
        if msg_type == 'text':
            content = msg_root.find('Content').text
            msg_id = msg_root.find('MsgId').text
            logger.info(f"[WeChat] 文本消息: {content}, MsgId: {msg_id}")
            
            # 调用 Agent 处理消息
            try:
                result = invoke_agent(content)
                messages = result.get("messages", [])
                response_text = messages[-1].content if messages else "处理失败"
                
                # 构建加密响应
                current_time = str(int(time.time()))
                response_xml = build_text_response(response_text, from_user, to_user_name, current_time)
                encrypted_response = crypto.encrypt(response_xml, nonce, timestamp)
                return encrypted_response
            except Exception as e:
                logger.exception(f"[WeChat] Agent处理失败: {e}")
                # 返回错误提示
                error_msg = "抱歉，处理您的消息时出现了问题，请稍后再试。"
                current_time = str(int(time.time()))
                response_xml = build_text_response(error_msg, from_user, to_user_name, current_time)
                encrypted_response = crypto.encrypt(response_xml, nonce, timestamp)
                return encrypted_response
        
        elif msg_type == 'event':
            event = msg_root.find('Event').text
            logger.info(f"[WeChat] 事件消息: {event}")
            # TODO: 处理事件消息
        
        # 7. 如果不需要回复，返回空字符串
        logger.info("[WeChat] 消息处理完成")
        return ""
        
    except Exception as e:
        logger.exception(f"[WeChat] 消息处理异常: {e}")
        # 返回 200 避免重试
        return ""
