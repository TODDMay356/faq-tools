#!/usr/bin/env python3
"""测试批量获取用户ID功能"""
import asyncio
import os
from dotenv import load_dotenv
from app.support.collect_info.feishu_client import FeishuClient

async def main():
    load_dotenv()
    
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    if not app_id or not app_secret:
        print("请设置环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        return
    
    client = FeishuClient(app_id, app_secret)
    
    # 测试批量获取用户ID
    await client.batch_get_user_id(
        emails=["lixintt@camelfin.com"],
        mobiles=[],
        include_resigned=True
    )

if __name__ == "__main__":
    asyncio.run(main())