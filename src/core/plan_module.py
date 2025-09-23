"""
计划模块

负责Plan和Task的持久化管理
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from ..models.plan import Plan
from ..models.task import Task
from ..models.listener import Listener
from ..database.memory_repositories import MemoryPlanRepository, MemoryTaskRepository, MemoryListenerRepository

logger = logging.getLogger(__name__)

class PlanManager:
    """计划管理器"""
    
    def __init__(self, plan_repo: MemoryPlanRepository):
        self.plan_repo = plan_repo
    
    async def create_plan(self, plan_config: Dict) -> str:
        """创建新的执行计划"""
        try:
            plan = Plan(
                id=plan_config.get("plan_id"),
                name=plan_config.get("name"),
                description=plan_config.get("prompt"),
                config=plan_config,
                created_at=datetime.now()
            )
            
            plan_id = await self.plan_repo.create(plan)
            logger.info(f"Created plan {plan_id}")
            return plan_id
            
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            raise
    
    async def update_plan(self, plan_id: str, updates: Dict):
        """更新计划配置"""
        try:
            await self.plan_repo.update(plan_id, updates)
            logger.info(f"Updated plan {plan_id}")
        except Exception as e:
            logger.error(f"Failed to update plan {plan_id}: {e}")
            raise
    
    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """获取计划详情"""
        return await self.plan_repo.get_by_id(plan_id)
    
    async def search_plans(self, criteria: Dict) -> List[Plan]:
        """搜索匹配的计划"""
        return await self.plan_repo.search(criteria)
    
    async def get_few_shot_examples(self) -> List[Dict]:
        """获取Few-shot学习示例"""
        # 从数据库或配置文件获取示例
        examples = await self.plan_repo.get_few_shot_examples()
        return examples

class TaskManager:
    """任务管理器"""
    
    def __init__(self, task_repo: MemoryTaskRepository):
        self.task_repo = task_repo
    
    async def create_task(self, task_config: Dict) -> str:
        """创建任务"""
        try:
            task = Task(
                id=task_config.get("task_id"),
                plan_id=task_config.get("plan_id"),
                name=task_config.get("name"),
                prompt=task_config.get("prompt"),
                status="NotStarted",
                context={"status": "NotStarted", "values": {}},
                created_at=datetime.now()
            )
            
            task_id = await self.task_repo.create(task)
            logger.info(f"Created task {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取单个任务"""
        return await self.task_repo.get_by_id(task_id)
    
    async def get_plan_tasks(self, plan_id: str) -> List[Task]:
        """获取计划的所有任务"""
        return await self.task_repo.get_by_plan_id(plan_id)
    
    async def get_task_context(self, task_id: str) -> Dict:
        """获取任务上下文"""
        task = await self.get_task(task_id)
        return task.context if task else {}

class ListenerManager:
    """侦听器管理器"""
    
    def __init__(self, listener_repo: MemoryListenerRepository):
        self.listener_repo = listener_repo
    
    async def create_listener(self, listener_config: Dict) -> str:
        """创建侦听器"""
        try:
            listener = Listener(
                id=listener_config.get("listener_id"),
                plan_id=listener_config.get("plan_id"),
                trigger_task_id=listener_config.get("trigger_task_id"),
                trigger_condition=listener_config.get("trigger_condition"),
                action_condition=listener_config.get("action_condition"),
                agent_id=listener_config.get("agent_id"),
                action_prompt=listener_config.get("action_prompt"),
                success_output=listener_config.get("success_output"),
                failure_output=listener_config.get("failure_output")
            )
            
            listener_id = await self.listener_repo.create(listener)
            logger.info(f"Created listener {listener_id}")
            return listener_id
            
        except Exception as e:
            logger.error(f"Failed to create listener: {e}")
            raise
    
    async def get_listeners_by_task(self, task_id: str) -> List[Listener]:
        """获取监听特定任务的侦听器"""
        return await self.listener_repo.get_by_trigger_task(task_id)
    
    async def get_listeners_by_trigger(self, task_id: str, status: str) -> List[Listener]:
        """获取特定触发条件的侦听器"""
        return await self.listener_repo.get_by_trigger(task_id, status)

class PlanModule:
    """计划模块主类"""
    
    def __init__(self, plan_repo: MemoryPlanRepository, task_repo: MemoryTaskRepository, listener_repo: MemoryListenerRepository):
        self.plan_manager = PlanManager(plan_repo)
        self.task_manager = TaskManager(task_repo)
        self.listener_manager = ListenerManager(listener_repo)
    
    async def start(self):
        """启动计划模块"""
        logger.info("Plan Module started")
    
    async def stop(self):
        """停止计划模块"""
        logger.info("Plan Module stopped")
