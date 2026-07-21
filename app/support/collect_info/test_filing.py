"""备案任务测试脚本"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from app.support.collect_info.feishu_client import FeishuClient
from app.support.collect_info.filing_processor import FilingProcessor

load_dotenv()


async def test_filing_processor():
    """测试备案处理器"""
    print("=" * 50)
    print("开始测试备案任务处理")
    print("=" * 50)
    
    # 初始化飞书客户端
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET")
    )
    
    # 配置参数
    filing_token = os.getenv("FILING_TOKEN", "")
    filing_table_id = os.getenv("FILING_TABLE_ID", "")
    assignee_ids = os.getenv("FILING_ASSIGNEE_IDS", "").split(",")
    assignee_ids = [id.strip() for id in assignee_ids if id.strip()]
    
    try:
        # 获取app_token
        print(f"获取多维表格app_token...")
        app_token = filing_token
        print(f"✓ App Token: {app_token}")
        
        # 创建处理器
        processor = FilingProcessor(
            feishu_client=feishu_client,
            assignee_ids=assignee_ids,
            app_token=app_token,
            table_id=filing_table_id
        )
        
        # 处理所有记录
        print(f"开始处理备案任务...")
        await processor.process_all()
        print("✓ 处理完成")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_filing_processor())