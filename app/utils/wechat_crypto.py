"""企业微信消息加解密工具"""
import base64
import hashlib
import struct
from Cryptodome.Cipher import AES
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class WeChatCrypto:
    """企业微信消息加解密类"""
    
    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        """
        初始化加解密工具
        
        Args:
            token: 企业微信配置的 Token
            encoding_aes_key: 企业微信配置的 EncodingAESKey (43位)
            corp_id: 企业ID
        """
        self.token = token
        self.corp_id = corp_id
        # EncodingAESKey 补 '=' 后 base64 解码得到 AESKey
        self.aes_key = base64.b64decode(encoding_aes_key + '=')
        
    def verify_signature(self, signature: str, timestamp: str, nonce: str, msg_encrypt: str) -> bool:
        """
        验证消息签名
        
        Args:
            signature: 待验证的签名
            timestamp: 时间戳
            nonce: 随机数
            msg_encrypt: 加密消息
            
        Returns:
            签名是否正确
        """
        try:
            # 将 token、timestamp、nonce、msg_encrypt 按字典序排序
            params = sorted([self.token, timestamp, nonce, msg_encrypt])
            # 拼接为一个字符串
            sort_str = ''.join(params)
            # SHA1 计算签名
            sha1 = hashlib.sha1()
            sha1.update(sort_str.encode('utf-8'))
            calculated_signature = sha1.hexdigest()
            
            return calculated_signature == signature
        except Exception as e:
            logger.error(f"签名验证失败: {e}")
            return False
    
    def decrypt(self, msg_encrypt: str) -> Tuple[str, str]:
        """
        解密消息
        
        Args:
            msg_encrypt: base64编码的加密消息
            
        Returns:
            (解密后的消息, receiveid)
            
        Raises:
            ValueError: 解密失败或验证失败
        """
        try:
            # 1. 对密文 base64 解码
            aes_msg = base64.b64decode(msg_encrypt)
            
            # 2. 使用 AESKey 做 AES-256-CBC 解密
            # IV 为 AESKey 的前16字节
            iv = self.aes_key[:16]
            cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
            rand_msg = cipher.decrypt(aes_msg)
            
            # 3. 去掉 PKCS7 填充
            pad = rand_msg[-1]
            if isinstance(pad, str):
                pad = ord(pad)
            rand_msg = rand_msg[:-pad]
            
            # 4. 去掉前16个随机字节
            content = rand_msg[16:]
            
            # 5. 取出4字节的 msg_len (网络字节序，大端)
            msg_len = struct.unpack('>I', content[:4])[0]
            
            # 6. 截取 msg_len 长度的消息
            msg = content[4:4+msg_len].decode('utf-8')
            
            # 7. 剩余部分为 receiveid
            receiveid = content[4+msg_len:].decode('utf-8')
            
            # 8. 验证 receiveid
            if receiveid != self.corp_id:
                raise ValueError(f"receiveid 验证失败: {receiveid} != {self.corp_id}")
            
            logger.info(f"消息解密成功, receiveid: {receiveid}")
            return msg, receiveid
            
        except Exception as e:
            logger.error(f"消息解密失败: {e}")
            raise ValueError(f"消息解密失败: {e}")
    
    def encrypt(self, msg: str) -> str:
        """
        加密消息（用于回复）
        
        Args:
            msg: 待加密的消息
            
        Returns:
            base64编码的加密消息
        """
        try:
            import os
            
            # 1. 生成16字节随机字符串
            rand_bytes = os.urandom(16)
            
            # 2. 计算 msg 长度（4字节网络字节序）
            msg_bytes = msg.encode('utf-8')
            msg_len = struct.pack('>I', len(msg_bytes))
            
            # 3. 拼接: rand(16) + msg_len(4) + msg + receiveid
            receiveid_bytes = self.corp_id.encode('utf-8')
            plain_text = rand_bytes + msg_len + msg_bytes + receiveid_bytes
            
            # 4. PKCS7 填充
            block_size = 32  # AES-256-CBC 块大小
            pad = block_size - len(plain_text) % block_size
            plain_text += bytes([pad] * pad)
            
            # 5. AES-256-CBC 加密
            iv = self.aes_key[:16]
            cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
            encrypted = cipher.encrypt(plain_text)
            
            # 6. base64 编码
            return base64.b64encode(encrypted).decode('utf-8')
            
        except Exception as e:
            logger.error(f"消息加密失败: {e}")
            raise ValueError(f"消息加密失败: {e}")
