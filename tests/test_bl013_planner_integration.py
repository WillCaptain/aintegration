import asyncio
import pytest
import pytest_asyncio

from src.core.plan_module import PlanModule
from src.infrastructure.a2a_server import A2AServer
from src.infrastructure.a2a_client import DefaultA2AClient
from src.database.memory_repositories import MemoryDatabaseConnection
from src.models.task import TaskStatus


@pytest_asyncio.fixture
async def plan_module_with_planner():
    db = MemoryDatabaseConnection()
    pm = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
    await pm.start()
    try:
        yield pm
    finally:
        await pm.stop()


@pytest.mark.asyncio
async def test_planner_triggers_on_main_done_and_adds_tasks(plan_module_with_planner):
    pm = plan_module_with_planner

    # 准备A2A Server并注册三个具备查询能力的虚拟Agent（返回默认success结构）
    a2a = A2AServer()
    await a2a.register_agent({
        "agent_id": "hr_agent_cfg",
        "agent_name": "HR Agent (cfg)",
        "provider": "internal",
        "version": "1.0.0",
        "capabilities": ["query_profile"],
        "endpoints": {"execute": "/agents/hr/execute"}
    })
    await a2a.register_agent({
        "agent_id": "inv_agent_cfg",
        "agent_name": "Inventory Agent (cfg)",
        "provider": "internal",
        "version": "1.0.0",
        "capabilities": ["check_outbound_status"],
        "endpoints": {"execute": "/agents/inv/execute"}
    })
    await a2a.register_agent({
        "agent_id": "access_agent_cfg",
        "agent_name": "Access Agent (cfg)",
        "provider": "internal",
        "version": "1.0.0",
        "capabilities": ["query_access"],
        "endpoints": {"execute": "/agents/access/execute"}
    })

    # 将A2A客户端注入PlanModule
    pm.set_a2a_client(DefaultA2AClient(a2a))

    # 创建最小计划：仅有主任务001
    plan_config = {
        "plan_id": "planner_demo",
        "name": "Planner触发演示",
        "description": "主任务完成后由Planner动态补齐",
        "main_task_id": "001",
        "tasks": [
            {"task_id": "001", "name": "主任务", "prompt": "完成主任务"}
        ],
        "listeners": []
    }
    plan_id = await pm.create_plan_from_config(plan_config)

    # 将主任务置为Done，触发Planner（ListenerEngine会回调）
    await pm.listener_engine.trigger_task_status_change(
        "001",
        TaskStatus.NOT_STARTED.value,
        TaskStatus.DONE.value,
        plan_id
    )

    # 等待Planner处理
    await asyncio.sleep(0.5)

    # 校验Planner已动态添加任务与侦听器（002/004/005，以及收敛邮件006的监听）
    tasks = await pm.task_manager.get_plan_tasks(plan_id)
    task_ids = {t.id for t in tasks}
    assert {"002", "004", "005"}.issubset(task_ids)

    # 监听器数量应至少新增3个（profile/outbound/access），可能还包含邮件收敛
    listeners_002 = await pm.listener_manager.get_listeners_by_task("002")
    listeners_004 = await pm.listener_manager.get_listeners_by_task("004")
    listeners_005 = await pm.listener_manager.get_listeners_by_task("005")
    assert len(listeners_002) >= 1
    assert len(listeners_004) >= 1
    assert len(listeners_005) >= 1


