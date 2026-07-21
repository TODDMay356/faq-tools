"""交易成功通知处理器"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta

from app.support.collect_info.feishu_client import FeishuClient
from app.services.multi_db_service import db_manager
from app.utils.database import DatabaseType

logger = logging.getLogger(__name__)

PENDING_BUCKET_ORDER = ("0-15天", "15-30天", "30-60天", "60天以上")


@dataclass
class PendingMerchantInfo:
    """待交易提醒商户信息"""
    record_id: str
    merchant_name: str
    merchant_id: str
    website: str
    submit_time: datetime
    days_passed: int


class TradeSuccessProcessor:
    """交易成功通知处理器"""
    
    def __init__(
        self,
        feishu_client: FeishuClient,
        app_token: str,
        table_id: str,
        group_chat_id: str
    ):
        self.feishu = feishu_client
        self.app_token = app_token
        self.table_id = table_id
        self.group_chat_id = group_chat_id
    
    def _extract_field(self, fields: Dict[str, Any], field_name: str, key: str = 'text', default: str = "") -> str:
        """提取飞书多维表格字段值"""
        data = fields.get(field_name, [])
        if not data or not isinstance(data, list) or len(data) == 0:
            return default
        return data[0].get(key, default)
    
    async def check_payment_order(self, merchant_id: str) -> bool:
        """查询td_payment_order表是否存在交易成功的订单"""
        sql = """
        SELECT COUNT(*) as count 
        FROM td_payment_order 
        WHERE merchant_id = %s AND status = '01'
        """
        result = db_manager.execute_one(sql, (merchant_id,), db_name=DatabaseType.PAYMENT)
        return result and result.get('count', 0) > 0
    
    async def check_service_trade_buyer_info(self, merchant_id: str) -> Dict[str, Any]:
        """检查服务贸易商户的买家信息完整性
        
        Returns:
            Dict包含: 
            - has_issue: bool, 是否存在问题
            - buyer_email_empty: bool, buyer_email是否为空
            - unique_id_empty: bool, unique_id是否为空
            - pay_order_uuid: str, 支付单UUID
        """
        # 查询最新的成功支付单
        sql = """
        SELECT pay_order_uuid, buyer_email ,pay_order_id
        FROM td_payment_order 
        WHERE merchant_id = %s AND status = '01' 
        ORDER BY create_time DESC 
        LIMIT 1
        """
        order = db_manager.execute_one(sql, (merchant_id,), db_name=DatabaseType.PAYMENT)
        
        if not order:
            return {"has_issue": False}
        
        pay_order_uuid = order.get('pay_order_uuid', '')
        pay_order_id = order.get('pay_order_id', '')
        buyer_email = order.get('buyer_email', '')
        buyer_email_empty = not buyer_email or buyer_email.strip() == ''
        
        # 查询买家信息表
        sql_buyer = """
        SELECT unique_id 
        FROM td_payment_order_buyer 
        WHERE pay_order_uuid = %s
        """
        buyer_info = db_manager.execute_one(sql_buyer, (pay_order_uuid,), db_name=DatabaseType.PAYMENT)
        
        unique_id_empty = True
        if buyer_info:
            unique_id = buyer_info.get('unique_id', '')
            unique_id_empty = not unique_id or unique_id.strip() == ''
        
        has_issue = buyer_email_empty or unique_id_empty
        
        return {
            "has_issue": has_issue,
            "buyer_email_empty": buyer_email_empty,
            "unique_id_empty": unique_id_empty,
            "pay_order_id": pay_order_id,
            "pay_order_uuid": pay_order_uuid
        }
    
    async def send_success_notification(self, merchant_name: str, merchant_id: str, website: str) -> None:
        """发送交易成功通知"""
        import json
        
        message_text = f"""【交易成功通知】
商户名称: {merchant_name}
MID: {merchant_id}
网址: {website}
状态: 已检测到交易成功订单
"""
        
        content = json.dumps({"text": message_text})
        
        await self.feishu.send_message(
            receive_id=self.group_chat_id,
            msg_type="text",
            content=content,
            receive_id_type="chat_id"
        )
        logger.info(f"已发送交易成功通知: {merchant_id}")
    
    async def send_buyer_info_warning(self, merchant_name: str, merchant_id: str, website: str, 
                                     buyer_email_empty: bool, unique_id_empty: bool, pay_order_uuid: str) -> None:
        """发送买家信息缺失警告"""
        import json
        
        issues = []
        if buyer_email_empty:
            issues.append("buyer_email为空")
        if unique_id_empty:
            issues.append("unique_id为空")
        
        issues_text = "、".join(issues)
        
        message_text = f"""【服务贸易买家信息缺失警告】
商户名称: {merchant_name}
MID: {merchant_id}
网址: {website}
支付单号: {pay_order_uuid}
问题: {issues_text}
请及时补充买家信息
"""
        
        content = json.dumps({"text": message_text})
        
        await self.feishu.send_message(
            receive_id=self.group_chat_id,
            msg_type="text",
            content=content,
            receive_id_type="chat_id"
        )
        logger.info(f"已发送买家信息缺失警告: {merchant_id}, 问题: {issues_text}")
    
    @staticmethod
    def _get_pending_bucket(days_passed: int) -> Optional[str]:
        """按未交易天数划分区间"""
        if days_passed < 1:
            return None
        if days_passed <= 15:
            return "0-15天"
        if days_passed <= 30:
            return "15-30天"
        if days_passed <= 60:
            return "30-60天"
        return "60天以上"

    @staticmethod
    def _should_send_pending_notify(
        days_passed: int,
        last_pending_notify: Optional[datetime],
    ) -> bool:
        """判断是否需要发送待交易通知（每天一次）"""
        if days_passed < 1:
            return False
        if not last_pending_notify:
            return True
        return datetime.now() - last_pending_notify >= timedelta(days=1)

    async def send_consolidated_pending_notification(
        self,
        merchants: List[PendingMerchantInfo],
    ) -> None:
        """合并发送待交易通知，按天数区间分组展示"""
        import json

        buckets: Dict[str, List[PendingMerchantInfo]] = {}
        for merchant in merchants:
            bucket = self._get_pending_bucket(merchant.days_passed)
            if bucket:
                buckets.setdefault(bucket, []).append(merchant)

        lines = ["【待交易提醒】", ""]
        for bucket in PENDING_BUCKET_ORDER:
            items = buckets.get(bucket, [])
            if not items:
                continue
            names = "、".join(item.merchant_name or item.merchant_id for item in items)
            lines.append(f"{bucket}（{len(items)}家）: {names}")
            for item in items:
                submit_time_str = item.submit_time.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(
                    f"  · {item.merchant_name} | MID: {item.merchant_id} | "
                    f"提交: {submit_time_str} | 已过{item.days_passed}天"
                )
            lines.append("")

        message_text = "\n".join(lines).rstrip()
        content = json.dumps({"text": message_text})

        await self.feishu.send_message(
            receive_id=self.group_chat_id,
            msg_type="text",
            content=content,
            receive_id_type="chat_id",
        )
        logger.info(
            "已发送合并待交易通知，共 %d 家商户，区间分布: %s",
            len(merchants),
            {bucket: len(buckets.get(bucket, [])) for bucket in PENDING_BUCKET_ORDER},
        )
    
    async def process_record(self, record: Dict[str, Any]) -> Optional[PendingMerchantInfo]:
        """处理单条记录，返回需要发送待交易提醒的商户信息"""
        fields = record.get("fields", {})
        record_id = record.get("record_id", "")
        
        # 提取字段
        merchant_id = self._extract_field(fields, "MID")
        merchant_name = self._extract_field(fields, "企业名称")
        website = self._extract_field(fields, "接入网址")
        trade_type = fields.get("贸易类型", "")
        submit_time_data = fields.get("提交时间")
        success_notify_time_data = fields.get("成功交易提醒时间")
        pending_notify_time_data = fields.get("无成功交易提醒时间")
        
        if not merchant_id:
            logger.warning(f"记录 {record_id} 缺少MID，跳过")
            return None
        
        # 提取提交时间
        submit_time = None
        if submit_time_data and isinstance(submit_time_data, (int, float)):
            submit_time = datetime.fromtimestamp(submit_time_data / 1000)
        
        # 提取上次提醒时间
        last_pending_notify = None
        if pending_notify_time_data and isinstance(pending_notify_time_data, (int, float)):
            last_pending_notify = datetime.fromtimestamp(pending_notify_time_data / 1000)
        
        try:
            # 查询是否有交易成功订单
            has_order = await self.check_payment_order(merchant_id)
            
            if has_order:
                # 检查是否已发送过成功通知
                if not success_notify_time_data:
                    # 发送交易成功通知
                    await self.send_success_notification(merchant_name, merchant_id, website)
                    
                    # 更新交易成功状态为1，并记录成功交易提醒时间
                    current_time = int(datetime.now().timestamp() * 1000)
                    await self.feishu.update_bitable_record(
                        app_token=self.app_token,
                        table_id=self.table_id,
                        record_id=record_id,
                        fields={
                            "交易成功状态": 1,
                            "成功交易提醒时间": current_time
                        }
                    )
                    logger.info(f"已更新记录 {record_id} 交易成功状态为1，记录提醒时间")
                else:
                    logger.info(f"记录 {record_id} 已发送过交易成功通知，跳过")
                
                # 如果是服务贸易，检查买家信息完整性
                if trade_type == "服务贸易":
                    buyer_check = await self.check_service_trade_buyer_info(merchant_id)
                    if buyer_check.get("has_issue"):
                        await self.send_buyer_info_warning(
                            merchant_name, 
                            merchant_id, 
                            website,
                            buyer_check.get("buyer_email_empty", False),
                            buyer_check.get("unique_id_empty", False),
                            buyer_check.get("pay_order_id", "")
                        )
            else:
                if submit_time:
                    days_passed = (datetime.now() - submit_time).days
                    if self._should_send_pending_notify(days_passed, last_pending_notify):
                        logger.info(
                            f"记录 {record_id} 提交超过{days_passed}天，加入待交易合并提醒"
                        )
                        return PendingMerchantInfo(
                            record_id=record_id,
                            merchant_name=merchant_name,
                            merchant_id=merchant_id,
                            website=website,
                            submit_time=submit_time,
                            days_passed=days_passed,
                        )
                    logger.info(f"记录 {record_id} 距离上次通知不足1天，跳过")

        except Exception as e:
            logger.error(f"处理记录 {record_id} 失败: {e}")

        return None
    
    async def process_all(self) -> None:
        """处理所有交易成功状态=0的记录"""
        records = await self.feishu.get_bitable_records(
            app_token=self.app_token,
            table_id=self.table_id,
            filter_field="交易成功状态",
            filter_value=0
        )
        logger.info(f"获取到 {len(records)} 条待处理记录")
        
        pending_merchants: List[PendingMerchantInfo] = []
        for record in records:
            pending = await self.process_record(record)
            if pending:
                pending_merchants.append(pending)

        if pending_merchants:
            await self.send_consolidated_pending_notification(pending_merchants)
            current_time = int(datetime.now().timestamp() * 1000)
            for pending in pending_merchants:
                await self.feishu.update_bitable_record(
                    app_token=self.app_token,
                    table_id=self.table_id,
                    record_id=pending.record_id,
                    fields={"无成功交易提醒时间": current_time},
                )
                logger.info(
                    f"记录 {pending.record_id} 已更新无成功交易提醒时间"
                )
