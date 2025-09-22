"""
数据库连接管理
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

logger = logging.getLogger(__name__)

Base = declarative_base()
metadata = MetaData()

class DatabaseConnection:
    """数据库连接管理器"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
        self._initialize()
    
    def _initialize(self):
        """初始化数据库连接"""
        try:
            # 创建异步引擎
            self.engine = create_async_engine(
                self.database_url,
                echo=False,  # 设置为True可以看到SQL语句
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            # 创建会话工厂
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("Database connection initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    async def create_session(self) -> AsyncSession:
        """创建数据库会话"""
        return self.session_factory()
    
    async def close(self):
        """关闭数据库连接"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")
    
    async def create_tables(self):
        """创建数据库表"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    async def drop_tables(self):
        """删除数据库表"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
