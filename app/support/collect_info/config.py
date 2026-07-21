"""配置文件"""
import os
from typing import List
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()


class CollectInfoSettings:
    """问卷收集配置"""
    
    # 飞书配置
    feishu_app_id: str = os.getenv("FEISHU_APP_ID", "")
    feishu_app_secret: str = os.getenv("FEISHU_APP_SECRET", "")
    feishu_bitable_app_token: str = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
    feishu_bitable_table_id: str = os.getenv("FEISHU_BITABLE_TABLE_ID", "")
    feishu_assignee_id: str = os.getenv("FEISHU_ASSIGNEE_ID", "")  # 吴涯的用户ID
    feishu_group_chat_id: str = os.getenv("FEISHU_GROUP_CHAT_ID", "")  # 接收消息的群组ID
    
    # 备案任务配置
    filing_token: str = os.getenv("FILING_TOKEN", "")
    filing_table_id: str = os.getenv("FILING_TABLE_ID", "")
    filing_assignee_ids: str = os.getenv("FILING_ASSIGNEE_IDS", "")  # 多个ID用逗号分隔
    
    # 交易成功通知配置
    trade_success_app_token: str = os.getenv("TRADE_SUCCESS_APP_TOKEN", "")
    trade_success_table_id: str = os.getenv("TRADE_SUCCESS_TABLE_ID", "")
    
    # 定时任务配置
    collect_info_interval: int = int(os.getenv("COLLECT_INFO_INTERVAL", "250"))  # 默认1小时
    filing_interval: int = int(os.getenv("FILING_INTERVAL", "300"))  # 默认5分钟
    trade_success_interval: int = int(os.getenv("TRADE_SUCCESS_INTERVAL", "3600"))  # 默认1小时
    
    def is_configured(self) -> bool:
        """检查是否已配置所有必需字段"""
        return all([
            self.feishu_app_id,
            self.feishu_app_secret,
            self.feishu_bitable_app_token,
            self.feishu_bitable_table_id,
            self.feishu_assignee_id,
            self.feishu_group_chat_id
        ])
    
    def is_filing_configured(self) -> bool:
        """检查备案任务是否已配置"""
        return all([
            self.feishu_app_id,
            self.feishu_app_secret,
            self.filing_token,
            self.filing_table_id,
            self.filing_assignee_ids
        ])
    
    def is_trade_success_configured(self) -> bool:
        """检查交易成功通知是否已配置"""
        return True
    
    def get_filing_assignee_list(self) -> List[str]:
        """获取备案任务经办人ID列表"""
        if not self.filing_assignee_ids:
            return []
        return [id.strip() for id in self.filing_assignee_ids.split(",") if id.strip()]


@lru_cache()
def get_collect_info_settings() -> CollectInfoSettings:
    """获取问卷收集配置实例（单例）"""
    return CollectInfoSettings()
