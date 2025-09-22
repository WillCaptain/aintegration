"""
任务侦听模块测试
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from src.core.task_listener import TaskListenerModule, TaskStateManager, ListenerScheduler
from src.models.task import Task, TaskStatus
from src.models.listener import Listener

class TestTaskStateManager:
    """任务状态管理器测试"""
    
    @pytest.fixture
    def mock_task_repo(self):
        """模拟任务仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def task_state_manager(self, mock_task_repo):
        """任务状态管理器实例"""
        return TaskStateManager(mock_task_repo)
    
    @pytest.mark.asyncio
    async def test_update_task_status(self, task_state_manager, mock_task_repo):
        """测试更新任务状态"""
        # 准备测试数据
        mock_task_repo.get_by_id.return_value = Task(
            id="001",
            plan_id="plan_101",
            name="测试任务",
            prompt="测试提示",
            status="NotStarted",
            context={},
            created_at=None
        )
        
        # 执行测试
        await task_state_manager.update_task_status("001", "Running", {"test": "value"})
        
        # 验证调用
        mock_task_repo.get_by_id.assert_called_once_with("001")
        mock_task_repo.update_status.assert_called_once_with("001", "Running", {"test": "value"})
    
    @pytest.mark.asyncio
    async def test_batch_update_tasks(self, task_state_manager, mock_task_repo):
        """测试批量更新任务"""
        from src.core.task_listener import TaskUpdate
        
        # 准备测试数据
        updates = [
            TaskUpdate(task_id="001", status="Running", context={"test1": "value1"}),
            TaskUpdate(task_id="002", status="Done", context={"test2": "value2"})
        ]
        
        mock_task_repo.get_by_id.return_value = Task(
            id="001",
            plan_id="plan_101",
            name="测试任务",
            prompt="测试提示",
            status="NotStarted",
            context={},
            created_at=None
        )
        
        # 执行测试
        await task_state_manager.batch_update_tasks(updates)
        
        # 验证调用次数
        assert mock_task_repo.update_status.call_count == 2

class TestListenerScheduler:
    """侦听器调度器测试"""
    
    @pytest.fixture
    def mock_listener_repo(self):
        """模拟侦听器仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_agent_manager(self):
        """模拟Agent管理器"""
        return AsyncMock()
    
    @pytest.fixture
    def listener_scheduler(self, mock_listener_repo, mock_agent_manager):
        """侦听器调度器实例"""
        return ListenerScheduler(mock_listener_repo, mock_agent_manager)
    
    @pytest.mark.asyncio
    async def test_on_task_status_changed(self, listener_scheduler, mock_listener_repo, mock_agent_manager):
        """测试任务状态变化处理"""
        # 准备测试数据
        listener = Listener(
            id="L001",
            plan_id="plan_101",
            trigger_task_id="001",
            trigger_condition="001.status == Running",
            action_condition="true",
            agent_id="HrAgent",
            action_prompt="测试提示",
            success_output={"task_id": "002", "status": "Done", "context": {}},
            failure_output={"task_id": "002", "status": "Error", "context": {}}
        )
        
        mock_listener_repo.get_by_trigger.return_value = [listener]
        mock_agent_manager.execute_agent.return_value = {"success": True, "result": "success"}
        
        # 执行测试
        await listener_scheduler.on_task_status_changed("001", "NotStarted", "Running", {"test": "value"})
        
        # 验证调用
        mock_listener_repo.get_by_trigger.assert_called_once_with("001", "Running")
        mock_agent_manager.execute_agent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_true(self, listener_scheduler):
        """测试条件评估 - 返回True"""
        listener = Listener(
            id="L001",
            plan_id="plan_101",
            trigger_task_id="001",
            trigger_condition="001.status == Running",
            action_condition="true",
            agent_id="HrAgent",
            action_prompt="测试提示",
            success_output={"task_id": "002", "status": "Done", "context": {}},
            failure_output={"task_id": "002", "status": "Error", "context": {}}
        )
        
        result = await listener_scheduler.evaluate_condition(listener, {"test": "value"})
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_evaluate_condition_false(self, listener_scheduler):
        """测试条件评估 - 返回False"""
        listener = Listener(
            id="L001",
            plan_id="plan_101",
            trigger_task_id="001",
            trigger_condition="001.status == Running",
            action_condition="false",
            agent_id="HrAgent",
            action_prompt="测试提示",
            success_output={"task_id": "002", "status": "Done", "context": {}},
            failure_output={"task_id": "002", "status": "Error", "context": {}}
        )
        
        result = await listener_scheduler.evaluate_condition(listener, {"test": "value"})
        
        assert result is False

class TestTaskListenerModule:
    """任务侦听模块测试"""
    
    @pytest.fixture
    def mock_repos(self):
        """模拟仓库"""
        return {
            "task_repo": AsyncMock(),
            "listener_repo": AsyncMock(),
            "agent_manager": AsyncMock()
        }
    
    @pytest.fixture
    def task_listener_module(self, mock_repos):
        """任务侦听模块实例"""
        return TaskListenerModule(
            mock_repos["task_repo"],
            mock_repos["listener_repo"],
            mock_repos["agent_manager"]
        )
    
    @pytest.mark.asyncio
    async def test_start(self, task_listener_module):
        """测试启动模块"""
        await task_listener_module.start()
        # 验证没有异常抛出
    
    @pytest.mark.asyncio
    async def test_stop(self, task_listener_module):
        """测试停止模块"""
        await task_listener_module.stop()
        # 验证没有异常抛出
