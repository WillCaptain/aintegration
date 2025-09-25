"""
Planner模块

负责智能规划，处理用户请求，创建和调整执行计划
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from ..models.plan import Plan
from ..models.execution import Execution
from ..database.memory_repositories import MemoryExecutionRepository

logger = logging.getLogger(__name__)

class RequestHandler:
    """请求处理器"""
    
    def __init__(self, plan_module, execution_repo: MemoryExecutionRepository):
        self.plan_module = plan_module
        self.execution_repo = execution_repo
    
    async def process_request(self, user_request: str) -> Execution:
        """处理用户请求"""
        try:
            logger.info(f"Processing user request: {user_request}")
            
            # 1. 理解用户意图
            intent = await self.understand_intent(user_request)
            
            # 2. 搜索匹配的计划
            matching_plans = await self.search_matching_plans(intent)
            
            # 3. 如果找到，直接执行
            if matching_plans:
                plan = matching_plans[0]  # 选择最佳匹配
                return await self._execute_plan(plan, user_request)
            
            # 4. 如果没找到，创建新计划
            return await self._create_and_execute_plan(intent, user_request)
            
        except Exception as e:
            logger.error(f"Error processing request '{user_request}': {e}")
            raise
    
    async def understand_intent(self, request: str) -> Dict:
        """理解用户意图"""
        # 这里需要集成大模型来理解用户意图
        # 简化实现，返回基础意图结构
        intent = {
            "type": "employee_onboarding",  # 从请求中推断
            "entities": {
                "employee_name": "张三",  # 从请求中提取
                "department": None,
                "level": None
            },
            "requirements": []
        }
        return intent
    
    async def search_matching_plans(self, intent: Dict) -> List[Plan]:
        """搜索匹配的计划"""
        # 根据意图搜索相关计划
        criteria = {
            "type": intent["type"],
            "entities": intent["entities"]
        }
        return await self.plan_module.plan_manager.search_plans(criteria)
    
    async def _execute_plan(self, plan: Plan, user_request: str) -> Execution:
        """执行现有计划"""
        try:
            # 创建执行记录
            execution = Execution(
                id=f"exec_{plan.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                plan_id=plan.id,
                user_request=user_request,
                status="running",
                created_at=datetime.now()
            )
            await self.execution_repo.create(execution)
            
            # 执行计划
            result = await self.plan_module.execute_plan(plan.id)
            
            # 更新执行状态
            if result["success"]:
                execution.status = "completed"
            else:
                execution.status = "error"
                execution.error_message = result.get("error", "Unknown error")
            
            execution.completed_at = datetime.now()
            await self.execution_repo.update(execution.id, {
                "status": execution.status,
                "completed_at": execution.completed_at,
                "error_message": execution.error_message
            })
            
            return execution
            
        except Exception as e:
            logger.error(f"Error executing plan {plan.id}: {e}")
            raise
    
    async def _create_and_execute_plan(self, intent: Dict, user_request: str) -> Execution:
        """创建并执行新计划"""
        try:
            # 生成计划
            plan = await self.plan_generator.create_plan_from_intent(intent)
            
            # 执行计划
            return await self._execute_plan(plan, user_request)
            
        except Exception as e:
            logger.error(f"Error creating and executing plan: {e}")
            raise

class PlanGenerator:
    """计划生成器"""
    
    def __init__(self, plan_module):
        self.plan_module = plan_module
    
    async def create_plan_from_intent(self, intent: Dict) -> Plan:
        """根据意图创建计划"""
        try:
            # 1. 获取Few-shot示例
            examples = await self.plan_module.plan_manager.get_few_shot_examples()
            
            # 2. 基于示例生成计划
            plan_config = await self._generate_plan_config(intent, examples)
            
            # 3. 创建计划
            plan_id = await self.plan_module.plan_manager.create_plan(plan_config)
            
            # 4. 创建任务和侦听器
            await self._create_tasks_and_listeners(plan_id, plan_config)
            
            return await self.plan_module.plan_manager.get_plan(plan_id)
            
        except Exception as e:
            logger.error(f"Error creating plan from intent: {e}")
            raise
    
    async def _generate_plan_config(self, intent: Dict, examples: List[Dict]) -> Dict:
        """生成计划配置"""
        # 这里需要集成大模型来生成计划配置
        # 简化实现，返回基础计划配置
        return {
            "plan_id": f"plan_{intent['type']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "name": f"{intent['type']}计划",
            "prompt": f"执行{intent['type']}流程",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": "001",
                    "name": "主任务",
                    "prompt": f"完成{intent['type']}"
                }
            ],
            "listeners": []
        }
    
    async def _create_tasks_and_listeners(self, plan_id: str, plan_config: Dict):
        """创建任务和侦听器"""
        # 创建任务
        for task_config in plan_config.get("tasks", []):
            task_config["plan_id"] = plan_id
            await self.plan_module.task_manager.create_task(task_config)
        
        # 创建侦听器
        for listener_config in plan_config.get("listeners", []):
            listener_config["plan_id"] = plan_id
            await self.plan_module.listener_manager.create_listener(listener_config)

class ExecutionMonitor:
    """执行监控器"""
    
    def __init__(self, execution_repo: MemoryExecutionRepository, plan_generator: PlanGenerator):
        self.execution_repo = execution_repo
        self.plan_generator = plan_generator
    
    async def monitor_execution(self, execution_id: str):
        """监控计划执行"""
        try:
            execution = await self.execution_repo.get_by_id(execution_id)
            if not execution:
                logger.error(f"Execution {execution_id} not found")
                return
            
            # 检查执行状态
            if execution.status == "error":
                await self.handle_execution_error(execution_id, Exception("Execution failed"))
                
        except Exception as e:
            logger.error(f"Error monitoring execution {execution_id}: {e}")
    
    async def handle_execution_error(self, execution_id: str, error: Exception):
        """处理执行错误"""
        try:
            logger.info(f"Handling execution error for {execution_id}")
            
            # 1. 分析错误原因
            error_analysis = await self._analyze_error(execution_id, error)
            
            # 2. 决定是否需要重新规划
            if error_analysis["should_replan"]:
                # 3. 启动ResiliencePlan
                await self._start_resilience_plan(execution_id, error_analysis)
                
        except Exception as e:
            logger.error(f"Error handling execution error: {e}")
    
    async def _analyze_error(self, execution_id: str, error: Exception) -> Dict:
        """分析错误原因"""
        # 简化实现
        return {
            "error_type": "system_error",
            "should_replan": True,
            "suggested_actions": ["retry", "fallback"]
        }
    
    async def _start_resilience_plan(self, execution_id: str, error_analysis: Dict):
        """启动弹性计划"""
        # 实现ResiliencePlan逻辑
        logger.info(f"Starting resilience plan for execution {execution_id}")

class PlannerModule:
    """Planner模块主类"""
    
    def __init__(self, plan_module, execution_repo: MemoryExecutionRepository):
        self.plan_module = plan_module
        self.execution_repo = execution_repo
        
        # 初始化子组件
        self.request_handler = RequestHandler(plan_module, execution_repo)
        self.plan_generator = PlanGenerator(plan_module)
        self.execution_monitor = ExecutionMonitor(execution_repo, self.plan_generator)
    
    async def start(self):
        """启动Planner模块"""
        logger.info("Planner Module started")
    
    async def stop(self):
        """停止Planner模块"""
        logger.info("Planner Module stopped")
    
    async def execute_request(self, user_request: str) -> Execution:
        """执行用户请求"""
        return await self.request_handler.process_request(user_request)
