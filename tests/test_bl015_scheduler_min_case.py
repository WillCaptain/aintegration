import asyncio
import pytest

from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule


@pytest.mark.asyncio
async def test_min_scheduler_code_listener_fail_retry_to_main_error():
    """
    最小复现：仅用代码侦听器，不用 Agent。

    - 任务: 001(主) 002(子)
    - L001: 001 Running -> 002 Running（启动子任务）
    - L002: 002 Running -> 002 Error（始终失败）
    - 期望：Planner 重试 2 次后超限，将主任务置为 Error
    """

    # 初始化
    db = MemoryDatabaseConnection()
    plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
    await plan_module.start()

    # 缩短最大重试到 2，方便断言
    plan_module.planner_agent.max_retry_count = 2

    # 计划与侦听器
    plan_config = {
        "plan_id": "min_sched_fail",
        "name": "min-case",
        "description": "code-listener only",
        "main_task_id": "001",
        "tasks": [
            {"task_id": "001", "name": "主任务", "prompt": "", "status": "NotStarted"},
            {"task_id": "002", "name": "子任务", "prompt": "", "status": "NotStarted"},
        ],
        "listeners": [
            {
                "listener_id": "L001",
                "trigger_task_id": "001",
                "trigger_condition": "001.status == Running",
                "listener_type": "code",
                "code_snippet": """
# 启动子任务
result = {"success": True, "target_task": "002", "target_status": "Running", "context": {}}
""",
                "success_output": {"task_id": "002", "status": "Running", "context": {}}
            },
            {
                "listener_id": "L002",
                "trigger_task_id": "002",
                "trigger_condition": "002.status == Running",
                "listener_type": "code",
                "code_snippet": """
# 第一次失败，第二次成功（依据 Planner 注入的 retry_info.attempt）
retry_info = context.get("tasks", {}).get("002", {}).get("context", {}).get("retry_info", {})
attempt = retry_info.get("attempt", 0)
if attempt == 0:
    # 初次执行：失败，触发 Planner 重试
    result = {"success": False, "target_task": "002", "target_status": "Error", "context": {"reason": "simulated_first"}}
else:
    # 重试后：成功
    result = {"success": True, "target_task": "002", "target_status": "Done", "context": {"note": "retried_success"}}
""",
                "success_output": {"task_id": "002", "status": "Done", "context": {}},
                "failure_output": {"task_id": "002", "status": "Error", "context": {}}
            },
            {
                "listener_id": "L003",
                "trigger_task_id": "002",
                "trigger_condition": "002.status == Done",
                "listener_type": "code",
                "code_snippet": """
# 子任务完成后，完成主任务
result = {"success": True, "target_task": "001", "target_status": "Done", "context": {"completed": True}}
""",
                "success_output": {"task_id": "001", "status": "Done", "context": {"completed": True}}
            },
        ]
    }

    plan_id = await plan_module.create_plan_from_config(plan_config)

    # 启动执行
    ok = await plan_module.listener_engine.start_plan_execution(plan_id)
    assert ok
    # 等主任务进入 Running，确保侦听链条开始
    for _ in range(10):
        mt = await plan_module.task_manager.get_task("001")
        if mt.status == "Running":
            break
        await asyncio.sleep(0.1)

    # 等待 Planner 重试后成功
    # 说明：一次失败 -> Planner 重置 -> 再次执行成功
    for _ in range(40):
        await asyncio.sleep(0.5)
        main_task = await plan_module.task_manager.get_task("001")
        if main_task.status == "Done":
            break

    main_task = await plan_module.task_manager.get_task("001")
    sub_task = await plan_module.task_manager.get_task("002")

    # 断言：子任务在第二次尝试后成功，主任务完成
    assert sub_task.status == "Done", f"sub status: {sub_task.status}"
    assert main_task.status == "Done", f"main status: {main_task.status}"

    # Planner 的重试记录应 >= 1
    retries = plan_module.planner_agent.task_retry_records.get(plan_id, {}).get("002", 0)
    assert retries >= 1, f"retries: {retries}"

    await plan_module.stop()


