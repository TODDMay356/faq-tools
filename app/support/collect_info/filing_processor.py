"""备案任务处理器"""
from typing import Dict, Any, List
import logging
import time

from app.support.collect_info.feishu_client import FeishuClient, TaskRequest, TaskMember, TaskDue

logger = logging.getLogger(__name__)


class FilingProcessor:
    """备案任务处理器"""
    
    def __init__(
        self,
        feishu_client: FeishuClient,
        assignee_ids: List[str],
        app_token: str,
        table_id: str
    ):
        self.feishu = feishu_client
        self.assignee_ids = assignee_ids
        self.app_token = app_token
        self.table_id = table_id
    
    def _extract_field(self, fields: Dict[str, Any], field_name: str, key: str = 'text', default: str = "") -> str:
        """提取飞书多维表格字段值"""
        data = fields.get(field_name, [])
        if not data or not isinstance(data, list) or len(data) == 0:
            return default
        return data[0].get(key, default)
    
    def _extract_multi_select_field(self, fields: Dict[str, Any], field_name: str) -> List[str]:
        """提取多选字段值"""
        data = fields.get(field_name, [])
        return data
    
    def _extract_file_field(self, fields: Dict[str, Any], field_name: str) -> List[Dict[str, str]]:
        """提取文件字段值"""
        data = fields.get(field_name, [])
        if not data or not isinstance(data, list):
            return []
        
        files = []
        for item in data:
            file_info = {
                'name': item.get('name', ''),
                'file_token': item.get('file_token', ''),
                'size': item.get('size', 0),
                'type': item.get('type', ''),
                'url': item.get('url', ''),
                'tmp_url': item.get('tmp_url', '')
            }
            files.append(file_info)
        return files
    
    async def process_record(self, record: Dict[str, Any]) -> None:
        """处理单条记录"""
        fields = record.get("fields", {})
        record_id = record.get("record_id", "")
        
        # 提取字段
        website = self._extract_field(fields, "生产网址")
        merchant_group = self._extract_field(fields, "商户群名称")
        filing_types = self._extract_multi_select_field(fields, "备案类型")
        google_pay_files = self._extract_file_field(fields, "谷歌Pay截图")
        
        if not all([website, merchant_group, filing_types]):
            logger.warning(f"记录 {record_id} 缺少必要字段，跳过")
            return
        
        # 创建飞书任务
        try:
            await self.create_filing_task(
                merchant_group=merchant_group,
                filing_types=filing_types,
                google_pay_files=google_pay_files,
                website=website
            )
            
            # 更新记录状态
            await self.feishu.update_bitable_record(
                app_token=self.app_token,
                table_id=self.table_id,
                record_id=record_id,
                fields={"流程执行状态": 1}
            )
            
            logger.info(f"成功处理记录 {record_id}，商户群: {merchant_group}")
            
        except Exception as e:
            logger.error(f"处理记录 {record_id} 失败: {e}")
    
    async def create_filing_task(
        self,
        merchant_group: str,
        filing_types: List[str],
        google_pay_files: List[Dict[str, str]],
        website: str
    ) -> None:
        """创建备案任务"""
        # 构建任务描述
        filing_types_str = "、".join(filing_types)
        description_parts = [
            f"商户群名称：{merchant_group}",
            f"备案类型：{filing_types_str}",
            f"生产网址：{website}",
            "申请备案网址"
        ]
        
        # 添加文件信息
        if google_pay_files:
            description_parts.append("\n需要上传的文件：")
            for file_info in google_pay_files:
                description_parts.append(f"- {file_info['name']} ({file_info.get('size', 0)} bytes)")
        
        description = "\n".join(description_parts)
        
        # 创建任务成员列表
        members = [TaskMember(id=assignee_id) for assignee_id in self.assignee_ids]
        
        # 创建截止时间（一天后）
        due_time = TaskDue(
            timestamp=str(int((time.time() + 86400) * 1000))
        )
        
        # 创建任务请求
        task_request = TaskRequest(
            summary=f"{merchant_group} - 备案类型：{filing_types_str}",
            description=description,
            members=members,
            due=due_time
        )
        
        result = await self.feishu.create_task(task_request)
        logger.info(f"创建任务响应类型: {type(result)}")
        logger.info(f"创建任务响应内容: {result}")
        task_guid = result.get("task").get('guid') if result.get("task") else None
        logger.info(f"提取的GUID: {task_guid}")
        logger.info(f"已创建备案任务: {merchant_group}, 任务GUID: {task_guid}")
        
        # 下载并上传文件到任务附件
        if google_pay_files and task_guid:
            await self.upload_files_to_task(task_guid, google_pay_files)
        elif google_pay_files and not task_guid:
            logger.error(f"任务创建成功但未获取到GUID，无法上传文件")
    
    async def upload_files_to_task(self, task_guid: str, files: List[Dict[str, str]]) -> None:
        """下载文件并上传到任务附件"""
        for file_info in files:
            try:
                file_token = file_info.get('file_token')
                file_name = file_info.get('name')
                
                if not file_token or not file_name:
                    logger.warning(f"文件信息不完整，跳过: {file_info}")
                    continue
                
                # 下载文件
                logger.info(f"下载文件: {file_name}")
                file_content = await self.feishu.download_file(file_token)
                
                # 上传到任务附件
                logger.info(f"上传文件到任务: {file_name}")
                await self.feishu.upload_file_to_task(task_guid, file_name, file_content)
                logger.info(f"文件上传成功: {file_name}")
                
            except Exception as e:
                logger.error(f"处理文件失败 {file_info.get('name', 'unknown')}: {e}")
    
    async def process_all(self) -> None:
        """处理所有流程执行状态=0的记录"""
        records = await self.feishu.get_bitable_records(
            app_token=self.app_token,
            table_id=self.table_id,
            filter_field="流程执行状态",
            filter_value=0
        )
        logger.info(f"获取到 {len(records)} 条待处理记录")
        
        for record in records:
            await self.process_record(record)
