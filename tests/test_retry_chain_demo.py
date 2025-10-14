"""
演示微动态规划的完整重试链条

通过日志文件清晰展示：任务失败 -> Planner 重试 -> 最终成功
"""

import pytest
import asyncio
import os
import json
from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule
from src.infrastructure.a2a_server import A2AServer
from src.infrastructure.a2a_client import DefaultA2AClient

# 模拟调用计数器
call_counter = {"grant_access_count": 0}

@pytest.mark.asyncio
async def test_retry_chain_with_logging():
    """演示完整的重试链条并记录到日志"""
    print("\n" + "="*80)
    print("演示：微动态规划 - 任务失败自动重试链条")
    print("="*80)
    
    # 清理旧日志
    log_file = "tests/.artifacts/retry_chain.log"
    if os.path.exists(log_file):
        os.remove(log_file)
    
    def log_event(event_type, details):
        """记录事件到日志文件"""
        os.makedirs("tests/.artifacts", exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            entry = {
                "timestamp": asyncio.get_event_loop().time(),
                "event": event_type,
                "details": details
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[日志] {event_type}: {details}")
    
    # 初始化 PlanModule
    db = MemoryDatabaseConnection()
    plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
    
    # 设置 A2A 客户端
    a2a_server = A2AServer()
    plan_module.set_a2a_client(DefaultA2AClient(a2a_server))
    await plan_module.start()
    
    # 设置最大重试次数为 2
    plan_module.planner_agent.max_retry_count = 1
    
    log_event("系统初始化", "PlanModule 和 PlannerAgent 已启动")
    
    # 创建测试计划
    plan_config = {
        "plan_id": "demo_retry_chain",
        "name": "重试链条演示",
        "description": "展示任务失败和 Planner 自动重试",
        "main_task_id": "001",
        "tasks": [
            {"task_id": "001", "name": "主任务", "prompt": "主任务", "status": "NotStarted"},
            {"task_id": "002", "name": "门禁申请", "prompt": "门禁申请", "status": "NotStarted"},
            {"task_id": "003", "name": "完成任务", "prompt": "完成", "status": "NotStarted"},
        ],
        "listeners": [
            {
                "listener_id": "L001",
                "trigger_task_id": "001",
                "trigger_condition": "001.status == Running",
                "listener_type": "code",
                "code_snippet": """
# 启动门禁申请任务
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
# 模拟门禁申请：检查重试次数，第1次失败，第2次成功
retry_info = context.get("tasks", {}).get("002", {}).get("context", {}).get("retry_info", {})
attempt = retry_info.get("attempt", 0)

if attempt == 0:
    # 第1次执行（没有重试记录）- 失败
    result = {"success": False, "target_task": "002", "target_status": "Error", "context": {"error": "门禁系统连接失败", "attempt": 1}}
else:
    # 重试后执行 - 成功
    result = {"success": True, "target_task": "002", "target_status": "Done", "context": {"access_id": "ACC001", "attempt": attempt + 1}}
""",
                "success_output": {"task_id": "002", "status": "Done", "context": {}},
                "failure_output": {"task_id": "002", "status": "Error", "context": {}}
            },
            {
                "listener_id": "L003a",
                "trigger_task_id": "002",
                "trigger_condition": "002.status == NotStarted",
                "listener_type": "code",
                "code_snippet": """
# 重试时（重置为 NotStarted）重新启动任务
result = {"success": True, "target_task": "002", "target_status": "Running", "context": {}}
""",
                "success_output": {"task_id": "002", "status": "Running", "context": {}}
            },

            {
                "listener_id": "L004",
                "trigger_task_id": "002",
                "trigger_condition": "002.status == Done",
                "listener_type": "code",
                "code_snippet": """
# 门禁成功后完成主任务
result = {"success": True, "target_task": "001", "target_status": "Done", "context": {"completed": True}}
""",
                "success_output": {"task_id": "001", "status": "Done", "context": {"completed": True}}
            },
        ]
    }
    
    plan_id = await plan_module.create_plan_from_config(plan_config)
    log_event("计划创建", f"Plan ID: {plan_id}")
    
    # 启动计划执行
    success = await plan_module.listener_engine.start_plan_execution(plan_id)
    log_event("计划启动", f"执行状态: {success}")
    
    # 等待执行完成
    for i in range(15):
        await asyncio.sleep(2)
        task_002 = await plan_module.task_manager.get_task("002")
        main_task = await plan_module.task_manager.get_task("001")
        
        log_event("状态检查", {
            "task_002": task_002.status,
            "task_002_retry": task_002.context.get("retry_info", {}),
            "main_task": main_task.status
        })
        
        if main_task.status == "Done":
            log_event("流程完成", "主任务已完成")
            break
    
    # 最终验证
    main_task = await plan_module.task_manager.get_task("001")
    task_002 = await plan_module.task_manager.get_task("002")
    
    print("\n" + "="*80)
    print("最终状态")
    print("="*80)
    print(f"主任务状态: {main_task.status}")
    print(f"任务 002 状态: {task_002.status}")
    print(f"任务 002 上下文: {task_002.context}")
    
    # 检查重试记录
    retry_records = plan_module.planner_agent.task_retry_records.get(plan_id, {})
    print(f"Planner 重试记录: {retry_records}")
    
    # 验证
    assert main_task.status == "Done", f"Expected Done, got {main_task.status}"
    assert task_002.status == "Done", f"Expected task 002 Done, got {task_002.status}"
    assert retry_records.get("002", 0) >= 1, "Should have at least 1 retry"
    
    print("\n" + "="*80)
    print("日志链条")
    print("="*80)
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            print(f"{event['event']}: {event['details']}")
    
    print("\n✅ 重试链条演示测试通过")
    print("请查看日志文件: tests/.artifacts/retry_chain.log")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
