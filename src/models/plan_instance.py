"""
计划实例数据模型

计划实例表示计划的一次具体执行，包含实例ID、计划ID、状态等信息
"""

import logging
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)

class PlanInstanceStatus(Enum):
    """计划实例状态枚举"""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"

@dataclass
class PlanInstance:
    """计划实例模型"""
    id: str  # plan_instance_id
    plan_id: str  # 引用的计划定义ID
    plan: 'Plan' = None  # 计划对象（元数据）
    prompt: str = ""  # 启动提示
    status: str = PlanInstanceStatus.NOT_STARTED.value
    context: Dict[str, Any] = None  # 实例上下文
    created_at: datetime = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_info: Optional[Dict[str, Any]] = None  # 错误信息
    task_instances: Dict[str, 'TaskInstance'] = None  # 任务实例字典 {task_id: TaskInstance}
    _execution_task: Optional[Any] = None  # 执行任务引用
    _executed_listeners: Optional[set] = None  # 已执行的侦听器ID集合（防止重复触发）
    _planner_verification_task: Optional[Any] = None  # PlannerAgent验证任务引用
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}
        if self.task_instances is None:
            self.task_instances = {}
        if self.created_at is None:
            self.created_at = datetime.now()
        if self._executed_listeners is None:
            self._executed_listeners = set()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PlanInstance':
        """从字典创建实例"""
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PlanInstance':
        """从JSON字符串创建实例"""
        import json
        data = json.loads(json_str)
        # 处理日期时间字段
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            data['updated_at'] = datetime.fromisoformat(data['updated_at']) if data['updated_at'] else None
        if 'started_at' in data:
            data['started_at'] = datetime.fromisoformat(data['started_at']) if data['started_at'] else None
        if 'completed_at' in data:
            data['completed_at'] = datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None
        return cls.from_dict(data)
    
    def is_running(self) -> bool:
        """检查实例是否正在运行"""
        return self.status == PlanInstanceStatus.RUNNING.value
    
    def is_completed(self) -> bool:
        """检查实例是否已完成"""
        return self.status == PlanInstanceStatus.DONE.value
    
    def is_failed(self) -> bool:
        """检查实例是否失败"""
        return self.status == PlanInstanceStatus.ERROR.value
    
    def is_cancelled(self) -> bool:
        """检查实例是否已取消"""
        return self.status == PlanInstanceStatus.CANCELLED.value
    
    def start(self):
        """启动实例"""
        if self.status == PlanInstanceStatus.NOT_STARTED.value:
            # 初始化上下文
            self._initialize_context()
            
            # 更新状态
            self.status = PlanInstanceStatus.RUNNING.value
            self.started_at = datetime.now()
            self.updated_at = datetime.now()
            
            # 记录plan启动
            try:
                from src.utils.execution_logger import execution_logger
                main_task = self.get_main_task_instance()
                execution_logger.plan_started(
                    plan_id=self.plan_id,
                    main_task_id=main_task.task_id if main_task else "001"
                )
            except:
                pass
            
            # 开始自我驱动执行（异步）
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # 创建任务但不等待
                task = loop.create_task(self.run_self_driven())
                # 存储任务引用以便后续取消
                self._execution_task = task
            except RuntimeError:
                # 如果没有运行的事件循环，创建一个新的
                task = asyncio.create_task(self.run_self_driven())
                self._execution_task = task
    
    async def run_self_driven(self):
        """自我驱动执行 - 核心执行循环"""
        logger.info(f"Starting self-driven execution for plan instance {self.id}")
        
        # 自动启动主任务
        self._start_main_task()
        
        # 立即处理初始状态变化（主任务启动）
        initial_changes = self._find_status_changes()
        if initial_changes:
            logger.info(f"Processing {len(initial_changes)} initial status changes")
            for task_id, old_status, new_status in initial_changes:
                await self._handle_task_status_change(task_id, old_status, new_status)
                # 标记为已处理
                task_instance = self.get_task_instance(task_id)
                if task_instance and task_instance.status_trace:
                    task_instance.status_trace[-1]['is_new'] = False
        
        while self.status == PlanInstanceStatus.RUNNING.value:
            # 查找需要执行的任务状态变化
            status_changes = self._find_status_changes()
            
            if not status_changes:
                # 没有状态变化，检查是否完成
                # 由PlannerAgent设置status为done，这里只检查
                if self._is_plan_completed():
                    # PlannerAgent已经设置了status为done和completed_at
                    logger.info(f"Plan instance {self.id} execution loop finished (status={self.status})")
                    break
                else:
                    # 等待状态变化或PlannerAgent设置done
                    await asyncio.sleep(0.1)
                    continue
            
            # 处理状态变化
            for task_id, old_status, new_status in status_changes:
                await self._handle_task_status_change(task_id, old_status, new_status)
                # 标记为已处理
                task_instance = self.get_task_instance(task_id)
                if task_instance and task_instance.status_trace:
                    task_instance.status_trace[-1]['is_new'] = False
            
            # 检查是否出错
            if self.status == PlanInstanceStatus.ERROR.value:
                logger.error(f"Plan instance {self.id} encountered error")
                break
        
        logger.info(f"Plan instance {self.id} execution finished with status: {self.status}")
    
    def _find_status_changes(self) -> List[tuple]:
        """查找状态变化"""
        changes = []
        print(f"[PlanInstance] Checking for status changes in {len(self.task_instances)} tasks")
        for task_instance in self.task_instances.values():
            print(f"[PlanInstance] Task {task_instance.task_id} has {len(task_instance.status_trace)} trace entries")
            if len(task_instance.status_trace) > 1:
                # 检查是否有新的状态变化
                last_trace = task_instance.status_trace[-1]
                print(f"[PlanInstance] Last trace: {last_trace}")
                if last_trace.get('is_new', False):
                    # 获取前一个状态
                    prev_status = task_instance.status_trace[-2]['status'] if len(task_instance.status_trace) > 1 else 'NotStarted'
                    changes.append((task_instance.task_id, prev_status, task_instance.status))
                    print(f"[PlanInstance] Found status change: {task_instance.task_id} {prev_status} -> {task_instance.status}")
        print(f"[PlanInstance] Found {len(changes)} status changes")
        return changes
    
    def _is_plan_completed(self) -> bool:
        """
        检查计划是否完成
        
        简单检查：plan_instance.status是否为done
        由PlannerAgent在验证完成后设置
        """
        return self.status == PlanInstanceStatus.DONE.value
    
    async def _handle_task_status_change(self, task_id: str, old_status: str, new_status: str):
        """处理任务状态变化"""
        print(f"[PlanInstance] Task {task_id} status changed from {old_status} to {new_status}")
        logger.info(f"Task {task_id} status changed from {old_status} to {new_status}")
        
        # 从 PlanInstance 中获取 listener_engine
        if not hasattr(self, '_listener_engine') or self._listener_engine is None:
            print(f"[PlanInstance] No listener engine available for plan instance {self.id}")
            logger.warning(f"No listener engine available for plan instance {self.id}")
            return
        
        # 查找被触发的侦听器
        print(f"[PlanInstance] Looking for triggered listeners for task {task_id} with status {new_status}")
        triggered_listeners = await self._listener_engine.find_triggered_listeners(self.id, task_id, new_status, self.plan, self)
        print(f"[PlanInstance] Found {len(triggered_listeners)} triggered listeners")
        
        # 执行被触发的侦听器（防止重复执行）
        for listener in triggered_listeners:
            # 检查该侦听器是否已执行过
            if listener.id in self._executed_listeners:
                print(f"[PlanInstance] Listener {listener.id} already executed, skipping")
                logger.info(f"Listener {listener.id} already executed for plan instance {self.id}, skipping")
                continue
            
            # 记录Listener被触发
            try:
                from src.utils.execution_logger import execution_logger
                execution_logger.listener_triggered(
                    plan_id=self.plan_id,
                    listener_id=listener.id,
                    trigger_task_id=listener.trigger_task_id,
                    trigger_condition=listener.trigger_condition
                )
            except:
                pass
            
            print(f"[PlanInstance] Executing listener {listener.id} for task {task_id}")
            logger.info(f"Executing listener {listener.id} for task {task_id}")
            result = await self._listener_engine.execute_listener(listener, self)
            print(f"[PlanInstance] Listener result: {result}")
            
            # 标记该侦听器已执行
            self._executed_listeners.add(listener.id)
            
            # 记录Listener执行结果
            try:
                from src.utils.execution_logger import execution_logger
                execution_logger.listener_executed(
                    plan_id=self.plan_id,
                    listener_id=listener.id,
                    success=result.get('success', False),
                    target_updates=result.get('task_updates', [])
                )
            except:
                pass
            
            # 应用侦听器结果
            await self._apply_listener_result(result)
    
    async def _apply_listener_result(self, result: Dict[str, Any]):
        """应用侦听器执行结果"""
        if result.get('success', False):
            # 应用任务更新（包括success_output中定义的状态更新）
            task_updates = result.get('task_updates', [])
            for update in task_updates:
                target_task_id = update.get('task_id')
                new_status = update.get('status')
                reason = update.get('reason', 'listener_execution')
                context_update = update.get('context', {})
                
                if target_task_id and new_status:
                    # 更新任务状态
                    self.update_task_status(target_task_id, new_status, reason)
                    
                    # 更新任务上下文
                    if context_update:
                        task_instance = self.get_task_instance(target_task_id)
                        if task_instance:
                            if not hasattr(task_instance, 'context') or task_instance.context is None:
                                task_instance.context = {}
                            task_instance.context.update(context_update)
                            print(f"[PlanInstance] Updated task {target_task_id} context: {context_update}")
        else:
            # 处理错误
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"Listener execution failed: {error_msg}")
            
            # 关键：失败时也要应用task_updates（包括设置001 Error的默认行为）
            task_updates = result.get('task_updates', [])
            print(f"[PlanInstance] Applying {len(task_updates)} task updates from failed listener")
            for update in task_updates:
                target_task_id = update.get('task_id')
                new_status = update.get('status')
                reason = update.get('reason', 'listener_failure')
                context_update = update.get('context', {})
                
                if target_task_id and new_status:
                    # 关键：先更新任务上下文，再更新状态
                    # 因为update_task_status会触发planner_callback，需要确保context已包含failed_listener_id
                    if context_update:
                        task_instance = self.get_task_instance(target_task_id)
                        if task_instance:
                            if not hasattr(task_instance, 'context') or task_instance.context is None:
                                task_instance.context = {}
                            task_instance.context.update(context_update)
                            print(f"[PlanInstance] Updated task {target_task_id} context BEFORE status update: {context_update}")
                    
                    # 然后更新任务状态（会触发planner_callback）
                    self.update_task_status(target_task_id, new_status, reason)
                    print(f"[PlanInstance] Updated task {target_task_id} status to {new_status}")
            
            # 如果主任务出错，标记计划实例为错误状态（但不终止，等待PlannerAgent重试）
            main_task = self.get_main_task_instance()
            if main_task and main_task.status == "Error":
                logger.warning(f"Main task is Error, waiting for PlannerAgent retry...")
                # 注意：不设置plan_instance.status为error，让它继续运行等待重试
    
    def _start_main_task(self):
        """启动主任务"""
        main_task = self.get_main_task_instance()
        if main_task and main_task.status == "NotStarted":
            # 更新主任务状态为 Running
            self.update_task_status(main_task.task_id, "Running", "plan_instance_started")
            logger.info(f"Main task {main_task.task_id} started automatically")
    
    async def register_to_listener_engine(self, listener_engine):
        """注册到侦听引擎"""
        try:
            # 保存 listener_engine 引用
            self._listener_engine = listener_engine
            
            success = await listener_engine.register_plan_instance(self)
            if success:
                # 设置 ListenerEngine 引用，用于事件发布
                self.set_listener_engine(listener_engine)
                logger.info(f"Plan instance {self.id} registered to listener engine")
            else:
                logger.error(f"Failed to register plan instance {self.id} to listener engine")
            return success
        except Exception as e:
            logger.error(f"Error registering plan instance {self.id} to listener engine: {e}")
            return False
    
    def _initialize_context(self):
        """初始化实例上下文"""
        # 系统上下文来自计划对象
        system_context = {
            "plan_id": self.plan_id,
            "plan_name": self.plan.name if self.plan else "",
            "plan_description": self.plan.description if self.plan else "",
            "tasks": self.task_instances,
            "listeners": self.plan.listeners if self.plan else []
        }
        
        # 用户上下文来自启动提示
        user_context = {
            "prompt": self.prompt,
            "user_input": self.prompt
        }
        
        # 合并上下文
        self.context = {
            "values": {
                "system": system_context,
                "user": user_context
            },
            "metadata": {
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "started_at": datetime.now().isoformat()
            }
        }
    
    def complete(self):
        """完成实例"""
        if self.status == PlanInstanceStatus.RUNNING.value:
            self.status = PlanInstanceStatus.DONE.value
            self.completed_at = datetime.now()
            self.updated_at = datetime.now()
    
    def fail(self, error_info: Optional[Dict[str, Any]] = None):
        """标记实例为失败"""
        if self.status == PlanInstanceStatus.RUNNING.value:
            self.status = PlanInstanceStatus.ERROR.value
            self.completed_at = datetime.now()
            self.updated_at = datetime.now()
            if error_info:
                self.error_info = error_info
    
    def cancel(self):
        """取消实例"""
        if self.status in [PlanInstanceStatus.NOT_STARTED.value, PlanInstanceStatus.RUNNING.value]:
            self.status = PlanInstanceStatus.CANCELLED.value
            self.completed_at = datetime.now()
            self.updated_at = datetime.now()
    
    def get_context_value(self, key: str, default: Any = None) -> Any:
        """获取上下文中的值"""
        return self.context.get("values", {}).get(key, default)
    
    def set_context_value(self, key: str, value: Any):
        """设置上下文中的值"""
        if "values" not in self.context:
            self.context["values"] = {}
        self.context["values"][key] = value
        self.updated_at = datetime.now()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        return self.context.get("metadata", {})
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]):
        """设置元数据"""
        self.context["metadata"] = value
        self.updated_at = datetime.now()
    
    def add_task_instance(self, task_instance: 'TaskInstance'):
        """添加任务实例"""
        self.task_instances[task_instance.task_id] = task_instance
        self.updated_at = datetime.now()
    
    def update_task_status(self, task_id: str, new_status: str, reason: str = "manual_update"):
        """更新任务状态（由 ListenerEngine 调用）"""
        task_instance = self.get_task_instance(task_id)
        if task_instance:
            old_status = task_instance.status
            task_instance.update_status(new_status, reason)
            
            # 更新 PlanInstance 的更新时间
            self.updated_at = datetime.now()
            
            # 发布状态变化事件
            self._publish_task_status_change_event(task_instance, old_status, new_status, reason)
    
    def _publish_task_status_change_event(self, task_instance: 'TaskInstance', old_status: str, new_status: str, reason: str):
        """发布任务状态变化事件"""
        logger.info(f"Task {task_instance.task_id} status changed: {old_status} -> {new_status} ({reason})")
        
        # 触发planner回调（任务001变为Done或Error时触发）
        if hasattr(self, '_listener_engine') and self._listener_engine:
            # 获取planner回调
            planner_callback = self._listener_engine._planner_callback
            print(f"[PlanInstance] _listener_engine exists, planner_callback exists: {planner_callback is not None}")
            if planner_callback:
                # 构建plan_context
                plan_context = {
                    "plan_id": self.plan_id,
                    "plan_instance_id": self.id,
                    "main_task_id": "001",  # 主任务ID
                    "tasks": {}
                }
                
                # 添加所有任务的状态信息
                for tid, ti in self.task_instances.items():
                    plan_context["tasks"][tid] = {
                        "status": ti.status,
                        "context": ti.context if hasattr(ti, 'context') else {}
                    }
                
                # 异步调用planner回调
                import asyncio
                try:
                    logger.info(f"[PlanInstance] Calling planner callback for task {task_instance.task_id}: {old_status}->{new_status}")
                    logger.info(f"[PlanInstance] plan_context keys: {plan_context.keys()}")
                    logger.info(f"[PlanInstance] is main task: {task_instance.task_id == plan_context.get('main_task_id')}")
                    
                    # 调用回调函数
                    result = planner_callback(self.plan_id, task_instance.task_id, old_status, new_status, plan_context)
                    
                    # 如果返回的是coroutine，需要异步执行
                    if asyncio.iscoroutine(result):
                        logger.info(f"[PlanInstance] Planner callback returned coroutine, creating background task")
                        try:
                            # 创建异步任务并保存引用
                            # 不能直接await，因为这是在同步方法中调用的
                            self._planner_verification_task = asyncio.create_task(result)
                            
                            # 添加完成回调
                            def _log_completion(t):
                                try:
                                    if t.exception():
                                        logger.error(f"[PlanInstance] Planner verification failed: {t.exception()}")
                                    else:
                                        logger.info(f"[PlanInstance] Planner verification completed successfully")
                                except Exception as e:
                                    logger.error(f"Error in completion callback: {e}")
                            
                            self._planner_verification_task.add_done_callback(_log_completion)
                            logger.info(f"[PlanInstance] Created planner verification task")
                        except Exception as e:
                            logger.error(f"[PlanInstance] Failed to create planner verification task: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                    else:
                        logger.info(f"[PlanInstance] Planner callback called (returned non-coroutine)")
                except Exception as e:
                    logger.error(f"[PlanInstance] Error calling planner callback: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.debug("No planner callback registered")
        else:
            logger.debug("No listener engine available for event publishing")
    
    def set_listener_engine(self, listener_engine):
        """设置 ListenerEngine 引用"""
        self._listener_engine = listener_engine
    
    def get_task_instance(self, task_id: str) -> Optional['TaskInstance']:
        """获取任务实例"""
        return self.task_instances.get(task_id)
    
    def get_all_task_instances(self) -> List['TaskInstance']:
        """获取所有任务实例"""
        return list(self.task_instances.values())
    
    def get_main_task_instance(self) -> Optional['TaskInstance']:
        """获取主任务实例"""
        for task_instance in self.task_instances.values():
            if task_instance.is_main_task():
                return task_instance
        return None
    
    def get_execution_trace(self) -> Dict[str, Any]:
        """
        获取计划执行追踪信息（执行清单+验证摘要）
        
        返回格式:
        {
            "checklist": [
                {
                    "agent_id": "hr",
                    "task_id": "002",
                    "task_name": "新员工注册",
                    "status": "executed_and_verified",  # 或 "executed_but_unverified" 或 "verification_failed"
                    "tools_used": ["query_profile"],
                    "icon": "✅"  # 或 "⚠️" 或 "❌"
                },
                ...
            ],
            "summary": {
                "overall_status": "passed",  # 或 "failed"
                "has_explicit_failure": false,
                "verified_count": 3,
                "unable_to_verify_count": 2,
                "failed_count": 0,
                "total_count": 5
            },
            "verification_completed": true  # planner_verification是否完成
        }
        """
        main_task = self.get_main_task_instance()
        if not main_task or not hasattr(main_task, 'context'):
            return {
                "checklist": [],
                "summary": {
                    "overall_status": "unknown",
                    "verified_count": 0,
                    "unable_to_verify_count": 0,
                    "failed_count": 0,
                    "total_count": 0
                },
                "verification_completed": False
            }
        
        verification_results = main_task.context.get("verification_results", {})
        planner_verification = main_task.context.get("planner_verification")
        
        return {
            "checklist": verification_results.get("_checklist", []),
            "summary": verification_results.get("_summary", {
                "overall_status": "unknown",
                "verified_count": 0,
                "unable_to_verify_count": 0,
                "failed_count": 0,
                "total_count": 0
            }),
            "verification_completed": planner_verification == "completed"
        }
    
    def update_task_instance_status(self, task_id: str, status: str, context: Dict[str, Any] = None):
        """更新任务实例状态"""
        task_instance = self.get_task_instance(task_id)
        if task_instance:
            task_instance.status = status
            if context:
                task_instance.context.update(context)
            task_instance.updated_at = datetime.now()
            self.updated_at = datetime.now()
    
    def get_task_instances_by_status(self, status: str) -> List['TaskInstance']:
        """根据状态获取任务实例"""
        return [task for task in self.task_instances.values() if task.status == status]
