import pytest
import pytest_asyncio

"""
BL-005: 执行 Plan（员工入职场景）

说明：
- 该用例基于设计文档中的“员工入职”流程（doc/AIntegration_Design.md），
  作为端到端执行验证的主场景。
- 当前仅占位规划，尚未实现执行引擎与监听驱动的端到端闭环。
"""


@pytest.mark.regression
@pytest.mark.bl005
class TestBL005PlanExecutionOnboarding:
    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="BL-005 Plan 执行端到端（员工入职）尚未实现")
    async def test_execute_plan_onboarding_flow(self, plan_module_factory):
        # 占位：从模板或配置构建“员工入职”Plan，并触发执行
        # 预期：监听链路推进任务状态，主任务完成，输出上下文符合设计文档
        assert False


