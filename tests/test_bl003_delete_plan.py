import pytest
import pytest_asyncio
import asyncio

from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule


@pytest.mark.regression
@pytest.mark.bl003
class TestBL003DeletePlan:
    @pytest.fixture(scope="class")
    def event_loop(self):
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()
    @pytest_asyncio.fixture(scope="class")
    async def plan_module(self, plan_module_class):
        # 直接复用类级PlanModule
        yield plan_module_class

    @pytest.mark.asyncio
    async def test_soft_delete_plan(self, plan_module):
        pid = await plan_module.create_plan_from_config({
            "plan_id": "bl003_soft",
            "name": "删除测试",
            "main_task_id": "001",
            "tasks": [
                {"task_id": "001", "name": "主任务", "prompt": "do"},
                {"task_id": "002", "name": "子任务", "prompt": "do2"},
            ],
            "listeners": [
                {"listener_id": "L001", "trigger_task_id": "001", "trigger_condition": "001.status == Done", "action_condition": "true"}
            ],
        })

        # 软删计划，预期：标记删除，不移除任务与监听；查询默认不返回已软删项
        await plan_module.plan_manager.soft_delete_plan(pid)
        plan = await plan_module.plan_manager.get_plan(pid)
        assert plan is not None and plan.get_config_value("metadata.deleted") is True

        # 默认列表不应包含软删计划
        plans = await plan_module.plan_manager.search_plans({})
        assert all(p.id != pid for p in plans)

    # 系统约定：不提供硬删除接口，全部软删除


