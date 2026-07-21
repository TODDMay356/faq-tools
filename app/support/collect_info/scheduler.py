"""定时任务调度器"""
import asyncio
import logging
from datetime import datetime
from .feishu_client import FeishuClient
from .flypay_client import FlyPayClient
from .processor import QuestionnaireProcessor
from .filing_processor import FilingProcessor
from .trade_success_processor import TradeSuccessProcessor

logger = logging.getLogger(__name__)


class CollectInfoScheduler:
    """问卷信息收集定时任务"""
    
    def __init__(
        self,
        feishu_app_id: str,
        feishu_app_secret: str,
        bitable_app_token: str,
        bitable_table_id: str,
        assignee_id: str,
        message_receive_id: str,
        interval_seconds: int = 3600
    ):
        self.feishu_client = FeishuClient(feishu_app_id, feishu_app_secret)
        self.flypay_client = FlyPayClient()
        self.processor = QuestionnaireProcessor(
            self.feishu_client,
            self.flypay_client,
            assignee_id,
            message_receive_id
        )
        self.app_token = bitable_app_token
        self.table_id = bitable_table_id
        self.interval = interval_seconds
        self.running = False
    
    async def run_once(self) -> None:
        """执行一次任务"""
        try:
            logger.info(f"开始处理问卷数据 - {datetime.now()}")
            await self.processor.process_all(self.app_token, self.table_id)
            logger.info("问卷数据处理完成")
        except Exception as e:
            logger.error(f"处理问卷数据失败: {e}", exc_info=True)
    
    async def start(self) -> None:
        """启动定时任务"""
        self.running = True
        logger.info(f"定时任务已启动，间隔: {self.interval}秒")
        
        while self.running:
            await self.run_once()
            await asyncio.sleep(self.interval)
    
    def stop(self) -> None:
        """停止定时任务"""
        self.running = False
        logger.info("定时任务已停止")


class FilingScheduler:
    """备案任务定时调度器"""
    
    def __init__(
        self,
        feishu_app_id: str,
        feishu_app_secret: str,
        filing_token: str,
        filing_table_id: str,
        assignee_ids: list,
        interval_seconds: int = 300
    ):
        self.feishu_client = FeishuClient(feishu_app_id, feishu_app_secret)
        self.filing_token = filing_token
        self.filing_table_id = filing_table_id
        self.assignee_ids = assignee_ids
        self.interval = interval_seconds
        self.running = False
        self.app_token = None
    
    async def get_app_token(self) -> str:
        """获取多维表格app_token"""
        if not self.app_token:
            self.app_token = await self.feishu_client.get_bitable_app_token_from_wiki(self.filing_token)
        return self.app_token
    
    async def run_once(self) -> None:
        """执行一次备案任务处理"""
        try:
            logger.info(f"开始处理备案任务 - {datetime.now()}")
            
            app_token = self.filing_token
            processor = FilingProcessor(
                feishu_client=self.feishu_client,
                assignee_ids=self.assignee_ids,
                app_token=app_token,
                table_id=self.filing_table_id
            )
            
            await processor.process_all()
            logger.info("备案任务处理完成")
        except Exception as e:
            logger.error(f"处理备案任务失败: {e}", exc_info=True)
    
    async def start(self) -> None:
        """启动定时任务"""
        self.running = True
        logger.info(f"备案任务定时器已启动，间隔: {self.interval}秒")
        
        while self.running:
            await self.run_once()
            await asyncio.sleep(self.interval)
    
    def stop(self) -> None:
        """停止定时任务"""
        self.running = False
        logger.info("备案任务定时器已停止")


class TradeSuccessScheduler:
    """交易成功通知定时调度器"""
    
    def __init__(
        self,
        feishu_app_id: str,
        feishu_app_secret: str,
        app_token: str,
        table_id: str,
        group_chat_id: str,
        interval_seconds: int = 3600
    ):
        self.feishu_client = FeishuClient(feishu_app_id, feishu_app_secret)
        self.app_token = app_token
        self.table_id = table_id
        self.group_chat_id = group_chat_id
        self.interval = interval_seconds
        self.running = False
    
    async def run_once(self) -> None:
        """执行一次交易成功检查"""
        try:
            logger.info(f"开始检查交易成功状态 - {datetime.now()}")

            processor = TradeSuccessProcessor(
                feishu_client=self.feishu_client,
                app_token=self.app_token,
                table_id=self.table_id,
                group_chat_id=self.group_chat_id
            )
            
            await processor.process_all()
            logger.info("交易成功检查完成")
        except Exception as e:
            logger.error(f"检查交易成功状态失败: {e}", exc_info=True)
    
    async def start(self) -> None:
        """启动定时任务"""
        self.running = True
        logger.info(f"交易成功通知定时器已启动，间隔: {self.interval}秒")
        
        while self.running:
            await self.run_once()
            await asyncio.sleep(self.interval)
    
    def stop(self) -> None:
        """停止定时任务"""
        self.running = False
        logger.info("交易成功通知定时器已停止")
