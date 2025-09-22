"""
Planner模块测试
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.core.planner import PlannerModule, RequestHandler, PlanGenerator, ExecutionMonitor
from src.models.execution import Execution

class TestRequestHandler:
    """请求处理器测试"""
    
    @pytest.fixture
    def mock_plan_module(self):
        """模拟计划模块"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_execution_repo(self):
        """模拟执行仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def request_handler(self, mock_plan_module, mock_execution_repo):
        """请求处理器实例"""
        return RequestHandler(mock_plan_module, mock_execution_repo)
    
    @pytest.mark.asyncio
    async def test_understand_intent(self, request_handler):
        """测试理解用户意图"""
        # 执行测试
        result = await request_handler.understand_intent("张三入职")
        
        # 验证结果
        assert result["type"] == "employee_onboarding"
        assert result["entities"]["employee_name"] == "张三"
    
    @pytest.mark.asyncio
    async def test_search_matching_plans(self, request_handler, mock_plan_module):
        """测试搜索匹配计划"""
        # 准备测试数据
        intent = {"type": "employee_onboarding", "entities": {"employee_name": "张三"}}
        mock_plan_module.plan_manager.search_plans.return_value = []
        
        # 执行测试
        result = await request_handler.search_matching_plans(intent)
        
        # 验证结果
        assert result == []
        mock_plan_module.plan_manager.search_plans.assert_called_once()

class TestPlanGenerator:
    """计划生成器测试"""
    
    @pytest.fixture
    def mock_plan_module(self):
        """模拟计划模块"""
        return AsyncMock()
    
    @pytest.fixture
    def plan_generator(self, mock_plan_module):
        """计划生成器实例"""
        return PlanGenerator(mock_plan_module)
    
    @pytest.mark.asyncio
    async def test_create_plan_from_intent(self, plan_generator, mock_plan_module):
        """测试根据意图创建计划"""
        # 准备测试数据
        intent = {"type": "employee_onboarding", "entities": {"employee_name": "张三"}}
        
        # 模拟计划管理器方法
        mock_plan_module.plan_manager.get_few_shot_examples.return_value = []
        mock_plan_module.plan_manager.create_plan.return_value = "plan_001"
        mock_plan_module.plan_manager.get_plan.return_value = Mock()
        
        # 模拟任务和侦听器管理器
        mock_plan_module.task_manager.create_task = AsyncMock()
        mock_plan_module.listener_manager.create_listener = AsyncMock()
        
        # 执行测试
        result = await plan_generator.create_plan_from_intent(intent)
        
        # 验证调用
        mock_plan_module.plan_manager.get_few_shot_examples.assert_called_once()
        mock_plan_module.plan_manager.create_plan.assert_called_once()
        mock_plan_module.plan_manager.get_plan.assert_called_once()

class TestExecutionMonitor:
    """执行监控器测试"""
    
    @pytest.fixture
    def mock_execution_repo(self):
        """模拟执行仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_plan_generator(self):
        """模拟计划生成器"""
        return AsyncMock()
    
    @pytest.fixture
    def execution_monitor(self, mock_execution_repo, mock_plan_generator):
        """执行监控器实例"""
        return ExecutionMonitor(mock_execution_repo, mock_plan_generator)
    
    @pytest.mark.asyncio
    async def test_monitor_execution(self, execution_monitor, mock_execution_repo):
        """测试监控执行"""
        # 准备测试数据
        execution = Execution(
            id="exec_001",
            user_request="张三入职",
            plan_id="plan_001",
            status="running",
            start_time=None
        )
        
        mock_execution_repo.get_by_id.return_value = execution
        
        # 执行测试
        await execution_monitor.monitor_execution("exec_001")
        
        # 验证调用
        mock_execution_repo.get_by_id.assert_called_once_with("exec_001")
    
    @pytest.mark.asyncio
    async def test_handle_execution_error(self, execution_monitor, mock_execution_repo):
        """测试处理执行错误"""
        # 准备测试数据
        error = Exception("Test error")
        
        # 执行测试
        await execution_monitor.handle_execution_error("exec_001", error)
        
        # 验证调用（这里应该根据实际实现验证具体的调用）

class TestPlannerModule:
    """Planner模块测试"""
    
    @pytest.fixture
    def mock_plan_module(self):
        """模拟计划模块"""
        return AsyncMock()
    
    @pytest.fixture
    def mock_execution_repo(self):
        """模拟执行仓库"""
        return AsyncMock()
    
    @pytest.fixture
    def planner_module(self, mock_plan_module, mock_execution_repo):
        """Planner模块实例"""
        return PlannerModule(mock_plan_module, mock_execution_repo)
    
    @pytest.mark.asyncio
    async def test_start(self, planner_module):
        """测试启动模块"""
        await planner_module.start()
        # 验证没有异常抛出
    
    @pytest.mark.asyncio
    async def test_stop(self, planner_module):
        """测试停止模块"""
        await planner_module.stop()
        # 验证没有异常抛出
    
    @pytest.mark.asyncio
    async def test_execute_request(self, planner_module, mock_plan_module, mock_execution_repo):
        """测试执行请求"""
        # 准备测试数据
        execution = Execution(
            id="exec_001",
            user_request="张三入职",
            plan_id="plan_001",
            status="running",
            start_time=None
        )
        
        planner_module.request_handler.process_request = AsyncMock(return_value=execution)
        
        # 执行测试
        result = await planner_module.execute_request("张三入职")
        
        # 验证结果
        assert result == execution
        planner_module.request_handler.process_request.assert_called_once_with("张三入职")
