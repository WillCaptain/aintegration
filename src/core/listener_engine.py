"""
侦听引擎模块

处理任务状态变化触发侦听器，实现事件驱动的任务执行
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime

from ..models.task import Task, TaskStatus
from ..models.listener import Listener
from ..models.plan import Plan, PlanStatus
from ..core.task_driver import TaskDriver
from ..database.memory_repositories import MemoryTaskRepository, MemoryListenerRepository, MemoryPlanRepository

logger = logging.getLogger(__name__)

class ListenerEngine:
    """侦听引擎"""
    
    def __init__(
        self, 
        task_repo: MemoryTaskRepository,
        listener_repo: MemoryListenerRepository,
        plan_repo: MemoryPlanRepository,
        task_driver: TaskDriver
    ):
        self.task_repo = task_repo
        self.listener_repo = listener_repo
        self.plan_repo = plan_repo
        self.task_driver = task_driver
        self.active_plans = {}  # 活跃计划的缓存
        self.execution_queue = asyncio.Queue()
        self.is_running = False
        self._execution_task = None
    
    async def start(self):
        """启动侦听引擎"""
        if self.is_running:
            logger.warning("Listener engine is already running")
            return
        
        self.is_running = True
        self._execution_task = asyncio.create_task(self._execution_loop())
        logger.info("Listener engine started")
    
    async def stop(self):
        """停止侦听引擎"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._execution_task:
            self._execution_task.cancel()
            try:
                await self._execution_task
            except asyncio.CancelledError:
                pass
        logger.info("Listener engine stopped")
    
    async def _execution_loop(self):
        """执行循环"""
        while self.is_running:
            try:
                # 等待任务状态变化事件
                event = await asyncio.wait_for(self.execution_queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                # 超时，继续循环
                continue
            except Exception as e:
                logger.error(f"Error in execution loop: {e}")
                await asyncio.sleep(1)  # 避免快速循环
    
    async def _process_event(self, event: Dict[str, Any]):
        """处理事件"""
        try:
            event_type = event.get("type")
            if event_type == "task_status_change":
                await self._handle_task_status_change(event)
            elif event_type == "plan_start":
                await self._handle_plan_start(event)
            elif event_type == "plan_complete":
                await self._handle_plan_complete(event)
            else:
                logger.warning(f"Unknown event type: {event_type}")
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
    async def _handle_task_status_change(self, event: Dict[str, Any]):
        """处理任务状态变化事件"""
        task_id = event.get("task_id")
        old_status = event.get("old_status")
        new_status = event.get("new_status")
        plan_id = event.get("plan_id")
        
        logger.info(f"Task {task_id} status changed from {old_status} to {new_status}")
        
        # 获取计划上下文
        plan_context = await self._get_plan_context(plan_id)
        
        # 查找触发的侦听器
        triggered_listeners = await self._find_triggered_listeners(task_id, new_status, plan_context)
        
        if not triggered_listeners:
            logger.warning(f"No listeners triggered for task {task_id} status change to {new_status}")
            # 这是一个异常状态变化，需要Planner处理
            await self._handle_orphaned_status_change(task_id, new_status, plan_id, plan_context)
            return
        
        # 按优先级排序侦听器
        triggered_listeners.sort(key=lambda l: l.priority)
        
        # 执行侦听器
        await self._execute_triggered_listeners(triggered_listeners, plan_context)
    
    async def _handle_plan_start(self, event: Dict[str, Any]):
        """处理计划启动事件"""
        plan_id = event.get("plan_id")
        logger.info(f"Plan {plan_id} started")
        
        # 将计划标记为活跃
        plan = await self.plan_repo.get_by_id(plan_id)
        if plan:
            plan.start()
            await self.plan_repo.update(plan_id, {"status": plan.status, "started_at": plan.started_at})
            self.active_plans[plan_id] = plan
    
    async def _handle_plan_complete(self, event: Dict[str, Any]):
        """处理计划完成事件"""
        plan_id = event.get("plan_id")
        logger.info(f"Plan {plan_id} completed")
        
        # 从活跃计划中移除
        if plan_id in self.active_plans:
            del self.active_plans[plan_id]
    
    async def _find_triggered_listeners(self, task_id: str, status: str, plan_context: Dict[str, Any]) -> List[Listener]:
        """查找触发的侦听器"""
        try:
            # 获取监听该任务的所有侦听器
            all_listeners = await self.listener_repo.get_by_trigger_task(task_id)
            
            triggered = []
            for listener in all_listeners:
                if listener.evaluate_trigger_condition(status):
                    triggered.append(listener)
            
            return triggered
        except Exception as e:
            logger.error(f"Error finding triggered listeners: {e}")
            return []
    
    async def _execute_triggered_listeners(self, listeners: List[Listener], plan_context: Dict[str, Any]):
        """执行触发的侦听器 - 流式处理，完成一个处理一个"""
        if not listeners:
            return
        
        logger.info(f"Executing {len(listeners)} triggered listeners")
        
        # 创建任务字典，保持listener和task的映射
        task_to_listener = {}
        for listener in listeners:
            task = asyncio.create_task(self.task_driver.execute_listener(listener, plan_context))
            task_to_listener[task] = listener
        
        # 流式处理完成的任务
        for completed_task in asyncio.as_completed(task_to_listener.keys()):
            listener = task_to_listener[completed_task]
            try:
                result = await completed_task
                logger.info(f"Processing result for listener {listener.id}: {result}")
                
                # 确定任务更新
                task_updates = self.task_driver.determine_task_updates(listener, result)
                logger.info(f"Determined task updates: {task_updates}")
                
                # 立即应用任务更新
                for update in task_updates:
                    logger.info(f"Applying task update: {update}")
                    await self._apply_task_update(update)
                    
            except Exception as e:
                logger.error(f"Error in execution for listener {listener.id}: {e}")
    
    async def _apply_task_update(self, update: Dict[str, Any]):
        """应用任务更新"""
        try:
            task_id = update["task_id"]
            new_status = update["status"]
            context_updates = update.get("context", {})
            execution_result = update.get("execution_result", {})
            
            # 获取当前任务
            task = await self.task_repo.get_by_id(task_id)
            if not task:
                logger.error(f"Task {task_id} not found for update")
                return
            
            # 检查状态转换是否有效
            if not task.can_transition_to(new_status):
                logger.warning(f"Invalid status transition for task {task_id}: {task.status} -> {new_status}")
                return
            
            old_status = task.status
            
            # 更新任务状态和上下文
            task.update_status(new_status, context_updates)
            await self.task_repo.update_status(task_id, new_status, context_updates)
            
            # 触发新的状态变化事件
            await self.trigger_task_status_change(task_id, old_status, new_status, task.plan_id)
            
            logger.info(f"Updated task {task_id} to status {new_status}")
            
        except Exception as e:
            logger.error(f"Error applying task update: {e}")
    
    async def _handle_orphaned_status_change(self, task_id: str, status: str, plan_id: str, plan_context: Dict[str, Any]):
        """处理孤立的状态变化（没有侦听器处理）"""
        logger.warning(f"Orphaned status change: task {task_id} -> {status}, no listeners found")
        
        # 这里应该通知Planner生成新的侦听器
        # 暂时记录日志，实际实现需要集成Planner
        await self._notify_planner_for_orphaned_change(task_id, status, plan_id, plan_context)
    
    async def _notify_planner_for_orphaned_change(self, task_id: str, status: str, plan_id: str, plan_context: Dict[str, Any]):
        """通知Planner处理孤立的状态变化"""
        # 这里应该调用Planner的接口
        # 暂时记录日志
        logger.info(f"Notifying planner for orphaned change: task {task_id} -> {status} in plan {plan_id}")
    
    async def _get_plan_context(self, plan_id: str) -> Dict[str, Any]:
        """获取计划上下文"""
        try:
            # 获取计划信息
            plan = await self.plan_repo.get_by_id(plan_id)
            if not plan:
                return {}
            
            # 获取所有任务
            tasks = await self.task_repo.get_by_plan_id(plan_id)
            
            # 构建上下文
            context = {
                "plan_id": plan_id,
                "plan_name": plan.name,
                "plan_status": plan.status,
                "tasks": {}
            }
            
            for task in tasks:
                context["tasks"][task.id] = {
                    "status": task.status,
                    "context": task.context,
                    "name": task.name
                }
            
            return context
        except Exception as e:
            logger.error(f"Error getting plan context: {e}")
            return {}
    
    async def trigger_task_status_change(self, task_id: str, old_status: str, new_status: str, plan_id: str):
        """触发任务状态变化事件"""
        event = {
            "type": "task_status_change",
            "task_id": task_id,
            "old_status": old_status,
            "new_status": new_status,
            "plan_id": plan_id,
            "timestamp": datetime.now()
        }
        
        await self.execution_queue.put(event)
        logger.debug(f"Triggered task status change event: {event}")
    
    async def trigger_plan_start(self, plan_id: str):
        """触发计划启动事件"""
        event = {
            "type": "plan_start",
            "plan_id": plan_id,
            "timestamp": datetime.now()
        }
        
        await self.execution_queue.put(event)
        logger.debug(f"Triggered plan start event: {event}")
    
    async def trigger_plan_complete(self, plan_id: str):
        """触发计划完成事件"""
        event = {
            "type": "plan_complete",
            "plan_id": plan_id,
            "timestamp": datetime.now()
        }
        
        await self.execution_queue.put(event)
        logger.debug(f"Triggered plan complete event: {event}")
    
    async def start_plan_execution(self, plan_id: str):
        """启动计划执行"""
        try:
            # 获取计划
            plan = await self.plan_repo.get_by_id(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return False
            
            # 获取主任务
            if plan.main_task_id:
                main_task = await self.task_repo.get_by_id(plan.main_task_id)
                if main_task:
                    # 启动主任务
                    main_task.update_status(TaskStatus.RUNNING.value)
                    await self.task_repo.update_status(plan.main_task_id, TaskStatus.RUNNING.value, {})
                    
                    # 触发计划启动事件
                    await self.trigger_plan_start(plan_id)
                    
                    # 触发主任务状态变化事件
                    await self.trigger_task_status_change(
                        plan.main_task_id, 
                        TaskStatus.NOT_STARTED.value, 
                        TaskStatus.RUNNING.value, 
                        plan_id
                    )
                    
                    logger.info(f"Started plan execution: {plan_id}")
                    return True
            
            logger.error(f"Plan {plan_id} has no main task")
            return False
            
        except Exception as e:
            logger.error(f"Error starting plan execution: {e}")
            return False
    
    async def check_plan_completion(self, plan_id: str) -> bool:
        """检查计划是否完成"""
        try:
            # 获取计划
            plan = await self.plan_repo.get_by_id(plan_id)
            if not plan or not plan.main_task_id:
                return False
            
            # 检查主任务状态
            main_task = await self.task_repo.get_by_id(plan.main_task_id)
            if main_task and main_task.is_completed():
                # 计划完成
                plan.complete()
                await self.plan_repo.update(plan_id, {
                    "status": plan.status,
                    "completed_at": plan.completed_at
                })
                
                # 触发计划完成事件
                await self.trigger_plan_complete(plan_id)
                
                logger.info(f"Plan {plan_id} completed")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking plan completion: {e}")
            return False
