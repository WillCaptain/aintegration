"""
实例仓库实现

管理计划实例和任务实例的存储
"""

import logging
from typing import Dict, List, Optional, Any
import copy
from datetime import datetime
from collections import defaultdict

from ..models.plan_instance import PlanInstance
from ..models.task_instance import TaskInstance

logger = logging.getLogger(__name__)

class MemoryPlanInstanceRepository:
    """内存版本的计划实例仓库"""
    
    def __init__(self):
        self.instances = {}
        self.next_id = 1
    
    async def create(self, instance: PlanInstance) -> str:
        """创建计划实例"""
        try:
            instance_id = instance.id or f"inst_{self.next_id:06d}"
            self.next_id += 1
            
            instance.id = instance_id
            if instance.created_at is None:
                instance.created_at = datetime.now()
            self.instances[instance_id] = instance
            
            logger.info(f"Memory: Created plan instance {instance_id}")
            return instance_id
        except Exception as e:
            logger.error(f"Memory: Failed to create plan instance: {e}")
            raise
    
    async def get_by_id(self, instance_id: str) -> Optional[PlanInstance]:
        """根据ID获取计划实例"""
        try:
            return self.instances.get(instance_id)
        except Exception as e:
            logger.error(f"Memory: Failed to get plan instance {instance_id}: {e}")
            raise
    
    async def update(self, instance_id: str, updates: Dict):
        """更新计划实例"""
        try:
            if instance_id in self.instances:
                instance = self.instances[instance_id]
                for key, value in updates.items():
                    if hasattr(instance, key):
                        setattr(instance, key, value)
                instance.updated_at = datetime.now()
                logger.info(f"Memory: Updated plan instance {instance_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to update plan instance {instance_id}: {e}")
            raise
    
    async def get_by_plan_id(self, plan_id: str) -> List[PlanInstance]:
        """根据计划ID获取所有实例"""
        try:
            return [inst for inst in self.instances.values() if inst.plan_id == plan_id]
        except Exception as e:
            logger.error(f"Memory: Failed to get instances for plan {plan_id}: {e}")
            raise
    
    async def delete(self, instance_id: str):
        """删除计划实例"""
        try:
            if instance_id in self.instances:
                del self.instances[instance_id]
                logger.info(f"Memory: Deleted plan instance {instance_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to delete plan instance {instance_id}: {e}")
            raise

class MemoryTaskInstanceRepository:
    """内存版本的任务实例仓库"""
    
    def __init__(self):
        self.instances = {}
        self.next_id = 1
    
    async def create(self, instance: TaskInstance) -> str:
        """创建任务实例"""
        try:
            instance_id = instance.id or f"task_inst_{self.next_id:06d}"
            self.next_id += 1
            
            instance.id = instance_id
            self.instances[instance_id] = instance
            
            logger.info(f"Memory: Created task instance {instance_id}")
            return instance_id
        except Exception as e:
            logger.error(f"Memory: Failed to create task instance: {e}")
            raise
    
    async def get_by_id(self, instance_id: str) -> Optional[TaskInstance]:
        """根据ID获取任务实例"""
        try:
            return self.instances.get(instance_id)
        except Exception as e:
            logger.error(f"Memory: Failed to get task instance {instance_id}: {e}")
            raise
    
    async def get_by_plan_instance_id(self, plan_instance_id: str) -> List[TaskInstance]:
        """根据计划实例ID获取所有任务实例"""
        try:
            return [inst for inst in self.instances.values() if inst.plan_instance_id == plan_instance_id]
        except Exception as e:
            logger.error(f"Memory: Failed to get task instances for plan instance {plan_instance_id}: {e}")
            raise
    
    async def get_by_plan_instance_and_task_id(self, plan_instance_id: str, task_id: str) -> Optional[TaskInstance]:
        """根据计划实例ID和任务ID获取任务实例"""
        try:
            for inst in self.instances.values():
                if inst.plan_instance_id == plan_instance_id and inst.task_id == task_id:
                    return inst
            return None
        except Exception as e:
            logger.error(f"Memory: Failed to get task instance {plan_instance_id}/{task_id}: {e}")
            raise
    
    async def update(self, instance_id: str, updates: Dict):
        """更新任务实例"""
        try:
            if instance_id in self.instances:
                instance = self.instances[instance_id]
                for key, value in updates.items():
                    if hasattr(instance, key):
                        setattr(instance, key, value)
                instance.updated_at = datetime.now()
                logger.info(f"Memory: Updated task instance {instance_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to update task instance {instance_id}: {e}")
            raise
    
    async def update_status(self, instance_id: str, status: str, context: Dict):
        """更新任务实例状态"""
        try:
            if instance_id in self.instances:
                instance = self.instances[instance_id]
                # 合并上下文，保留既有键（如 retry_info），仅更新 values 子项
                existing_ctx = instance.context if isinstance(instance.context, dict) else {}
                values_ctx = existing_ctx.get("values", {})
                # 传入的 context 视为 values 的增量更新
                if isinstance(context, dict):
                    values_ctx.update(context)
                existing_ctx["values"] = values_ctx
                # 同步记录当前状态（保持兼容，很多测试依赖 context.status）
                existing_ctx["status"] = status

                instance.status = status
                instance.context = existing_ctx
                instance.updated_at = datetime.now()
                logger.info(f"Memory: Updated task instance {instance_id} status to {status}")
        except Exception as e:
            logger.error(f"Memory: Failed to update task instance {instance_id} status: {e}")
            raise
    
    async def delete(self, instance_id: str):
        """删除任务实例"""
        try:
            if instance_id in self.instances:
                del self.instances[instance_id]
                logger.info(f"Memory: Deleted task instance {instance_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to delete task instance {instance_id}: {e}")
            raise
