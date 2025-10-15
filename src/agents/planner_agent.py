"""
PlannerAgent（系统内置、长期演进）

职责：
- 监听任务状态变化（由 ListenerEngine 回调）
- 在 main task Done 时，通过 A2A 查询各系统状态进行验证
- 记录验证结果，为后续动态规划功能做准备

说明：
- 当前专注于状态验证，不进行动态任务生成
- 与 A2A 交互通过 A2AClient 抽象，便于未来替换为官方 A2A 实现
- 业务执行由配置化 BizAgent 处理
"""

from __future__ import annotations

import logging
import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..infrastructure.a2a_client import A2AClient
from ..infrastructure.llm_client import build_llm_client
from ..utils.execution_logger import execution_logger
from ..models.plan_instance import PlanInstanceStatus
from ..models.listener import Listener

logger = logging.getLogger(__name__)


class PlannerAgent:
    def __init__(self, a2a_client: A2AClient, llm_client=None, max_retry_count: int = 3):
        self.a2a = a2a_client
        self.llm = llm_client or build_llm_client()
        self.max_retry_count = max_retry_count  # 默认最大重试次数

        # PlannerAgent不维护任何硬编码的系统列表或工具映射
        # 所有信息都从plan config和执行记录（plan_run_logs）动态提取
        
        # 任务重试记录 {plan_instance_id: {task_id: retry_count}}
        self.task_retry_records: Dict[str, Dict[str, int]] = {}
        # 计划运行轨迹：{plan_instance_id: [log_item, ...]}
        self.plan_run_logs: Dict[str, List[Dict[str, Any]]] = {}

    async def on_task_status_change(self, plan_module, plan_id: str, task_id: str, old_status: Optional[str], new_status: str, plan_context: Dict[str, Any]):
        """由 ListenerEngine 触发：统一入口"""
        try:
            # 获取 plan_instance_id（如果存在）
            plan_instance_id = plan_context.get("plan_instance_id")
            
            # 记录状态变化到计划运行轨迹
            log_key = plan_instance_id or plan_id  # 优先使用 plan_instance_id
            self._append_plan_log(log_key, {
                "type": "task_status_change",
                "task_id": task_id,
                "old_status": old_status,
                "new_status": new_status,
                "plan_instance_id": plan_instance_id,
                "timestamp": asyncio.get_event_loop().time(),
            })
            is_main_task = plan_context.get("main_task_id") == task_id

            # 处理任务错误状态（微动态规划）
            if str(new_status).lower() == "error":
                await self._handle_task_error(plan_module, plan_id, task_id, plan_context, is_main_task, plan_instance_id)
                return

            # 只在主任务 Done 时进行状态验证和设置plan状态
            if not (is_main_task and str(new_status).lower() == "done"):
                logger.debug("Planner skipped: not main task done")
                return

            # 记录到execution_logger - 模拟默认侦听器L000DONE被触发
            print(f"[PlannerAgent] ✅ 处理001 Done，模拟触发默认侦听器 listener_id: L000DONE")
            execution_logger.planner_decision(plan_id, "DONE_HANDLER_TRIGGERED", task_id, {
                "virtual_listener_id": "L000DONE",
                "trigger": "001.status == Done",
                "plan_instance_id": plan_instance_id
            })
            
            logger.info(f"Planner verification triggered: main task {task_id} done in plan {plan_id}")
            
            # 设置plan状态为Done
            plan = await plan_module.plan_repo.get_by_id(plan_id)
            if plan:
                await plan_module.plan_repo.update(plan_id, {"status": "Done"})

            # 通过 A2A 查询各系统状态进行验证
            logger.info(f"Extracting employee context from plan_context: {plan_context.keys()}")
            employee_ctx = self._extract_employee_context(plan_context)
            logger.info(f"Employee context extracted: {employee_ctx}")
            
            # 从plan config中提取已执行的agent列表
            logger.info(f"Extracting executed agents from plan config...")
            executed_agents = await self._extract_executed_agents_from_plan(plan_module, plan_id, plan_instance_id, log_key)
            logger.info(f"Executed agents: {executed_agents}")
            
            logger.info(f"Starting system verification via A2A...")
            verification_results = await self._verify_all_systems(executed_agents, employee_ctx)

            # 记录验证结果
            logger.info(f"System verification completed. Results: {verification_results}")
            
            # 更新主任务上下文，记录验证结果
            # 优先更新PlanInstance中的TaskInstance
            if plan_instance_id:
                plan_instance = await plan_module.get_plan_instance(plan_instance_id)
                if plan_instance:
                    main_task_instance = plan_instance.get_main_task_instance()
                    if main_task_instance:
                        if not hasattr(main_task_instance, 'context') or main_task_instance.context is None:
                            main_task_instance.context = {}
                        main_task_instance.context["verification_results"] = verification_results
                        main_task_instance.context["planner_verification"] = "completed"
                        logger.info(f"Updated main task instance context with verification results")
                    
                    # PlannerAgent负责设置plan_instance状态
                    overall_status = verification_results.get("_summary", {}).get("overall_status", "passed")
                    if overall_status == "passed":
                        # 没有显式失败，设置plan_instance为done
                        plan_instance.status = PlanInstanceStatus.DONE.value
                        plan_instance.completed_at = datetime.now()
                        plan_instance.updated_at = datetime.now()
                        logger.info(f"[PlannerAgent] Plan instance {plan_instance_id} marked as done (verification passed)")
                    else:
                        # 有显式失败，设置为error
                        plan_instance.status = PlanInstanceStatus.ERROR.value
                        plan_instance.updated_at = datetime.now()
                        logger.error(f"[PlannerAgent] Plan instance {plan_instance_id} marked as error (verification failed)")
            else:
                # 回退到老的Task模型（向后兼容）
                main_task = await plan_module.task_manager.get_task(task_id)
                if main_task:
                    main_task.context["verification_results"] = verification_results
                    await plan_module.task_repo.update(task_id, {"context": main_task.context})
                    logger.info(f"Updated main task context with verification results")

        except Exception as e:
            logger.error(f"PlannerAgent error: {e}")

    def attach_engine_logger(self, listener_engine):
        """让侦听引擎把侦听器驱动的任务更新也写入 Planner 轨迹。"""
        def _log(plan_id: str, item: Dict[str, Any]):
            self._append_plan_log(plan_id, item)
        listener_engine.set_planner_logger(_log)

    def _append_plan_log(self, log_key: str, item: Dict[str, Any]):
        if log_key not in self.plan_run_logs:
            self.plan_run_logs[log_key] = []
        self.plan_run_logs[log_key].append(item)
    
    def _find_failed_listener_from_logs(self, log_key: str, main_task_id: str) -> Optional[str]:
        """从plan_run_logs中找到最近一次导致主任务Error的侦听器ID"""
        if log_key not in self.plan_run_logs:
            return None
        
        logs = self.plan_run_logs[log_key]
        # 从后往前找，找到最近一次设置主任务为Error的侦听器更新
        for entry in reversed(logs):
            if entry.get("type") == "listener_update":
                if (entry.get("target_task_id") == main_task_id and 
                    entry.get("new_status") == "Error"):
                    return entry.get("listener_id")
        return None
    
    async def _retry_listener_by_id(self, plan_module, plan_id: str, listener_id: str, plan_instance_id: Optional[str] = None):
        """根据listener_id重新执行该侦听器（直接调用，不触发状态变化）"""
        execution_logger.planner_decision(plan_id, "RETRY_LISTENER_BY_ID", listener_id, {"plan_instance_id": plan_instance_id})
        
        print(f"[Planner] 🔄 开始重试侦听器: {listener_id}")
        
        # 获取plan_instance获取listener
        listener = None
        if plan_instance_id:
            plan_instance = await plan_module.get_plan_instance(plan_instance_id)
            if plan_instance and plan_instance.plan:
                # 从plan.listeners中查找
                # listener_id格式：inst_000001_L002，需要提取L002部分
                # plan.listeners中的listener.id是原始ID（如L002）
                original_listener_id = listener_id.replace(f"{plan_instance_id}_", "")
                print(f"[Planner] 查找侦听器: {listener_id} (原始ID: {original_listener_id})")
                
                for l in plan_instance.plan.listeners:
                    # plan.listeners是Dict列表，不是Listener对象列表！
                    l_id = l.get('listener_id') if isinstance(l, dict) else l.id
                    print(f"[Planner] 检查侦听器: l_id={l_id}, 目标={original_listener_id}, 类型={type(l)}")
                    
                    if l_id == original_listener_id:
                        # 找到了！从dict创建Listener对象
                        print(f"[Planner] ✓ 从plan.listeners找到原始侦听器: {l_id}")
                        print(f"[Planner] listener配置: {l}")
                        
                        # 从dict创建listener对象
                        try:
                            listener = Listener(
                                id=listener_id,  # 使用完整ID（带plan_instance_id前缀）
                                plan_id=plan_id,
                                trigger_task_id=l.get('trigger_task_id'),
                                trigger_condition=l.get('trigger_condition', l.get('trigger_status', 'Done')),
                                action_condition='execute',
                                listener_type=l.get('listener_type', l.get('action_type', 'agent')),
                                plan_instance_id=plan_instance_id,
                                agent_id=l.get('agent_id'),
                                action_prompt=l.get('action_prompt'),
                                code_snippet=l.get('code_snippet'),
                                success_output=l.get('success_output'),
                                failure_output=l.get('failure_output')
                            )
                            print(f"[Planner] ✓ 创建侦听器实例成功: id={listener.id}, agent_id={listener.agent_id}, type={listener.listener_type}")
                            break
                        except Exception as e:
                            print(f"[Planner] ❌ 创建侦听器实例失败: {e}")
                            import traceback
                            print(f"[Planner] 错误堆栈:\n{traceback.format_exc()}")
                            raise
        
        if not listener:
            # 回退：从listener_repo查找
            print(f"[Planner] 尝试从listener_repo查找: {listener_id}")
            listener = await plan_module.listener_manager.listener_repo.get_by_id(listener_id)
        
        if not listener:
            logger.warning(f"Listener {listener_id} not found for retry")
            print(f"[Planner] ❌ 未找到侦听器: {listener_id}")
            execution_logger.planner_decision(plan_id, "RETRY_LISTENER_ERROR", listener_id, {"error": "Listener not found"})
            return
        
        print(f"[Planner] 获取到侦听器: id={listener.id}, type={listener.listener_type}, agent_id={getattr(listener, 'agent_id', None)}")
        
        # 获取最新计划上下文（包含所有任务的当前状态）
        plan_context = await plan_module.listener_engine._get_plan_context(plan_id)
        # 如果存在 plan_instance_id，添加到上下文中
        if plan_instance_id:
            plan_context["plan_instance_id"] = plan_instance_id
        
        print(f"[Planner] plan_context内容: tasks数量={len(plan_context.get('tasks', {}))}")
        print(f"[Planner] 主任务001 context keys: {list(plan_context.get('tasks', {}).get('001', {}).get('context', {}).keys())}")
        
        # 检查是否找到了listener
        if not listener:
            print(f"[Planner] ❌ CRITICAL: listener is None after search!")
            execution_logger.planner_decision(plan_id, "RETRY_LISTENER_ERROR", listener_id, {"error": "listener is None"})
            return
        
        print(f"[Planner] ✅ Listener found and ready: id={listener.id}, type={listener.listener_type}")
        
        # 重试listener：直接执行，不需要修改_executed_listeners（它只是历史记录）
        try:
            logger.info(f"Retrying listener {listener_id}")
            print(f"[Planner] 🔄 重试侦听器 {listener_id}")
            
            # 如果有plan_instance，直接通过PlanInstance执行listener
            if plan_instance_id:
                plan_instance = await plan_module.get_plan_instance(plan_instance_id)
                if plan_instance:
                    # 直接执行listener，不修改_executed_listeners（保持历史记录完整）
                    print(f"[Planner] 📌 通过PlanInstance执行侦听器...")
                    result = await plan_module.listener_engine.execute_listener(listener, plan_instance)
                    print(f"[Planner] 📊 侦听器执行结果: success={result.get('success')}, task_updates={len(result.get('task_updates', []))}")
                    
                    # 应用结果（success_output会设置对应的task状态）
                    print(f"[Planner] 📝 应用侦听器结果...")
                    await plan_instance._apply_listener_result(result)
                    print(f"[Planner] ✅ 侦听器结果已应用")
                    
                    execution_logger.planner_decision(plan_id, "RETRY_LISTENER_COMPLETED", listener_id, {
                        "success": result.get('success', False),
                        "task_updates_count": len(result.get('task_updates', []))
                    })
                else:
                    print(f"[Planner] ❌ plan_instance not found")
                    execution_logger.planner_decision(plan_id, "RETRY_LISTENER_ERROR", listener_id, {"error": "plan_instance not found"})
                    return
            else:
                print(f"[Planner] ❌ No plan_instance_id")
                execution_logger.planner_decision(plan_id, "RETRY_LISTENER_ERROR", listener_id, {"error": "plan_instance_id required"})
                return
            
            logger.info(f"Retried listener {listener_id} successfully")
            print(f"[Planner] ✅ 侦听器重试成功: {listener_id}")
        except Exception as e:
            logger.warning(f"Failed to retry listener {listener_id}: {e}")
            print(f"[Planner] ❌ 侦听器重试失败: {listener_id}, error={e}")
            import traceback
            print(f"[Planner] 错误堆栈:\n{traceback.format_exc()}")
            execution_logger.planner_decision(plan_id, "RETRY_LISTENER_ERROR", listener_id, {"error": str(e)})

    async def _extract_executed_agents_from_plan(self, plan_module, plan_id: str, plan_instance_id: Optional[str], log_key: str) -> List[Dict[str, Any]]:
        """
        从plan config中提取已执行的agent列表，并检查哪些agent有验证能力
        
        返回格式：[{"agent_id": "hr", "task_id": "002"}, ...]
        只返回那些在A2A中注册了验证工具的agent
        """
        try:
            # 获取plan配置
            plan = await plan_module.plan_repo.get_by_id(plan_id)
            if not plan or not plan.listeners:
                logger.warning(f"Plan {plan_id} has no listeners")
                return []
            
            # 获取plan_instance，检查哪些任务已完成
            if plan_instance_id:
                plan_instance = await plan_module.get_plan_instance(plan_instance_id)
                if not plan_instance:
                    logger.warning(f"Plan instance {plan_instance_id} not found")
                    return []
                
                # 从listeners配置中提取已执行的agent
                executed_agents = []
                for listener_config in plan.listeners:
                    # 检查listener的success_output中的task_id状态
                    success_output = listener_config.get('success_output', {})
                    target_task_id = success_output.get('task_id')
                    
                    if target_task_id:
                        # 检查该任务是否已完成
                        task_instance = plan_instance.get_task_instance(target_task_id)
                        if task_instance and task_instance.status == "Done":
                            agent_id = listener_config.get('agent_id')
                            
                            # 跳过code类型的listener（没有agent）
                            listener_type = listener_config.get('listener_type', 'agent')
                            if listener_type == 'code':
                                continue
                            
                            if agent_id and agent_id not in [a['agent_id'] for a in executed_agents]:
                                # 所有执行过的agent都加入验证列表
                                # PlannerAgent不知道也不关心agent是否有验证能力
                                # 由BizAgent自己决定如何响应验证请求
                                executed_agents.append({
                                    "agent_id": agent_id,
                                    "task_id": target_task_id,
                                    "task_name": task_instance.name if hasattr(task_instance, 'name') else target_task_id
                                })
                                logger.info(f"Found executed agent: {agent_id} for task {target_task_id}")
                
                return executed_agents
            else:
                # 回退到老方式（向后兼容）
                return []
                
        except Exception as e:
            logger.error(f"Error extracting executed agents: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def _extract_employee_context(self, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        # 从主任务上下文提取员工信息
        # 支持新旧两种上下文格式
        
        # 新格式：PlanInstance的plan_context可能直接包含plan_instance_id
        plan_instance_id = plan_context.get("plan_instance_id")
        
        # 尝试从tasks中获取（老格式）
        main_task_context = plan_context.get("tasks", {}).get("001", {}).get("context", {})
        
        # 新格式可能直接在main_task_context中
        # 老格式在values中
        values = main_task_context if isinstance(main_task_context, dict) else {}
        if "values" in values:
            values = values.get("values", {})
        
        return {
            "employee_id": values.get("id") or values.get("employee_id", "WZ001"),  # 默认值
            "employee_name": values.get("name") or values.get("employee_name", "Will Zhang"),  # 默认值
        }

    async def _verify_all_systems(self, executed_agents: List[Dict[str, Any]], employee_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        通过A2A请求各个BizAgent验证系统状态
        
        完全泛化的设计：
        1. 从executed_agents获取已执行的agent列表（来自plan config）
        2. 对每个agent发送验证请求
        3. BizAgent自己决定调用什么验证工具
        4. 收集并返回所有验证结果
        """
        logger.info(f"Verifying {len(executed_agents)} systems with employee_ctx: {employee_ctx}")
        
        if not executed_agents:
            logger.warning("No executed agents to verify")
            return {}
        
        tasks = []
        agent_infos = []
        
        for agent_info in executed_agents:
            agent_id = agent_info.get("agent_id")
            task_id = agent_info.get("task_id")
            task_name = agent_info.get("task_name", task_id)
            
            logger.info(f"Preparing verification request for agent: {agent_id} (completed task: {task_name})")
            
            # 构建验证请求（泛化的语义请求）
            # PlannerAgent不知道具体要验证什么，只是告诉BizAgent去验证该任务是否成功
            # 重要：如果没有验证工具，应该返回"无法验证"而不是重新执行操作
            verification_action = f"""请验证任务'{task_name}'是否成功完成。

员工信息：
- 姓名：{employee_ctx.get('employee_name')}
- ID：{employee_ctx.get('employee_id')}

注意：
1. 如果你有query_*或check_*类型的验证工具，请使用这些工具查询状态
2. 如果你没有验证工具，请直接返回"无法验证该任务，请使用其他方式确认"
3. 不要重新执行原操作工具（如create_*, grant_*, apply_*, send_*等）
"""
            
            execute_params = {
                "employee_id": employee_ctx.get("employee_id"),
                "employee_name": employee_ctx.get("employee_name"),
                "task_id": task_id,
                "task_name": task_name,
                "action": "verify_task_completion"
            }
            
            logger.info(f"[PlannerAgent] Sending A2A verification request to {agent_id}")
            logger.info(f"[PlannerAgent] Action: {verification_action}")
            logger.info(f"[PlannerAgent] Params: {execute_params}")
            
            # 通过A2A执行
            agent_infos.append(agent_info)
            tasks.append(self.a2a.execute(agent_id, verification_action, execute_params))
        
        logger.info(f"[PlannerAgent] Waiting for {len(tasks)} verification tasks to complete...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.info(f"[PlannerAgent] All verification tasks completed")

        verification: Dict[str, Any] = {}
        has_explicit_failure = False
        
        for i, agent_info in enumerate(agent_infos):
            agent_id = agent_info.get("agent_id")
            r = results[i]
            
            if isinstance(r, Exception):
                logger.error(f"[PlannerAgent] Verification exception for {agent_id}: {r}")
                verification[agent_id] = {
                    "verified": "exception", 
                    "error": str(r),
                    "task_id": agent_info.get("task_id")
                }
                # 异常不算显式失败
            else:
                logger.info(f"[PlannerAgent] Verification result from {agent_id}: success={r.get('success')}, tools_used={r.get('tools_used', [])}")
                
                # 检查bizagent返回的结果
                success = r.get("success", False)
                response = r.get("response", "")
                tools_used = r.get("tools_used", [])
                
                # 判断验证状态
                if not success:
                    # 显式返回失败
                    verified_status = False
                    has_explicit_failure = True
                elif not tools_used or len(tools_used) == 0:
                    # 没有调用任何工具 = 无法验证（但不算失败）
                    verified_status = "unable_to_verify"
                else:
                    # 调用了验证工具且成功
                    verified_status = True
                
                verification[agent_id] = {
                    "verified": verified_status, 
                    "response": response,
                    "tools_used": tools_used,
                    "task_id": agent_info.get("task_id")
                }
                
                logger.info(f"[PlannerAgent] Agent {agent_id} verification status: {verified_status}")
        
        # 添加总体验证状态
        verification["_summary"] = {
            "has_explicit_failure": has_explicit_failure,
            "overall_status": "failed" if has_explicit_failure else "passed"
        }
        
        return verification

    async def _handle_task_error(self, plan_module, plan_id: str, task_id: str, plan_context: Dict[str, Any], is_main_task: bool, plan_instance_id: Optional[str] = None):
        """处理任务错误状态（微动态规划）"""
        log_key = plan_instance_id or plan_id  # 优先使用 plan_instance_id
        logger.info(f"Planner handling task error: plan={plan_id}, task={task_id}, is_main={is_main_task}, instance={plan_instance_id}")
        
        # 记录到execution_logger - 模拟默认侦听器L000ERROR被触发
        print(f"[PlannerAgent] 🔴 处理001 Error，模拟触发默认侦听器 listener_id: L000ERROR")
        execution_logger.planner_decision(plan_id, "ERROR_HANDLER_TRIGGERED", task_id, {
            "virtual_listener_id": "L000ERROR",
            "trigger": "001.status == Error",
            "plan_instance_id": plan_instance_id
        })
        
        # 检查主任务是否已经在"等待resume"状态，如果是，不做重试
        if is_main_task:
            # 获取task instance
            task = None
            if plan_instance_id:
                plan_instance = await plan_module.get_plan_instance(plan_instance_id)
                if plan_instance:
                    task = plan_instance.get_task_instance(task_id)
            
            if task and hasattr(task, 'context') and task.context.get("error_info", {}).get("status") == "waiting_for_resume":
                logger.info(f"Main task {task_id} already in waiting_for_resume state, skip retry")
                return
            
            # 主任务Error：找到导致Error的侦听器，重试该侦听器
            # 而不是重试主任务本身
            
            # 初始化重试记录
            if log_key not in self.task_retry_records:
                self.task_retry_records[log_key] = {}
            
            # 优先从task context中读取failed_listener_id（新的默认机制）
            failed_listener_id = None
            task_context = plan_context.get("tasks", {}).get(task_id, {}).get("context", {})
            print(f"[PlannerAgent] Task {task_id} context keys: {list(task_context.keys())}")
            print(f"[PlannerAgent] Looking for failed_listener_id in context...")
            failed_listener_id = task_context.get("failed_listener_id")
            print(f"[PlannerAgent] failed_listener_id from context: {failed_listener_id}")
            
            if failed_listener_id:
                logger.info(f"Found failed listener from task context: {failed_listener_id}")
            else:
                # 回退到从plan_run_logs查找（向后兼容）
                print(f"[PlannerAgent] failed_listener_id not in context, checking plan_run_logs...")
                failed_listener_id = self._find_failed_listener_from_logs(log_key, task_id)
                if failed_listener_id:
                    logger.info(f"Found failed listener from plan_run_logs: {failed_listener_id}")
                else:
                    print(f"[PlannerAgent] failed_listener_id not found in plan_run_logs either")
            
            if not failed_listener_id:
                logger.warning(f"Cannot find failed listener for main task {task_id}")
                print(f"[PlannerAgent] ERROR: Cannot find failed_listener_id, marking plan as error")
                await self._mark_plan_error(plan_module, plan_id, task_id, 0, plan_instance_id)
                return
            
            print(f"[PlannerAgent] ✓ Found failed listener: {failed_listener_id}, proceeding with retry...")
            
            # 获取该侦听器的重试次数
            retry_key = f"listener_{failed_listener_id}"
            current_retry = self.task_retry_records[log_key].get(retry_key, 0)
            
            if current_retry < self.max_retry_count:
                # 还有重试机会
                current_retry += 1
                self.task_retry_records[log_key][retry_key] = current_retry
                
                logger.info(f"Main task error caused by listener {failed_listener_id}, retrying {current_retry}/{self.max_retry_count}")
                execution_logger.planner_decision(plan_id, "MAIN_TASK_ERROR_RETRY_LISTENER", task_id, {
                    "failed_listener": failed_listener_id,
                    "current_retry": current_retry,
                    "max_retries": self.max_retry_count,
                    "plan_instance_id": plan_instance_id
                })
                
                # 将主任务设置为Retrying状态
                # 其他侦听器不会响应Retrying状态，避免重复触发
                # 只有L007（完成侦听器）会在所有子任务完成后将001设置为Done
                if plan_instance_id:
                    plan_instance = await plan_module.get_plan_instance(plan_instance_id)
                    if plan_instance:
                        main_task_instance = plan_instance.get_main_task_instance()
                        if main_task_instance:
                            # 清除failed_listener_id
                            if "failed_listener_id" in main_task_instance.context:
                                del main_task_instance.context["failed_listener_id"]
                            # 添加重试标记
                            main_task_instance.context["retry_attempt"] = current_retry
                            # 设置为Retrying状态（不会触发其他侦听器）
                            print(f"[PlannerAgent] 设置主任务为Retrying状态（attempt {current_retry}）")
                            main_task_instance.update_status("Retrying", f"retry_listener_{failed_listener_id}_attempt_{current_retry}")
                            logger.info(f"Set main task {task_id} to Retrying status for retry attempt {current_retry}")
                
                # 重新执行失败的侦听器
                # 侦听器成功后会自然推进流程，最终通过L007将主任务设为Done
                await self._retry_listener_by_id(plan_module, plan_id, failed_listener_id, plan_instance_id)
                return
            else:
                # 超过重试次数，标记为等待resume
                logger.warning(f"Listener {failed_listener_id} exceeded max retries ({self.max_retry_count})")
                execution_logger.planner_decision(plan_id, "LISTENER_MAX_RETRIES_EXCEEDED", failed_listener_id, {
                    "current_retry": current_retry,
                    "max_retries": self.max_retry_count
                })
                # 传递failed_listener_id，供resume使用
                await self._mark_plan_error(plan_module, plan_id, task_id, current_retry, plan_instance_id, failed_listener_id)
                # 设置plan状态为Error
                await plan_module.plan_repo.update(plan_id, {"status": "Error"})
                return
        
        # 注意：以下代码是旧的任务级别重试机制，已被listener级别重试机制取代
        # 保留此代码作为向后兼容，但在当前设计中不应该被执行
        # 因为所有listener失败都会设置主任务001为Error，不会有非主任务的Error
        logger.warning(f"Non-main task {task_id} error encountered (should not happen in current design)")
        logger.warning(f"All listener failures should set main task to Error, not subtask {task_id}")
        # 直接将主任务设置为Error，触发listener重试机制
        main_task_id = plan_context.get("main_task_id", "001")
        await self._mark_plan_error(plan_module, plan_id, main_task_id, 0, plan_instance_id)
    
    async def _decide_retry_strategy(self, plan_module, task_id: str, current_retry: int, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """决定重试策略（可以通过 LLM 智能决策）"""
        # 当前简化实现：使用固定重试次数
        # 未来可以根据错误类型、任务重要性等因素智能决定
        return {
            "max_retries": self.max_retry_count,
            "strategy": "immediate"  # immediate | exponential_backoff
        }
    
    # _retry_task方法已移除 - 使用listener级别的重试机制(_retry_listener_by_id)代替

    # _retrigger_upstream_listener方法已移除 - 不再使用任务级别的重试机制
    
    async def _mark_plan_error(self, plan_module, plan_id: str, main_task_id: str, failed_retries: int, plan_instance_id: Optional[str] = None, failed_listener_id: Optional[str] = None):
        """标记计划为错误状态"""
        # 获取task instance
        main_task = None
        if plan_instance_id:
            plan_instance = await plan_module.get_plan_instance(plan_instance_id)
            if plan_instance:
                main_task = plan_instance.get_task_instance(main_task_id)
        
        if main_task:
            main_task.context["error_info"] = {
                "failed_retries": failed_retries,
                "status": "waiting_for_resume",
                "message": f"Task failed after {failed_retries} retries"
            }
            # 保存failed_listener_id供resume使用
            if failed_listener_id:
                main_task.context["failed_listener_id"] = failed_listener_id
                logger.info(f"Saved failed_listener_id to main task context: {failed_listener_id}")
            main_task.status = "Error"
            
            if plan_instance_id:
                # 更新任务实例
                await plan_module.update_task_instance_status(plan_instance_id, main_task_id, "Error", main_task.context)
                
                # 设置plan_instance状态为error
                plan_instance = await plan_module.get_plan_instance(plan_instance_id)
                if plan_instance:
                    plan_instance.status = PlanInstanceStatus.ERROR.value
                    logger.info(f"Plan instance {plan_instance_id} status set to error, waiting for resume")
                
                logger.info(f"Plan instance {plan_instance_id} marked as error, waiting for resume")
            else:
                # 回退到传统更新
                await plan_module.task_repo.update(main_task_id, {
                    "status": "Error",
                    "context": main_task.context
                })
                logger.info(f"Plan {plan_id} marked as error, waiting for resume")
    
    async def resume_plan(self, plan_module, plan_id: str, plan_instance_id: Optional[str] = None) -> bool:
        """恢复错误状态的计划（Resume机制）"""
        log_key = plan_instance_id or plan_id  # 优先使用 plan_instance_id
        logger.info(f"Resuming plan {plan_id} (instance: {plan_instance_id})")
        print(f"[PlannerAgent] 📋 Resume plan: {plan_id}, instance: {plan_instance_id}")
        
        execution_logger.planner_decision(plan_id, "RESUME_PLAN_STARTED", "001", {
            "plan_instance_id": plan_instance_id
        })
        
        # 获取plan_instance和主任务
        if not plan_instance_id:
            logger.error(f"Resume requires plan_instance_id")
            return False
        
        plan_instance = await plan_module.get_plan_instance(plan_instance_id)
        if not plan_instance:
            logger.error(f"Plan instance {plan_instance_id} not found")
            return False
        
        main_task = plan_instance.get_main_task_instance()
        if not main_task or main_task.status != "Error":
            logger.warning(f"Main task is not in Error status: {main_task.status if main_task else 'None'}")
            return False
        
        # 从context读取failed_listener_id
        failed_listener_id = main_task.context.get("failed_listener_id")
        if not failed_listener_id:
            logger.error(f"No failed_listener_id in main task context")
            print(f"[PlannerAgent] ❌ Resume失败: 主任务context中没有failed_listener_id")
            return False
        
        print(f"[PlannerAgent] ✓ 找到失败的侦听器: {failed_listener_id}")
        
        # 清空该计划的重试记录，允许重新尝试
        if log_key in self.task_retry_records:
            old_records = self.task_retry_records[log_key].copy()
            self.task_retry_records[log_key] = {}
            print(f"[PlannerAgent] 清除重试记录: {old_records}")
            logger.info(f"Reset retry records for plan {log_key}: {old_records}")
        
        # 清除error_info中的waiting_for_resume状态
        if "error_info" in main_task.context:
            main_task.context["error_info"]["status"] = "resuming"
            print(f"[PlannerAgent] 设置error_info.status = resuming")
        
        # 恢复plan_instance状态为running（允许自我驱动循环继续）
        print(f"[PlannerAgent] 恢复plan_instance.status: error → running")
        plan_instance.status = PlanInstanceStatus.RUNNING.value
        
        # 设置主任务为Retrying状态（类似自动重试）
        print(f"[PlannerAgent] 设置主任务为Retrying状态（resume）")
        main_task.update_status("Retrying", "resume_retry_listener")
        
        # 清除failed_listener_id
        if "failed_listener_id" in main_task.context:
            del main_task.context["failed_listener_id"]
        
        execution_logger.planner_decision(plan_id, "RESUME_RETRY_LISTENER", failed_listener_id, {
            "plan_instance_id": plan_instance_id
        })
        
        # 重新执行失败的侦听器（与自动重试使用相同的逻辑）
        try:
            await self._retry_listener_by_id(plan_module, plan_id, failed_listener_id, plan_instance_id)
            print(f"[PlannerAgent] ✅ Resume成功: 侦听器 {failed_listener_id} 已重新执行")
            
            # 不需要重新启动自我驱动循环
            # 原因：
            # 1. L002成功后会通过listener机制自然推进后续流程
            # 2. 如果重新启动循环，会导致重复扫描已完成的任务，触发重复的listener
            # 3. plan_instance.status已设置为RUNNING，如果循环还在运行会自动继续
            
            # 只在循环已经完全退出时才重新启动
            import asyncio
            if not hasattr(plan_instance, '_execution_task') or plan_instance._execution_task is None or plan_instance._execution_task.done():
                print(f"[PlannerAgent] 自我驱动循环已退出，重新启动...")
                try:
                    loop = asyncio.get_running_loop()
                    # 创建新的执行任务，但会扫描已处理的状态（这是问题所在）
                    # 更好的方式是：不重新启动，让listener引擎继续推进流程
                    # task = loop.create_task(plan_instance.run_self_driven())
                    # plan_instance._execution_task = task
                    
                    # 实际上不需要重新启动，listener成功会继续推进流程
                    print(f"[PlannerAgent] ⚠️ 跳过重新启动循环，由listener引擎继续推进流程")
                except Exception as e:
                    logger.warning(f"Failed to restart self-driven loop: {e}")
                    print(f"[PlannerAgent] ⚠️ 检查循环状态失败: {e}")
            else:
                print(f"[PlannerAgent] ✅ 自我驱动循环仍在运行，无需重新启动")
            
            execution_logger.planner_decision(plan_id, "RESUME_PLAN_COMPLETED", "001", {
                "plan_instance_id": plan_instance_id
            })
            return True
        except Exception as e:
            logger.error(f"Failed to resume plan {plan_id}: {e}")
            print(f"[PlannerAgent] ❌ Resume失败: {e}")
            execution_logger.planner_decision(plan_id, "RESUME_PLAN_ERROR", "001", {
                "error": str(e),
                "plan_instance_id": plan_instance_id
            })
            return False

    # 动态任务生成功能已移除，专注于状态验证和微动态规划
    # 未来可在下一个特性中重新实现


