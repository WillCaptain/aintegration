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
    """侦听引擎 - 提供侦听器管理工具方法"""
    
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
        self.plan_instance_listeners = {}  # plan_instance_id -> [listener_id]
        self.is_running = False
        self._execution_task = None
        self.execution_queue = asyncio.Queue()
        # 可选的Planner回调：用于处理孤立/错误/收敛等事件
        self._planner_callback: Optional[Callable[[str, str, str, str, Dict[str, Any]], Any]] = None
        # 可选的Planner日志记录回调：记录执行轨迹
        self._planner_logger: Optional[Callable[[str, Dict[str, Any]], Any]] = None

    def set_planner_callback(self, callback: Callable[[str, str, str, str, Dict[str, Any]], Any]):
        """注册Planner回调。签名: (plan_id, task_id, old_status, new_status, plan_context)"""
        self._planner_callback = callback
    
    def set_planner_logger(self, callback: Callable[[str, Dict[str, Any]], Any]):
        """注册Planner日志回调。签名: (plan_id, log_item)"""
        self._planner_logger = callback
    
    async def get_listeners_for_plan_instance(self, plan_instance_id: str, plan: 'Plan') -> List[Listener]:
        """获取计划实例的所有侦听器"""
        listener_ids = self.plan_instance_listeners.get(plan_instance_id, [])
        listeners = []
        for listener_id in listener_ids:
            listener = await self.listener_repo.get_by_id(listener_id)
            if listener:
                listeners.append(listener)
        return listeners
    
    
    async def find_triggered_listeners(self, plan_instance_id: str, task_id: str, task_status: str, plan: 'Plan', plan_instance: 'PlanInstance' = None) -> List[Listener]:
        """查找被触发的侦听器"""
        listeners = await self.get_listeners_for_plan_instance(plan_instance_id, plan)
        print(f"[ListenerEngine] 查找触发的侦听器: task_id={task_id}, status={task_status}, 总侦听器数={len(listeners)}")
        
        triggered = []
        for listener in listeners:
            condition = listener.trigger_condition
            print(f"[ListenerEngine] 检查侦听器 {listener.id}: trigger_task_id={listener.trigger_task_id}, condition={condition}")
            
            # 首先检查trigger_task_id是否匹配（支持逗号分隔的多任务ID）
            listener_trigger_ids = []
            if isinstance(listener.trigger_task_id, str):
                if "," in listener.trigger_task_id:
                    listener_trigger_ids = [x.strip() for x in listener.trigger_task_id.split(",")]
                else:
                    listener_trigger_ids = [listener.trigger_task_id.strip()]
            else:
                listener_trigger_ids = [str(listener.trigger_task_id).strip()]
            
            # 如果当前task_id不在侦听器的触发任务列表中，跳过
            if task_id not in listener_trigger_ids:
                print(f"[ListenerEngine] ✗ 侦听器 {listener.id} 的trigger_task_id {listener_trigger_ids} 不包含当前task_id {task_id}")
                continue
            
            # 检查是否匹配
            matched = False
            
            # 1. 尝试简单匹配（向后兼容）：condition == task_status
            if condition == task_status:
                print(f"[ListenerEngine] ✓ 侦听器 {listener.id} 匹配(简单状态值)!")
                matched = True
            # 2. 尝试完整格式匹配：task_id.status == status
            elif condition == f"{task_id}.status == {task_status}":
                print(f"[ListenerEngine] ✓ 侦听器 {listener.id} 匹配(完整格式)!")
                matched = True
            # 3. 尝试复杂条件评估（包含 &&, ||, != 等）
            elif plan_instance and any(op in condition for op in ['.status', '&&', '||', '!=']):
                if self._evaluate_condition(condition, plan_instance):
                    print(f"[ListenerEngine] ✓ 侦听器 {listener.id} 复杂条件匹配!")
                    matched = True
                else:
                    print(f"[ListenerEngine] ✗ 侦听器 {listener.id} 复杂条件不满足")
            
            if matched:
                triggered.append(listener)
        
        print(f"[ListenerEngine] 找到 {len(triggered)} 个触发的侦听器")
        return triggered
    
    def _evaluate_condition(self, condition: str, plan_instance: 'PlanInstance') -> bool:
        """评估条件（支持 &&, ||, ==, !=）"""
        try:
            import re
            
            # 检查是否是简单的状态值（向后兼容），例如: "Done"
            if not any(op in condition for op in ['.status', '&&', '||', '==', '!=']):
                # 简单状态值，无法评估（需要在外层匹配）
                print(f"[ListenerEngine] 简单条件格式，无法评估: {condition}")
                return False
            
            # 构建任务状态字典
            task_status_dict = {}
            for task_id, task_instance in plan_instance.task_instances.items():
                task_status_dict[f"{task_id}.status"] = task_instance.status
            
            print(f"[ListenerEngine] 评估条件: {condition}")
            print(f"[ListenerEngine] 当前任务状态: {task_status_dict}")
            
            # 使用正则表达式替换条件中的变量和状态值
            import re
            eval_condition = condition
            
            # 1. 替换任务状态变量为实际值，例如: 004.status -> "Done"
            for var, value in task_status_dict.items():
                eval_condition = eval_condition.replace(var, f'"{value}"')
            
            # 2. 替换状态值为带引号的字符串，例如: == Done -> == "Done"
            # 匹配模式: (==|!=) 后面跟着的单词（状态值）
            eval_condition = re.sub(r'(==|!=)\s*(\w+)', r'\1 "\2"', eval_condition)
            
            # 3. 替换逻辑运算符
            eval_condition = eval_condition.replace(" && ", " and ")
            eval_condition = eval_condition.replace(" || ", " or ")
            
            print(f"[ListenerEngine] 转换后的条件: {eval_condition}")
            
            # 安全评估表达式
            try:
                result = eval(eval_condition, {"__builtins__": {}}, {})
                print(f"[ListenerEngine] 条件评估结果: {result}")
                return bool(result)
            except Exception as e:
                print(f"[ListenerEngine] 条件评估失败: {e}")
                logger.error(f"Failed to evaluate condition '{eval_condition}': {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False
    
    async def execute_listener(self, listener: Listener, plan_instance: 'PlanInstance') -> Dict[str, Any]:
        """执行侦听器"""
        try:
            # 使用 TaskDriver 执行侦听器
            result = await self.task_driver.execute_listener(listener, plan_instance)
            return result
        except Exception as e:
            logger.error(f"Error executing listener {listener.listener_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'task_updates': []
            }
    
    async def register_plan_instance(self, plan_instance: 'PlanInstance'):
        """注册计划实例到侦听引擎"""
        try:
            plan_id = plan_instance.plan_id
            plan_instance_id = plan_instance.id
            
            # 获取计划的侦听器配置
            plan = await self.plan_repo.get_by_id(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found for instance {plan_instance_id}")
                return False
            
            # 为每个侦听器创建实例级别的侦听器
            for listener_config in plan.listeners:
                listener_id = f"{plan_instance_id}_{listener_config['listener_id']}"
                
                # 创建侦听器实例
                listener_type = listener_config.get('listener_type', listener_config.get('action_type', 'agent'))
                
                # 获取code_snippet（支持多种配置格式）
                code_snippet = None
                if listener_type == 'code':
                    code_snippet = (
                        listener_config.get('code_snippet') or 
                        listener_config.get('action_config', {}).get('code', '')
                    )
                
                listener = Listener(
                    id=listener_id,
                    plan_id=plan_id,
                    trigger_task_id=listener_config['trigger_task_id'],
                    trigger_condition=listener_config.get('trigger_status', listener_config.get('trigger_condition', 'Done')),
                    action_condition='execute',
                    listener_type=listener_type,
                    plan_instance_id=plan_instance_id,
                    agent_id=listener_config.get('agent_id'),
                    action_prompt=listener_config.get('action_prompt'),
                    code_snippet=code_snippet,
                    success_output=listener_config.get('success_output'),
                    failure_output=listener_config.get('failure_output')
                )
                
                # 保存侦听器实例
                await self.listener_repo.create(listener)
                logger.info(f"Registered listener {listener_id} for plan instance {plan_instance_id}")
            
            # 记录计划实例的侦听器ID列表
            listener_ids = [f"{plan_instance_id}_{listener_config['listener_id']}" for listener_config in plan.listeners]
            self.plan_instance_listeners[plan_instance_id] = listener_ids
            
            logger.info(f"Registered plan instance {plan_instance_id} with {len(plan.listeners)} listeners")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register plan instance {plan_instance.id}: {e}")
            return False
    
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
        logger.info("侦听器引擎执行循环开始")
        while self.is_running:
            try:
                # 等待任务状态变化事件
                event = await asyncio.wait_for(self.execution_queue.get(), timeout=1.0)
                logger.info(f"收到事件: {event}")
                await self._process_event(event)
            except asyncio.TimeoutError:
                # 超时，继续循环
                continue
            except Exception as e:
                logger.error(f"Error in execution loop: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
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
        plan_instance_id = event.get("plan_instance_id")
        
        logger.info(f"Task {task_id} status changed from {old_status} to {new_status} (plan_instance: {plan_instance_id})")
        
        # 获取计划上下文
        plan_context = await self._get_plan_context(plan_id)
        
        # 查找触发的侦听器
        triggered_listeners = await self._find_triggered_listeners(task_id, new_status, plan_context)
        
        # 当无侦听器命中、任务进入错误状态、或主任务完成时，触发Planner
        is_main_task = False
        try:
            is_main_task = plan_context.get("main_task_id") == task_id
        except Exception:
            is_main_task = False

        should_notify_planner = False
        reasons: List[str] = []
        if not triggered_listeners:
            reasons.append("no_listeners")
            should_notify_planner = True
        if str(new_status) == TaskStatus.ERROR.value:
            reasons.append("task_error")
            should_notify_planner = True
        if is_main_task and str(new_status) == TaskStatus.DONE.value:
            reasons.append("main_done")
            should_notify_planner = True

        if should_notify_planner:
            if not triggered_listeners:
                logger.warning(f"No listeners triggered for task {task_id} status change to {new_status}")
            logger.info(f"Notify planner due to: {','.join(reasons)}")
            await self._notify_planner(task_id, old_status, new_status, plan_id, plan_context, plan_instance_id)
            if not triggered_listeners:
                # 无侦听器情况下直接返回，避免后续空执行
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
    
    async def _handle_plan_complete(self, event: Dict[str, Any]):
        """处理计划完成事件"""
        plan_id = event.get("plan_id")
        logger.info(f"Plan {plan_id} completed")
        
    
    async def _find_triggered_listeners(self, task_id: str, status: str, plan_context: Dict[str, Any]) -> List[Listener]:
        """查找触发的侦听器：支持 trigger_task_id 为列表；用 plan 上下文解析复合 trigger_condition"""
        try:
            all_listeners = await self.listener_repo.get_by_trigger_task(task_id)

            def _eval_condition(expr: str) -> bool:
                if not expr or expr.strip().lower() == "any":
                    return True
                parts = [p.strip() for p in expr.split("&&")]
                for part in parts:
                    if ".status ==" in part:
                        tid, expected = part.split(".status ==")
                        tid = tid.strip()
                        expected = expected.strip()
                        # 从计划上下文读取对应任务状态
                        try:
                            actual = plan_context["tasks"][tid]["status"]
                        except Exception:
                            return False
                        if actual != expected:
                            return False
                    else:
                        return False
                return True

            triggered: List[Listener] = []
            for listener in all_listeners:
                # 检查侦听器是否监听当前任务ID
                listener_trigger_ids = []
                if isinstance(listener.trigger_task_id, list):
                    listener_trigger_ids = [str(x).strip() for x in listener.trigger_task_id]
                elif isinstance(listener.trigger_task_id, str):
                    if "," in listener.trigger_task_id:
                        listener_trigger_ids = [x.strip() for x in listener.trigger_task_id.split(",")]
                    else:
                        listener_trigger_ids = [listener.trigger_task_id.strip()]
                else:
                    listener_trigger_ids = [str(listener.trigger_task_id).strip()]
                
                logger.debug(f"Check listener {listener.id}: trigger_ids={listener_trigger_ids}, expr='{listener.trigger_condition}' for event task={task_id} status={status}")
                # 如果当前任务ID在侦听器的触发任务列表中，且满足触发条件
                if task_id in listener_trigger_ids and _eval_condition(listener.trigger_condition or ""):
                    logger.debug(f"Listener {listener.id} triggered by task {task_id} with status {status}")
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
        
        # 创建任务列表
        tasks = []
        for listener in listeners:
            task = asyncio.create_task(self.task_driver.execute_listener(listener, plan_context))
            tasks.append((listener, task))
        
        # 流式处理完成的任务
        for listener, task in tasks:
            try:
                result = await task
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
            plan_instance_id = update.get("plan_instance_id")
            
            # 如果有 plan_instance_id，通过 PlanInstance 更新任务状态
            if plan_instance_id:
                # 通过 PlanInstance 更新任务状态（会发出事件）
                # 注意：这里需要从 PlanModule 获取 PlanInstance，暂时跳过
                # plan_instance.update_task_status(task_id, new_status, f"listener_execution: {execution_result.get('reason', 'completed')}")
                return
            
            # 回退到传统方式（向后兼容）
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
        # 兼容旧方法：委托到统一通知入口
        await self._notify_planner(task_id, plan_context.get("tasks", {}).get(task_id, {}).get("status"), status, plan_id, plan_context)

    async def _notify_planner(self, task_id: str, old_status: Optional[str], new_status: str, plan_id: str, plan_context: Dict[str, Any], plan_instance_id: Optional[str] = None):
        """统一通知Planner入口"""
        try:
            if self._planner_callback is None:
                logger.info(f"Planner callback not registered. Skip planner notification for {task_id} -> {new_status}")
                return
            logger.info(f"Calling planner callback for task {task_id}: {old_status} -> {new_status} (plan_instance: {plan_instance_id})")
            cb = self._planner_callback
            # 将 plan_instance_id 添加到 plan_context 中传递
            if plan_instance_id:
                plan_context["plan_instance_id"] = plan_instance_id
            maybe_awaitable = cb(plan_id, task_id, old_status, new_status, plan_context)
            if asyncio.iscoroutine(maybe_awaitable):
                await maybe_awaitable
        except Exception as e:
            logger.error(f"Error notifying planner: {e}")
    
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
                "main_task_id": plan.main_task_id,
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
    
    async def trigger_task_status_change(self, task_id: str, old_status: str, new_status: str, plan_id: str, plan_instance_id: Optional[str] = None):
        """触发任务状态变化事件"""
        event = {
            "type": "task_status_change",
            "task_id": task_id,
            "old_status": old_status,
            "new_status": new_status,
            "plan_id": plan_id,
            "plan_instance_id": plan_instance_id,
            "timestamp": datetime.now()
        }
        
        await self.execution_queue.put(event)
        logger.info(f"Triggered task status change event: {event}")
    
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
                    logger.info(f"准备触发任务状态变化事件: {plan.main_task_id}, {TaskStatus.NOT_STARTED.value} -> {TaskStatus.RUNNING.value}")
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
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
