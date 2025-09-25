import pytest
import pytest_asyncio
import asyncio
from datetime import datetime
from typing import Dict, Any
from tests.utils.mock_agent import create_mock_agent_runtime

"""
BL-012: 事件驱动系统 - 侦听器管理

测试场景：
1. 任务状态变化 → 侦听器触发 → 驱动其他任务状态变化 → 触发下一个侦听器
2. 两种驱动方式：代码执行 和 BizAgent 返回
3. 侦听器链式触发
"""


@pytest.mark.regression
@pytest.mark.bl012
class TestBL012ListenerEngine:
    @pytest.mark.asyncio
    async def test_listener_chain_execution_code_driven(self, plan_module_factory):
        """测试代码驱动的侦听器链式执行"""
        plan_module = plan_module_factory
        
        # 创建测试计划：任务A -> 侦听器1(代码) -> 任务B -> 侦听器2(代码) -> 任务C
        plan_config = {
            "plan_id": "listener_chain_test",
            "name": "侦听器链式执行测试",
            "description": "测试代码驱动的侦听器链式触发",
            "main_task_id": "task_a",
            "tasks": [
                {
                    "task_id": "task_a",
                    "name": "任务A",
                    "prompt": "启动流程",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_b", 
                    "name": "任务B",
                    "prompt": "中间处理",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_c",
                    "name": "任务C", 
                    "prompt": "最终处理",
                    "status": "NotStarted"
                }
            ],
            "listeners": [
                {
                    "listener_id": "listener_1",
                    "trigger_task_id": "task_a",
                    "trigger_condition": "task_a.status == Running",
                    "action_condition": "true",
                    "listener_type": "code",
                    "code_snippet": """
# 代码驱动的侦听器1：当任务A运行时，启动任务B
result = {
    "success": True,
    "target_task": "task_b",
    "target_status": "Running",
    "context": {"triggered_by": "listener_1", "timestamp": str(datetime.now())}
}
""",
                    "success_output": {
                        "task_id": "task_b",
                        "status": "Running",
                        "context": {"triggered_by": "listener_1"}
                    },
                    "failure_output": {
                        "task_id": "task_b", 
                        "status": "Error",
                        "context": {"error": "listener_1_failed"}
                    }
                },
                {
                    "listener_id": "listener_2",
                    "trigger_task_id": "task_b",
                    "trigger_condition": "task_b.status == Running", 
                    "action_condition": "true",
                    "listener_type": "code",
                    "code_snippet": """
# 代码驱动的侦听器2：当任务B运行时，启动任务C
result = {
    "success": True,
    "target_task": "task_c",
    "target_status": "Running",
    "context": {"triggered_by": "listener_2", "timestamp": str(datetime.now())}
}
""",
                    "success_output": {
                        "task_id": "task_c",
                        "status": "Running", 
                        "context": {"triggered_by": "listener_2"}
                    },
                    "failure_output": {
                        "task_id": "task_c",
                        "status": "Error",
                        "context": {"error": "listener_2_failed"}
                    }
                }
            ]
        }
        
        # 创建计划
        plan_id = await plan_module.create_plan_from_config(plan_config)
        assert plan_id == "listener_chain_test"
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        # 等待侦听器链式执行完成
        await asyncio.sleep(2)  # 给侦听器执行时间
        
        # 检查任务状态变化
        task_a = await plan_module.task_manager.get_task("task_a")
        task_b = await plan_module.task_manager.get_task("task_b") 
        task_c = await plan_module.task_manager.get_task("task_c")
        
        assert task_a.status == "Running"  # 主任务启动
        assert task_b.status == "Running"  # 侦听器1触发
        assert task_c.status == "Running"  # 侦听器2触发
        
        # 检查上下文更新
        assert task_b.context.get("values", {}).get("triggered_by") == "listener_1"
        assert task_c.context.get("values", {}).get("triggered_by") == "listener_2"

    @pytest.mark.asyncio
    async def test_listener_chain_execution_agent_driven(self, plan_module_factory):
        """测试Agent驱动的侦听器链式执行"""
        # 创建Mock Agent Runtime
        mock_agent_runtime = create_mock_agent_runtime()
        
        # 创建PlanModule with Mock Agent
        from src.database.memory_repositories import MemoryDatabaseConnection
        from src.core.plan_module import PlanModule
        
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(
            plan_repo=db.plan_repo,
            task_repo=db.task_repo,
            listener_repo=db.listener_repo,
            adk_integration=mock_agent_runtime
        )
        await plan_module.start()
        
        # 创建测试计划：任务A -> 侦听器1(Agent) -> 任务B -> 侦听器2(Agent) -> 任务C
        plan_config = {
            "plan_id": "agent_chain_test",
            "name": "Agent侦听器链式执行测试",
            "description": "测试Agent驱动的侦听器链式触发",
            "main_task_id": "task_a",
            "tasks": [
                {
                    "task_id": "task_a",
                    "name": "任务A",
                    "prompt": "启动流程",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_b",
                    "name": "任务B", 
                    "prompt": "中间处理",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_c",
                    "name": "任务C",
                    "prompt": "最终处理", 
                    "status": "NotStarted"
                }
            ],
            "listeners": [
                {
                    "listener_id": "agent_listener_1",
                    "trigger_task_id": "task_a",
                    "trigger_condition": "task_a.status == Running",
                    "action_condition": "true",
                    "listener_type": "agent",
                    "agent_id": "TestAgent",
                    "action_prompt": "当任务A运行时，启动任务B。返回JSON格式：{\"success\": true, \"target_task\": \"task_b\", \"target_status\": \"Running\", \"context\": {\"triggered_by\": \"agent_listener_1\"}}",
                    "success_output": {
                        "task_id": "task_b",
                        "status": "Running",
                        "context": {"triggered_by": "agent_listener_1"}
                    },
                    "failure_output": {
                        "task_id": "task_b",
                        "status": "Error", 
                        "context": {"error": "agent_listener_1_failed"}
                    }
                },
                {
                    "listener_id": "agent_listener_2",
                    "trigger_task_id": "task_b",
                    "trigger_condition": "task_b.status == Running",
                    "action_condition": "true", 
                    "listener_type": "agent",
                    "agent_id": "TestAgent",
                    "action_prompt": "当任务B运行时，启动任务C。返回JSON格式：{\"success\": true, \"target_task\": \"task_c\", \"target_status\": \"Running\", \"context\": {\"triggered_by\": \"agent_listener_2\"}}",
                    "success_output": {
                        "task_id": "task_c",
                        "status": "Running",
                        "context": {"triggered_by": "agent_listener_2"}
                    },
                    "failure_output": {
                        "task_id": "task_c",
                        "status": "Error",
                        "context": {"error": "agent_listener_2_failed"}
                    }
                }
            ]
        }
        
        # 创建计划
        plan_id = await plan_module.create_plan_from_config(plan_config)
        assert plan_id == "agent_chain_test"
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        # 等待侦听器链式执行完成
        await asyncio.sleep(2)  # 给侦听器执行时间
        
        # 检查任务状态变化
        task_a = await plan_module.task_manager.get_task("task_a")
        task_b = await plan_module.task_manager.get_task("task_b")
        task_c = await plan_module.task_manager.get_task("task_c")
        
        assert task_a.status == "Running"  # 主任务启动
        assert task_b.status == "Running"  # 侦听器1触发
        assert task_c.status == "Running"  # 侦听器2触发
        
        # 检查上下文更新
        assert task_b.context.get("values", {}).get("triggered_by") == "agent_listener_1"
        assert task_c.context.get("values", {}).get("triggered_by") == "agent_listener_2"
        
        # 清理
        await plan_module.stop()

    @pytest.mark.asyncio
    async def test_mixed_listener_chain_execution(self, plan_module_factory):
        """测试混合驱动的侦听器链式执行（代码+Agent）"""
        # 创建Mock Agent Runtime
        mock_agent_runtime = create_mock_agent_runtime()
        
        # 创建PlanModule with Mock Agent
        from src.database.memory_repositories import MemoryDatabaseConnection
        from src.core.plan_module import PlanModule
        
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(
            plan_repo=db.plan_repo,
            task_repo=db.task_repo,
            listener_repo=db.listener_repo,
            adk_integration=mock_agent_runtime
        )
        await plan_module.start()
        
        # 创建测试计划：任务A -> 侦听器1(代码) -> 任务B -> 侦听器2(Agent) -> 任务C
        plan_config = {
            "plan_id": "mixed_chain_test",
            "name": "混合侦听器链式执行测试",
            "description": "测试代码+Agent混合驱动的侦听器链式触发",
            "main_task_id": "task_a",
            "tasks": [
                {
                    "task_id": "task_a",
                    "name": "任务A",
                    "prompt": "启动流程",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_b",
                    "name": "任务B",
                    "prompt": "中间处理",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_c",
                    "name": "任务C",
                    "prompt": "最终处理",
                    "status": "NotStarted"
                }
            ],
            "listeners": [
                {
                    "listener_id": "code_listener",
                    "trigger_task_id": "task_a",
                    "trigger_condition": "task_a.status == Running",
                    "action_condition": "true",
                    "listener_type": "code",
                    "code_snippet": """
# 代码驱动的侦听器：当任务A运行时，启动任务B
result = {
    "success": True,
    "target_task": "task_b",
    "target_status": "Running",
    "context": {"triggered_by": "code_listener", "method": "code"}
}
""",
                    "success_output": {
                        "task_id": "task_b",
                        "status": "Running",
                        "context": {"triggered_by": "code_listener", "method": "code"}
                    }
                },
                {
                    "listener_id": "agent_listener",
                    "trigger_task_id": "task_b",
                    "trigger_condition": "task_b.status == Running",
                    "action_condition": "true",
                    "listener_type": "agent",
                    "agent_id": "TestAgent",
                    "action_prompt": "当任务B运行时，启动任务C。返回JSON格式：{\"success\": true, \"target_task\": \"task_c\", \"target_status\": \"Running\", \"context\": {\"triggered_by\": \"agent_listener\", \"method\": \"agent\"}}",
                    "success_output": {
                        "task_id": "task_c",
                        "status": "Running",
                        "context": {"triggered_by": "agent_listener", "method": "agent"}
                    }
                }
            ]
        }
        
        # 创建计划
        plan_id = await plan_module.create_plan_from_config(plan_config)
        assert plan_id == "mixed_chain_test"
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        # 等待侦听器链式执行完成
        await asyncio.sleep(2)  # 给侦听器执行时间
        
        # 检查任务状态变化
        task_a = await plan_module.task_manager.get_task("task_a")
        task_b = await plan_module.task_manager.get_task("task_b")
        task_c = await plan_module.task_manager.get_task("task_c")
        
        assert task_a.status == "Running"  # 主任务启动
        assert task_b.status == "Running"  # 代码侦听器触发
        assert task_c.status == "Running"  # Agent侦听器触发
        
        # 检查上下文更新
        assert task_b.context.get("values", {}).get("triggered_by") == "code_listener"
        assert task_b.context.get("values", {}).get("method") == "code"
        assert task_c.context.get("values", {}).get("triggered_by") == "agent_listener"
        assert task_c.context.get("values", {}).get("method") == "agent"
        
        # 清理
        await plan_module.stop()

    @pytest.mark.asyncio
    async def test_listener_condition_evaluation(self, plan_module_factory):
        """测试侦听器条件评估"""
        plan_module = plan_module_factory
        
        # 创建测试计划：测试不同的触发条件和行动条件
        plan_config = {
            "plan_id": "condition_test",
            "name": "侦听器条件测试",
            "description": "测试侦听器的触发条件和行动条件评估",
            "main_task_id": "task_a",
            "tasks": [
                {
                    "task_id": "task_a",
                    "name": "任务A",
                    "prompt": "测试任务",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_b",
                    "name": "任务B",
                    "prompt": "条件任务",
                    "status": "NotStarted"
                }
            ],
            "listeners": [
                {
                    "listener_id": "condition_listener",
                    "trigger_task_id": "task_a",
                    "trigger_condition": "task_a.status == Running",
                    "action_condition": "true",
                    "listener_type": "code",
                    "code_snippet": """
# 条件测试侦听器
result = {
    "success": True,
    "target_task": "task_b",
    "target_status": "Running",
    "context": {"condition_met": True}
}
""",
                    "success_output": {
                        "task_id": "task_b",
                        "status": "Running",
                        "context": {"condition_met": True}
                    }
                }
            ]
        }
        
        # 创建计划
        plan_id = await plan_module.create_plan_from_config(plan_config)
        assert plan_id == "condition_test"
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        # 等待侦听器执行完成
        await asyncio.sleep(1)
        
        # 检查任务状态变化
        task_a = await plan_module.task_manager.get_task("task_a")
        task_b = await plan_module.task_manager.get_task("task_b")
        
        assert task_a.status == "Running"  # 主任务启动
        assert task_b.status == "Running"  # 条件满足，侦听器触发
        
        # 检查上下文更新
        assert task_b.context.get("values", {}).get("condition_met") is True

    @pytest.mark.asyncio
    async def test_listener_priority_execution(self, plan_module_factory):
        """测试侦听器优先级执行"""
        plan_module = plan_module_factory
        
        # 创建测试计划：测试多个侦听器的优先级执行
        plan_config = {
            "plan_id": "priority_test",
            "name": "侦听器优先级测试",
            "description": "测试多个侦听器的优先级执行顺序",
            "main_task_id": "task_a",
            "tasks": [
                {
                    "task_id": "task_a",
                    "name": "任务A",
                    "prompt": "测试任务",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_b",
                    "name": "任务B",
                    "prompt": "高优先级任务",
                    "status": "NotStarted"
                },
                {
                    "task_id": "task_c",
                    "name": "任务C",
                    "prompt": "低优先级任务",
                    "status": "NotStarted"
                }
            ],
            "listeners": [
                {
                    "listener_id": "low_priority_listener",
                    "trigger_task_id": "task_a",
                    "trigger_condition": "task_a.status == Running",
                    "action_condition": "true",
                    "listener_type": "code",
                    "priority": 10,  # 低优先级
                    "code_snippet": """
# 低优先级侦听器
result = {
    "success": True,
    "target_task": "task_c",
    "target_status": "Running",
    "context": {"priority": 10, "executed": True}
}
""",
                    "success_output": {
                        "task_id": "task_c",
                        "status": "Running",
                        "context": {"priority": 10, "executed": True}
                    }
                },
                {
                    "listener_id": "high_priority_listener",
                    "trigger_task_id": "task_a",
                    "trigger_condition": "task_a.status == Running",
                    "action_condition": "true",
                    "listener_type": "code",
                    "priority": 1,  # 高优先级
                    "code_snippet": """
# 高优先级侦听器
result = {
    "success": True,
    "target_task": "task_b",
    "target_status": "Running",
    "context": {"priority": 1, "executed": True}
}
""",
                    "success_output": {
                        "task_id": "task_b",
                        "status": "Running",
                        "context": {"priority": 1, "executed": True}
                    }
                }
            ]
        }
        
        # 创建计划
        plan_id = await plan_module.create_plan_from_config(plan_config)
        assert plan_id == "priority_test"
        
        # 启动计划执行
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        assert success is True
        
        # 等待侦听器执行完成
        await asyncio.sleep(1)
        
        # 检查任务状态变化
        task_a = await plan_module.task_manager.get_task("task_a")
        task_b = await plan_module.task_manager.get_task("task_b")
        task_c = await plan_module.task_manager.get_task("task_c")
        
        assert task_a.status == "Running"  # 主任务启动
        assert task_b.status == "Running"  # 高优先级侦听器触发
        assert task_c.status == "Running"  # 低优先级侦听器也触发
        
        # 检查上下文更新（两个侦听器都应该执行）
        assert task_b.context.get("values", {}).get("priority") == 1
        assert task_b.context.get("values", {}).get("executed") is True
        assert task_c.context.get("values", {}).get("priority") == 10
        assert task_c.context.get("values", {}).get("executed") is True
