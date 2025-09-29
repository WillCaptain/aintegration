"""
计划模块测试

测试计划模块的核心功能
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime

from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule
from src.models.plan import Plan, PlanStatus
from src.models.task import Task, TaskStatus
from src.models.listener import Listener, ListenerType

@pytest_asyncio.fixture
async def plan_module():
    """创建计划模块实例"""
    db_connection = MemoryDatabaseConnection()
    plan_module = PlanModule(
        plan_repo=db_connection.plan_repo,
        task_repo=db_connection.task_repo,
        listener_repo=db_connection.listener_repo
    )
    await plan_module.start()
    yield plan_module
    await plan_module.stop()

@pytest.fixture
def sample_plan_config():
    """示例计划配置"""
    return {
        "plan_id": "test_plan_001",
        "name": "测试计划",
        "description": "用于测试的计划",
        "main_task_id": "001",
        "tasks": [
            {
                "task_id": "001",
                "name": "主任务",
                "prompt": "执行主任务"
            },
            {
                "task_id": "002",
                "name": "子任务1",
                "prompt": "执行子任务1"
            }
        ],
        "listeners": [
            {
                "listener_id": "L001",
                "trigger_task_id": "001",
                "trigger_condition": "001.status == Running",
                "listener_type": "code",
                "code_snippet": "result = {'success': True, 'data': 'test'}",
                "success_output": {
                    "task_id": "002",
                    "status": "Done",
                    "context": {"result": "{{result.data}}"}
                },
                "failure_output": {
                    "task_id": "002",
                    "status": "Error",
                    "context": {"error": "执行失败"}
                }
            }
        ]
    }

@pytest.mark.asyncio
async def test_create_plan_from_config(plan_module, sample_plan_config):
    """测试从配置创建计划"""
    plan_id = await plan_module.create_plan_from_config(sample_plan_config)
    
    assert plan_id == "test_plan_001"
    
    # 验证计划已创建
    plan = await plan_module.plan_manager.get_plan(plan_id)
    assert plan is not None
    assert plan.name == "测试计划"
    assert plan.main_task_id == "001"
    
    # 验证任务已创建
    tasks = await plan_module.task_manager.get_plan_tasks(plan_id)
    assert len(tasks) == 2
    
    # 验证侦听器已创建
    listeners = await plan_module.listener_manager.get_listeners_by_task("001")
    assert len(listeners) == 1

@pytest.mark.asyncio
async def test_task_status_transitions(plan_module):
    """测试任务状态转换"""
    # 创建测试任务
    task_config = {
        "task_id": "test_task_001",
        "plan_id": "test_plan_001",
        "name": "测试任务",
        "prompt": "测试任务描述"
    }
    
    task_id = await plan_module.task_manager.create_task(task_config)
    task = await plan_module.task_manager.get_task(task_id)
    
    # 测试状态转换 - 现在允许任意状态转换
    assert task.can_transition_to(TaskStatus.RUNNING.value)
    assert task.can_transition_to(TaskStatus.DONE.value)  # 现在允许任意状态转换
    
    # 更新状态
    task.update_status(TaskStatus.RUNNING.value)
    assert task.status == TaskStatus.RUNNING.value
    
    # 测试从Running到Done
    assert task.can_transition_to(TaskStatus.DONE.value)
    task.update_status(TaskStatus.DONE.value)
    assert task.status == TaskStatus.DONE.value
    
    # 测试完成状态也可以转换（现在允许任意状态转换）
    assert task.can_transition_to(TaskStatus.RUNNING.value)

@pytest.mark.asyncio
async def test_listener_trigger_conditions(plan_module):
    """测试侦听器触发条件"""
    # 创建测试侦听器
    listener_config = {
        "listener_id": "test_listener_001",
        "plan_id": "test_plan_001",
        "trigger_task_id": "001",
        "trigger_condition": "001.status == Running",
        "listener_type": "code",
        "code_snippet": "result = {'success': True}",
        "success_output": {"task_id": "002", "status": "Done", "context": {}},
        "failure_output": {"task_id": "002", "status": "Error", "context": {}}
    }
    
    listener_id = await plan_module.listener_manager.create_listener(listener_config)
    listener = await plan_module.listener_manager.get_listener(listener_id)
    
    # 测试触发条件评估
    assert listener.evaluate_trigger_condition("Running")
    assert not listener.evaluate_trigger_condition("Done")
    # action_condition 已移除，不再测试

@pytest.mark.asyncio
async def test_plan_execution(plan_module, sample_plan_config):
    """测试计划执行"""
    # 创建计划
    plan_id = await plan_module.create_plan_from_config(sample_plan_config)
    
    # 执行计划
    result = await plan_module.execute_plan(plan_id)
    assert result["success"] is True
    
    # 等待一段时间让侦听引擎处理
    await asyncio.sleep(1)
    
    # 检查计划状态
    status = await plan_module.get_plan_status(plan_id)
    assert status is not None
    assert status['plan_status'] in ['active', 'completed', 'failed']

@pytest.mark.asyncio
async def test_orphaned_change_handling(plan_module):
    """测试孤立状态变化的处理"""
    # 创建一个没有侦听器的任务状态变化
    # 这应该触发Planner生成新的侦听器
    
    # 创建测试计划
    plan_config = {
        "plan_id": "orphaned_test_plan",
        "name": "孤立变化测试计划",
        "description": "测试孤立状态变化处理",
        "main_task_id": "001",
        "tasks": [
            {
                "task_id": "001",
                "name": "孤立任务",
                "prompt": "没有侦听器的任务"
            }
        ],
        "listeners": []  # 没有侦听器
    }
    
    plan_id = await plan_module.create_plan_from_config(plan_config)
    
    # 手动触发孤立状态变化
    await plan_module.listener_engine.trigger_task_status_change(
        "001", 
        TaskStatus.NOT_STARTED.value, 
        TaskStatus.RUNNING.value, 
        plan_id
    )
    
    # 等待处理
    await asyncio.sleep(1)
    
    # 这里应该看到Planner生成了新的侦听器
    # 实际实现中，这会在listener_engine中处理

@pytest.mark.asyncio
async def test_plan_status_management(plan_module):
    """测试计划状态管理"""
    # 创建测试计划
    plan_config = {
        "plan_id": "status_test_plan",
        "name": "状态测试计划",
        "description": "测试计划状态管理",
        "main_task_id": "001",
        "tasks": [
            {
                "task_id": "001",
                "name": "状态测试任务",
                "prompt": "测试任务"
            }
        ],
        "listeners": []
    }
    
    plan_id = await plan_module.create_plan_from_config(plan_config)
    plan = await plan_module.plan_manager.get_plan(plan_id)
    
    # 测试状态转换
    assert plan.status == PlanStatus.DRAFT.value
    
    # 启动计划
    plan.start()
    assert plan.is_active()
    assert plan.status == PlanStatus.ACTIVE.value
    
    # 完成计划
    plan.complete()
    assert plan.is_completed()
    assert plan.status == PlanStatus.COMPLETED.value

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
