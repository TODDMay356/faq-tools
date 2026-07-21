"""交易成功通知处理器测试脚本"""
import asyncio
import os
from dotenv import load_dotenv

from app.support.collect_info.feishu_client import FeishuClient
from app.support.collect_info.trade_success_processor import TradeSuccessProcessor

load_dotenv()


async def test_trade_success_processor():
    """测试交易成功通知处理器"""
    print("=" * 50)
    print("开始测试交易成功通知处理器")
    print("=" * 50)
    
    # 初始化飞书客户端
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET")
    )
    feishu_bitable_app_token: str = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
    feishu_bitable_table_id: str = os.getenv("FEISHU_BITABLE_TABLE_ID", "")
    # 初始化处理器
    processor = TradeSuccessProcessor(
        feishu_client=feishu_client,
        app_token=feishu_bitable_app_token,
        table_id=feishu_bitable_table_id,
        group_chat_id=os.getenv("FEISHU_GROUP_CHAT_ID")
    )
    
    try:
        print(f"\n配置信息:")
        print(f"  App Token: {processor.app_token}")
        print(f"  Table ID: {processor.table_id}")
        print(f"  Group Chat ID: {processor.group_chat_id}")
        
        print(f"\n开始处理交易成功状态检查...")
        await processor.process_all()
        print("✓ 处理完成")
        
    except Exception as e:
        print(f"✗ 处理失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_trade_success_processor())
