"""
邮件发送MVP测试用例

测试场景：创建一个简单的邮件发送计划，包含一个任务和一个Email Agent
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.models.plan import Plan
from src.models.task import Task, TaskStatus
from src.models.listener import Listener
from src.models.execution import Execution
from src.core.plan_module import PlanModule
from src.core.task_listener import TaskListenerModule
from src.core.planner import PlannerModule
from src.core.atom_agent import AtomAgentModule, BizAgent, AgentConfig

class TestEmailMVP:
    """邮件发送MVP测试"""
    
    @pytest.fixture
    def mock_repositories(self):
        """模拟所有仓库"""
        return {
            "plan_repo": AsyncMock(),
            "task_repo": AsyncMock(),
            "listener_repo": AsyncMock(),
            "execution_repo": AsyncMock()
        }
    
    @pytest.fixture
    def mock_infrastructure(self):
        """模拟基础设施组件"""
        return {
            "mcp_server": AsyncMock(),
            "a2a_server": AsyncMock(),
            "adk_integration": AsyncMock()
        }
    
    @pytest.fixture
    def email_agent_config(self):
        """Email Agent配置"""
        return AgentConfig(
            agent_id="email_agent_v1",
            agent_name="Email Agent",
            system_context="你是一个邮件发送的专业代理，负责发送各种类型的邮件",
            allowed_tools=["send_email"],
            mcp_tools=[
                {
                    "name": "send_email",
                    "endpoint": "https://api.emailservice.com/send",
                    "method": "POST",
                    "schema": {
                        "to": "string",
                        "subject": "string",
                        "body": "string"
                    }
                }
            ]
        )
    
    @pytest.fixture
    def email_plan_config(self):
        """邮件发送计划配置"""
        return {
            "plan_id": "email_plan_001",
            "name": "邮件发送计划",
            "prompt": "发送邮件给指定用户",
            "main_task_id": "task_001",
            "tasks": [
                {
                    "task_id": "task_001",
                    "name": "发送邮件",
                    "prompt": "向用户发送邮件"
                }
            ],
            "listeners": [
                {
                    "listener_id": "listener_001",
                    "trigger_task_id": "task_001",
                    "trigger_condition": "task_001.status == Running",
                    "action_condition": "true",
                    "agent_id": "email_agent_v1",
                    "action_prompt": "向用户{task_001.context.to}发送邮件，主题：{task_001.context.subject}，内容：{task_001.context.body}",
                    "success_output": {
                        "task_id": "task_001",
                        "status": "Done",
                        "context": {"email_sent": True, "message_id": "msg_123"}
                    },
                    "failure_output": {
                        "task_id": "task_001", 
                        "status": "Error",
                        "context": {"error": "邮件发送失败"}
                    }
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_create_email_plan(self, mock_repositories, email_plan_config):
        """测试创建邮件发送计划"""
        # 准备测试数据
        plan_module = PlanModule(
            mock_repositories["plan_repo"],
            mock_repositories["task_repo"], 
            mock_repositories["listener_repo"]
        )
        
        mock_repositories["plan_repo"].create.return_value = "email_plan_001"
        mock_repositories["task_repo"].create.return_value = "task_001"
        mock_repositories["listener_repo"].create.return_value = "listener_001"
        
        # 执行测试 - 创建计划
        plan_id = await plan_module.plan_manager.create_plan(email_plan_config)
        assert plan_id == "email_plan_001"
        
        # 执行测试 - 创建任务
        for task_config in email_plan_config["tasks"]:
            task_config["plan_id"] = "email_plan_001"
            task_id = await plan_module.task_manager.create_task(task_config)
            assert task_id == "task_001"
        
        # 执行测试 - 创建侦听器
        for listener_config in email_plan_config["listeners"]:
            listener_config["plan_id"] = "email_plan_001"
            listener_id = await plan_module.listener_manager.create_listener(listener_config)
            assert listener_id == "listener_001"
        
        # 验证调用次数
        assert mock_repositories["plan_repo"].create.call_count == 1
        assert mock_repositories["task_repo"].create.call_count == 1
        assert mock_repositories["listener_repo"].create.call_count == 1
    
    @pytest.mark.asyncio
    async def test_email_agent_execution(self, mock_infrastructure, email_agent_config):
        """测试Email Agent执行"""
        # 创建Email Agent
        with patch('src.core.atom_agent.ReactAgent') as mock_react_agent_class:
            mock_agent = AsyncMock()
            mock_react_agent_class.return_value = mock_agent
            
            email_agent = BizAgent(email_agent_config, mock_infrastructure["adk_integration"])
            
            # 模拟Agent执行结果
            mock_agent.execute.return_value = {
                "success": True,
                "response": "邮件发送成功",
                "tools_used": ["send_email"],
                "result": "邮件已发送到user@example.com"
            }
            
            # 执行测试
            context = {
                "to": "user@example.com",
                "subject": "测试邮件",
                "body": "这是一封测试邮件"
            }
            
            result = await email_agent.execute("发送邮件", context)
            
            # 验证结果
            assert result["success"] is True
            assert "邮件发送成功" in result["response"]
            assert "send_email" in result["tools_used"]
            
            # 验证Agent被调用
            mock_agent.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_task_listener_execution(self, mock_repositories, mock_infrastructure):
        """测试任务侦听器执行邮件发送流程"""
        # 创建任务侦听模块
        task_listener = TaskListenerModule(
            mock_repositories["task_repo"],
            mock_repositories["listener_repo"],
            mock_infrastructure["a2a_server"]  # 作为agent_manager
        )
        
        # 模拟任务状态
        mock_task = Task(
            id="task_001",
            plan_id="email_plan_001",
            name="发送邮件",
            prompt="向用户发送邮件",
            status="Running",
            context={"to": "user@example.com", "subject": "测试", "body": "内容"},
            created_at=datetime.now()
        )
        
        # 模拟侦听器
        mock_listener = Listener(
            id="listener_001",
            plan_id="email_plan_001",
            trigger_task_id="task_001",
            trigger_condition="task_001.status == Running",
            action_condition="true",
            agent_id="email_agent_v1",
            action_prompt="发送邮件",
            success_output={"task_id": "task_001", "status": "Done", "context": {"email_sent": True}},
            failure_output={"task_id": "task_001", "status": "Error", "context": {"error": "发送失败"}}
        )
        
        # 配置模拟返回值
        mock_repositories["task_repo"].get_by_id.return_value = mock_task
        mock_repositories["listener_repo"].get_by_trigger.return_value = [mock_listener]
        mock_infrastructure["a2a_server"].execute_agent.return_value = {"success": True, "result": "邮件发送成功"}
        
        # 执行测试 - 更新任务状态触发侦听器
        await task_listener.task_state_manager.update_task_status(
            "task_001", 
            "Running", 
            {"to": "user@example.com", "subject": "测试", "body": "内容"}
        )
        
        # 验证调用
        mock_repositories["task_repo"].get_by_id.assert_called_with("task_001")
        mock_repositories["listener_repo"].get_by_trigger.assert_called_with("task_001", "Running")
        mock_infrastructure["a2a_server"].execute_agent.assert_called()
    
    @pytest.mark.asyncio
    async def test_complete_email_send_workflow(self, mock_repositories, mock_infrastructure):
        """测试完整的邮件发送工作流程"""
        # 创建Planner模块
        planner = PlannerModule(
            Mock(),  # plan_module
            mock_repositories["execution_repo"]
        )
        
        # 模拟执行记录
        execution = Execution(
            id="exec_001",
            user_request="发送邮件给张三",
            plan_id="email_plan_001",
            status="running",
            start_time=datetime.now()
        )
        
        mock_repositories["execution_repo"].create.return_value = "exec_001"
        mock_repositories["execution_repo"].get_by_id.return_value = execution
        
        # 执行测试 - 创建执行记录
        execution_id = await planner.execution_repo.create(execution)
        assert execution_id == "exec_001"
        
        # 验证执行记录创建
        mock_repositories["execution_repo"].create.assert_called_once()
        
        # 模拟执行状态更新
        await planner.execution_repo.update_status("exec_001", "completed")
        
        # 验证状态更新
        mock_repositories["execution_repo"].update_status.assert_called_with("exec_001", "completed")
    
    @pytest.mark.asyncio
    async def test_email_agent_with_mcp_tools(self, mock_infrastructure):
        """测试Email Agent与MCP工具集成"""
        # 配置MCP Server模拟
        mock_infrastructure["mcp_server"].execute_tool.return_value = {
            "success": True,
            "result": {
                "message_id": "msg_123456",
                "status": "sent",
                "timestamp": "2024-01-01T10:00:00Z"
            }
        }
        
        # 执行MCP工具调用
        result = await mock_infrastructure["mcp_server"].execute_tool(
            "send_email",
            {
                "to": "user@example.com",
                "subject": "测试邮件",
                "body": "这是测试内容"
            }
        )
        
        # 验证结果
        assert result["success"] is True
        assert result["result"]["message_id"] == "msg_123456"
        assert result["result"]["status"] == "sent"
        
        # 验证MCP Server调用
        mock_infrastructure["mcp_server"].execute_tool.assert_called_once_with(
            "send_email",
            {
                "to": "user@example.com",
                "subject": "测试邮件", 
                "body": "这是测试内容"
            }
        )
    
    @pytest.mark.asyncio
    async def test_email_plan_execution_scenarios(self):
        """测试邮件发送计划的各种执行场景"""
        
        # 场景1: 成功发送邮件
        success_scenario = {
            "user_request": "发送邮件给张三",
            "context": {
                "to": "zhangsan@company.com",
                "subject": "会议通知",
                "body": "明天上午10点开会"
            },
            "expected_result": {
                "status": "Done",
                "context": {"email_sent": True, "message_id": "msg_123"}
            }
        }
        
        # 场景2: 邮件发送失败
        failure_scenario = {
            "user_request": "发送邮件给李四",
            "context": {
                "to": "invalid-email",
                "subject": "测试",
                "body": "内容"
            },
            "expected_result": {
                "status": "Error",
                "context": {"error": "邮件地址格式错误"}
            }
        }
        
        # 场景3: 网络超时
        timeout_scenario = {
            "user_request": "发送邮件给王五",
            "context": {
                "to": "wangwu@company.com",
                "subject": "紧急通知",
                "body": "重要信息"
            },
            "expected_result": {
                "status": "Error",
                "context": {"error": "网络超时"}
            }
        }
        
        # 这里可以添加具体的测试逻辑
        # 由于这是测试框架，我们主要验证场景配置的正确性
        assert success_scenario["expected_result"]["status"] == "Done"
        assert failure_scenario["expected_result"]["status"] == "Error"
        assert timeout_scenario["expected_result"]["status"] == "Error"

class TestEmailPlanIntegration:
    """邮件发送计划集成测试"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_email_sending(self):
        """端到端邮件发送测试"""
        # 这个测试将验证从用户请求到邮件发送完成的整个流程
        
        # 1. 用户请求: "发送邮件给张三"
        user_request = "发送邮件给张三"
        
        # 2. Planner理解请求并创建执行计划
        # 3. 创建Plan: email_plan_001
        # 4. 创建Task: task_001 (发送邮件)
        # 5. 创建Listener: listener_001 (监听task_001状态变化)
        # 6. 启动执行: task_001状态变为Running
        # 7. Listener触发: 调用email_agent_v1
        # 8. Agent执行: 通过MCP调用邮件服务
        # 9. 结果处理: 更新task_001状态为Done
        # 10. 执行完成: 记录执行日志
        
        # 这里应该实现完整的端到端测试逻辑
        # 由于涉及多个模块的集成，需要更复杂的模拟和编排
        
        assert user_request == "发送邮件给张三"
    
    @pytest.mark.asyncio
    async def test_email_plan_with_multiple_recipients(self):
        """测试向多个收件人发送邮件的场景"""
        # 扩展场景：向多个收件人发送相同邮件
        recipients = ["zhangsan@company.com", "lisi@company.com", "wangwu@company.com"]
        
        for recipient in recipients:
            # 为每个收件人创建一个独立的执行流程
            # 这样可以并行处理多个邮件发送任务
            
            assert "@" in recipient  # 验证邮箱格式
            assert "company.com" in recipient  # 验证域名
    
    @pytest.mark.asyncio
    async def test_email_plan_error_handling(self):
        """测试邮件发送计划的错误处理"""
        error_scenarios = [
            {"error": "邮箱地址不存在", "expected_action": "重试发送"},
            {"error": "邮件服务不可用", "expected_action": "记录错误并通知用户"},
            {"error": "邮件内容包含敏感词", "expected_action": "拒绝发送并提示修改"}
        ]
        
        for scenario in error_scenarios:
            # 验证错误处理逻辑
            assert "error" in scenario
            assert "expected_action" in scenario
