"""
内存版本的Repository实现

将所有数据库操作mock成内存操作，避免数据库依赖
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

from ..models.plan import Plan
from ..models.task import Task
from ..models.listener import Listener
from ..models.execution import Execution

logger = logging.getLogger(__name__)

class MemoryPlanRepository:
    """内存版本的计划仓库"""
    
    def __init__(self):
        self.plans = {}
        self.next_id = 1
    
    async def create(self, plan: Plan) -> str:
        """创建计划"""
        try:
            plan_id = plan.id or f"plan_{self.next_id:06d}"
            self.next_id += 1
            
            plan.id = plan_id
            plan.created_at = datetime.now()
            self.plans[plan_id] = plan
            
            logger.info(f"Memory: Created plan {plan_id}")
            return plan_id
        except Exception as e:
            logger.error(f"Memory: Failed to create plan: {e}")
            raise
    
    async def get_by_id(self, plan_id: str) -> Optional[Plan]:
        """根据ID获取计划"""
        try:
            return self.plans.get(plan_id)
        except Exception as e:
            logger.error(f"Memory: Failed to get plan {plan_id}: {e}")
            raise
    
    async def update(self, plan_id: str, updates: Dict):
        """更新计划"""
        try:
            if plan_id in self.plans:
                plan = self.plans[plan_id]
                for key, value in updates.items():
                    if hasattr(plan, key):
                        setattr(plan, key, value)
                plan.updated_at = datetime.now()
                logger.info(f"Memory: Updated plan {plan_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to update plan {plan_id}: {e}")
            raise
    
    async def delete(self, plan_id: str):
        """删除计划"""
        try:
            if plan_id in self.plans:
                del self.plans[plan_id]
                logger.info(f"Memory: Deleted plan {plan_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to delete plan {plan_id}: {e}")
            raise
    
    async def search(self, criteria: Dict) -> List[Plan]:
        """搜索计划"""
        try:
            results = []
            for plan in self.plans.values():
                # 简化搜索逻辑
                if criteria.get("query"):
                    query = criteria["query"].lower()
                    if (query in plan.name.lower() or 
                        query in plan.description.lower()):
                        results.append(plan)
                else:
                    results.append(plan)
            return results
        except Exception as e:
            logger.error(f"Memory: Failed to search plans: {e}")
            raise
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Plan]:
        """列出所有计划"""
        try:
            plans_list = list(self.plans.values())
            return plans_list[offset:offset + limit]
        except Exception as e:
            logger.error(f"Memory: Failed to list plans: {e}")
            raise
    
    async def get_few_shot_examples(self) -> List[Dict]:
        """获取Few-shot示例"""
        return [
            {
                "scenario": "新员工入职",
                "plan_template": {
                    "tasks": [
                        {"task_id": "001", "name": "新员工完成入职", "prompt": "新员工入职"},
                        {"task_id": "002", "name": "新员工注册", "prompt": "新员工在Hr系统中完成新员工注册"}
                    ],
                    "listeners": [
                        {
                            "listener_id": "L001",
                            "trigger_task_id": "001",
                            "trigger_condition": "001.status == Running",
                            "action_condition": "true",
                            "agent_id": "HrAgent",
                            "action_prompt": "根据员工的身份证号、姓名信息在HR系统中创建员工记录",
                            "success_output": {"task_id": "002", "status": "Done", "context": {}},
                            "failure_output": {"task_id": "002", "status": "Error", "context": {}}
                        }
                    ]
                },
                "modification_guide": "如何根据具体需求修改计划"
            }
        ]

class MemoryTaskRepository:
    """内存版本的任务仓库"""
    
    def __init__(self):
        self.tasks = {}
        self.next_id = 1
    
    async def create(self, task: Task) -> str:
        """创建任务"""
        try:
            task_id = task.id or f"task_{self.next_id:06d}"
            self.next_id += 1
            
            task.id = task_id
            task.created_at = datetime.now()
            self.tasks[task_id] = task
            
            logger.info(f"Memory: Created task {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Memory: Failed to create task: {e}")
            raise
    
    async def get_by_id(self, task_id: str) -> Optional[Task]:
        """根据ID获取任务"""
        try:
            return self.tasks.get(task_id)
        except Exception as e:
            logger.error(f"Memory: Failed to get task {task_id}: {e}")
            raise
    
    async def update(self, task_id: str, updates: Dict):
        """更新任务"""
        try:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                task.updated_at = datetime.now()
                logger.info(f"Memory: Updated task {task_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to update task {task_id}: {e}")
            raise
    
    async def update_status(self, task_id: str, status: str, context: Dict):
        """更新任务状态"""
        try:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = status
                task.context = {"status": status, "values": context}
                task.updated_at = datetime.now()
                logger.info(f"Memory: Updated task {task_id} status to {status}")
        except Exception as e:
            logger.error(f"Memory: Failed to update task {task_id} status: {e}")
            raise
    
    async def get_by_plan_id(self, plan_id: str) -> List[Task]:
        """根据计划ID获取任务列表"""
        try:
            return [task for task in self.tasks.values() if task.plan_id == plan_id]
        except Exception as e:
            logger.error(f"Memory: Failed to get tasks for plan {plan_id}: {e}")
            raise
    
    async def delete(self, task_id: str):
        """删除任务"""
        try:
            if task_id in self.tasks:
                del self.tasks[task_id]
                logger.info(f"Memory: Deleted task {task_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to delete task {task_id}: {e}")
            raise
    
    async def search_by_status(self, status: str) -> List[Task]:
        """根据状态搜索任务"""
        try:
            return [task for task in self.tasks.values() if task.status == status]
        except Exception as e:
            logger.error(f"Memory: Failed to search tasks by status {status}: {e}")
            raise

class MemoryListenerRepository:
    """内存版本的侦听器仓库"""
    
    def __init__(self):
        self.listeners = {}
        self.next_id = 1
    
    async def create(self, listener: Listener) -> str:
        """创建侦听器"""
        try:
            listener_id = listener.id or f"listener_{self.next_id:06d}"
            self.next_id += 1
            
            listener.id = listener_id
            self.listeners[listener_id] = listener
            
            logger.info(f"Memory: Created listener {listener_id}")
            return listener_id
        except Exception as e:
            logger.error(f"Memory: Failed to create listener: {e}")
            raise
    
    async def get_by_id(self, listener_id: str) -> Optional[Listener]:
        """根据ID获取侦听器"""
        try:
            return self.listeners.get(listener_id)
        except Exception as e:
            logger.error(f"Memory: Failed to get listener {listener_id}: {e}")
            raise
    
    async def get_by_trigger_task(self, task_id: str) -> List[Listener]:
        """获取监听特定任务的侦听器"""
        try:
            return [listener for listener in self.listeners.values() 
                   if listener.trigger_task_id == task_id]
        except Exception as e:
            logger.error(f"Memory: Failed to get listeners for trigger task {task_id}: {e}")
            raise
    
    async def get_by_trigger(self, task_id: str, status: str) -> List[Listener]:
        """获取特定触发条件的侦听器"""
        try:
            results = []
            for listener in self.listeners.values():
                if listener.trigger_task_id == task_id:
                    # 简化触发条件匹配
                    trigger_condition = listener.trigger_condition
                    expected_condition = f"{task_id}.status == {status}"
                    if expected_condition in trigger_condition or "Any" in trigger_condition:
                        results.append(listener)
            return results
        except Exception as e:
            logger.error(f"Memory: Failed to get listeners for trigger {task_id}/{status}: {e}")
            raise
    
    async def get_by_plan_id(self, plan_id: str) -> List[Listener]:
        """根据计划ID获取侦听器列表"""
        try:
            return [listener for listener in self.listeners.values() 
                   if listener.plan_id == plan_id]
        except Exception as e:
            logger.error(f"Memory: Failed to get listeners for plan {plan_id}: {e}")
            raise
    
    async def update(self, listener_id: str, updates: Dict):
        """更新侦听器"""
        try:
            if listener_id in self.listeners:
                listener = self.listeners[listener_id]
                for key, value in updates.items():
                    if hasattr(listener, key):
                        setattr(listener, key, value)
                logger.info(f"Memory: Updated listener {listener_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to update listener {listener_id}: {e}")
            raise
    
    async def delete(self, listener_id: str):
        """删除侦听器"""
        try:
            if listener_id in self.listeners:
                del self.listeners[listener_id]
                logger.info(f"Memory: Deleted listener {listener_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to delete listener {listener_id}: {e}")
            raise

class MemoryExecutionRepository:
    """内存版本的执行记录仓库"""
    
    def __init__(self):
        self.executions = {}
        self.next_id = 1
    
    async def create(self, execution: Execution) -> str:
        """创建执行记录"""
        try:
            execution_id = execution.id or f"exec_{self.next_id:06d}"
            self.next_id += 1
            
            execution.id = execution_id
            execution.start_time = datetime.now()
            self.executions[execution_id] = execution
            
            logger.info(f"Memory: Created execution {execution_id}")
            return execution_id
        except Exception as e:
            logger.error(f"Memory: Failed to create execution: {e}")
            raise
    
    async def get_by_id(self, execution_id: str) -> Optional[Execution]:
        """根据ID获取执行记录"""
        try:
            return self.executions.get(execution_id)
        except Exception as e:
            logger.error(f"Memory: Failed to get execution {execution_id}: {e}")
            raise
    
    async def update(self, execution_id: str, updates: Dict):
        """更新执行记录"""
        try:
            if execution_id in self.executions:
                execution = self.executions[execution_id]
                for key, value in updates.items():
                    if hasattr(execution, key):
                        setattr(execution, key, value)
                logger.info(f"Memory: Updated execution {execution_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to update execution {execution_id}: {e}")
            raise
    
    async def update_status(self, execution_id: str, status: str, error_message: Optional[str] = None):
        """更新执行状态"""
        try:
            if execution_id in self.executions:
                execution = self.executions[execution_id]
                execution.status = status
                if error_message:
                    execution.error_message = error_message
                if status in ["completed", "failed", "cancelled"]:
                    execution.end_time = datetime.now()
                logger.info(f"Memory: Updated execution {execution_id} status to {status}")
        except Exception as e:
            logger.error(f"Memory: Failed to update execution {execution_id} status: {e}")
            raise
    
    async def add_log_entry(self, execution_id: str, event: str, details: Dict, task_id: Optional[str] = None):
        """添加执行日志条目"""
        try:
            if execution_id in self.executions:
                execution = self.executions[execution_id]
                execution.add_log_entry(event, details, task_id)
                logger.info(f"Memory: Added log entry to execution {execution_id}: {event}")
        except Exception as e:
            logger.error(f"Memory: Failed to add log entry to execution {execution_id}: {e}")
            raise
    
    async def get_by_status(self, status: str) -> List[Execution]:
        """根据状态获取执行记录"""
        try:
            return [execution for execution in self.executions.values() 
                   if execution.status == status]
        except Exception as e:
            logger.error(f"Memory: Failed to get executions by status {status}: {e}")
            raise
    
    async def get_by_plan_id(self, plan_id: str) -> List[Execution]:
        """根据计划ID获取执行记录"""
        try:
            return [execution for execution in self.executions.values() 
                   if execution.plan_id == plan_id]
        except Exception as e:
            logger.error(f"Memory: Failed to get executions for plan {plan_id}: {e}")
            raise
    
    async def list_recent(self, limit: int = 100, offset: int = 0) -> List[Execution]:
        """获取最近的执行记录"""
        try:
            executions_list = list(self.executions.values())
            # 按开始时间排序
            executions_list.sort(key=lambda x: x.start_time or datetime.min, reverse=True)
            return executions_list[offset:offset + limit]
        except Exception as e:
            logger.error(f"Memory: Failed to list recent executions: {e}")
            raise
    
    async def delete(self, execution_id: str):
        """删除执行记录"""
        try:
            if execution_id in self.executions:
                del self.executions[execution_id]
                logger.info(f"Memory: Deleted execution {execution_id}")
        except Exception as e:
            logger.error(f"Memory: Failed to delete execution {execution_id}: {e}")
            raise

class MemoryDatabaseConnection:
    """内存版本的数据库连接"""
    
    def __init__(self):
        self.plan_repo = MemoryPlanRepository()
        self.task_repo = MemoryTaskRepository()
        self.listener_repo = MemoryListenerRepository()
        self.execution_repo = MemoryExecutionRepository()
    
    async def create_session(self):
        """创建数据库会话（内存版本不需要）"""
        return self
    
    async def close(self):
        """关闭数据库连接（内存版本不需要）"""
        pass
    
    async def create_tables(self):
        """创建数据库表（内存版本不需要）"""
        pass
    
    async def drop_tables(self):
        """删除数据库表（内存版本不需要）"""
        pass

