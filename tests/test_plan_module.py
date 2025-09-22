"""
计划模块测试
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.core.plan_module import PlanModule, PlanManager, TaskManager, ListenerManager
from src.models.plan import Plan
from src.models.task import Task
from src.models.listener import Listener

class TestPlanManager:
    """计划管理器测试"""
    
    @pytest.fixture
    def mock_plan_repo(self):
        """模拟计划仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def plan_manager(self, mock_plan_repo):
        """计划管理器实例"""
        return PlanManager(mock_plan_repo)
    
    @pytest.mark.asyncio
    async def test_create_plan(self, plan_manager, mock_plan_repo):
        """测试创建计划"""
        # 准备测试数据
        plan_config = {
            "plan_id": "plan_001",
            "name": "测试计划",
            "prompt": "测试描述"
        }
        
        mock_plan_repo.create.return_value = "plan_001"
        
        # 执行测试
        result = await plan_manager.create_plan(plan_config)
        
        # 验证结果
        assert result == "plan_001"
        mock_plan_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_plan(self, plan_manager, mock_plan_repo):
        """测试获取计划"""
        # 准备测试数据
        plan = Plan(
            id="plan_001",
            name="测试计划",
            description="测试描述",
            config={},
            created_at=None
        )
        
        mock_plan_repo.get_by_id.return_value = plan
        
        # 执行测试
        result = await plan_manager.get_plan("plan_001")
        
        # 验证结果
        assert result == plan
        mock_plan_repo.get_by_id.assert_called_once_with("plan_001")
    
    @pytest.mark.asyncio
    async def test_search_plans(self, plan_manager, mock_plan_repo):
        """测试搜索计划"""
        # 准备测试数据
        criteria = {"type": "employee_onboarding"}
        mock_plan_repo.search.return_value = []
        
        # 执行测试
        result = await plan_manager.search_plans(criteria)
        
        # 验证结果
        assert result == []
        mock_plan_repo.search.assert_called_once_with(criteria)

class TestTaskManager:
    """任务管理器测试"""
    
    @pytest.fixture
    def mock_task_repo(self):
        """模拟任务仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def task_manager(self, mock_task_repo):
        """任务管理器实例"""
        return TaskManager(mock_task_repo)
    
    @pytest.mark.asyncio
    async def test_create_task(self, task_manager, mock_task_repo):
        """测试创建任务"""
        # 准备测试数据
        task_config = {
            "task_id": "task_001",
            "plan_id": "plan_001",
            "name": "测试任务",
            "prompt": "测试提示"
        }
        
        mock_task_repo.create.return_value = "task_001"
        
        # 执行测试
        result = await task_manager.create_task(task_config)
        
        # 验证结果
        assert result == "task_001"
        mock_task_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_task(self, task_manager, mock_task_repo):
        """测试获取任务"""
        # 准备测试数据
        task = Task(
            id="task_001",
            plan_id="plan_001",
            name="测试任务",
            prompt="测试提示",
            status="NotStarted",
            context={},
            created_at=None
        )
        
        mock_task_repo.get_by_id.return_value = task
        
        # 执行测试
        result = await task_manager.get_task("task_001")
        
        # 验证结果
        assert result == task
        mock_task_repo.get_by_id.assert_called_once_with("task_001")
    
    @pytest.mark.asyncio
    async def test_get_plan_tasks(self, task_manager, mock_task_repo):
        """测试获取计划任务"""
        # 准备测试数据
        tasks = [
            Task(
                id="task_001",
                plan_id="plan_001",
                name="测试任务1",
                prompt="测试提示1",
                status="NotStarted",
                context={},
                created_at=None
            ),
            Task(
                id="task_002",
                plan_id="plan_001",
                name="测试任务2",
                prompt="测试提示2",
                status="Done",
                context={},
                created_at=None
            )
        ]
        
        mock_task_repo.get_by_plan_id.return_value = tasks
        
        # 执行测试
        result = await task_manager.get_plan_tasks("plan_001")
        
        # 验证结果
        assert result == tasks
        mock_task_repo.get_by_plan_id.assert_called_once_with("plan_001")

class TestListenerManager:
    """侦听器管理器测试"""
    
    @pytest.fixture
    def mock_listener_repo(self):
        """模拟侦听器仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def listener_manager(self, mock_listener_repo):
        """侦听器管理器实例"""
        return ListenerManager(mock_listener_repo)
    
    @pytest.mark.asyncio
    async def test_create_listener(self, listener_manager, mock_listener_repo):
        """测试创建侦听器"""
        # 准备测试数据
        listener_config = {
            "listener_id": "listener_001",
            "plan_id": "plan_001",
            "trigger_task_id": "task_001",
            "trigger_condition": "task_001.status == Running",
            "action_condition": "true",
            "agent_id": "HrAgent",
            "action_prompt": "测试提示",
            "success_output": {"task_id": "task_002", "status": "Done", "context": {}},
            "failure_output": {"task_id": "task_002", "status": "Error", "context": {}}
        }
        
        mock_listener_repo.create.return_value = "listener_001"
        
        # 执行测试
        result = await listener_manager.create_listener(listener_config)
        
        # 验证结果
        assert result == "listener_001"
        mock_listener_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_listeners_by_task(self, listener_manager, mock_listener_repo):
        """测试获取任务侦听器"""
        # 准备测试数据
        listeners = [
            Listener(
                id="listener_001",
                plan_id="plan_001",
                trigger_task_id="task_001",
                trigger_condition="task_001.status == Running",
                action_condition="true",
                agent_id="HrAgent",
                action_prompt="测试提示",
                success_output={"task_id": "task_002", "status": "Done", "context": {}},
                failure_output={"task_id": "task_002", "status": "Error", "context": {}}
            )
        ]
        
        mock_listener_repo.get_by_trigger_task.return_value = listeners
        
        # 执行测试
        result = await listener_manager.get_listeners_by_task("task_001")
        
        # 验证结果
        assert result == listeners
        mock_listener_repo.get_by_trigger_task.assert_called_once_with("task_001")

class TestPlanModule:
    """计划模块测试"""
    
    @pytest.fixture
    def mock_repos(self):
        """模拟仓库"""
        return {
            "plan_repo": AsyncMock(),
            "task_repo": AsyncMock(),
            "listener_repo": AsyncMock()
        }
    
    @pytest.fixture
    def plan_module(self, mock_repos):
        """计划模块实例"""
        return PlanModule(
            mock_repos["plan_repo"],
            mock_repos["task_repo"],
            mock_repos["listener_repo"]
        )
    
    @pytest.mark.asyncio
    async def test_start(self, plan_module):
        """测试启动模块"""
        await plan_module.start()
        # 验证没有异常抛出
    
    @pytest.mark.asyncio
    async def test_stop(self, plan_module):
        """测试停止模块"""
        await plan_module.stop()
        # 验证没有异常抛出
