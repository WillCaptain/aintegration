"""
计划模块

负责Plan和Task的持久化管理，集成侦听引擎和任务驱动器
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..models.plan import Plan, PlanStatus
from ..models.task import Task, TaskStatus
from ..models.listener import Listener, ListenerType
from ..database.memory_repositories import MemoryPlanRepository, MemoryTaskRepository, MemoryListenerRepository
from ..core.listener_engine import ListenerEngine
from ..core.task_driver import TaskDriver
from ..infrastructure.llm_client import build_llm_client
from ..infrastructure.adk_integration import AgentRuntime
from ..infrastructure.a2a_client import A2AClient, DefaultA2AClient
from ..agents.planner_agent import PlannerAgent

logger = logging.getLogger(__name__)

class PlanManager:
    """计划管理器"""
    
    def __init__(self, plan_repo: MemoryPlanRepository):
        self.plan_repo = plan_repo
    
    async def create_plan(self, plan_config: Dict) -> str:
        """创建新的执行计划"""
        try:
            # 验证必需字段
            plan_id = plan_config.get("plan_id")
            if not plan_id:
                raise ValueError("plan_id is required")
            
            # created_at 支持从配置中传入（ISO8601），否则使用当前时间
            created_at = datetime.now()
            try:
                if plan_config.get("created_at"):
                    iso = plan_config["created_at"]
                    # 处理不同的时间格式
                    if iso.endswith('Z'):
                        iso = iso[:-1] + '+00:00'
                    created_at = datetime.fromisoformat(iso)
            except Exception as e:
                print(f"Warning: Failed to parse created_at '{plan_config.get('created_at')}': {e}")
                created_at = datetime.now()

            plan = Plan(
                id=plan_id,
                name=plan_config.get("name", "未命名计划"),
                description=plan_config.get("description") or plan_config.get("prompt") or "",
                config=plan_config,
                main_task_id=plan_config.get("main_task_id"),
                created_at=created_at
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
            # 兼容旧签名：不含 expected_version
            await self.plan_repo.update(plan_id, updates)
            logger.info(f"Updated plan {plan_id}")
        except Exception as e:
            logger.error(f"Failed to update plan {plan_id}: {e}")
            raise

    async def update_plan_with_expected(self, plan_id: str, updates: Dict, expected_version: Optional[str] = None):
        """更新计划（支持乐观锁 expected_version）"""
        try:
            await self.plan_repo.update(plan_id, updates, expected_version=expected_version)
            logger.info(f"Updated plan {plan_id} with expected_version={expected_version}")
        except Exception as e:
            logger.error(f"Failed to update plan {plan_id} with expected: {e}")
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

    async def soft_delete_plan(self, plan_id: str) -> bool:
        """软删除计划（metadata.deleted=True）"""
        return await self.plan_repo.soft_delete(plan_id)

    async def hard_delete_plan(self, plan_id: str) -> bool:
        """硬删除计划：需先通过引用检查，无引用方可删除"""
        # 引用检查占位：真实实现应检查任务、监听、执行记录等
        # 这里内存实现简单检查是否存在任务或监听
        raise NotImplementedError("hard_delete_plan is not implemented for memory repo yet")

    async def get_plan_versions(self, plan_id: str) -> List[Dict[str, Any]]:
        """获取计划版本历史"""
        return await self.plan_repo.get_versions(plan_id)

    async def rollback_plan(self, plan_id: str, target_version: str) -> bool:
        """回滚计划到指定版本号"""
        return await self.plan_repo.rollback(plan_id, target_version)

class TaskManager:
    """任务管理器"""
    
    def __init__(self, task_repo: MemoryTaskRepository):
        self.task_repo = task_repo
    
    async def create_task(self, task_config: Dict) -> str:
        """创建任务"""
        try:
            # 验证必需字段
            task_id = task_config.get("task_id")
            if not task_id:
                raise ValueError("task_id is required")
            
            name = task_config.get("name")
            if not name:
                raise ValueError("task name is required")
            
            task = Task(
                id=task_id,
                plan_id=task_config.get("plan_id"),
                name=name,
                prompt=task_config.get("prompt", ""),
                status="NotStarted",
                context={"status": "NotStarted", "values": {}, "metadata": task_config.get("metadata", {})},
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
                listener_type=listener_config.get("listener_type"),
                agent_id=listener_config.get("agent_id"),
                action_prompt=listener_config.get("action_prompt"),
                code_snippet=listener_config.get("code_snippet"),
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
    
    async def get_listener(self, listener_id: str) -> Optional[Listener]:
        """获取单个侦听器"""
        return await self.listener_repo.get_by_id(listener_id)


class PlanModule:
    """计划模块主类"""
    
    def __init__(
        self, 
        plan_repo: MemoryPlanRepository, 
        task_repo: MemoryTaskRepository, 
        listener_repo: MemoryListenerRepository,
        adk_integration: Optional[AgentRuntime] = None,
        a2a_client: Optional[A2AClient] = None
    ):
        self.plan_manager = PlanManager(plan_repo)
        self.task_manager = TaskManager(task_repo)
        self.listener_manager = ListenerManager(listener_repo)
        self.plan_repo = plan_repo
        self.task_repo = task_repo
        self.listener_repo = listener_repo
        
        # 初始化任务驱动器和侦听引擎
        self.task_driver = TaskDriver(adk_integration=adk_integration)
        self.listener_engine = ListenerEngine(task_repo, listener_repo, plan_repo, self.task_driver)
        
        # 初始化 LLM 客户端
        self.llm_client = build_llm_client()

        # 初始化 A2A 与 PlannerAgent（默认使用内置A2A实现，可替换为官方实现）
        self.a2a_client = a2a_client or DefaultA2AClient()
        self.planner_agent = PlannerAgent(self.a2a_client, self.llm_client)

        # 将Planner回调注册到侦听引擎
        self.listener_engine.set_planner_callback(
            lambda plan_id, task_id, old_status, new_status, plan_ctx: self.planner_agent.on_task_status_change(
                self, plan_id, task_id, old_status, new_status, plan_ctx
            )
        )

    # 便捷设置：允许在运行时注入/替换 A2A 客户端（例如测试中绑定实际的 A2AServer）
    def set_a2a_client(self, a2a_client: A2AClient):
        self.a2a_client = a2a_client
        self.planner_agent = PlannerAgent(self.a2a_client)
        # 重新注册回调以使用新的实例
        self.listener_engine.set_planner_callback(
            lambda plan_id, task_id, old_status, new_status, plan_ctx: self.planner_agent.on_task_status_change(
                self, plan_id, task_id, old_status, new_status, plan_ctx
            )
        )
        
        # 注册孤立状态变化的处理
        self._register_orphaned_change_handler()
    
    def _register_orphaned_change_handler(self):
        """注册孤立状态变化的处理"""
        # 这里可以注册回调函数，当发生孤立状态变化时调用
        pass
    
    async def start(self):
        """启动计划模块"""
        try:
            # 启动侦听引擎
            await self.listener_engine.start()
            logger.info("Plan Module started")
        except Exception as e:
            logger.error(f"Failed to start Plan Module: {e}")
            raise
    
    async def stop(self):
        """停止计划模块"""
        try:
            # 停止侦听引擎
            await self.listener_engine.stop()
            logger.info("Plan Module stopped")
        except Exception as e:
            logger.error(f"Error stopping Plan Module: {e}")
    
    async def execute_plan(self, plan_id: str) -> Dict[str, Any]:
        """执行计划：从 repo 反序列化 Plan 并执行"""
        try:
            # 从 repo 获取 Plan 对象
            plan = await self.plan_manager.get_plan(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return {
                    "success": False,
                    "error": f"Plan {plan_id} not found"
                }
            
            # 使用 Plan 对象的 execute 方法
            return await plan.execute(self)
            
        except Exception as e:
            logger.error(f"Error executing plan {plan_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_plan_from_config(self, plan_config: Dict[str, Any]) -> str:
        """从配置创建计划"""
        try:
            # 创建计划
            plan_id = await self.plan_manager.create_plan(plan_config)
            
            # 创建任务
            for task_config in plan_config.get("tasks", []):
                task_config["plan_id"] = plan_id
                await self.task_manager.create_task(task_config)
            
            # 创建侦听器
            for listener_config in plan_config.get("listeners", []):
                listener_config["plan_id"] = plan_id
                await self.listener_manager.create_listener(listener_config)
            
            logger.info(f"Created plan {plan_id} with {len(plan_config.get('tasks', []))} tasks and {len(plan_config.get('listeners', []))} listeners")
            return plan_id
            
        except Exception as e:
            logger.error(f"Error creating plan from config: {e}")
            raise
    
    async def replan(self, plan_id: str, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """重新规划：更新计划配置并重新执行"""
        try:
            # 从 repo 获取 Plan 对象
            plan = await self.plan_manager.get_plan(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return {
                    "success": False,
                    "error": f"Plan {plan_id} not found"
                }
            
            # 使用 Plan 对象的 replan 方法
            return await plan.replan(self, new_config)
            
        except Exception as e:
            logger.error(f"Error replanning {plan_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_listener_for_orphaned_change(self, task_id: str, status: str, plan_id: str, plan_context: Dict[str, Any]) -> Optional[Listener]:
        """为孤立的状态变化生成侦听器"""
        try:
            # 使用LLM生成侦听器配置
            prompt = f"""
任务 {task_id} 的状态变更为 {status}，但没有对应的侦听器处理。
请根据以下上下文生成一个合适的侦听器配置：

计划上下文：
{json.dumps(plan_context, ensure_ascii=False, indent=2)}

请返回JSON格式的侦听器配置，包含：
- listener_id: 侦听器ID
- trigger_task_id: 触发任务ID
- trigger_condition: 触发条件
- action_condition: 行动条件
- listener_type: 侦听器类型（agent或code）
- agent_id: 智能体ID（如果是agent类型）
- action_prompt: 行动提示（如果是agent类型）
- code_snippet: 代码片段（如果是code类型）
- success_output: 成功输出配置
- failure_output: 失败输出配置
"""
            
            response = await self.llm_client.generate(prompt)
            
            # 解析响应
            try:
                listener_config = json.loads(response)
                listener_config["plan_id"] = plan_id
                
                # 创建侦听器
                listener_id = await self.listener_manager.create_listener(listener_config)
                logger.info(f"Generated listener {listener_id} for orphaned change: {task_id} -> {status}")
                
                return await self.listener_manager.get_listener(listener_id)
                
            except json.JSONDecodeError:
                logger.error(f"Failed to parse LLM response as JSON: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating listener for orphaned change: {e}")
            return None
    
    async def get_plan_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """获取计划状态"""
        try:
            plan = await self.plan_manager.get_plan(plan_id)
            if not plan:
                return None
            
            # 获取所有任务
            tasks = await self.task_manager.get_plan_tasks(plan_id)
            
            return {
                "plan_id": plan_id,
                "plan_name": plan.name,
                "plan_status": plan.status,
                "main_task_id": plan.main_task_id,
                "tasks": [
                    {
                        "task_id": task.id,
                        "name": task.name,
                        "status": task.status,
                        "context": task.context
                    }
                    for task in tasks
                ],
                "created_at": plan.created_at,
                "started_at": plan.started_at,
                "completed_at": plan.completed_at
            }
        except Exception as e:
            logger.error(f"Error getting plan status: {e}")
            return None

    async def get_plan_versions(self, plan_id: str) -> List[Dict[str, Any]]:
        """获取计划版本历史（转发至仓库）"""
        try:
            return await self.plan_manager.plan_repo.get_versions(plan_id)
        except Exception as e:
            logger.error(f"Error getting plan versions: {e}")
            return []

    async def rollback_plan(self, plan_id: str, target_version: str) -> bool:
        """回滚计划到指定版本（转发至仓库）"""
        try:
            return await self.plan_manager.plan_repo.rollback(plan_id, target_version)
        except Exception as e:
            logger.error(f"Error rolling back plan {plan_id} to {target_version}: {e}")
            return False

    async def search_plans(self, 
                          name: Optional[str] = None,
                          tags: Optional[List[str]] = None,
                          status: Optional[str] = None,
                          query: Optional[str] = None,
                          created_after: Optional[str] = None,
                          created_before: Optional[str] = None,
                          sort_by: str = "created_at",
                          sort_order: str = "desc",
                          limit: Optional[int] = None,
                          offset: int = 0,
                          include_deleted: bool = False) -> List[Plan]:
        """搜索计划"""
        try:
            criteria = {
                "name": name,
                "tags": tags,
                "status": status,
                "query": query,
                "created_after": created_after,
                "created_before": created_before,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "limit": limit,
                "offset": offset,
                "include_deleted": include_deleted
            }
            
            # 移除None值
            criteria = {k: v for k, v in criteria.items() if v is not None}
            
            return await self.plan_manager.plan_repo.search(criteria)
        except Exception as e:
            logger.error(f"Error searching plans: {e}")
            return []
