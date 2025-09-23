"""
任务侦听模块

负责任务状态管理和侦听器调度
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from ..models.task import Task, TaskStatus
from ..models.listener import Listener
from ..database.memory_repositories import MemoryTaskRepository, MemoryListenerRepository

logger = logging.getLogger(__name__)

@dataclass
class TaskUpdate:
    """任务更新数据结构"""
    task_id: str
    status: str
    context: Dict

class TaskStateManager:
    """任务状态管理器"""
    
    def __init__(self, task_repo: MemoryTaskRepository):
        self.task_repo = task_repo
        self.status_change_callbacks = []
    
    async def update_task_status(self, task_id: str, status: str, context: Dict):
        """更新任务状态和上下文"""
        try:
            # 1. 获取当前状态
            current_task = await self.task_repo.get_by_id(task_id)
            old_status = current_task.status if current_task else None
            
            # 2. 更新数据库
            await self.task_repo.update_status(task_id, status, context)
            
            # 3. 触发状态变化事件
            await self._notify_status_changed(task_id, old_status, status, context)
            
            logger.info(f"Task {task_id} status updated: {old_status} -> {status}")
            
        except Exception as e:
            logger.error(f"Failed to update task {task_id} status: {e}")
            raise
    
    async def batch_update_tasks(self, updates: List[TaskUpdate]):
        """批量更新多个任务状态"""
        for update in updates:
            await self.update_task_status(update.task_id, update.status, update.context)
    
    def add_status_change_callback(self, callback):
        """添加状态变化回调"""
        self.status_change_callbacks.append(callback)
    
    async def _notify_status_changed(self, task_id: str, old_status: str, new_status: str, context: Dict):
        """通知状态变化"""
        for callback in self.status_change_callbacks:
            try:
                await callback(task_id, old_status, new_status, context)
            except Exception as e:
                logger.error(f"Callback error: {e}")

class ListenerScheduler:
    """侦听器调度器"""
    
    def __init__(self, listener_repo: MemoryListenerRepository, agent_manager):
        self.listener_repo = listener_repo
        self.agent_manager = agent_manager
    
    async def on_task_status_changed(self, task_id: str, old_status: str, new_status: str, context: Dict):
        """任务状态变化事件处理"""
        try:
            # 1. 查找监听该任务状态变化的侦听器
            listeners = await self.listener_repo.get_by_trigger(task_id, new_status)
            
            logger.info(f"Found {len(listeners)} listeners for task {task_id} status {new_status}")
            
            # 2. 检查每个侦听器的触发条件
            for listener in listeners:
                if await self.evaluate_condition(listener, context):
                    await self.trigger_agent(listener, context)
                    
        except Exception as e:
            logger.error(f"Error processing status change for task {task_id}: {e}")
    
    async def evaluate_condition(self, listener: Listener, context: Dict) -> bool:
        """评估侦听器触发条件"""
        try:
            # 这里需要实现条件表达式解析器
            # 支持类似 "003.status == Done && 005.status == Done" 的条件
            return await self._parse_condition(listener.action_condition, context)
        except Exception as e:
            logger.error(f"Error evaluating condition for listener {listener.id}: {e}")
            return False
    
    async def _parse_condition(self, condition: str, context: Dict) -> bool:
        """解析条件表达式"""
        # 简化实现，实际需要更复杂的表达式解析器
        if condition == "true":
            return True
        
        # 解析多任务状态条件
        if "&&" in condition:
            parts = condition.split("&&")
            for part in parts:
                if not await self._evaluate_single_condition(part.strip(), context):
                    return False
            return True
        
        return await self._evaluate_single_condition(condition, context)
    
    async def _evaluate_single_condition(self, condition: str, context: Dict) -> bool:
        """评估单个条件"""
        # 例如: "003.status == Done"
        if ".status ==" in condition:
            task_id, status = condition.split(".status ==")
            task_id = task_id.strip()
            status = status.strip()
            
            # 从数据库获取任务状态
            task = await self.task_repo.get_by_id(task_id)
            return task and task.status == status
        
        return False
    
    async def trigger_agent(self, listener: Listener, context: Dict):
        """触发Agent执行"""
        try:
            logger.info(f"Triggering agent {listener.agent_id} for listener {listener.id}")
            
            # 1. 构建Agent输入上下文
            agent_context = await self._build_agent_context(listener, context)
            
            # 2. 调用Agent执行
            result = await self.agent_manager.execute_agent(
                listener.agent_id,
                listener.action_prompt,
                agent_context
            )
            
            # 3. 处理Agent返回结果
            await self._handle_agent_result(listener, result)
            
        except Exception as e:
            logger.error(f"Error triggering agent {listener.agent_id}: {e}")
            # 处理失败情况
            await self._handle_agent_failure(listener, e)
    
    async def _build_agent_context(self, listener: Listener, context: Dict) -> Dict:
        """构建Agent输入上下文"""
        # 解析action_prompt中的上下文变量引用
        # 例如: {001.context.id} -> 获取任务001的上下文中的id字段
        agent_context = {}
        
        # 这里需要实现上下文变量的解析和注入
        # 简化实现
        agent_context.update(context)
        
        return agent_context
    
    async def _handle_agent_result(self, listener: Listener, result: Dict):
        """处理Agent执行结果"""
        if result.get("success", False):
            # 成功情况
            output = listener.success_output
        else:
            # 失败情况
            output = listener.failure_output
        
        # 更新目标任务状态
        await self.task_repo.update_status(
            output["task_id"],
            output["status"],
            output["context"]
        )
    
    async def _handle_agent_failure(self, listener: Listener, error: Exception):
        """处理Agent执行失败"""
        output = listener.failure_output
        output["context"]["error"] = str(error)
        
        await self.task_repo.update_status(
            output["task_id"],
            output["status"],
            output["context"]
        )

class TaskListenerModule:
    """任务侦听模块主类"""
    
    def __init__(self, task_repo: MemoryTaskRepository, listener_repo: MemoryListenerRepository, agent_manager):
        self.task_state_manager = TaskStateManager(task_repo)
        self.listener_scheduler = ListenerScheduler(listener_repo, agent_manager)
        
        # 注册状态变化回调
        self.task_state_manager.add_status_change_callback(
            self.listener_scheduler.on_task_status_changed
        )
    
    async def start(self):
        """启动任务侦听模块"""
        logger.info("Task Listener Module started")
    
    async def stop(self):
        """停止任务侦听模块"""
        logger.info("Task Listener Module stopped")
