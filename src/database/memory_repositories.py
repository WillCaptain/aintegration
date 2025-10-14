"""
内存版本的Repository实现

将所有数据库操作mock成内存操作，避免数据库依赖
"""

import logging
from typing import Dict, List, Optional, Any
import copy
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
        # 版本历史：plan_id -> [config_snapshot, ...]
        self.plan_versions: Dict[str, List[Dict[str, Any]]] = {}
    
    async def create(self, plan: Plan) -> str:
        """创建计划"""
        try:
            plan_id = plan.id or f"plan_{self.next_id:06d}"
            self.next_id += 1
            
            plan.id = plan_id
            # 只有在没有设置created_at时才使用当前时间
            if plan.created_at is None:
                plan.created_at = datetime.now()
            self.plans[plan_id] = plan
            # 初始化版本历史（保存创建时的快照）
            self.plan_versions[plan_id] = [copy.deepcopy(plan.to_dict())]
            
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
    
    async def update(self, plan_id: str, updates: Dict, expected_version: Optional[str] = None):
        """更新计划"""
        try:
            if plan_id in self.plans:
                plan = self.plans[plan_id]
                # 乐观锁：校验预期版本（如果提供）
                if expected_version is not None:
                    current_version = None
                    try:
                        current_version = plan.metadata.get("version") if hasattr(plan, 'metadata') and plan.metadata else None
                    except Exception:
                        current_version = None
                    if current_version != expected_version:
                        raise Exception(f"version conflict: expected={expected_version}, current={current_version}")
                def deep_merge(dst, src):
                    for k, v in src.items():
                        if (
                            k in dst and isinstance(dst[k], dict) and isinstance(v, dict)
                        ):
                            deep_merge(dst[k], v)
                        else:
                            dst[k] = v

                for key, value in updates.items():
                    if key == "metadata" and isinstance(value, dict) and hasattr(plan, 'metadata'):
                        # 更新 metadata 字段
                        if not hasattr(plan, 'metadata') or plan.metadata is None:
                            plan.metadata = {}
                        deep_merge(plan.metadata, value)
                    elif hasattr(plan, key):
                        setattr(plan, key, value)
                plan.updated_at = datetime.now()
                # 追加最新版本快照（保存整个 Plan 对象的字典表示）
                self.plan_versions.setdefault(plan_id, [])
                self.plan_versions[plan_id].append(copy.deepcopy(plan.to_dict()))
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
                # 软删过滤（除非显式包含）
                include_deleted = bool(criteria.get("include_deleted"))
                is_deleted = False
                try:
                    # 兼容两种元数据路径：顶层metadata或config.metadata
                    meta = {}
                    try:
                        meta = plan.config.get("config", {}).get("metadata", {})
                    except Exception:
                        meta = {}
                    if not meta:
                        meta = plan.config.get("metadata", {})
                    is_deleted = meta.get("deleted") is True
                except Exception:
                    is_deleted = False
                if is_deleted and not include_deleted:
                    continue
                
                # 名称过滤
                if criteria.get("name"):
                    name_pattern = criteria["name"].lower()
                    if name_pattern not in plan.name.lower():
                        continue
                
                # 标签过滤
                if criteria.get("tags"):
                    required_tags = criteria["tags"]
                    if not isinstance(required_tags, list):
                        required_tags = [required_tags]
                    
                    plan_tags = []
                    try:
                        meta = plan.config.get("config", {}).get("metadata", {}) or plan.config.get("metadata", {})
                        plan_tags = meta.get("tags", [])
                        if not isinstance(plan_tags, list):
                            plan_tags = []
                    except Exception:
                        plan_tags = []
                    
                    # 所有要求的标签都必须存在
                    if not all(tag in plan_tags for tag in required_tags):
                        continue
                
                # 状态过滤
                if criteria.get("status"):
                    required_status = criteria["status"]
                    plan_status = None
                    try:
                        meta = plan.config.get("config", {}).get("metadata", {}) or plan.config.get("metadata", {})
                        plan_status = meta.get("status")
                    except Exception:
                        plan_status = None
                    
                    if plan_status != required_status:
                        continue
                
                # 时间范围过滤
                if criteria.get("created_after"):
                    try:
                        from datetime import datetime
                        created_after = datetime.fromisoformat(criteria["created_after"].replace('Z', '+00:00'))
                        # 仅包含在该时间之后（含等于）的计划
                        if plan.created_at and plan.created_at < created_after:
                            continue
                    except Exception:
                        pass
                
                if criteria.get("created_before"):
                    try:
                        from datetime import datetime
                        created_before = datetime.fromisoformat(criteria["created_before"].replace('Z', '+00:00'))
                        # 仅包含在该时间之前（含等于）的计划
                        if plan.created_at and plan.created_at > created_before:
                            continue
                    except Exception:
                        pass
                
                # 全文搜索
                if criteria.get("query"):
                    query = criteria["query"].lower()
                    searchable_text = f"{plan.name} {plan.description}".lower()
                    if query not in searchable_text:
                        continue
                
                results.append(plan)
            
            # 排序
            sort_by = criteria.get("sort_by", "created_at")
            sort_order = criteria.get("sort_order", "desc")
            
            if sort_by == "name":
                results.sort(key=lambda x: x.name, reverse=(sort_order == "desc"))
            elif sort_by == "created_at":
                results.sort(key=lambda x: x.created_at or datetime.min, reverse=(sort_order == "desc"))
            elif sort_by == "updated_at":
                results.sort(key=lambda x: x.updated_at or datetime.min, reverse=(sort_order == "desc"))
            
            # 分页
            limit = criteria.get("limit")
            offset = criteria.get("offset", 0)
            
            if limit is not None:
                results = results[offset:offset + limit]
            elif offset > 0:
                results = results[offset:]
            
            return results
        except Exception as e:
            logger.error(f"Memory: Failed to search plans: {e}")
            raise

    async def soft_delete(self, plan_id: str) -> bool:
        """软删除：在metadata.deleted打标，不物理移除"""
        try:
            if plan_id not in self.plans:
                return False
            plan = self.plans[plan_id]
            if "metadata" not in plan.config or not isinstance(plan.config.get("metadata"), dict):
                plan.config["metadata"] = {}
            plan.config["metadata"]["deleted"] = True
            plan.updated_at = datetime.now()
            # 记录快照
            self.plan_versions.setdefault(plan_id, [])
            self.plan_versions[plan_id].append(copy.deepcopy(plan.config))
            logger.info(f"Memory: Soft-deleted plan {plan_id}")
            return True
        except Exception as e:
            logger.error(f"Memory: Failed to soft delete plan {plan_id}: {e}")
            raise
    
    async def list_all(self, limit: int = 100, offset: int = 0) -> List[Plan]:
        """列出所有计划"""
        try:
            plans_list = list(self.plans.values())
            return plans_list[offset:offset + limit]
        except Exception as e:
            logger.error(f"Memory: Failed to list plans: {e}")
            raise

    async def get_versions(self, plan_id: str) -> List[Dict[str, Any]]:
        """获取计划的版本历史（按时间顺序）"""
        try:
            return [copy.deepcopy(cfg) for cfg in self.plan_versions.get(plan_id, [])]
        except Exception as e:
            logger.error(f"Memory: Failed to get plan versions {plan_id}: {e}")
            raise

    async def rollback(self, plan_id: str, target_version: str) -> bool:
        """回滚到某个版本号（按 metadata.version 匹配）"""
        try:
            if plan_id not in self.plans:
                return False
            history = self.plan_versions.get(plan_id, [])
            target_snapshot = None
            for snapshot in history:
                try:
                    if snapshot.get("metadata", {}).get("version") == target_version:
                        target_snapshot = snapshot
                except Exception:
                    continue
            if target_snapshot is None:
                return False
            # 应用回滚
            plan = self.plans[plan_id]
            plan.config = copy.deepcopy(target_snapshot)
            plan.updated_at = datetime.now()
            # 记录一次回滚后的快照
            self.plan_versions.setdefault(plan_id, [])
            self.plan_versions[plan_id].append(copy.deepcopy(plan.config))
            logger.info(f"Memory: Rolled back plan {plan_id} to version {target_version}")
            return True
        except Exception as e:
            logger.error(f"Memory: Failed to rollback plan {plan_id}: {e}")
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
                # 合并上下文，保留既有键（如 retry_info），仅更新 values 子项
                existing_ctx = task.context if isinstance(task.context, dict) else {}
                values_ctx = existing_ctx.get("values", {})
                # 传入的 context 视为 values 的增量更新
                if isinstance(context, dict):
                    values_ctx.update(context)
                existing_ctx["values"] = values_ctx
                # 同步记录当前状态（保持兼容，很多测试依赖 context.status）
                existing_ctx["status"] = status

                task.status = status
                task.context = existing_ctx
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
        """获取监听特定任务的侦听器（支持 trigger_task_id 为列表或逗号分隔）"""
        try:
            results: List[Listener] = []
            for listener in self.listeners.values():
                trig = listener.trigger_task_id
                ids: List[str] = []
                if isinstance(trig, list):
                    ids = [str(x).strip() for x in trig]
                elif isinstance(trig, str):
                    if "," in trig:
                        ids = [x.strip() for x in trig.split(",")]
                    else:
                        ids = [trig.strip()]
                else:
                    ids = [str(trig).strip()]
                if task_id in ids:
                    results.append(listener)
            return results
        except Exception as e:
            logger.error(f"Memory: Failed to get listeners for trigger task {task_id}: {e}")
            raise
    
    async def get_by_trigger(self, task_id: str, status: str) -> List[Listener]:
        """获取特定触发条件的侦听器（与 get_by_trigger_task 相同的触发集合过滤）"""
        try:
            results: List[Listener] = []
            for listener in self.listeners.values():
                trig = listener.trigger_task_id
                ids: List[str] = []
                if isinstance(trig, list):
                    ids = [str(x).strip() for x in trig]
                elif isinstance(trig, str):
                    if "," in trig:
                        ids = [x.strip() for x in trig.split(",")]
                    else:
                        ids = [trig.strip()]
                else:
                    ids = [str(trig).strip()]
                if task_id in ids:
                    # 基础过滤，具体条件由引擎判定
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

