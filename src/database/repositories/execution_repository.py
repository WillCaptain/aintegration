"""
执行记录数据仓库
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.execution import Execution

logger = logging.getLogger(__name__)

class ExecutionRepository:
    """执行记录数据仓库"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create(self, execution: Execution) -> str:
        """创建执行记录"""
        try:
            logger.info(f"Creating execution: {execution.id}")
            return execution.id
        except Exception as e:
            logger.error(f"Failed to create execution: {e}")
            raise
    
    async def get_by_id(self, execution_id: str) -> Optional[Execution]:
        """根据ID获取执行记录"""
        try:
            logger.info(f"Getting execution by ID: {execution_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get execution {execution_id}: {e}")
            raise
    
    async def update(self, execution_id: str, updates: Dict):
        """更新执行记录"""
        try:
            logger.info(f"Updating execution: {execution_id}")
        except Exception as e:
            logger.error(f"Failed to update execution {execution_id}: {e}")
            raise
    
    async def update_status(self, execution_id: str, status: str, error_message: Optional[str] = None):
        """更新执行状态"""
        try:
            logger.info(f"Updating execution {execution_id} status to {status}")
            updates = {"status": status}
            if error_message:
                updates["error_message"] = error_message
            await self.update(execution_id, updates)
        except Exception as e:
            logger.error(f"Failed to update execution {execution_id} status: {e}")
            raise
    
    async def add_log_entry(self, execution_id: str, event: str, details: Dict, task_id: Optional[str] = None):
        """添加执行日志条目"""
        try:
            logger.info(f"Adding log entry to execution {execution_id}: {event}")
            # 实现日志添加逻辑
        except Exception as e:
            logger.error(f"Failed to add log entry to execution {execution_id}: {e}")
            raise
    
    async def get_by_status(self, status: str) -> List[Execution]:
        """根据状态获取执行记录"""
        try:
            logger.info(f"Getting executions with status: {status}")
            return []
        except Exception as e:
            logger.error(f"Failed to get executions by status {status}: {e}")
            raise
    
    async def get_by_plan_id(self, plan_id: str) -> List[Execution]:
        """根据计划ID获取执行记录"""
        try:
            logger.info(f"Getting executions for plan: {plan_id}")
            return []
        except Exception as e:
            logger.error(f"Failed to get executions for plan {plan_id}: {e}")
            raise
    
    async def list_recent(self, limit: int = 100, offset: int = 0) -> List[Execution]:
        """获取最近的执行记录"""
        try:
            logger.info(f"Listing recent executions with limit={limit}, offset={offset}")
            return []
        except Exception as e:
            logger.error(f"Failed to list recent executions: {e}")
            raise
    
    async def delete(self, execution_id: str):
        """删除执行记录"""
        try:
            logger.info(f"Deleting execution: {execution_id}")
        except Exception as e:
            logger.error(f"Failed to delete execution {execution_id}: {e}")
            raise
