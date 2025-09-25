"""
TaskDriver模块

负责执行智能体和代码，驱动任务状态变化
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..models.task import Task, TaskStatus
from ..models.listener import Listener, ListenerType
from ..infrastructure.llm_client import LLMClient, build_llm_client
from ..infrastructure.adk_integration import AgentRuntime

logger = logging.getLogger(__name__)

class TaskDriver:
    """任务驱动器"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None, adk_integration: Optional[AgentRuntime] = None):
        self.llm_client = llm_client or build_llm_client()
        self.adk_integration = adk_integration
        self.execution_context = {}
    
    async def execute_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行侦听器"""
        try:
            logger.info(f"Executing listener {listener.id} of type {listener.listener_type}")
            
            # 检查行动条件
            if not listener.evaluate_action_condition(plan_context):
                logger.info(f"Action condition not met for listener {listener.id}")
                return {"success": False, "reason": "action_condition_not_met"}
            
            # 根据侦听器类型执行
            if listener.is_agent_listener():
                return await self._execute_agent_listener(listener, plan_context)
            elif listener.is_code_listener():
                return await self._execute_code_listener(listener, plan_context)
            else:
                logger.error(f"Unknown listener type: {listener.listener_type}")
                return {"success": False, "reason": "unknown_listener_type"}
                
        except Exception as e:
            logger.error(f"Error executing listener {listener.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_agent_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行智能体侦听器"""
        try:
            if not listener.agent_id or not listener.action_prompt:
                return {"success": False, "reason": "missing_agent_config"}
            
            # 构建完整的提示词，包含上下文变量替换
            prompt = self._build_prompt_with_context(listener.action_prompt, plan_context)
            
            # 如果有ADK集成，使用ADK执行智能体
            if self.adk_integration:
                # 尝试结构化上下文执行，便于直接命中工具
                if hasattr(self.adk_integration, "execute_agent_with_context"):
                    return await self.adk_integration.execute_agent_with_context(listener.agent_id, prompt, plan_context)
                return await self._execute_with_adk(listener.agent_id, prompt, plan_context)
            else:
                # 使用LLM客户端执行
                return await self._execute_with_llm(prompt, plan_context)
                
        except Exception as e:
            logger.error(f"Error executing agent listener {listener.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_code_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行代码侦听器"""
        try:
            if not listener.code_snippet:
                return {"success": False, "reason": "missing_code_snippet"}
            
            # 在安全环境中执行代码
            return await self._execute_code_safely(listener.code_snippet, plan_context)
            
        except Exception as e:
            logger.error(f"Error executing code listener {listener.id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_prompt_with_context(self, prompt: str, plan_context: Dict[str, Any]) -> str:
        """构建包含上下文变量的提示词"""
        # 简单的变量替换，实际实现需要更复杂的模板引擎
        result = prompt
        for key, value in plan_context.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result
    
    async def _execute_with_adk(self, agent_id: str, prompt: str, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """使用ADK执行智能体"""
        try:
            # 这里需要根据实际的ADK集成接口调整
            if hasattr(self.adk_integration, 'execute_agent'):
                result = await self.adk_integration.execute_agent(agent_id, prompt, plan_context)
                return self._process_agent_result(result)
            else:
                logger.warning("ADK integration does not support agent execution")
                return await self._execute_with_llm(prompt, plan_context)
        except Exception as e:
            logger.error(f"Error executing with ADK: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_with_llm(self, prompt: str, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """使用LLM执行"""
        try:
            # 构建完整的上下文
            context_str = "\n".join([f"{k}: {v}" for k, v in plan_context.items()])
            full_prompt = f"""
{prompt}

上下文信息：
{context_str}

请根据上述信息和上下文执行相应的操作，并返回JSON格式的结果。
"""
            
            response = await self.llm_client.generate(full_prompt)
            return self._parse_llm_response(response)
            
        except Exception as e:
            logger.error(f"Error executing with LLM: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_code_safely(self, code_snippet: str, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """在安全环境中执行代码"""
        try:
            # 创建安全的执行环境
            safe_globals = {
                '__builtins__': {
                    'print': print,
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'list': list,
                    'dict': dict,
                    'tuple': tuple,
                    'set': set,
                    'min': min,
                    'max': max,
                    'sum': sum,
                    'abs': abs,
                    'round': round,
                    'sorted': sorted,
                    'reversed': reversed,
                    'enumerate': enumerate,
                    'zip': zip,
                    'range': range,
                    'datetime': datetime,
                },
                'context': plan_context,
                'result': {}
            }
            
            # 执行代码
            exec(code_snippet, safe_globals)
            
            # 获取执行结果
            result = safe_globals.get('result', {})
            return {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"Error executing code safely: {e}")
            return {"success": False, "error": str(e)}
    
    def _process_agent_result(self, result: Any) -> Dict[str, Any]:
        """处理智能体执行结果"""
        if isinstance(result, dict):
            return result
        elif isinstance(result, str):
            return self._parse_llm_response(result)
        else:
            return {"success": True, "result": result}
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            import json
            # 尝试解析JSON响应
            if response.strip().startswith('{') and response.strip().endswith('}'):
                return json.loads(response.strip())
            else:
                # 如果不是JSON，包装为成功响应
                return {"success": True, "result": response}
        except json.JSONDecodeError:
            # 解析失败，包装为成功响应
            return {"success": True, "result": response}
    
    def determine_task_updates(self, listener: Listener, execution_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据执行结果确定任务更新"""
        updates = []
        
        if execution_result.get("success", False):
            # 成功情况
            target_task_id = listener.get_success_target_task()
            target_status = listener.get_success_target_status()
            context_updates = listener.get_success_context()
            
            if target_task_id and target_status:
                updates.append({
                    "task_id": target_task_id,
                    "status": target_status,
                    "context": context_updates,
                    "execution_result": execution_result
                })
        else:
            # 失败情况
            target_task_id = listener.get_failure_target_task()
            target_status = listener.get_failure_target_status()
            context_updates = listener.get_failure_context()
            
            if target_task_id and target_status:
                updates.append({
                    "task_id": target_task_id,
                    "status": target_status,
                    "context": context_updates,
                    "execution_result": execution_result,
                    "error": execution_result.get("error", "Unknown error")
                })
        
        return updates
    
