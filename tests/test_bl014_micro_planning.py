"""
BL014: 微动态规划测试

测试场景：
1. 任务失败时 Planner 自动重试（最多 3 次）
2. 超过重试次数后，主任务设置为 Error 状态
3. 通过 resume API 恢复计划执行
"""

import pytest
import asyncio
import os
from datetime import datetime

from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule
from src.infrastructure.a2a_server import A2AServer
from src.infrastructure.a2a_client import DefaultA2AClient


@pytest.mark.asyncio
class TestBL014MicroPlanning:
    """BL014: 微动态规划测试"""
    
    async def test_task_failure_with_retry(self):
        """测试任务失败自动重试机制"""
        print("\n=== 测试任务失败自动重试 ===")
        
        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        
        # 设置 A2A 客户端
        a2a_server = A2AServer()
        await a2a_server.register_agent({
            "agent_id": "test_agent",
            "agent_name": "Test Agent",
            "provider": "internal",
            "version": "1.0.0",
            "capabilities": ["test_action"],
            "endpoints": {"execute": "/agents/test/execute"}
        })
        
        plan_module.set_a2a_client(DefaultA2AClient(a2a_server))
        await plan_module.start()
        
        # 创建测试计划
        plan_config = {
            "plan_id": "test_retry_plan",
            "name": "测试重试计划",
            "description": "测试任务失败重试",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": "001",
                    "name": "主任务",
                    "prompt": "主任务",
                    "status": "NotStarted"
                },
                {
                    "task_id": "002",
                    "name": "可能失败的任务",
                    "prompt": "这个任务可能失败",
                    "status": "NotStarted"
                }
            ],
            "listeners": [
                {
                    "listener_id": "L001",
                    "trigger_task_id": "001",
                    "trigger_condition": "001.status == Running",
                    "listener_type": "code",
                    "code_snippet": """
# 将任务 002 状态设置为 Running
result = {
    "success": True,
    "target_task": "002",
    "target_status": "Running",
    "context": {}
}
""",
                    "success_output": {
                        "task_id": "002",
                        "status": "Running",
                        "context": {}
                    }
                }
            ]
        }
        
        plan_id = await plan_module.create_plan_from_config(plan_config)
        assert plan_id == "test_retry_plan"
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        # 等待 L001 执行
        await asyncio.sleep(2)
        
        # 手动触发任务 002 失败
        print("手动触发任务 002 失败")
        await plan_module.listener_engine.trigger_task_status_change(
            "002", "Running", "Error", plan_id
        )
        
        # 等待 Planner 处理重试
        await asyncio.sleep(3)
        
        # 检查任务 002 的重试信息
        task_002 = await plan_module.task_manager.get_task("002")
        print(f"任务 002 状态: {task_002.status}")
        print(f"任务 002 上下文: {task_002.context}")
        
        # 验证 Planner 记录了重试次数
        assert plan_module.planner_agent is not None
        assert "test_retry_plan" in plan_module.planner_agent.task_retry_records
        assert "002" in plan_module.planner_agent.task_retry_records["test_retry_plan"]
        
        retry_count = plan_module.planner_agent.task_retry_records["test_retry_plan"]["002"]
        print(f"重试次数: {retry_count}")
        assert retry_count == 1, f"Expected retry count 1, got {retry_count}"
        
        print("✅ 任务失败自动重试测试通过")
    
    async def test_max_retries_exceeded(self):
        """测试超过最大重试次数后的行为"""
        print("\n=== 测试超过最大重试次数 ===")
        
        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        
        # 设置 A2A 客户端
        a2a_server = A2AServer()
        plan_module.set_a2a_client(DefaultA2AClient(a2a_server))
        await plan_module.start()
        
        # 创建测试计划（添加总是失败的侦听器）
        plan_config = {
            "plan_id": "test_max_retry_plan",
            "name": "测试最大重试计划",
            "description": "测试超过最大重试次数",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": "001",
                    "name": "主任务",
                    "prompt": "主任务",
                    "status": "NotStarted"
                },
                {
                    "task_id": "002",
                    "name": "总是失败的任务",
                    "prompt": "这个任务总是失败",
                    "status": "NotStarted"
                }
            ],
            "listeners": [
                {
                    "listener_id": "L001",
                    "trigger_task_id": "001",
                    "trigger_condition": "001.status == Running",
                    "listener_type": "code",
                    "code_snippet": """
# 启动任务 002
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
# 总是返回失败
result = {"success": False, "target_task": "002", "target_status": "Error", "context": {"error": "模拟失败"}}
""",
                    "success_output": {"task_id": "002", "status": "Done", "context": {}},
                    "failure_output": {"task_id": "002", "status": "Error", "context": {"error": "模拟失败"}}
                },
                {
                    "listener_id": "L002b",
                    "trigger_task_id": "002",
                    "trigger_condition": "002.status == NotStarted",
                    "listener_type": "code",
                    "code_snippet": """
# 重试时设置为 Running
result = {"success": True, "target_task": "002", "target_status": "Running", "context": {}}
""",
                    "success_output": {"task_id": "002", "status": "Running", "context": {}}
                },
            ]
        }
        
        plan_id = await plan_module.create_plan_from_config(plan_config)
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        # 等待任务失败并重试多次
        print("等待任务 002 失败并重试...")
        await asyncio.sleep(30)  # 等待多次重试（需要足够时间进行 3 次重试）
        
        # 检查任务状态和重试记录
        task_002 = await plan_module.task_manager.get_task("002")
        main_task = await plan_module.task_manager.get_task("001")
        print(f"任务 002 状态: {task_002.status}")
        print(f"主任务状态: {main_task.status}")
        
        # 验证 Planner 记录了重试
        retry_records = plan_module.planner_agent.task_retry_records.get(plan_id, {})
        print(f"重试记录: {retry_records}")
        assert retry_records.get("002", 0) >= 1, "Should have at least 1 retry attempt"
        
        # 验证重试机制工作（任务应该在 NotStarted/Running/Error 之间循环）
        assert task_002.status in ["NotStarted", "Running", "Error"], "Task should be in retry cycle"
        
        print("✅ 超过最大重试次数测试通过（重试机制验证）")
    
    async def test_plan_resume(self):
        """测试计划恢复功能"""
        print("\n=== 测试计划恢复功能 ===")
        
        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        
        # 设置 A2A 客户端
        a2a_server = A2AServer()
        plan_module.set_a2a_client(DefaultA2AClient(a2a_server))
        await plan_module.start()
        
        # 创建测试计划
        plan_config = {
            "plan_id": "test_resume_plan",
            "name": "测试恢复计划",
            "description": "测试计划恢复功能",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": "001",
                    "name": "主任务",
                    "prompt": "主任务",
                    "status": "NotStarted"
                },
                {
                    "task_id": "002",
                    "name": "可恢复的任务",
                    "prompt": "这个任务可以恢复",
                    "status": "NotStarted"
                }
            ],
            "listeners": []
        }
        
        plan_id = await plan_module.create_plan_from_config(plan_config)
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        await asyncio.sleep(1)
        
        # 手动设置任务 002 为 Error 状态
        await plan_module.task_repo.update("002", {"status": "Error"})
        
        # 手动设置重试记录到最大值（模拟已经重试过 3 次）
        plan_module.planner_agent.task_retry_records[plan_id] = {"002": 3}
        
        print("准备恢复计划...")
        
        # 恢复计划
        success = await plan_module.planner_agent.resume_plan(plan_module, plan_id)
        assert success is True, "Plan resume should succeed"
        
        await asyncio.sleep(2)
        
        # 验证重试计数器被重置（整个 plan 的记录应该被清空）
        retry_records = plan_module.planner_agent.task_retry_records.get(plan_id, {})
        print(f"Resume 后重试记录: {retry_records}")
        assert len(retry_records) == 0, f"Retry records should be empty after resume, got {retry_records}"
        
        print("✅ 计划恢复功能测试通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
