"""
邮件发送执行引擎

专门用于执行邮件发送计划的简化引擎
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from ..agents.email_agent import EmailAgent
from ..models.task import Task, TaskStatus
from ..models.listener import Listener
from ..models.execution import Execution

logger = logging.getLogger(__name__)

class EmailExecutionEngine:
    """邮件发送执行引擎"""
    
    def __init__(self):
        self.email_agent = EmailAgent()
        self.running_executions = {}
        self.task_states = {}
        self.listeners = {}
    
    async def execute_email_plan(self, plan_config: Dict[str, Any], context: Dict[str, Any]) -> Execution:
        """执行邮件发送计划"""
        try:
            plan_id = plan_config["plan_id"]
            logger.info(f"开始执行邮件发送计划: {plan_id}")
            
            # 创建执行记录
            execution = Execution(
                id=f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                user_request=context.get("user_request", "发送邮件"),
                plan_id=plan_id,
                status="running",
                start_time=datetime.now()
            )
            
            # 注册执行记录
            self.running_executions[execution.id] = execution
            
            # 初始化任务状态
            await self._initialize_tasks(plan_config)
            
            # 注册侦听器
            await self._register_listeners(plan_config)
            
            # 开始执行主任务
            main_task_id = plan_config["main_task_id"]
            await self._update_task_status(main_task_id, TaskStatus.RUNNING.value, context)
            
            # 等待执行完成
            await self._wait_for_completion(execution.id, timeout=30)
            
            # 更新执行状态
            execution.status = "completed"
            execution.end_time = datetime.now()
            
            logger.info(f"邮件发送计划执行完成: {plan_id}")
            return execution
            
        except Exception as e:
            logger.error(f"执行邮件发送计划时发生错误: {e}")
            if execution:
                execution.status = "failed"
                execution.error_message = str(e)
                execution.end_time = datetime.now()
            raise
    
    async def _initialize_tasks(self, plan_config: Dict[str, Any]):
        """初始化任务状态"""
        for task_config in plan_config["tasks"]:
            task_id = task_config["task_id"]
            self.task_states[task_id] = {
                "status": TaskStatus.NOT_STARTED.value,
                "context": {"status": TaskStatus.NOT_STARTED.value, "values": {}},
                "created_at": datetime.now()
            }
            logger.debug(f"初始化任务状态: {task_id} -> {TaskStatus.NOT_STARTED.value}")
    
    async def _register_listeners(self, plan_config: Dict[str, Any]):
        """注册侦听器"""
        for listener_config in plan_config["listeners"]:
            listener_id = listener_config["listener_id"]
            self.listeners[listener_id] = Listener(
                id=listener_id,
                plan_id=listener_config["plan_id"],
                trigger_task_id=listener_config["trigger_task_id"],
                trigger_condition=listener_config["trigger_condition"],
                action_condition=listener_config["action_condition"],
                agent_id=listener_config["agent_id"],
                action_prompt=listener_config["action_prompt"],
                success_output=listener_config["success_output"],
                failure_output=listener_config["failure_output"]
            )
            logger.debug(f"注册侦听器: {listener_id}")
    
    async def _update_task_status(self, task_id: str, status: str, context: Dict[str, Any]):
        """更新任务状态"""
        try:
            old_status = self.task_states.get(task_id, {}).get("status", "Unknown")
            self.task_states[task_id] = {
                "status": status,
                "context": {"status": status, "values": context},
                "updated_at": datetime.now()
            }
            
            logger.info(f"任务状态更新: {task_id} {old_status} -> {status}")
            
            # 触发侦听器
            await self._trigger_listeners(task_id, status, context)
            
        except Exception as e:
            logger.error(f"更新任务状态时发生错误: {e}")
            raise
    
    async def _trigger_listeners(self, task_id: str, status: str, context: Dict[str, Any]):
        """触发相关侦听器"""
        try:
            triggered_listeners = []
            
            for listener_id, listener in self.listeners.items():
                # 检查是否匹配触发条件
                if self._matches_trigger_condition(listener, task_id, status):
                    # 检查行动条件
                    if await self._evaluate_action_condition(listener, context):
                        triggered_listeners.append(listener)
            
            logger.debug(f"触发侦听器数量: {len(triggered_listeners)}")
            
            # 执行触发的侦听器
            for listener in triggered_listeners:
                await self._execute_listener(listener, context)
                
        except Exception as e:
            logger.error(f"触发侦听器时发生错误: {e}")
            raise
    
    def _matches_trigger_condition(self, listener: Listener, task_id: str, status: str) -> bool:
        """检查是否匹配触发条件"""
        try:
            # 简化实现：检查任务ID和状态
            trigger_condition = listener.trigger_condition
            expected_condition = f"{task_id}.status == {status}"
            
            # 支持多种条件格式
            if expected_condition in trigger_condition:
                return True
            
            # 支持通配符匹配
            if "Any" in trigger_condition and listener.trigger_task_id == task_id:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"检查触发条件时发生错误: {e}")
            return False
    
    async def _evaluate_action_condition(self, listener: Listener, context: Dict[str, Any]) -> bool:
        """评估行动条件"""
        try:
            action_condition = listener.action_condition
            
            # 简化实现：支持 "true" 条件
            if action_condition == "true":
                return True
            
            # 可以在这里添加更复杂的条件评估逻辑
            return True
            
        except Exception as e:
            logger.error(f"评估行动条件时发生错误: {e}")
            return False
    
    async def _execute_listener(self, listener: Listener, context: Dict[str, Any]):
        """执行侦听器"""
        try:
            logger.info(f"执行侦听器: {listener.id} -> {listener.agent_id}")
            
            # 构建Agent执行上下文
            agent_context = self._build_agent_context(listener, context)
            
            # 执行Agent
            if listener.agent_id == "email_agent_v1":
                result = await self.email_agent.execute(listener.action_prompt, agent_context)
            else:
                # 其他类型的Agent
                result = {"success": False, "error": f"未知的Agent类型: {listener.agent_id}"}
            
            # 处理执行结果
            if result["success"]:
                output = listener.success_output
                logger.info(f"侦听器执行成功: {listener.id}")
            else:
                output = listener.failure_output
                logger.warning(f"侦听器执行失败: {listener.id} - {result.get('error', '未知错误')}")
            
            # 更新目标任务状态
            target_task_id = output["task_id"]
            target_status = output["status"]
            target_context = output["context"]
            
            await self._update_task_status(target_task_id, target_status, target_context)
            
        except Exception as e:
            logger.error(f"执行侦听器时发生错误: {e}")
            # 处理失败情况
            output = listener.failure_output
            output["context"]["error"] = str(e)
            
            target_task_id = output["task_id"]
            target_status = output["status"]
            target_context = output["context"]
            
            await self._update_task_status(target_task_id, target_status, target_context)
    
    def _build_agent_context(self, listener: Listener, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建Agent执行上下文"""
        try:
            # 解析action_prompt中的上下文变量引用
            # 简化实现：直接传递context
            agent_context = context.copy()
            
            # 可以在这里添加更复杂的上下文构建逻辑
            # 比如解析 {task_001.context.to} 这样的变量引用
            
            return agent_context
            
        except Exception as e:
            logger.error(f"构建Agent上下文时发生错误: {e}")
            return context
    
    async def _wait_for_completion(self, execution_id: str, timeout: int = 30):
        """等待执行完成"""
        try:
            start_time = datetime.now()
            
            while (datetime.now() - start_time).seconds < timeout:
                execution = self.running_executions.get(execution_id)
                if not execution:
                    break
                
                # 检查是否所有任务都已完成
                if self._all_tasks_completed():
                    break
                
                # 等待一段时间再检查
                await asyncio.sleep(0.1)
            
            logger.debug(f"等待执行完成: {execution_id}")
            
        except Exception as e:
            logger.error(f"等待执行完成时发生错误: {e}")
            raise
    
    def _all_tasks_completed(self) -> bool:
        """检查是否所有任务都已完成"""
        for task_id, task_state in self.task_states.items():
            if task_state["status"] not in [TaskStatus.DONE.value, TaskStatus.ERROR.value]:
                return False
        return True
    
    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取执行状态"""
        execution = self.running_executions.get(execution_id)
        if not execution:
            return None
        
        return {
            "execution_id": execution.id,
            "status": execution.status,
            "start_time": execution.start_time.isoformat() if execution.start_time else None,
            "end_time": execution.end_time.isoformat() if execution.end_time else None,
            "error_message": execution.error_message,
            "task_states": self.task_states.copy()
        }
    
    def cleanup_execution(self, execution_id: str):
        """清理执行记录"""
        if execution_id in self.running_executions:
            del self.running_executions[execution_id]
            logger.debug(f"清理执行记录: {execution_id}")
