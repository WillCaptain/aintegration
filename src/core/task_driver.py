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
from ..infrastructure.mcp_client import MCP_LAST_TOOL_RESULTS

logger = logging.getLogger(__name__)

class TaskDriver:
    """任务驱动器"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None, adk_integration: Optional[AgentRuntime] = None):
        self.llm_client = llm_client or build_llm_client()
        self.adk_integration = adk_integration
        self.execution_context = {}
    
    async def execute_listener_old_plan_context(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行侦听器（旧方法，仅用于向后兼容，应该被移除）"""
        try:
            print(f"[TaskDriver] 开始执行侦听器 {listener.id}, 类型: {listener.listener_type}")
            logger.info(f"Executing listener {listener.id} of type {listener.listener_type}")
            
            # 新机制：不再校验 action_condition，触发即评估 trigger_condition 并执行
            print(f"[TaskDriver] 侦听器 {listener.id} 触发，开始执行")
            
            # 根据侦听器类型执行
            if listener.is_agent_listener():
                print(f"[TaskDriver] 执行 Agent 侦听器 {listener.id}, agent_id: {listener.agent_id}")
                return await self._execute_agent_listener(listener, plan_context)
            elif listener.is_code_listener():
                print(f"[TaskDriver] 执行代码侦听器 {listener.id}")
                return await self._execute_code_listener(listener, plan_context)
            else:
                print(f"[TaskDriver] 未知侦听器类型: {listener.listener_type}")
                logger.error(f"Unknown listener type: {listener.listener_type}")
                return {"success": False, "reason": "unknown_listener_type"}
                
        except Exception as e:
            print(f"[TaskDriver] 执行侦听器 {listener.id} 时出错: {e}")
            logger.error(f"Error executing listener {listener.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_agent_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行智能体侦听器"""
        try:
            print(f"[TaskDriver] 检查 Agent 配置: agent_id={listener.agent_id}, action_prompt={bool(listener.action_prompt)}")
            
            if not listener.agent_id or not listener.action_prompt:
                print(f"[TaskDriver] Agent 配置缺失")
                return {"success": False, "reason": "missing_agent_config"}
            
            # 构建完整的提示词，包含上下文变量替换
            prompt = self._build_prompt_with_context(listener.action_prompt, plan_context)
            print(f"[TaskDriver] 构建的提示词: {prompt[:200]}...")
            
            # 如果有ADK集成，使用ADK执行智能体
            result = None
            if self.adk_integration:
                print(f"[TaskDriver] 使用 ADK 集成执行 Agent")
                # 尝试结构化上下文执行，便于直接命中工具
                has_method = hasattr(self.adk_integration, "execute_agent_with_context")
                print(f"[TaskDriver] adk_integration有execute_agent_with_context方法: {has_method}")
                if has_method:
                    print(f"[TaskDriver] 调用execute_agent_with_context，agent_id={listener.agent_id}")
                    result = await self.adk_integration.execute_agent_with_context(listener.agent_id, prompt, plan_context)
                else:
                    print(f"[TaskDriver] 调用_execute_with_adk")
                    result = await self._execute_with_adk(listener.agent_id, prompt, plan_context)
            else:
                print(f"[TaskDriver] 没有 ADK 集成，使用 ReactAgent 直接执行")
                # 使用 ReactAgent 直接执行
                result = await self._execute_with_adk(listener.agent_id, prompt, plan_context)
            
            # 根据执行结果生成task_updates
            if result.get('success', False):
                # 成功：使用success_output
                if listener.success_output:
                    print(f"[TaskDriver] Agent执行成功，生成task_updates")
                    task_updates = [{
                        'task_id': listener.success_output.get('task_id'),
                        'status': listener.success_output.get('status'),
                        'reason': 'listener_success',
                        'context': listener.success_output.get('context', {})
                    }]
                    result['task_updates'] = task_updates
                    print(f"[TaskDriver] 生成的task_updates: {task_updates}")
            else:
                # 失败：调用determine_task_updates生成默认更新（包括001 Error）
                print(f"[TaskDriver] Agent执行失败，调用determine_task_updates生成默认更新")
                task_updates = self.determine_task_updates(listener, result)
                result['task_updates'] = task_updates
                print(f"[TaskDriver] 失败生成的task_updates: {task_updates}")
            
            return result
                
        except Exception as e:
            print(f"[TaskDriver] 执行 Agent 侦听器 {listener.id} 时出错: {e}")
            logger.error(f"Error executing agent listener {listener.id}: {e}")
            error_result = {"success": False, "error": str(e)}
            # 生成默认的错误更新
            task_updates = self.determine_task_updates(listener, error_result)
            error_result['task_updates'] = task_updates
            return error_result
    
    async def _execute_code_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行代码侦听器"""
        try:
            if not listener.code_snippet:
                return {"success": False, "reason": "missing_code_snippet"}
            
            # 在安全环境中执行代码
            result = await self._execute_code_safely(listener.code_snippet, plan_context)
            
            # 根据执行结果生成task_updates
            if result.get('success', False):
                # 成功：如果代码没有返回task_updates，使用success_output
                if not result.get('task_updates') and listener.success_output:
                    print(f"[TaskDriver] 代码执行成功，生成task_updates")
                    task_updates = [{
                        'task_id': listener.success_output.get('task_id'),
                        'status': listener.success_output.get('status'),
                        'reason': 'listener_success',
                        'context': listener.success_output.get('context', {})
                    }]
                    result['task_updates'] = task_updates
                    print(f"[TaskDriver] 生成的task_updates: {task_updates}")
            else:
                # 失败：调用determine_task_updates生成默认更新（包括001 Error）
                print(f"[TaskDriver] 代码执行失败，调用determine_task_updates生成默认更新")
                task_updates = self.determine_task_updates(listener, result)
                result['task_updates'] = task_updates
                print(f"[TaskDriver] 失败生成的task_updates: {task_updates}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing code listener {listener.id}: {e}")
            error_result = {"success": False, "error": str(e)}
            # 生成默认的错误更新
            task_updates = self.determine_task_updates(listener, error_result)
            error_result['task_updates'] = task_updates
            return error_result
    
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
            print(f"[TaskDriver] 开始创建 ReactAgent: agent_id={agent_id}")
            
            # 使用 ReactAgent 执行智能体
            from src.infrastructure.adk_integration import ReactAgent
            
            # 创建 ReactAgent 实例，使用 agent_id 作为 app_name
            agent = ReactAgent(
                system_prompt=f"你是一个{agent_id}系统的专业代理",
                app_name=agent_id
            )
            
            print(f"[TaskDriver] ReactAgent 创建成功，开始执行: {prompt[:100]}...")
            
            # 执行 Agent
            result = await agent.execute(prompt)
            
            print(f"[TaskDriver] ReactAgent 执行完成，结果: {result}")
            return self._process_agent_result(result)
            
        except Exception as e:
            print(f"[TaskDriver] 执行 ReactAgent 时出错: {e}")
            import traceback
            print(f"[TaskDriver] 错误堆栈: {traceback.format_exc()}")
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
                'result': {},
                'task_updates': []
            }
            
            # 执行代码
            exec(code_snippet, safe_globals)
            
            # 获取执行结果
            result = safe_globals.get('result', {})
            task_updates = safe_globals.get('task_updates', [])
            return {"success": True, "result": result, "task_updates": task_updates}
            
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
        print(f"[TaskDriver] 确定任务更新: listener={listener.id}, result={execution_result}")
        updates = []
        
        # 对于代码侦听器，检查 result 中的 success 字段
        is_success = execution_result.get("success", False)
        # 针对 Agent 侦听器：尝试解析 ADK/ReactAgent 返回结构中的工具结果 success
        if listener.is_agent_listener():
            try:
                # 泛化处理：不使用硬编码的agent_tool_map
                # FastMCP/ReactAgent 常见返回：{"success": True, "output": {"success": True, "result": {"success": bool, ...}}}
                outer = execution_result.get("output") or execution_result.get("result") or {}
                inner = outer.get("result") if isinstance(outer, dict) else {}
                if isinstance(inner, dict) and "success" in inner:
                    is_success = bool(inner.get("success"))
                    print(f"[TaskDriver] 依据 Agent 工具结果判定 success: {is_success}")
                
                # ReactAgent 汇总文本中亦可能包含失败线索，作为兜底
                if is_success and isinstance(execution_result.get("response"), str):
                    resp_text = execution_result.get("response", "")
                    if "Mock failure" in resp_text or "\"success\": false" in resp_text.lower():
                        is_success = False
                        print("[TaskDriver] 从 ReactAgent 文本响应中检测到失败线索，强制视为失败")
                
                # 泛化处理：从action_prompt或response中动态提取工具名
                target_tool = None
                if hasattr(listener, 'action_prompt') and listener.action_prompt:
                    # 从提示语中提取工具名（简单从 action_prompt 中提取）
                    ap = (listener.action_prompt or '').lower()
                    for key in MCP_LAST_TOOL_RESULTS.keys():
                        if key.lower() in ap:
                            target_tool = key
                            break
                
                # 如果提示词无法判定，尝试从 response 中提取
                if target_tool is None and isinstance(execution_result.get("response"), str):
                    resp_text = execution_result.get("response", "").lower()
                    for key in MCP_LAST_TOOL_RESULTS.keys():
                        if key.lower() in resp_text:
                            target_tool = key
                            break
                
                # 查询 MCP 客户端最近一次该工具的真实结果
                if target_tool and target_tool in MCP_LAST_TOOL_RESULTS:
                    last = MCP_LAST_TOOL_RESULTS[target_tool]
                    if isinstance(last, dict) and last.get('success') is False:
                        is_success = False
                        print(f"[TaskDriver] 依据 MCP 底层结果判定 {target_tool} 失败，强制视为失败")
            except Exception as e:
                print(f"[TaskDriver] 解析 Agent 结果判定成功与否时出错: {e}")
        if is_success and "result" in execution_result:
            inner_result = execution_result["result"]
            if isinstance(inner_result, dict) and "success" in inner_result:
                # 如果 inner result 有 success 字段，使用它来判断
                is_success = inner_result.get("success", False)
                print(f"[TaskDriver] 使用内部 result.success 判断: {is_success}")
        
        if is_success:
            # 成功情况
            target_task_id = listener.get_success_target_task()
            target_status = listener.get_success_target_status()
            context_updates = listener.get_success_context()
            
            print(f"[TaskDriver] 成功情况: target_task_id={target_task_id}, target_status={target_status}, context={context_updates}")
            
            if target_task_id and target_status:
                updates.append({
                    "task_id": target_task_id,
                    "status": target_status,
                    "context": context_updates,
                    "execution_result": execution_result,
                    "plan_instance_id": listener.plan_instance_id  # 添加 plan_instance_id
                })
                print(f"[TaskDriver] 添加成功更新: {updates[-1]}")
            else:
                print(f"[TaskDriver] 成功情况但缺少目标任务或状态")
        else:
            # 失败情况
            target_task_id = listener.get_failure_target_task()
            target_status = listener.get_failure_target_status()
            context_updates = listener.get_failure_context()
            
            print(f"[TaskDriver] 失败情况: target_task_id={target_task_id}, target_status={target_status}, context={context_updates}")
            
            if target_task_id and target_status:
                updates.append({
                    "task_id": target_task_id,
                    "status": target_status,
                    "context": context_updates,
                    "execution_result": execution_result,
                    "error": execution_result.get("error", "Unknown error"),
                    "plan_instance_id": listener.plan_instance_id  # 添加 plan_instance_id
                })
                print(f"[TaskDriver] 添加失败更新: {updates[-1]}")
            else:
                # 默认行为：失败时设置主任务为Error（触发Planner重试）
                # 约定：主任务ID默认为"001"
                # 关键：在context中记录失败的listener_id，供PlannerAgent读取并重试
                print(f"[TaskDriver] ⚠️ 失败但无failure_output，使用默认行为：设置主任务001 Error并记录失败的listener_id")
                print(f"[TaskDriver] 失败的listener: {listener.id}")
                print(f"[TaskDriver] 错误信息: {execution_result.get('error', 'Unknown error')}")
                
                update_to_add = {
                    "task_id": "001",
                    "status": "Error",
                    "context": {
                        "failed_listener_id": listener.id,  # 记录失败的侦听器ID
                        "error": execution_result.get("error", "Unknown error"),
                        "error_info": {
                            "listener_id": listener.id,
                            "agent_id": listener.agent_id if hasattr(listener, 'agent_id') else None,
                            "error_message": execution_result.get("error", "Unknown error")
                        }
                    },
                    "execution_result": execution_result,
                    "error": execution_result.get("error", "Unknown error"),
                    "plan_instance_id": listener.plan_instance_id  # 添加 plan_instance_id
                }
                updates.append(update_to_add)
                print(f"[TaskDriver] ✓ 添加默认失败更新: {update_to_add}")
                print(f"[TaskDriver] context包含: failed_listener_id={listener.id}")
        
        print(f"[TaskDriver] 最终更新列表: {updates}")
        return updates
    
    async def execute_listener(self, listener: Listener, plan_instance: 'PlanInstance') -> Dict[str, Any]:
        """执行侦听器"""
        try:
            print(f"[TaskDriver] 开始执行侦听器 {listener.id}, 类型: {listener.listener_type}")
            logger.info(f"Executing listener {listener.id} of type {listener.listener_type}")
            
            # 根据侦听器类型执行
            if listener.listener_type == 'agent':
                print(f"[TaskDriver] 执行 Agent 侦听器 {listener.id}")
                return await self._execute_agent_listener_new(listener, plan_instance)
            elif listener.listener_type == 'code':
                print(f"[TaskDriver] 执行代码侦听器 {listener.id}")
                return await self._execute_code_listener_new(listener, plan_instance)
            else:
                print(f"[TaskDriver] 未知侦听器类型: {listener.listener_type}")
                logger.error(f"Unknown listener type: {listener.listener_type}")
                return {"success": False, "error": "unknown_listener_type", "task_updates": []}
                
        except Exception as e:
            print(f"[TaskDriver] 执行侦听器 {listener.id} 时出错: {e}")
            logger.error(f"Error executing listener {listener.id}: {e}")
            return {"success": False, "error": str(e), "task_updates": []}
    
    async def _execute_agent_listener_new(self, listener: Listener, plan_instance: 'PlanInstance') -> Dict[str, Any]:
        """执行 Agent 侦听器（新版本）"""
        try:
            # 构建计划上下文，包含所有任务实例的上下文
            plan_context = {
                "plan_id": plan_instance.plan_id,
                "plan_instance_id": plan_instance.id,
                "context": plan_instance.context,
                "prompt": plan_instance.prompt
            }
            
            # 添加所有任务实例的上下文，格式为 {task_id}.context.{field}
            for task_id, task_instance in plan_instance.task_instances.items():
                task_context_key = f"{task_id}.context"
                if task_instance.context:
                    for field, value in task_instance.context.items():
                        plan_context[f"{task_id}.context.{field}"] = value
            
            # 执行 Agent
            agent_result = await self._execute_agent_listener(listener, plan_context)
            
            # 转换为新格式
            if agent_result.get("success", False):
                return {
                    "success": True,
                    "task_updates": agent_result.get("task_updates", [])
                }
            else:
                # 失败时也要返回task_updates（包括默认的001 Error）
                return {
                    "success": False,
                    "error": agent_result.get("reason", "Unknown error"),
                    "task_updates": agent_result.get("task_updates", [])
                }
                
        except Exception as e:
            logger.error(f"Error executing agent listener {listener.listener_id}: {e}")
            return {"success": False, "error": str(e), "task_updates": []}
    
    async def _execute_code_listener_new(self, listener: Listener, plan_instance: 'PlanInstance') -> Dict[str, Any]:
        """执行代码侦听器（新版本）"""
        try:
            # 构建计划上下文，包含所有任务实例的上下文
            plan_context = {
                "plan_id": plan_instance.plan_id,
                "plan_instance_id": plan_instance.id,
                "context": plan_instance.context,
                "prompt": plan_instance.prompt
            }
            
            # 添加所有任务实例的上下文，格式为 {task_id}.context.{field}
            for task_id, task_instance in plan_instance.task_instances.items():
                if task_instance.context:
                    for field, value in task_instance.context.items():
                        plan_context[f"{task_id}.context.{field}"] = value
            
            # 执行代码
            code_result = await self._execute_code_listener(listener, plan_context)
            
            # 转换为新格式
            if code_result.get("success", False):
                return {
                    "success": True,
                    "task_updates": code_result.get("task_updates", [])
                }
            else:
                # 失败时也要返回task_updates
                return {
                    "success": False,
                    "error": code_result.get("reason", "Unknown error"),
                    "task_updates": code_result.get("task_updates", [])
                }
                
        except Exception as e:
            logger.error(f"Error executing code listener {listener.listener_id}: {e}")
            return {"success": False, "error": str(e), "task_updates": []}
    
