"""问卷数据处理器"""
from typing import Dict, Any, List
import logging

from app.support.collect_info.feishu_client import FeishuClient
from app.support.collect_info.flypay_client import FlyPayClient

logger = logging.getLogger(__name__)


class QuestionnaireProcessor:
    """问卷数据处理器"""
    
    def __init__(
        self,
        feishu_client: FeishuClient,
        flypay_client: FlyPayClient,
        assignee_id: str,
        group_chat_id: str
    ):
        self.feishu = feishu_client
        self.flypay = flypay_client
        self.assignee_id = assignee_id
        self.group_chat_id = group_chat_id
    
    def calculate_trade_type(self, record_fields: Dict[str, Any]) -> str:
        """计算贸易类型"""
        trade_type = record_fields.get("贸易类型", "")
        service_subtype = record_fields.get("服务贸易子类型", "")
        goods_subtype = record_fields.get("货物贸易子类型", "")
        
        if not service_subtype and not goods_subtype:
            return trade_type
        
        if not service_subtype:
            return f"{trade_type}-{goods_subtype}"
        
        if not goods_subtype:
            return f"{trade_type}-{service_subtype}"
        
        return f"{trade_type}-{service_subtype}-{goods_subtype}"
    
    def _extract_field(self, fields: Dict[str, Any], field_name: str, key: str = 'text', default: str = "") -> str:
        """提取飞书多维表格字段值"""
        data = fields.get(field_name, [])
        if not data or not isinstance(data, list) or len(data) == 0:
            return default
        return data[0].get(key, default)
    
    async def process_record(self, record: Dict[str, Any], app_token: str, table_id: str) -> None:
        """处理单条记录"""
        fields = record.get("fields", {})
        record_id = record.get("record_id", "")
        
        # 提取字段
        person = self._extract_field(fields, "提交人", "name")
        email = self._extract_field(fields, "联系邮箱", "text")
        website = self._extract_field(fields, "接入网址", "text")
        payment_methods = self._extract_field(fields, "支付方式", "text")
        merchant_name = self._extract_field(fields, "企业名称", "text")
        integration_method = fields.get("接入类型", "")
        
        if not all([person, email, website]):
            logger.warning(f"记录 {record_id} 缺少必要字段，跳过")
            return
        
        # 计算贸易类型
        trade_type = self.calculate_trade_type(fields)
        
        # 创建FlyPay账号
        try:
            result = await self.flypay.create_merchant(
                id=record_id,
                person=person,
                email=email,
                website=website,
                trade_type=trade_type
            )
            
            # 提取商户ID
            merchant_id = self._extract_merchant_id(result)
            
            # 发送飞书消息
            await self.send_result_message(
                result=result,
                merchant_name=merchant_name,
                email=email,
                website=website,
                trade_type=trade_type,
                integration_type=integration_method,
                payment_methods=payment_methods,
                mid=merchant_id
            )
            
            # 创建任务
            await self.create_tasks(
                merchant_name=merchant_name,
                website=website,
                mid=merchant_id,
                payment_methods=payment_methods,
                integration_method=integration_method
            )
            
            # 更新记录状态和商户ID
            update_fields = {"流程执行状态": 1}
            if merchant_id:
                update_fields["MID"] = merchant_id
                
            await self.feishu.update_bitable_record(
                app_token=app_token,
                table_id=table_id,
                record_id=record_id,
                fields=update_fields
            )
            
            logger.info(f"成功处理记录 {record_id}，商户ID: {merchant_id}")
            
        except Exception as e:
            logger.error(f"处理记录 {record_id} 失败: {e}")
    
    def _extract_merchant_id(self, result: Dict[str, Any]) -> str:
        """从创建商户响应中提取商户ID"""
        try:
            data = result.get("data", "")
            if isinstance(data, str) and "MT" in data:
                # 从 "新增商户成功 MT200010000004777,123456@qq.com,..." 中提取商户ID
                parts = data.split(",")
                for part in parts:
                    if part.strip().startswith("MT"):
                        return part.strip()
                    # 处理 "新增商户成功 MT200010000004777" 的情况
                    if "MT" in part:
                        mt_index = part.find("MT")
                        return part[mt_index:].strip()
            return ""
        except Exception as e:
            logger.error(f"提取商户ID失败: {e}")
            return ""
    
    async def send_result_message(
        self,
        result: Dict[str, Any],
        merchant_name: str,
        email: str,
        website: str,
        trade_type: str,
        integration_type: str,
        payment_methods: str,
        mid: str
    ) -> None:
        """发送结果消息"""
        import json

        create_result = json.dumps(result, ensure_ascii=False, indent=2)

        message_text = f"""
商户名称:{merchant_name}
邮箱:{email}
网址:{website}
贸易类型:{trade_type}
接入类型:{integration_type}
支付方式:{payment_methods}
MID:{mid}
创建商户结果:{create_result}
"""

        content = json.dumps({
            "text": message_text
        })

        await self.feishu.send_message(
            receive_id=self.group_chat_id,
            msg_type="text",
            content=content,
            receive_id_type="chat_id"
        )

    
    async def create_tasks(
        self,
        merchant_name: str,
        website: str,
        mid: str,
        payment_methods: str,
        integration_method: str
    ) -> None:
        """创建飞书任务"""
        from app.support.collect_info.feishu_client import TaskRequest, TaskMember, TaskDue
        from app.support.collect_info.config import get_collect_info_settings
        import time
        
        # 任务1: 开通支付方式
        if payment_methods:
            member = TaskMember(id=self.assignee_id)
            due_time = TaskDue(timestamp=str(int((time.time() + 86400) * 1000)))
            
            description = f"""
商户名称:{merchant_name}
网址:{website}
MID:{mid}
需要开通以下支付方式：{payment_methods}
            """
            
            task_request = TaskRequest(
                summary=f"{website} - 开通支付方式",
                description=description,
                members=[member],
                due=due_time
            )
            await self.feishu.create_task(task_request)
            logger.info(f"已创建支付方式任务: {website}")
        
        # 任务2: ApplePay GooglePay域名备案
        if integration_method == "ApplePay GooglePay SDK":
            config = get_collect_info_settings()
            assignee_ids = config.get_filing_assignee_list()
            members = [TaskMember(id=assignee_id) for assignee_id in assignee_ids]
            due_time = TaskDue(timestamp=str(int((time.time() + 86400) * 1000)))
            
            description = f"""
商户名称:{merchant_name}
网址:{website}
MID:{mid}
接入类型:{integration_method}
需要备案测试环境ApplePay域名
网址:{website}
            """
            
            task_request = TaskRequest(
                summary=f"商户:{merchant_name} ApplePay 测试环境域名备案",
                description=description,
                members=members,
                due=due_time
            )
            await self.feishu.create_task(task_request)
            logger.info(f"已创建ApplePay GooglePay备案任务: {website}")
    
    async def process_all(self, app_token: str, table_id: str) -> None:
        """处理所有记录"""
        records = await self.feishu.get_bitable_records(app_token, table_id, filter_field="流程执行状态",
        filter_value=0)
        logger.info(f"获取到 {len(records)} 条记录")
        
        for record in records:
            await self.process_record(record, app_token, table_id)


# ==================== 测试脚本 ====================
async def test_process_all():
    """测试处理所有记录"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    print("=" * 50)
    print("开始测试问卷数据处理")
    print("=" * 50)
    
    # 初始化客户端
    feishu_client = FeishuClient(
        app_id=os.getenv("FEISHU_APP_ID"),
        app_secret=os.getenv("FEISHU_APP_SECRET")
    )
    
    flypay_client = FlyPayClient(
    )
    
    # 初始化处理器
    processor = QuestionnaireProcessor(
        feishu_client=feishu_client,
        flypay_client=flypay_client,
        assignee_id=os.getenv("FEISHU_ASSIGNEE_ID"),
        group_chat_id=os.getenv("FEISHU_GROUP_CHAT_ID")
    )
    
    # 获取配置
    app_token = os.getenv("FEISHU_BITABLE_APP_TOKEN")
    table_id = os.getenv("FEISHU_BITABLE_TABLE_ID")
    
    try:
        print(f"\n开始处理多维表格数据...")
        print(f"App Token: {app_token}")
        print(f"Table ID: {table_id}")
        
        await processor.process_all(app_token, table_id)
        print("✓ 处理完成")
        
    except Exception as e:
        print(f"✗ 处理失败: {e}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_process_all())