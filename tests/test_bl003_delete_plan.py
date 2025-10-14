import pytest
import pytest_asyncio
import asyncio

from src.database.memory_repositories import MemoryDatabaseConnection
from src.database.instance_repositories import MemoryPlanInstanceRepository, MemoryTaskInstanceRepository
from src.core.plan_module import PlanModule


@pytest.mark.regression
@pytest.mark.bl003
class TestBL003DeletePlan:
    @pytest_asyncio.fixture
    async def plan_module(self):
        """创建计划模块实例"""
        db = MemoryDatabaseConnection()
        plan_instance_repo = MemoryPlanInstanceRepository()
        task_instance_repo = MemoryTaskInstanceRepository()
        mod = PlanModule(
            plan_repo=db.plan_repo,
            task_repo=db.task_repo,
            listener_repo=db.listener_repo,
            plan_instance_repo=plan_instance_repo,
            task_instance_repo=task_instance_repo
        )
        await mod.start()
        yield mod
        await mod.stop()

    @pytest.mark.asyncio
    async def test_soft_delete_plan(self, plan_module):
        plan = await plan_module.create_plan_from_config({
            "plan_id": "bl003_soft",
            "name": "删除测试",
            "main_task_id": "001",
            "metadata": {"author": "test_user", "version": "1.0.0"},
            "tasks": [
                {"task_id": "001", "name": "主任务", "prompt": "do"},
                {"task_id": "002", "name": "子任务", "prompt": "do2"},
            ],
            "listeners": [
                {"listener_id": "L001", "trigger_task_id": "001", "trigger_status": "Done", "action_type": "code", "action_config": {"code": "print('done')"}}
            ],
        })

        # 软删计划，预期：标记删除，不移除任务与监听；查询默认不返回已软删项
        await plan_module.plan_manager.soft_delete_plan(plan.id)
        deleted_plan = await plan_module.plan_manager.get_plan(plan.id)
        assert deleted_plan is not None and deleted_plan.metadata.get("deleted") is True

        # 默认列表不应包含软删计划
        plans = await plan_module.plan_manager.search_plans({})
        assert all(p.id != plan.id for p in plans)

    # 系统约定：不提供硬删除接口，全部软删除


