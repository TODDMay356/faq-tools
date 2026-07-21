import sys
import os
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager

# 设置 HuggingFace 镜像（必须在任何导入之前）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_ENDPOINT"] = "https://hf-mirror.com"

# 添加项目根目录到Python路径
if __name__ == "__main__":
    root_dir = Path(__file__).parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

from fastapi import FastAPI, BackgroundTasks
from app.api.api import api_router
from app.api.wechat import router as wechat_router
from app.api.wechat_robot import router as wechat_router_robot
from app.api.wechat_robot import router as wechat_robot_router
from app.support.collect_info.config import get_collect_info_settings
from app.support.collect_info.scheduler import CollectInfoScheduler, FilingScheduler, TradeSuccessScheduler
from app.support.msg_transfer.long_connection import FeishuLongConnectionClient
from app.support.msg_transfer.config import get_msg_transfer_settings
from app.support.msg_transfer.scheduler import MsgTransferScheduler
import logging

# 基础日志配置（INFO 级别，输出时间、级别、模块与消息）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# 全局调度器实例
scheduler = None
filing_scheduler = None
trade_success_scheduler = None
msg_transfer_scheduler = None
msg_transfer_long_conn = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global scheduler, filing_scheduler, trade_success_scheduler, msg_transfer_scheduler, msg_transfer_long_conn
    
    # 启动时初始化调度器
    try:
        config = get_collect_info_settings()
        if config.is_configured():
            scheduler = CollectInfoScheduler(
                feishu_app_id=config.feishu_app_id,
                feishu_app_secret=config.feishu_app_secret,
                bitable_app_token=config.feishu_bitable_app_token,
                bitable_table_id=config.feishu_bitable_table_id,
                assignee_id=config.feishu_assignee_id,
                message_receive_id=config.feishu_group_chat_id,
                interval_seconds=config.collect_info_interval
            )
            asyncio.create_task(scheduler.start())
            logging.info("问卷收集调度器已启动")
        else:
            logging.info("问卷收集配置不完整，跳过启动调度器")

        # 备案任务调度器
        if config.is_filing_configured():
            filing_scheduler = FilingScheduler(
                feishu_app_id=config.feishu_app_id,
                feishu_app_secret=config.feishu_app_secret,
                filing_token=config.filing_token,
                filing_table_id=config.filing_table_id,
                assignee_ids=config.get_filing_assignee_list(),
                interval_seconds=config.filing_interval
            )
            asyncio.create_task(filing_scheduler.start())
            logging.info("备案任务调度器已启动")
        
        # 交易成功通知调度器
        if config.is_trade_success_configured():
            trade_success_scheduler = TradeSuccessScheduler(
                feishu_app_id=config.feishu_app_id,
                feishu_app_secret=config.feishu_app_secret,
                app_token=config.feishu_bitable_app_token,
                table_id=config.feishu_bitable_table_id,
                group_chat_id=config.feishu_group_chat_id,
                interval_seconds=config.trade_success_interval
            )
            asyncio.create_task(trade_success_scheduler.start())
            logging.info("交易成功通知调度器已启动")

        # 消息转发调度器
        msg_transfer_settings = get_msg_transfer_settings()
        msg_transfer_scheduler = MsgTransferScheduler.from_settings()
        if msg_transfer_scheduler:
            app.state.msg_transfer_scheduler = msg_transfer_scheduler
            asyncio.create_task(msg_transfer_scheduler.start())
            logging.info("消息转发调度器已启动")
        else:
            app.state.msg_transfer_scheduler = None
            logging.info("消息转发业务配置不完整，跳过转发调度器")

        # 长连接客户端：只要有消息转发专用 app_id/app_secret 就启动，便于飞书后台验证连接
        if msg_transfer_settings.has_long_connection_credentials():
            msg_transfer_long_conn = FeishuLongConnectionClient(
                app_id=msg_transfer_settings.feishu_app_id,
                app_secret=msg_transfer_settings.feishu_app_secret,
                scheduler=msg_transfer_scheduler,
            )
            msg_transfer_long_conn.start(asyncio.get_running_loop())
            logging.info("消息转发飞书长连接已启动")
        else:
            logging.info("消息转发长连接凭证缺失，跳过长连接启动")

    except Exception as e:
        logging.error(f"启动调度器失败: {e}")
    
    yield
    
    # 关闭时停止调度器
    if scheduler:
        scheduler.stop()
        logging.info("问卷收集调度器已停止")
    if filing_scheduler:
        filing_scheduler.stop()
        logging.info("备案任务调度器已停止")
    if trade_success_scheduler:
        trade_success_scheduler.stop()
        logging.info("交易成功通知调度器已停止")
    if msg_transfer_scheduler:
        msg_transfer_scheduler.stop()
        logging.info("消息转发调度器已停止")
    app.state.msg_transfer_scheduler = None


app = FastAPI(title="FAQ 问答系统", lifespan=lifespan)

app.include_router(api_router, prefix="/api/v1")
app.include_router(wechat_router, prefix="/api/wechat")
app.include_router(wechat_router_robot, prefix="/api/wechat")
app.include_router(wechat_robot_router, prefix="/api")


@app.get("/")
async def root():
    """
    应用程序的根节点。
    """
    return {"message": "欢迎来到 FAQ 问答系统!"}


@app.post("/api/collect-info/trigger")
async def trigger_collect_info():
    """
    手动触发问卷信息收集
    """
    global scheduler
    if scheduler:
        await scheduler.run_once()
        return {"message": "问卷信息收集已触发"}
    else:
        return {"error": "调度器未初始化"}, 500


@app.get("/api/collect-info/status")
async def collect_info_status():
    """
    获取问卷收集调度器状态
    """
    global scheduler
    if scheduler:
        return {
            "running": scheduler.running,
            "interval": scheduler.interval
        }
    else:
        return {"error": "调度器未初始化"}, 500


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
