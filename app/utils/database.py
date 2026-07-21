"""
数据库连接管理工具
支持多数据库配置和连接池管理
"""
import logging
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
from enum import Enum
import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB
from app.core.config import settings


class DatabaseType(Enum):
    """数据库类型枚举"""
    DEFAULT = 'default'
    PAYMENT = 'payment'
    USER = 'user'
    LOG = 'log'

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库连接管理器"""
    
    def __init__(self):
        self._pools: Dict[str, PooledDB] = {}
        self._init_pools()
    
    def _init_pools(self):
        """初始化数据库连接池"""
        # 从配置中读取数据库配置
        db_configs = getattr(settings, 'DATABASES', {})
        
        for db_name, config in db_configs.items():
            try:
                pool = PooledDB(
                    creator=pymysql,
                    maxconnections=config.get('max_connections', 20),
                    mincached=config.get('min_cached', 2),
                    maxcached=config.get('max_cached', 5),
                    maxshared=config.get('max_shared', 3),
                    blocking=True,
                    maxusage=None,
                    setsession=[],
                    ping=0,
                    host=config['host'],
                    port=config.get('port', 3306),
                    user=config['user'],
                    password=config['password'],
                    database=config['database'],
                    charset=config.get('charset', 'utf8mb4'),
                    cursorclass=DictCursor
                )
                self._pools[db_name] = pool
                logger.info(f"数据库连接池 {db_name} 初始化成功")
            except Exception as e:
                logger.error(f"数据库连接池 {db_name} 初始化失败: {e}")
    
    @contextmanager
    def get_connection(self, db_name: DatabaseType = DatabaseType.DEFAULT):
        """获取数据库连接上下文管理器"""
        db_key = db_name.value if isinstance(db_name, DatabaseType) else db_name
        
        if db_key not in self._pools:
            raise ValueError(f"数据库配置 {db_key} 不存在")
        
        conn = None
        try:
            conn = self._pools[db_key].connection()
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"数据库操作错误: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, sql: str, params: tuple = None, db_name: DatabaseType = DatabaseType.DEFAULT) -> List[Dict[str, Any]]:
        """执行查询SQL，返回结果列表"""
        with self.get_connection(db_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
    
    def execute_one(self, sql: str, params: tuple = None, db_name: DatabaseType = DatabaseType.DEFAULT) -> Optional[Dict[str, Any]]:
        """执行查询SQL，返回单条结果"""
        with self.get_connection(db_name) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
    
    def execute_update(self, sql: str, params: tuple = None, db_name: DatabaseType = DatabaseType.DEFAULT) -> int:
        """执行更新SQL，返回影响行数"""
        with self.get_connection(db_name) as conn:
            with conn.cursor() as cursor:
                result = cursor.execute(sql, params)
                conn.commit()
                return result
    
    def get_table_data(self, table_name: str, conditions: str = None, 
                      params: tuple = None, db_name: DatabaseType = DatabaseType.DEFAULT) -> List[Dict[str, Any]]:
        """读取表数据"""
        sql = f"SELECT * FROM {table_name}"
        if conditions:
            sql += f" WHERE {conditions}"
        
        return self.execute_query(sql, params, db_name)
    
    def get_table_count(self, table_name: str, conditions: str = None, 
                       params: tuple = None, db_name: DatabaseType = DatabaseType.DEFAULT) -> int:
        """获取表记录数"""
        sql = f"SELECT COUNT(*) as count FROM {table_name}"
        if conditions:
            sql += f" WHERE {conditions}"
        
        result = self.execute_one(sql, params, db_name)
        return result['count'] if result else 0


# 全局数据库管理器实例
db_manager = DatabaseManager()