import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any

"""
BL-004: 查询 Plan

测试用例：
- 按名称查询
- 按标签查询  
- 按状态查询
- 按创建时间范围查询
- 全文搜索
- 分页和排序
- 组合查询条件
"""


@pytest.mark.regression
@pytest.mark.bl004
class TestBL004QueryPlan:
    @pytest.mark.asyncio
    async def test_search_plans_by_name(self, plan_module_factory):
        """测试按名称查询Plan"""
        plan_module = plan_module_factory
        
        # 创建测试数据
        plan_config1 = {
            "plan_id": "test_plan_1",
            "name": "员工入职流程",
            "description": "新员工入职的完整流程",
            "config": {
                "metadata": {
                    "author": "test_user",
                    "tags": ["hr", "onboarding"]
                }
            }
        }
        
        plan_config2 = {
            "plan_id": "test_plan_2", 
            "name": "员工离职流程",
            "description": "员工离职的完整流程",
            "config": {
                "metadata": {
                    "author": "test_user",
                    "tags": ["hr", "offboarding"]
                }
            }
        }
        
        plan_config3 = {
            "plan_id": "test_plan_3",
            "name": "项目启动流程", 
            "description": "新项目启动的流程",
            "config": {
                "metadata": {
                    "author": "test_user",
                    "tags": ["project", "management"]
                }
            }
        }
        
        # 创建plans
        await plan_module.create_plan_from_config(plan_config1)
        await plan_module.create_plan_from_config(plan_config2)
        await plan_module.create_plan_from_config(plan_config3)
        
        # 按名称查询
        results = await plan_module.search_plans(name="员工")
        assert len(results) == 2
        plan_names = [plan.name for plan in results]
        assert "员工入职流程" in plan_names
        assert "员工离职流程" in plan_names
        
        # 精确名称查询
        results = await plan_module.search_plans(name="员工入职流程")
        assert len(results) == 1
        assert results[0].name == "员工入职流程"
        
        # 不存在的名称
        results = await plan_module.search_plans(name="不存在的流程")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_plans_by_tags(self, plan_module_factory):
        """测试按标签查询Plan"""
        plan_module = plan_module_factory
        
        # 创建测试数据
        plans_config = [
            {
                "plan_id": "hr_plan_1",
                "name": "员工入职",
                "config": {"metadata": {"tags": ["hr", "onboarding"]}}
            },
            {
                "plan_id": "hr_plan_2", 
                "name": "员工离职",
                "config": {"metadata": {"tags": ["hr", "offboarding"]}}
            },
            {
                "plan_id": "project_plan_1",
                "name": "项目启动",
                "config": {"metadata": {"tags": ["project", "management"]}}
            },
            {
                "plan_id": "mixed_plan_1",
                "name": "混合流程",
                "config": {"metadata": {"tags": ["hr", "project"]}}
            }
        ]
        
        for config in plans_config:
            await plan_module.create_plan_from_config(config)
        
        # 按单个标签查询
        results = await plan_module.search_plans(tags=["hr"])
        assert len(results) == 3
        plan_names = [plan.name for plan in results]
        assert "员工入职" in plan_names
        assert "员工离职" in plan_names
        assert "混合流程" in plan_names
        
        # 按多个标签查询（AND关系）
        results = await plan_module.search_plans(tags=["hr", "onboarding"])
        assert len(results) == 1
        assert results[0].name == "员工入职"
        
        # 不存在的标签
        results = await plan_module.search_plans(tags=["nonexistent"])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_plans_by_status(self, plan_module_factory):
        """测试按状态查询Plan"""
        plan_module = plan_module_factory
        
        # 创建测试数据
        plan_config = {
            "plan_id": "status_test_plan",
            "name": "状态测试计划",
            "config": {"metadata": {"status": "active"}}
        }
        
        await plan_module.create_plan_from_config(plan_config)
        
        # 按状态查询
        results = await plan_module.search_plans(status="active")
        assert len(results) == 1
        assert results[0].name == "状态测试计划"
        
        # 不存在的状态
        results = await plan_module.search_plans(status="inactive")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_plans_by_time_range(self, plan_module_factory):
        """测试按时间范围查询Plan"""
        plan_module = plan_module_factory
        
        # 创建测试数据
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        last_week = now - timedelta(days=7)
        
        # 模拟不同创建时间的plans
        plan_configs = [
            {
                "plan_id": "recent_plan",
                "name": "最近的计划",
                "created_at": now.isoformat()
            },
            {
                "plan_id": "yesterday_plan", 
                "name": "昨天的计划",
                "created_at": yesterday.isoformat()
            },
            {
                "plan_id": "old_plan",
                "name": "旧计划",
                "created_at": last_week.isoformat()
            }
        ]
        
        for config in plan_configs:
            await plan_module.create_plan_from_config(config)
        
        # 查询最近2天的plans（从昨天开始，包含昨天和今天）
        results = await plan_module.search_plans(
            created_after=yesterday.isoformat()
        )
        assert len(results) == 2
        plan_names = [plan.name for plan in results]
        assert "最近的计划" in plan_names
        assert "昨天的计划" in plan_names
        
        # 查询特定时间范围（从last_week之后到yesterday之前，不包含边界）
        results = await plan_module.search_plans(
            created_after=last_week.isoformat(),
            created_before=yesterday.isoformat()
        )
        # 应该包含old_plan和yesterday_plan，因为边界是包含的
        assert len(results) == 2
        plan_names = [plan.name for plan in results]
        assert "昨天的计划" in plan_names
        assert "旧计划" in plan_names

    @pytest.mark.asyncio
    async def test_search_plans_full_text(self, plan_module_factory):
        """测试全文搜索"""
        plan_module = plan_module_factory
        
        # 创建测试数据
        plan_configs = [
            {
                "plan_id": "email_plan",
                "name": "邮件发送流程",
                "description": "自动发送欢迎邮件给新员工"
            },
            {
                "plan_id": "database_plan",
                "name": "数据库初始化",
                "description": "为新员工创建数据库账户和权限"
            },
            {
                "plan_id": "notification_plan",
                "name": "通知流程",
                "description": "发送邮件通知相关人员"
            }
        ]
        
        for config in plan_configs:
            await plan_module.create_plan_from_config(config)
        
        # 全文搜索
        results = await plan_module.search_plans(query="邮件")
        assert len(results) == 2
        plan_names = [plan.name for plan in results]
        assert "邮件发送流程" in plan_names
        assert "通知流程" in plan_names
        
        # 搜索描述内容
        results = await plan_module.search_plans(query="数据库")
        assert len(results) == 1
        assert results[0].name == "数据库初始化"

    @pytest.mark.asyncio
    async def test_search_plans_pagination(self, plan_module_factory):
        """测试分页查询"""
        plan_module = plan_module_factory
        
        # 创建10个测试plans
        for i in range(10):
            plan_config = {
                "plan_id": f"pagination_plan_{i}",
                "name": f"分页测试计划 {i}",
                "description": f"这是第{i}个分页测试计划"
            }
            await plan_module.create_plan_from_config(plan_config)
        
        # 第一页（按创建时间升序）
        results = await plan_module.search_plans(limit=3, offset=0, sort_by="created_at", sort_order="asc")
        assert len(results) == 3
        assert results[0].name == "分页测试计划 0"
        assert results[1].name == "分页测试计划 1"
        assert results[2].name == "分页测试计划 2"
        
        # 第二页
        results = await plan_module.search_plans(limit=3, offset=3, sort_by="created_at", sort_order="asc")
        assert len(results) == 3
        assert results[0].name == "分页测试计划 3"
        assert results[1].name == "分页测试计划 4"
        assert results[2].name == "分页测试计划 5"
        
        # 最后一页（不足一页）
        results = await plan_module.search_plans(limit=3, offset=9, sort_by="created_at", sort_order="asc")
        assert len(results) == 1
        assert results[0].name == "分页测试计划 9"

    @pytest.mark.asyncio
    async def test_search_plans_sorting(self, plan_module_factory):
        """测试排序查询"""
        plan_module = plan_module_factory
        
        # 创建测试数据
        plan_configs = [
            {
                "plan_id": "plan_c",
                "name": "计划C",
                "created_at": "2024-01-03T00:00:00Z"
            },
            {
                "plan_id": "plan_a",
                "name": "计划A", 
                "created_at": "2024-01-01T00:00:00Z"
            },
            {
                "plan_id": "plan_b",
                "name": "计划B",
                "created_at": "2024-01-02T00:00:00Z"
            }
        ]
        
        for config in plan_configs:
            await plan_module.create_plan_from_config(config)
        
        # 按名称升序排序
        results = await plan_module.search_plans(sort_by="name", sort_order="asc")
        assert len(results) == 3
        assert results[0].name == "计划A"
        assert results[1].name == "计划B"
        assert results[2].name == "计划C"
        
        # 按名称降序排序
        results = await plan_module.search_plans(sort_by="name", sort_order="desc")
        assert len(results) == 3
        assert results[0].name == "计划C"
        assert results[1].name == "计划B"
        assert results[2].name == "计划A"
        
        # 按创建时间升序排序
        results = await plan_module.search_plans(sort_by="created_at", sort_order="asc")
        assert len(results) == 3
        assert results[0].name == "计划A"
        assert results[1].name == "计划B"
        assert results[2].name == "计划C"

    @pytest.mark.asyncio
    async def test_search_plans_combined_filters(self, plan_module_factory):
        """测试组合查询条件"""
        plan_module = plan_module_factory
        
        # 创建测试数据
        plan_configs = [
            {
                "plan_id": "hr_active_plan",
                "name": "HR活跃计划",
                "config": {
                    "metadata": {
                        "tags": ["hr"],
                        "status": "active"
                    }
                }
            },
            {
                "plan_id": "hr_inactive_plan",
                "name": "HR非活跃计划", 
                "config": {
                    "metadata": {
                        "tags": ["hr"],
                        "status": "inactive"
                    }
                }
            },
            {
                "plan_id": "project_active_plan",
                "name": "项目活跃计划",
                "config": {
                    "metadata": {
                        "tags": ["project"],
                        "status": "active"
                    }
                }
            }
        ]
        
        for config in plan_configs:
            await plan_module.create_plan_from_config(config)
        
        # 组合查询：HR标签 + 活跃状态
        results = await plan_module.search_plans(
            tags=["hr"],
            status="active"
        )
        assert len(results) == 1
        assert results[0].name == "HR活跃计划"
        
        # 组合查询：名称包含"计划" + 活跃状态
        results = await plan_module.search_plans(
            name="计划",
            status="active"
        )
        assert len(results) == 2
        plan_names = [plan.name for plan in results]
        assert "HR活跃计划" in plan_names
        assert "项目活跃计划" in plan_names

    @pytest.mark.asyncio
    async def test_search_plans_empty_result(self, plan_module_factory):
        """测试空结果查询"""
        plan_module = plan_module_factory
        
        # 查询不存在的条件
        results = await plan_module.search_plans(name="不存在的计划")
        assert len(results) == 0
        
        results = await plan_module.search_plans(tags=["不存在的标签"])
        assert len(results) == 0
        
        results = await plan_module.search_plans(query="不存在的关键词")
        assert len(results) == 0
