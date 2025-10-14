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
        
        # 获取侦听器
        listener = await plan_module.listener_manager.listener_repo.get_by_id(listener_id)
        if not listener:
            logger.warning(f"Listener {listener_id} not found for retry")
            return
        
        print(f"[Planner] 获取到侦听器: id={listener.id}, type={listener.listener_type}, agent_id={getattr(listener, 'agent_id', None)}")
        
        # 获取最新计划上下文（包含所有任务的当前状态）
        plan_context = await plan_module.listener_engine._get_plan_context(plan_id)
        # 如果存在 plan_instance_id，添加到上下文中
        if plan_instance_id:
            plan_context["plan_instance_id"] = plan_instance_id
        
        print(f"[Planner] plan_context内容: tasks数量={len(plan_context.get('tasks', {}))}")
        print(f"[Planner] 主任务001 context keys: {list(plan_context.get('tasks', {}).get('001', {}).get('context', {}).keys())}")
        
        # 使用与状态变化相同的方式执行侦听器：调用_execute_triggered_listeners
        try:
            logger.info(f"Retrying listener {listener_id} via _execute_triggered_listeners")
            print(f"[Planner] 通过_execute_triggered_listeners重试侦听器 {listener_id}")
            
            # 使用ListenerEngine的_execute_triggered_listeners方法，确保执行路径完全一致
            await plan_module.listener_engine._execute_triggered_listeners([listener], plan_context)
            
            execution_logger.planner_decision(plan_id, "RETRY_LISTENER_COMPLETED", listener_id, {})
            logger.info(f"Retried listener {listener_id} successfully")
        except Exception as e:
            logger.warning(f"Failed to retry listener {listener_id}: {e}")
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
        
        # 检查主任务是否已经在"等待resume"状态，如果是，不做重试
        if is_main_task:
            # 使用统一的查询方法，优先实例查询
            task = await plan_module.get_task_with_instance_fallback(task_id, plan_instance_id)
            if task and task.context.get("error_info", {}).get("status") == "waiting_for_resume":
                logger.info(f"Main task {task_id} already in waiting_for_resume state, skip retry")
                return
            
            # 主任务Error：从plan_run_logs找到导致Error的侦听器，重试该侦听器
            # 而不是重试主任务本身
            
            # 初始化重试记录
            if log_key not in self.task_retry_records:
                self.task_retry_records[log_key] = {}
            
            # 使用侦听器ID作为重试计数的key
            failed_listener_id = self._find_failed_listener_from_logs(log_key, task_id)
            if not failed_listener_id:
                logger.warning(f"Cannot find failed listener for main task {task_id}")
                await self._mark_plan_error(plan_module, plan_id, task_id, 0, plan_instance_id)
                return
            
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
                
                # 不改变主任务状态（保持Error），只重新执行失败的侦听器
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
                await self._mark_plan_error(plan_module, plan_id, task_id, current_retry, plan_instance_id)
                # 设置plan状态为Error
                await plan_module.plan_repo.update(plan_id, {"status": "Error"})
                return

        # 初始化重试记录
        if log_key not in self.task_retry_records:
            self.task_retry_records[log_key] = {}
        
        # 获取当前重试次数
        current_retry = self.task_retry_records[log_key].get(task_id, 0)
        
        # 从 LLM 获取重试决策（可以根据错误类型智能决定重试次数）
        retry_decision = await self._decide_retry_strategy(plan_module, task_id, current_retry, plan_context)
        max_retries = retry_decision.get("max_retries", self.max_retry_count)
        
        if current_retry < max_retries:
            # 还有重试机会，重新设置任务状态触发重试
            current_retry += 1
            self.task_retry_records[log_key][task_id] = current_retry
            
            logger.info(f"Retrying task {task_id}: attempt {current_retry}/{max_retries}")
            
            # 记录Planner重试决策
            execution_logger.planner_decision(
                plan_id, "RETRY_TASK", task_id,
                {"current_retry": current_retry, "max_retries": max_retries, "remaining": max_retries - current_retry}
            )
            
            # 重置任务状态为 NotStarted，让侦听器重新触发
            await self._retry_task(plan_module, task_id, current_retry, plan_instance_id)
            
        else:
            # 超过重试次数
            logger.warning(f"Task {task_id} exceeded max retries ({max_retries}), no more retries")
            
            # 记录超限决策
            execution_logger.planner_decision(
                plan_id, "MAX_RETRIES_EXCEEDED", task_id,
                {"current_retry": current_retry, "max_retries": max_retries, "is_main_task": is_main_task}
            )
            
            if is_main_task:
                # 如果是主任务，保持 Error 状态，等待 resume
                logger.info(f"Main task {task_id} in Error state, waiting for resume")
                await self._mark_plan_error(plan_module, plan_id, task_id, current_retry)
            else:
                # 如果是子任务，将主任务也设置为 Error
                main_task_id = plan_context.get("main_task_id")
                if main_task_id:
                    logger.info(f"Setting main task {main_task_id} to Error due to subtask {task_id} failure")
                    
                    # 记录主任务Error决策
                    execution_logger.planner_decision(
                        plan_id, "SET_MAIN_TASK_ERROR", main_task_id,
                        {"reason": f"subtask_{task_id}_exceeded_retries", "subtask_retries": current_retry}
                    )
                    
                    # 调用 _mark_plan_error 来正确记录 error_info（内部已更新数据库）
                    await self._mark_plan_error(plan_module, plan_id, main_task_id, current_retry)
                    # 不要触发状态变化事件，避免递归触发Planner自己的重试逻辑
    
    async def _decide_retry_strategy(self, plan_module, task_id: str, current_retry: int, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """决定重试策略（可以通过 LLM 智能决策）"""
        # 当前简化实现：使用固定重试次数
        # 未来可以根据错误类型、任务重要性等因素智能决定
        return {
            "max_retries": self.max_retry_count,
            "strategy": "immediate"  # immediate | exponential_backoff
        }
    
    async def _retry_task(self, plan_module, task_id: str, retry_attempt: int, plan_instance_id: Optional[str] = None):
        """重试任务：重置任务状态"""
        # 使用统一的查询方法，优先实例查询
        task = await plan_module.get_task_with_instance_fallback(task_id, plan_instance_id)
        if not task:
            logger.error(f"Task {task_id} not found for retry")
            return
        
        old_status = task.status
        plan_id = task.plan_id
        
        # 记录重试信息到任务上下文
        if "retry_info" not in task.context:
            task.context["retry_info"] = {}
        task.context["retry_info"]["attempt"] = retry_attempt
        task.context["retry_info"]["last_retry_time"] = json.dumps({"time": "now"})  # 简化时间记录
        
        if plan_instance_id:
            # 更新任务实例
            await plan_module.update_task_instance_status(plan_instance_id, task_id, "NotStarted", task.context)
        else:
            # 回退到传统更新
            await plan_module.task_repo.update(task_id, {
                "status": "NotStarted",
                "context": task.context
            })
        
        # 触发状态变化事件，让侦听器扫描
        await plan_module.listener_engine.trigger_task_status_change(
            task_id, old_status, "NotStarted", plan_id, plan_instance_id
        )
        
        logger.info(f"Task {task_id} reset to NotStarted for retry attempt {retry_attempt}")

        # 同步：尝试重新触发上游侦听器（让驱动该任务的侦听器再次评估）
        try:
            await self._retrigger_upstream_listener(plan_module, plan_id, task_id, plan_instance_id)
        except Exception as e:
            logger.warning(f"Failed to retrigger upstream for task {task_id}: {e}")

    async def _retrigger_upstream_listener(self, plan_module, plan_id: str, failed_task_id: str, plan_instance_id: Optional[str] = None) -> None:
        """直接重放上游侦听器一次（而非仅投递状态事件），确保重试链路被真正执行。"""
        logger.info(f"Retriggering upstream listener for task {failed_task_id}")
        execution_logger.planner_decision(plan_id, "RETRIGGER_UPSTREAM", failed_task_id, {})
        
        listeners = await plan_module.listener_manager.listener_repo.get_by_plan_id(plan_id)
        # 找出以 failed_task_id 为目标输出的侦听器（成功或失败输出）
        upstream_listeners = []
        for ls in listeners:
            try:
                so = getattr(ls, "success_output", None) or {}
                fo = getattr(ls, "failure_output", None) or {}
                if (so.get("task_id") == failed_task_id) or (fo.get("task_id") == failed_task_id):
                    upstream_listeners.append(ls)
                    logger.info(f"Found upstream listener {ls.id} for task {failed_task_id}")
            except Exception as e:
                logger.warning(f"Error checking listener {getattr(ls, 'id', '?')}: {e}")
                continue
        if not upstream_listeners:
            logger.info(f"No upstream listeners found for failed task {failed_task_id}")
            execution_logger.planner_decision(plan_id, "NO_UPSTREAM_FOUND", failed_task_id, {})
            return
        # 获取最新计划上下文
        plan_context = await plan_module.listener_engine._get_plan_context(plan_id)
        # 如果存在 plan_instance_id，添加到上下文中
        if plan_instance_id:
            plan_context["plan_instance_id"] = plan_instance_id
        # 逐个执行这些上游侦听器，并应用更新
        for ls in upstream_listeners:
            try:
                execution_logger.planner_decision(plan_id, "EXECUTING_UPSTREAM", failed_task_id, {"listener_id": ls.id, "plan_instance_id": plan_instance_id})
                result = await plan_module.listener_engine.task_driver.execute_listener(ls, plan_context)
                updates = plan_module.listener_engine.task_driver.determine_task_updates(ls, result)
                execution_logger.planner_decision(plan_id, "UPSTREAM_RESULT", failed_task_id, {
                    "listener_id": ls.id, 
                    "success": result.get("success", False),
                    "updates_count": len(updates)
                })
                for upd in updates:
                    await plan_module.listener_engine._apply_task_update(upd)
                logger.info(f"Replayed upstream listener {ls.id} to drive task {failed_task_id}")
            except Exception as e:
                logger.warning(f"Failed to replay upstream listener {getattr(ls,'id','?')}: {e}")
                execution_logger.planner_decision(plan_id, "UPSTREAM_ERROR", failed_task_id, {
                    "listener_id": getattr(ls, 'id', '?'),
                    "error": str(e)
                })
    
    async def _mark_plan_error(self, plan_module, plan_id: str, main_task_id: str, failed_retries: int, plan_instance_id: Optional[str] = None):
        """标记计划为错误状态"""
        # 使用统一的查询方法，优先实例查询
        main_task = await plan_module.get_task_with_instance_fallback(main_task_id, plan_instance_id)
        if main_task:
            main_task.context["error_info"] = {
                "failed_retries": failed_retries,
                "status": "waiting_for_resume",
                "message": f"Task failed after {failed_retries} retries"
            }
            main_task.status = "Error"
            
            if plan_instance_id:
                # 更新任务实例
                await plan_module.update_task_instance_status(plan_instance_id, main_task_id, "Error", main_task.context)
                logger.info(f"Plan instance {plan_instance_id} marked as error, waiting for resume")
            else:
                # 回退到传统更新
                await plan_module.task_repo.update(main_task_id, {
                    "status": "Error",
                    "context": main_task.context
                })
                logger.info(f"Plan {plan_id} marked as error, waiting for resume")
    
    async def resume_plan(self, plan_module, plan_id: str, plan_instance_id: Optional[str] = None) -> bool:
        """恢复错误状态的计划"""
        log_key = plan_instance_id or plan_id  # 优先使用 plan_instance_id
        logger.info(f"Resuming plan {plan_id} (instance: {plan_instance_id})")
        
        # 获取计划中处于 Error 状态的任务
        if plan_instance_id:
            # 使用实例查询
            tasks = await plan_module.get_plan_instance_tasks(plan_instance_id)
            error_tasks = [t for t in tasks if t.status == "Error"]
        else:
            # 回退到传统查询
            tasks = await plan_module.task_manager.get_plan_tasks(plan_id)
            error_tasks = [t for t in tasks if t.status == "Error"]
        
        if not error_tasks:
            logger.warning(f"No error tasks found in plan {plan_id}")
            return False

        # 可选：清空该计划的重试记录，便于重新尝试
        if log_key in self.task_retry_records:
            self.task_retry_records[log_key] = {}
            logger.info(f"Reset all retry records for plan {log_key}")

        # 不修改任何任务状态；改为针对每个错误任务，重放其上游侦听器一次
        replay_count = 0
        for task in error_tasks:
            try:
                logger.info(f"Replaying upstream listeners for error task {task.id}")
                await self._retrigger_upstream_listener(plan_module, plan_id, task.id, plan_instance_id)
                replay_count += 1
            except Exception as e:
                logger.warning(f"Failed to replay upstream for {task.id}: {e}")

        return replay_count > 0

    # 动态任务生成功能已移除，专注于状态验证和微动态规划
    # 未来可在下一个特性中重新实现


