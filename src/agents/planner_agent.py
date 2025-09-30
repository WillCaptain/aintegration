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

from ..infrastructure.a2a_client import A2AClient
from ..infrastructure.llm_client import build_llm_client

logger = logging.getLogger(__name__)


class PlannerAgent:
    def __init__(self, a2a_client: A2AClient, llm_client=None):
        self.a2a = a2a_client
        self.llm = llm_client or build_llm_client()

        # 能力到 agent 的映射将通过 A2AClient 动态发现
        self.required_capabilities = {
            "hr": "query_profile",              # HR 查询档案
            "inventory": "check_outbound_status",  # 库存查询出库
            "access": "query_access"           # 门禁查询
        }

    async def on_task_status_change(self, plan_module, plan_id: str, task_id: str, old_status: Optional[str], new_status: str, plan_context: Dict[str, Any]):
        """由 ListenerEngine 触发：统一入口"""
        try:
            is_main_task = plan_context.get("main_task_id") == task_id

            # 只在主任务 Done 时进行状态验证
            if not (is_main_task and str(new_status).lower() == "done"):
                logger.debug("Planner skipped: not main task done")
                return

            logger.info(f"Planner verification triggered: main task {task_id} done in plan {plan_id}")

            # 通过 A2A 查询各系统状态进行验证
            employee_ctx = self._extract_employee_context(plan_context)
            verification_results = await self._verify_all_systems(employee_ctx)

            # 记录验证结果
            logger.info(f"System verification results: {verification_results}")
            
            # 更新主任务上下文，记录验证结果
            main_task = await plan_module.task_manager.get_task(task_id)
            if main_task:
                main_task.context["verification_results"] = verification_results
                await plan_module.task_repo.update(task_id, {"context": main_task.context})
                logger.info(f"Updated main task context with verification results")

        except Exception as e:
            logger.error(f"PlannerAgent error: {e}")

    def _extract_employee_context(self, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        # 从主任务上下文提取员工信息
        # 主任务上下文包含员工的基本信息
        main_task_context = plan_context.get("tasks", {}).get("001", {}).get("context", {})
        values = main_task_context.get("values", {})
        
        return {
            "employee_id": values.get("id", "WZ001"),  # 默认值
            "employee_name": values.get("name", "Will Zhang"),  # 默认值
        }

    async def _verify_all_systems(self, employee_ctx: Dict[str, Any]) -> Dict[str, Any]:
        tasks = []
        keys = []
        for key, capability in self.required_capabilities.items():
            agent_id = await self.a2a.find_agent_by_capability(capability)
            if not agent_id:
                logger.warning(f"No agent provides capability: {capability}")
                continue
            keys.append(key)
            tasks.append(self.a2a.execute(agent_id, capability, {
                "employee_id": employee_ctx.get("employee_id"),
                "employee_name": employee_ctx.get("employee_name"),
            }))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verification: Dict[str, Any] = {}
        for i, key in enumerate(keys):
            r = results[i]
            if isinstance(r, Exception):
                verification[key] = {"verified": False, "error": str(r)}
            else:
                verified = r.get("success") and r.get("data", {}).get("verified", False)
                verification[key] = {"verified": bool(verified), "raw": r}
        return verification

    # 动态任务生成功能已移除，专注于状态验证
    # 未来可在下一个特性中重新实现


