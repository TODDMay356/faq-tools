"""
多数据库服务示例
演示如何在实际业务中使用多数据库配置
"""
from typing import List, Dict, Any, Optional
from app.utils.database import db_manager, DatabaseType
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    """支付服务 - 使用payment数据库"""
    
    @staticmethod
    def get_payment_orders(merchant_id: int, status: str = None) -> List[Dict[str, Any]]:
        """获取支付订单"""
        conditions = "merchant_id = %s"
        params = [merchant_id]
        
        if status:
            conditions += " AND status = %s"
            params.append(status)
        
        return db_manager.get_table_data(
            "payment_orders", 
            conditions, 
            tuple(params),
            db_name=DatabaseType.PAYMENT
        )
    
    @staticmethod
    def create_payment_order(order_data: Dict[str, Any]) -> int:
        """创建支付订单"""
        sql = """
        INSERT INTO payment_orders (merchant_id, order_no, amount, currency, status, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        """
        params = (
            order_data['merchant_id'],
            order_data['order_no'],
            order_data['amount'],
            order_data['currency'],
            order_data['status']
        )
        
        return db_manager.execute_update(sql, params, db_name=DatabaseType.PAYMENT)
    
    @staticmethod
    def get_payment_statistics(merchant_id: int) -> Dict[str, Any]:
        """获取支付统计"""
        sql = """
        SELECT 
            COUNT(*) as total_orders,
            SUM(CASE WHEN status = 'success' THEN amount ELSE 0 END) as success_amount,
            COUNT(CASE WHEN status = 'success' THEN 1 END) as success_count,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count
        FROM payment_orders 
        WHERE merchant_id = %s
        """
        
        result = db_manager.execute_one(sql, (merchant_id,), db_name=DatabaseType.PAYMENT)
        return result or {}


class UserService:
    """用户服务 - 使用user数据库"""
    
    @staticmethod
    def get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        return db_manager.execute_one(
            "SELECT * FROM users WHERE id = %s",
            (user_id,),
            db_name=DatabaseType.USER
        )
    
    @staticmethod
    def get_merchant_users(merchant_id: int) -> List[Dict[str, Any]]:
        """获取商户用户列表"""
        return db_manager.execute_query(
            "SELECT * FROM users WHERE merchant_id = %s AND status = 'active'",
            (merchant_id,),
            db_name=DatabaseType.USER
        )
    
    @staticmethod
    def update_user_login_time(user_id: int) -> int:
        """更新用户登录时间"""
        sql = "UPDATE users SET last_login = NOW() WHERE id = %s"
        return db_manager.execute_update(sql, (user_id,), db_name=DatabaseType.USER)


class LogService:
    """日志服务 - 使用log数据库"""
    
    @staticmethod
    def log_operation(user_id: int, operation: str, details: str) -> int:
        """记录操作日志"""
        sql = """
        INSERT INTO operation_logs (user_id, operation, details, created_at)
        VALUES (%s, %s, %s, NOW())
        """
        return db_manager.execute_update(
            sql, 
            (user_id, operation, details),
            db_name=DatabaseType.LOG
        )
    
    @staticmethod
    def get_user_logs(user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户操作日志"""
        sql = """
        SELECT * FROM operation_logs 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
        """
        return db_manager.execute_query(sql, (user_id, limit), db_name=DatabaseType.LOG)
    
    @staticmethod
    def get_system_logs(start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取系统日志"""
        sql = """
        SELECT * FROM system_logs 
        WHERE created_at BETWEEN %s AND %s 
        ORDER BY created_at DESC
        """
        return db_manager.execute_query(sql, (start_date, end_date), db_name=DatabaseType.LOG)


class BusinessService:
    """业务服务 - 跨数据库操作示例"""
    
    @staticmethod
    def get_user_payment_summary(user_id: int) -> Dict[str, Any]:
        """获取用户支付汇总 - 跨数据库查询"""
        # 从用户数据库获取用户信息
        user_info = UserService.get_user_info(user_id)
        if not user_info:
            return {}
        
        # 从支付数据库获取支付统计
        payment_stats = PaymentService.get_payment_statistics(user_info['merchant_id'])
        
        # 从日志数据库获取最近操作
        recent_logs = LogService.get_user_logs(user_id, 10)
        
        return {
            'user_info': user_info,
            'payment_stats': payment_stats,
            'recent_logs': recent_logs
        }
    
    @staticmethod
    def process_payment_with_log(order_data: Dict[str, Any], user_id: int) -> bool:
        """处理支付并记录日志 - 跨数据库事务示例"""
        try:
            # 创建支付订单
            result = PaymentService.create_payment_order(order_data)
            
            # 记录操作日志
            LogService.log_operation(
                user_id, 
                'create_payment_order',
                f"Created order: {order_data['order_no']}"
            )
            
            # 更新用户最后活动时间
            UserService.update_user_login_time(user_id)
            
            logger.info(f"支付订单创建成功: {order_data['order_no']}")
            return True
            
        except Exception as e:
            logger.error(f"支付订单创建失败: {e}")
            # 记录错误日志
            LogService.log_operation(
                user_id,
                'create_payment_order_failed', 
                f"Failed to create order: {str(e)}"
            )
            return False