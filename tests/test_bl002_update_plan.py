import pytest
import pytest_asyncio
from datetime import datetime

from src.database.memory_repositories import MemoryDatabaseConnection
from src.database.instance_repositories import MemoryPlanInstanceRepository, MemoryTaskInstanceRepository
from src.core.plan_module import PlanModule
from src.models.plan import Plan


@pytest.mark.regression
@pytest.mark.bl002
class TestBL002UpdatePlan:
    @pytest_asyncio.fixture
    async def plan_module(self):
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
    async def test_update_plan_with_versioning(self, plan_module):
        # 创建 v1
        v1 = {
            "plan_id": "bl002_plan",
            "name": "计划V1",
            "description": "desc v1",
            "main_task_id": "001",
            "metadata": {"author": "user", "version": "1.0.0", "updated_at": datetime.now().isoformat()},
            "tasks": [{"task_id": "001", "name": "主任务", "prompt": "do"}],
            "listeners": [],
        }
        plan = await plan_module.create_plan_from_config(v1)
        assert plan.id == "bl002_plan"
        assert plan.metadata["version"] == "1.0.0"

        # 更新为 v2 并期望保存历史
        updates = {"metadata": {"version": "1.1.0", "note": "minor"}, "description": "desc v2"}
        await plan_module.plan_manager.update_plan_with_expected(plan.id, updates, expected_version="1.0.0")

        # 查询版本历史
        history = await plan_module.get_plan_versions(plan.id)
        assert isinstance(history, list) and len(history) >= 2
        # 最新版本（v2）
        latest = history[-1]
        assert latest["metadata"]["version"] == "1.1.0"
        assert latest["metadata"].get("note") == "minor"
        assert latest["description"] == "desc v2"
        # 作者未变化
        assert latest["metadata"]["author"] == "user"
        # 上一个版本（v1）
        prev = history[-2]
        assert prev["metadata"]["version"] == "1.0.0"
        assert prev.get("description") == "desc v1"
        assert "note" not in prev.get("metadata", {})

    @pytest.mark.asyncio
    async def test_rollback_to_previous_version(self, plan_module):
        plan = await plan_module.create_plan_from_config({
            "plan_id": "bl002_plan_rb",
            "name": "计划V1",
            "description": "desc v1",
            "main_task_id": "001",
            "metadata": {"version": "1.0.0", "author": "user"},
            "tasks": [{"task_id": "001", "name": "主任务", "prompt": "do"}],
            "listeners": [],
        })

        await plan_module.plan_manager.update_plan(plan.id, {"metadata": {"version": "1.1.0"}})
        await plan_module.rollback_plan(plan.id, target_version="1.0.0")

        updated_plan = await plan_module.plan_manager.get_plan(plan.id)
        assert updated_plan.metadata["version"] == "1.0.0"
        # 回滚后的内容也应随版本恢复
        assert updated_plan.description == "desc v1"
        assert updated_plan.metadata["author"] == "user"
        # v1 不应包含 v2 扩展的 note 字段
        assert updated_plan.metadata.get("note") is None

    @pytest.mark.asyncio
    async def test_version_conflict_protection(self, plan_module):
        plan = await plan_module.create_plan_from_config({
            "plan_id": "bl002_conflict",
            "name": "计划V1",
            "description": "desc v1",
            "main_task_id": "001",
            "metadata": {"version": "1.0.0"},
            "tasks": [{"task_id": "001", "name": "主任务", "prompt": "do"}],
            "listeners": [],
        })

        # 带 If-Match 或 expected_version 的乐观锁语义
        with pytest.raises(Exception):
            await plan_module.plan_manager.update_plan_with_expected(
                plan.id,
                {"metadata": {"version": "1.1.0"}},
                expected_version="0.9.0",
            )


