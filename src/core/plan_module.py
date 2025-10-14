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
from ..models.plan_instance import PlanInstance, PlanInstanceStatus
from ..models.task_instance import TaskInstance, TaskInstanceStatus
from ..database.memory_repositories import MemoryPlanRepository, MemoryTaskRepository, MemoryListenerRepository
from ..database.instance_repositories import MemoryPlanInstanceRepository, MemoryTaskInstanceRepository
from ..core.listener_engine import ListenerEngine
from ..core.task_driver import TaskDriver
from ..infrastructure.llm_client import build_llm_client
from ..infrastructure.adk_integration import AgentRuntime
from ..infrastructure.a2a_client import A2AClient, DefaultA2AClient
from ..agents.planner_agent import PlannerAgent
from .agent_config_loader import agent_config_loader

logger = logging.getLogger(__name__)

class PlanManager:
    """计划管理器"""
    
    def __init__(self, plan_repo: MemoryPlanRepository):
        self.plan_repo = plan_repo
    
    async def create_plan(self, plan_config: Dict) -> Plan:
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
                metadata=plan_config.get("metadata", {}),  # 提取元数据
                tasks=plan_config.get("tasks", []),  # 填充任务元数据
                listeners=plan_config.get("listeners", []),  # 填充侦听器元数据
                main_task_id=plan_config.get("main_task_id"),
                created_at=created_at
            )
            
            plan_id = await self.plan_repo.create(plan)
            plan.id = plan_id  # 设置生成的ID
            logger.info(f"Created plan {plan_id}")
            return plan  # 返回Plan对象而不是ID
            
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

    async def rollback_plan(self, plan_id: str, target_version: str) -> bool:
        """回滚计划到指定版本号"""
        return await self.plan_repo.rollback(plan_id, target_version)




class PlanModule:
    """计划模块主类"""
    
    def __init__(
        self, 
        plan_repo: MemoryPlanRepository, 
        task_repo: MemoryTaskRepository, 
        listener_repo: MemoryListenerRepository,
        plan_instance_repo: Optional[MemoryPlanInstanceRepository] = None,
        task_instance_repo: Optional[MemoryTaskInstanceRepository] = None,
        adk_integration: Optional[AgentRuntime] = None,
        a2a_client: Optional[A2AClient] = None,
        auto_register_agents: bool = True
    ):
        self.plan_manager = PlanManager(plan_repo)
        self.plan_repo = plan_repo
        self.task_repo = task_repo
        self.listener_repo = listener_repo
        
        # 实例仓库
        self.plan_instance_repo = plan_instance_repo or MemoryPlanInstanceRepository()
        self.task_instance_repo = task_instance_repo or MemoryTaskInstanceRepository()
        
        # 保存adk_integration引用
        self.adk_integration = adk_integration
        
        # 初始化任务驱动器和侦听引擎
        self.task_driver = TaskDriver(adk_integration=adk_integration)
        self.listener_engine = ListenerEngine(task_repo, listener_repo, plan_repo, self.task_driver)
        
        # A2A 客户端和 Planner Agent
        self.a2a_client = a2a_client
        self.planner_agent = None
        self.auto_register_agents = auto_register_agents
        
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
        self.planner_agent = PlannerAgent(self.a2a_client, self.llm_client)
        # 重新注册回调以使用新的实例
        self.listener_engine.set_planner_callback(
            lambda plan_id, task_id, old_status, new_status, plan_ctx: self.planner_agent.on_task_status_change(
                self, plan_id, task_id, old_status, new_status, plan_ctx
            )
        )
        # 连接引擎日志到 Planner 轨迹
        self.planner_agent.attach_engine_logger(self.listener_engine)
        
        # 注册孤立状态变化的处理
        self._register_orphaned_change_handler()
    
    def _register_orphaned_change_handler(self):
        """注册孤立状态变化的处理"""
        # 这里可以注册回调函数，当发生孤立状态变化时调用
        pass
    
    async def _auto_register_agents(self):
        """自动注册所有 BizAgent 到 A2A Server"""
        try:
            logger.info("Starting auto-registration of agents...")
            
            # 加载所有 Agent 配置
            agent_configs = agent_config_loader.load_all_agents()
            logger.info(f"Loaded {len(agent_configs)} agent configurations: {list(agent_configs.keys())}")
            
            if not agent_configs:
                logger.warning("No agent configurations found")
                return
            
            # 获取所有 Agent 卡片
            agent_cards = agent_config_loader.get_all_agent_cards()
            logger.info(f"Generated {len(agent_cards)} agent cards")
            
            # 批量注册到 A2A Server
            if hasattr(self.a2a_client, 'a2a_server') and self.a2a_client.a2a_server:
                registered_count = await self.a2a_client.a2a_server.register_agents_batch(agent_cards)
                logger.info(f"Auto-registered {registered_count} agents to A2A Server")
            else:
                logger.warning("A2A Server not available for auto-registration")
                
        except Exception as e:
            logger.error(f"Failed to auto-register agents: {e}")
            raise
    
    async def start(self):
        """启动计划模块"""
        try:
            # 连接AgentRuntime和A2AServer（如果都存在）
            if self.adk_integration and hasattr(self.a2a_client, 'a2a_server') and self.a2a_client.a2a_server:
                self.a2a_client.a2a_server.set_agent_runtime(self.adk_integration)
                logger.info("AgentRuntime connected to A2AServer")
            
            # 自动注册 Agent（如果启用）
            if self.auto_register_agents and self.a2a_client:
                await self._auto_register_agents()
            
            # 初始化 Planner Agent
            if self.a2a_client:
                self.planner_agent = PlannerAgent(self.a2a_client, self.llm_client)
                # 注册 Planner 回调（使用 lambda 传递 plan_module）
                self.listener_engine.set_planner_callback(
                    lambda plan_id, task_id, old_status, new_status, plan_ctx: self.planner_agent.on_task_status_change(
                        self, plan_id, task_id, old_status, new_status, plan_ctx
                    )
                )
                # 连接引擎日志到 Planner 轨迹
                self.planner_agent.attach_engine_logger(self.listener_engine)
                logger.info("Planner Agent initialized and registered")
            
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
    
    async def create_plan_from_config(self, plan_config: Dict[str, Any]) -> Plan:
        """从配置创建计划"""
        try:
            # 创建计划（包含任务和侦听器元数据）
            plan = await self.plan_manager.create_plan(plan_config)
            
            # 注意：不再创建传统的任务和侦听器记录
            # 所有数据现在存储在 Plan 对象中，运行时数据存储在 PlanInstance 中
            
            logger.info(f"Created plan {plan.id} with {len(plan.tasks)} tasks and {len(plan.listeners)} listeners")
            return plan
            
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
    
    
    async def get_plan_status(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """获取计划状态"""
        try:
            plan = await self.plan_manager.get_plan(plan_id)
            if not plan:
                return None
            
            # 使用 Plan 对象中的任务元数据
            return {
                "plan_id": plan_id,
                "plan_name": plan.name,
                "plan_status": plan.status,  # Plan 的生命周期状态
                "main_task_id": plan.main_task_id,
                "tasks": plan.tasks,  # 任务元数据
                "listeners": plan.listeners,  # 侦听器元数据
                "created_at": plan.created_at,
                "updated_at": plan.updated_at
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

    # ========== 实例管理方法 ==========
    
    async def start_plan_by_prompt(self, prompt: str, plan_id: str) -> PlanInstance:
        """根据提示启动计划，返回计划实例对象"""
        try:
            # 获取计划定义
            plan = await self.plan_manager.get_plan(plan_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")
            
            # 创建计划实例
            plan_instance = PlanInstance(
                id="",  # 由仓库生成
                plan_id=plan_id,
                plan=plan,  # 传入计划对象
                prompt=prompt,
                status=PlanInstanceStatus.NOT_STARTED.value,
                context={"values": {}, "metadata": {}}  # 临时上下文，稍后会被 start() 方法覆盖
            )
            
            # 从计划元数据创建任务实例
            for task_config in plan.tasks:
                task_instance = TaskInstance(
                    id="",  # 由仓库生成
                    plan_instance_id="",  # 稍后设置
                    task_id=task_config["task_id"],
                    plan_id=plan_id,
                    name=task_config["name"],
                    status=TaskInstanceStatus.NOT_STARTED.value,
                    parent_task_id=task_config.get("parent_task_id")
                )
                plan_instance.add_task_instance(task_instance)
            
            # 保存计划实例到仓库
            plan_instance_id = await self.plan_instance_repo.create(plan_instance)
            plan_instance.id = plan_instance_id
            
            # 更新所有任务实例的 plan_instance_id
            for task_instance in plan_instance.get_all_task_instances():
                task_instance.plan_instance_id = plan_instance_id
                await self.task_instance_repo.create(task_instance)
            
            # 注册到侦听引擎
            await plan_instance.register_to_listener_engine(self.listener_engine)
            
            logger.info(f"Created plan instance {plan_instance_id} for plan {plan_id} (status: {plan_instance.status})")
            return plan_instance
            
        except Exception as e:
            logger.error(f"Error starting plan by prompt: {e}")
            raise
    
    
    async def get_plan_instance(self, plan_instance_id: str) -> Optional[PlanInstance]:
        """获取计划实例"""
        return await self.plan_instance_repo.get_by_id(plan_instance_id)
    
    async def get_task_instance(self, plan_instance_id: str, task_id: str) -> Optional[TaskInstance]:
        """获取任务实例"""
        return await self.task_instance_repo.get_by_plan_instance_and_task_id(plan_instance_id, task_id)
    
    
    async def get_plan_instance_tasks(self, plan_instance_id: str) -> List[TaskInstance]:
        """获取计划实例的所有任务实例"""
        return await self.task_instance_repo.get_by_plan_instance_id(plan_instance_id)
    
    async def update_task_instance_status(self, plan_instance_id: str, task_id: str, status: str, context: Dict[str, Any]):
        """更新任务实例状态"""
        task_instance = await self.get_task_instance(plan_instance_id, task_id)
        if task_instance:
            task_instance_id = task_instance.id
            await self.task_instance_repo.update_status(task_instance_id, status, context)
    
    async def get_plan_instance_status(self, plan_instance_id: str) -> Optional[Dict[str, Any]]:
        """获取计划实例状态"""
        try:
            plan_instance = await self.get_plan_instance(plan_instance_id)
            if not plan_instance:
                return None
            
            # 获取所有任务实例
            task_instances = await self.get_plan_instance_tasks(plan_instance_id)
            
            return {
                "plan_instance_id": plan_instance_id,
                "plan_id": plan_instance.plan_id,
                "status": plan_instance.status,
                "prompt": plan_instance.prompt,
                "tasks": [
                    {
                        "task_id": task.task_id,
                        "task_instance_id": task.id,
                        "name": task.name,
                        "status": task.status,
                        "context": task.context
                    }
                    for task in task_instances
                ],
                "created_at": plan_instance.created_at,
                "started_at": plan_instance.started_at,
                "completed_at": plan_instance.completed_at,
                "error_info": plan_instance.error_info
            }
        except Exception as e:
            logger.error(f"Error getting plan instance status: {e}")
            return None
