"""测试企业微信消息加解密功能"""
import sys
sys.path.insert(0, '.')

from app.utils.wechat_crypto import WeChatCrypto


def test_decrypt():
    """测试解密功能（使用官方文档示例）"""
    # 官方文档示例配置
    corp_id = "wx5823bf96d3bd56c7"
    token = "QDG6eK"
    encoding_aes_key = "jWmYm7qr5nMoAUwZRjGtBxmz3KA1tkAj3ykkR6q2B2C"
    
    # 初始化加解密工具
    crypto = WeChatCrypto(token, encoding_aes_key, corp_id)
    
    # 官方文档示例数据
    signature = "477715d11cdb4164915debcba66cb864d751f3e6"
    timestamp = "1409659813"
    nonce = "1372623149"
    msg_encrypt = "RypEvHKD8QQKFhvQ6QleEB4J58tiPdvo+rtK1I9qca6aM/wvqnLSV5zEPeusUiX5L5X/0lWfrf0QADHHhGd3QczcdCUpj911L3vg3W/sYYvuJTs3TUUkSUXxaccAS0qhxchrRYt66wiSpGLYL42aM6A8dTT+6k4aSknmPj48kzJs8qLjvd4Xgpue06DOdnLxAUHzM6+kDZ+HMZfJYuR+LtwGc2hgf5gsijff0ekUNXZiqATP7PF5mZxZ3Izoun1s4zG4LUMnvw2r+KqCKIw+3IQH03v+BCA9nMELNqbSf6tiWSrXJB3LAVGUcallcrw8V2t9EL4EhzJWrQUax5wLVMNS0+rUPA3k22Ncx4XXZS9o0MBH27Bo6BpNelZpS+/uh9KsNlY6bHCmJU9p8g7m3fVKn28H3KDYA5Pl/T8Z1ptDAVe0lXdQ2YoyyH2uyPIGHBZZIs2pDBS8R07+qN+E7Q=="
    
    # 1. 测试签名验证
    print("=" * 60)
    print("测试签名验证")
    print("=" * 60)
    is_valid = crypto.verify_signature(signature, timestamp, nonce, msg_encrypt)
    print(f"签名验证结果: {is_valid}")
    assert is_valid, "签名验证失败"
    print("✓ 签名验证通过\n")
    
    # 2. 测试消息解密
    print("=" * 60)
    print("测试消息解密")
    print("=" * 60)
    try:
        decrypted_msg, receiveid = crypto.decrypt(msg_encrypt)
        print(f"解密成功!")
        print(f"receiveid: {receiveid}")
        print(f"明文消息:\n{decrypted_msg}")
        
        # 验证解密结果
        assert receiveid == corp_id, f"receiveid 不匹配: {receiveid} != {corp_id}"
        assert "<MsgType><![CDATA[text]]></MsgType>" in decrypted_msg, "消息内容不正确"
        assert "<Content><![CDATA[hello]]></Content>" in decrypted_msg, "消息内容不正确"
        
        print("\n✓ 解密验证通过")
        
    except Exception as e:
        print(f"✗ 解密失败: {e}")
        raise
    
    # 3. 测试加密功能
    print("\n" + "=" * 60)
    print("测试消息加密")
    print("=" * 60)
    test_msg = '<xml><ToUserName><![CDATA[mycreate]]></ToUserName><FromUserName><![CDATA[wx5823bf96d3bd56c7]]></FromUserName><CreateTime>1409659813</CreateTime><MsgType><![CDATA[text]]></MsgType><Content><![CDATA[hello]]></Content></xml>'
    
    try:
        encrypted = crypto.encrypt(test_msg)
        print(f"加密成功!")
        print(f"密文长度: {len(encrypted)}")
        print(f"密文前100字符: {encrypted[:100]}...")
        
        # 解密验证
        decrypted_again, receiveid_again = crypto.decrypt(encrypted)
        assert decrypted_again == test_msg, "加密后解密的消息不一致"
        assert receiveid_again == corp_id, "receiveid 不一致"
        
        print("\n✓ 加密验证通过")
        
    except Exception as e:
        print(f"✗ 加密失败: {e}")
        raise
    
    print("\n" + "=" * 60)
    print("所有测试通过! ✓")
    print("=" * 60)


if __name__ == "__main__":
    test_decrypt()
