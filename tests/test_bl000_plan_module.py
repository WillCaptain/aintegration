"""
计划模块测试

测试计划模块的核心功能 - 基于新的 PlanInstance 架构
"""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime

from src.database.memory_repositories import MemoryDatabaseConnection
from src.database.instance_repositories import MemoryPlanInstanceRepository, MemoryTaskInstanceRepository
from src.core.plan_module import PlanModule
from src.models.plan import Plan, PlanStatus
from src.models.plan_instance import PlanInstance, PlanInstanceStatus
from src.models.task_instance import TaskInstance, TaskInstanceStatus
from src.models.listener import Listener, ListenerType

@pytest_asyncio.fixture
async def plan_module():
    """创建计划模块实例"""
    db_connection = MemoryDatabaseConnection()
    plan_instance_repo = MemoryPlanInstanceRepository()
    task_instance_repo = MemoryTaskInstanceRepository()
    
    plan_module = PlanModule(
        plan_repo=db_connection.plan_repo,
        task_repo=db_connection.task_repo,
        listener_repo=db_connection.listener_repo,
        plan_instance_repo=plan_instance_repo,
        task_instance_repo=task_instance_repo
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
                "trigger_status": "Done",
                "action_type": "code",
                "action_config": {
                    "code": '''
# 主任务完成后，启动子任务
print("主任务完成，启动子任务")
task_updates = [{"task_id": "002", "status": "Done", "reason": "main_task_completed"}]
'''
                }
            }
        ]
    }

@pytest.mark.asyncio
async def test_create_plan_from_config(plan_module, sample_plan_config):
    """测试从配置创建计划"""
    plan = await plan_module.create_plan_from_config(sample_plan_config)
    
    assert plan.id == "test_plan_001"
    assert plan.name == "测试计划"
    assert plan.main_task_id == "001"
    
    # 验证计划元数据中的任务
    assert len(plan.tasks) == 2
    assert plan.tasks[0]["task_id"] == "001"
    assert plan.tasks[1]["task_id"] == "002"
    
    # 验证计划元数据中的侦听器
    assert len(plan.listeners) == 1
    assert plan.listeners[0]["listener_id"] == "L001"

@pytest.mark.asyncio
async def test_plan_instance_creation_and_task_management(plan_module, sample_plan_config):
    """测试计划实例创建和任务管理"""
    # 创建计划
    plan = await plan_module.create_plan_from_config(sample_plan_config)
    
    # 创建计划实例
    prompt = "请帮我完成测试流程"
    plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
    
    assert plan_instance.id is not None
    assert plan_instance.plan_id == plan.id
    assert plan_instance.status == PlanInstanceStatus.NOT_STARTED.value
    
    # 验证任务实例已创建
    task_instances = plan_instance.get_all_task_instances()
    assert len(task_instances) == 2
    
    # 验证主任务
    main_task = plan_instance.get_main_task_instance()
    assert main_task is not None
    assert main_task.task_id == "001"
    assert main_task.status == TaskInstanceStatus.NOT_STARTED.value
    assert main_task.is_main_task() == True
    
    # 验证子任务
    sub_task = plan_instance.get_task_instance("002")
    assert sub_task is not None
    assert sub_task.task_id == "002"
    assert sub_task.status == TaskInstanceStatus.NOT_STARTED.value
    assert sub_task.is_main_task() == False

@pytest.mark.asyncio
async def test_plan_instance_self_driven_execution(plan_module, sample_plan_config):
    """测试计划实例自我驱动执行"""
    # 创建计划
    plan = await plan_module.create_plan_from_config(sample_plan_config)
    
    # 创建计划实例
    prompt = "请帮我完成测试流程"
    plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
    
    # 启动计划实例（开始自我驱动）
    plan_instance.start()
    
    # 等待主任务自动启动（异步执行）
    await asyncio.sleep(0.1)
    
    # 验证主任务自动启动
    main_task = plan_instance.get_main_task_instance()
    assert main_task.status == TaskInstanceStatus.RUNNING.value
    
    # 手动完成主任务，触发侦听器
    plan_instance.update_task_status("001", TaskInstanceStatus.DONE.value, "manual_completion")
    
    # 等待自我驱动执行
    await asyncio.sleep(1)
    
    # 验证子任务被触发
    sub_task = plan_instance.get_task_instance("002")
    assert sub_task.status == TaskInstanceStatus.DONE.value
    
    # 验证计划实例完成
    assert plan_instance.status == PlanInstanceStatus.DONE.value

@pytest.mark.asyncio
async def test_task_instance_status_trace(plan_module, sample_plan_config):
    """测试任务实例状态轨迹"""
    # 创建计划
    plan = await plan_module.create_plan_from_config(sample_plan_config)
    
    # 创建计划实例
    prompt = "请帮我完成测试流程"
    plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
    
    # 启动计划实例
    plan_instance.start()
    
    # 等待主任务自动启动（异步执行）
    await asyncio.sleep(0.1)
    
    # 验证状态轨迹
    main_task = plan_instance.get_main_task_instance()
    status_trace = main_task.get_status_history()
    
    # 应该有初始化和启动两个状态
    assert len(status_trace) >= 2
    assert status_trace[0]["status"] == TaskInstanceStatus.NOT_STARTED.value
    assert status_trace[0]["reason"] == "initialized"
    assert status_trace[1]["status"] == TaskInstanceStatus.RUNNING.value
    assert status_trace[1]["reason"] == "plan_instance_started"
    
    # 手动更新状态
    plan_instance.update_task_status("001", TaskInstanceStatus.DONE.value, "test_completion")
    
    # 验证新状态被记录
    status_trace = main_task.get_status_history()
    assert len(status_trace) == 3
    assert status_trace[2]["status"] == TaskInstanceStatus.DONE.value
    assert status_trace[2]["reason"] == "test_completion"

@pytest.mark.asyncio
async def test_plan_instance_without_listeners(plan_module):
    """测试没有侦听器的计划实例"""
    # 创建没有侦听器的计划
    plan_config = {
        "plan_id": "simple_test_plan",
        "name": "简单测试计划",
        "description": "测试没有侦听器的计划",
        "main_task_id": "001",
        "tasks": [
            {
                "task_id": "001",
                "name": "简单任务",
                "prompt": "没有侦听器的任务",
                "is_main_task": True
            }
        ],
        "listeners": []  # 没有侦听器
    }
    
    plan = await plan_module.create_plan_from_config(plan_config)
    
    # 创建计划实例
    prompt = "请帮我完成简单任务"
    plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
    
    # 启动计划实例
    plan_instance.start()
    
    # 等待主任务自动启动（异步执行）
    await asyncio.sleep(0.1)
    
    # 验证主任务启动
    main_task = plan_instance.get_main_task_instance()
    assert main_task.status == TaskInstanceStatus.RUNNING.value
    
    # 手动完成主任务
    plan_instance.update_task_status("001", TaskInstanceStatus.DONE.value, "manual_completion")
    
    # 等待自我驱动执行
    await asyncio.sleep(0.5)
    
    # 验证计划实例完成（因为没有侦听器，主任务完成就直接完成）
    assert plan_instance.status == PlanInstanceStatus.DONE.value

@pytest.mark.asyncio
async def test_plan_lifecycle_management(plan_module):
    """测试计划生命周期管理"""
    # 创建测试计划
    plan_config = {
        "plan_id": "lifecycle_test_plan",
        "name": "生命周期测试计划",
        "description": "测试计划生命周期管理",
        "main_task_id": "001",
        "tasks": [
            {
                "task_id": "001",
                "name": "生命周期测试任务",
                "prompt": "测试任务",
                "is_main_task": True
            }
        ],
        "listeners": []
    }
    
    plan = await plan_module.create_plan_from_config(plan_config)
    
    # 测试计划状态
    assert plan.status == PlanStatus.DRAFT.value
    
    # 测试计划实例状态管理
    prompt = "请帮我完成生命周期测试"
    plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
    
    # 初始状态
    assert plan_instance.status == PlanInstanceStatus.NOT_STARTED.value
    
    # 启动计划实例
    plan_instance.start()
    assert plan_instance.status == PlanInstanceStatus.RUNNING.value
    
    # 完成计划实例
    plan_instance.update_task_status("001", TaskInstanceStatus.DONE.value, "completion")
    await asyncio.sleep(0.1)  # 等待自我驱动处理
    
    # 验证计划实例完成
    assert plan_instance.status == PlanInstanceStatus.DONE.value

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
