"""
任务数据仓库
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.task import Task

logger = logging.getLogger(__name__)

class TaskRepository:
    """任务数据仓库"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create(self, task: Task) -> str:
        """创建任务"""
        try:
            logger.info(f"Creating task: {task.id}")
            return task.id
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise
    
    async def get_by_id(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        try:
            logger.info(f"Getting task by ID: {task_id}")
            # 简化实现，返回模拟任务
            if task_id == "001":
                return Task(
                    id="001",
                    plan_id="plan_101",
                    name="新员工完成入职",
                    prompt="新员工入职",
                    status="Running",
                    context={"status": "Running", "values": {"employee_name": "张三"}},
                    created_at=None
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get task {task_id}: {e}")
            raise
    
    async def update(self, task_id: str, updates: Dict):
        """更新任务"""
        try:
            logger.info(f"Updating task: {task_id}")
        except Exception as e:
            logger.error(f"Failed to update task {task_id}: {e}")
            raise
    
    async def update_status(self, task_id: str, status: str, context: Dict):
        """更新任务状态"""
        try:
            logger.info(f"Updating task {task_id} status to {status}")
            # 实现状态更新逻辑
        except Exception as e:
            logger.error(f"Failed to update task {task_id} status: {e}")
            raise
    
    async def get_by_plan_id(self, plan_id: str) -> List[Task]:
        """根据计划ID获取任务列表"""
        try:
            logger.info(f"Getting tasks for plan: {plan_id}")
            # 简化实现，返回模拟任务列表
            if plan_id == "plan_101":
                return [
                    Task(
                        id="001",
                        plan_id="plan_101",
                        name="新员工完成入职",
                        prompt="新员工入职",
                        status="Running",
                        context={"status": "Running", "values": {"employee_name": "张三"}},
                        created_at=None
                    ),
                    Task(
                        id="002",
                        plan_id="plan_101",
                        name="新员工注册",
                        prompt="新员工在Hr系统中完成新员工注册",
                        status="NotStarted",
                        context={"status": "NotStarted", "values": {}},
                        created_at=None
                    )
                ]
            return []
        except Exception as e:
            logger.error(f"Failed to get tasks for plan {plan_id}: {e}")
            raise
    
    async def delete(self, task_id: str):
        """删除任务"""
        try:
            logger.info(f"Deleting task: {task_id}")
        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            raise
    
    async def search_by_status(self, status: str) -> List[Task]:
        """根据状态搜索任务"""
        try:
            logger.info(f"Searching tasks with status: {status}")
            return []
        except Exception as e:
            logger.error(f"Failed to search tasks by status {status}: {e}")
            raise
