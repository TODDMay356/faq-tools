"""
数据库使用示例
"""
from app.utils.database import db_manager, DatabaseType


def example_usage():
    """数据库使用示例"""
    
    # 1. 执行查询返回列表
    users = db_manager.execute_query(
        "SELECT * FROM users WHERE age > %s", 
        (18,),
        db_name=DatabaseType.USER
    )
    print(f"查询到 {len(users)} 个用户")
    
    # 2. 查询单条记录
    user = db_manager.execute_one(
        "SELECT * FROM users WHERE id = %s", 
        (1,),
        db_name=DatabaseType.USER
    )
    if user:
        print(f"用户: {user['name']}")
    
    # 3. 读取整个表
    all_orders = db_manager.get_table_data("payment_orders", db_name=DatabaseType.PAYMENT)
    print(f"表中共有 {len(all_orders)} 条记录")
    
    # 4. 带条件读取表
    active_users = db_manager.get_table_data(
        "users", 
        "status = %s AND created_at > %s",
        ('active', '2024-01-01'),
        db_name=DatabaseType.USER
    )
    
    # 5. 获取记录数
    count = db_manager.get_table_count(
        "users", 
        "status = %s", 
        ('active',),
        db_name=DatabaseType.USER
    )
    print(f"活跃用户数: {count}")
    
    # 6. 执行更新
    affected_rows = db_manager.execute_update(
        "UPDATE users SET last_login = NOW() WHERE id = %s",
        (1,),
        db_name=DatabaseType.USER
    )
    print(f"更新了 {affected_rows} 行")
    
    # 7. 记录日志
    db_manager.execute_update(
        "INSERT INTO operation_logs (user_id, operation, created_at) VALUES (%s, %s, NOW())",
        (1, 'login'),
        db_name=DatabaseType.LOG
    )


if __name__ == "__main__":
    example_usage()