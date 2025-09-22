"""
侦听器数据仓库
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.listener import Listener

logger = logging.getLogger(__name__)

class ListenerRepository:
    """侦听器数据仓库"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create(self, listener: Listener) -> str:
        """创建侦听器"""
        try:
            logger.info(f"Creating listener: {listener.id}")
            return listener.id
        except Exception as e:
            logger.error(f"Failed to create listener: {e}")
            raise
    
    async def get_by_id(self, listener_id: str) -> Optional[Listener]:
        """根据ID获取侦听器"""
        try:
            logger.info(f"Getting listener by ID: {listener_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to get listener {listener_id}: {e}")
            raise
    
    async def get_by_trigger_task(self, task_id: str) -> List[Listener]:
        """获取监听特定任务的侦听器"""
        try:
            logger.info(f"Getting listeners for trigger task: {task_id}")
            return []
        except Exception as e:
            logger.error(f"Failed to get listeners for trigger task {task_id}: {e}")
            raise
    
    async def get_by_trigger(self, task_id: str, status: str) -> List[Listener]:
        """获取特定触发条件的侦听器"""
        try:
            logger.info(f"Getting listeners for trigger: task={task_id}, status={status}")
            # 简化实现，返回模拟侦听器
            if task_id == "001" and status == "Running":
                return [
                    Listener(
                        id="L001",
                        plan_id="plan_101",
                        trigger_task_id="001",
                        trigger_condition="001.status == Running",
                        action_condition="true",
                        agent_id="HrAgent",
                        action_prompt="根据员工的身份证号、姓名信息在HR系统中创建员工记录，输入001的上下文",
                        success_output={"task_id": "002", "status": "Done", "context": {"emp_id": "xxx", "level": "xxx"}},
                        failure_output={"task_id": "002", "status": "Error", "context": {"error": "HR系统连接失败"}}
                    ),
                    Listener(
                        id="L002",
                        plan_id="plan_101",
                        trigger_task_id="001",
                        trigger_condition="001.status == Running",
                        action_condition="true",
                        agent_id="AccessAgent",
                        action_prompt="根据员工ID为新员工申请门禁权限，输入001的上下文",
                        success_output={"task_id": "005", "status": "Done", "context": {"access_id": "xxx"}},
                        failure_output={"task_id": "005", "status": "Error", "context": {"error": "门禁系统异常"}}
                    )
                ]
            return []
        except Exception as e:
            logger.error(f"Failed to get listeners for trigger {task_id}/{status}: {e}")
            raise
    
    async def get_by_plan_id(self, plan_id: str) -> List[Listener]:
        """根据计划ID获取侦听器列表"""
        try:
            logger.info(f"Getting listeners for plan: {plan_id}")
            return []
        except Exception as e:
            logger.error(f"Failed to get listeners for plan {plan_id}: {e}")
            raise
    
    async def update(self, listener_id: str, updates: Dict):
        """更新侦听器"""
        try:
            logger.info(f"Updating listener: {listener_id}")
        except Exception as e:
            logger.error(f"Failed to update listener {listener_id}: {e}")
            raise
    
    async def delete(self, listener_id: str):
        """删除侦听器"""
        try:
            logger.info(f"Deleting listener: {listener_id}")
        except Exception as e:
            logger.error(f"Failed to delete listener {listener_id}: {e}")
            raise
