"""
邮件发送MVP集成测试

测试完整的邮件发送流程：从API请求到邮件发送完成
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from main import app
from src.core.email_plan_creator import EmailPlanCreator
from src.core.email_execution_engine import EmailExecutionEngine
from src.agents.email_agent import EmailAgent

class TestEmailMVPIntegration:
    """邮件发送MVP集成测试"""
    
    @pytest.fixture
    def client(self):
        """FastAPI测试客户端"""
        return TestClient(app)
    
    @pytest.fixture
    def email_plan_creator(self):
        """邮件计划创建器"""
        return EmailPlanCreator()
    
    @pytest.fixture
    def email_execution_engine(self):
        """邮件执行引擎"""
        return EmailExecutionEngine()
    
    @pytest.fixture
    def email_agent(self):
        """邮件Agent"""
        return EmailAgent()
    
    def test_create_email_plan(self, email_plan_creator):
        """测试创建邮件发送计划"""
        # 测试数据
        recipient = "test@example.com"
        subject = "测试邮件"
        body = "这是一封测试邮件"
        
        # 创建计划
        plan_config = email_plan_creator.create_send_email_plan(
            recipient=recipient,
            subject=subject,
            body=body
        )
        
        # 验证计划结构
        assert plan_config["plan_id"].startswith("email_plan_")
        assert plan_config["name"] == f"发送邮件给{recipient}"
        assert len(plan_config["tasks"]) == 1
        assert len(plan_config["listeners"]) == 1
        
        # 验证任务配置
        task = plan_config["tasks"][0]
        assert task["task_id"] == plan_config["main_task_id"]
        assert task["name"] == "发送邮件"
        
        # 验证侦听器配置
        listener = plan_config["listeners"][0]
        assert listener["agent_id"] == "email_agent_v1"
        assert listener["trigger_task_id"] == task["task_id"]
        assert recipient in listener["action_prompt"]
        assert subject in listener["action_prompt"]
        assert body in listener["action_prompt"]
    
    def test_validate_email_plan(self, email_plan_creator):
        """测试验证邮件计划"""
        # 创建有效的计划
        plan_config = email_plan_creator.create_send_email_plan(
            recipient="test@example.com",
            subject="测试",
            body="内容"
        )
        
        # 验证计划
        validation_result = email_plan_creator.validate_email_plan(plan_config)
        
        assert validation_result["valid"] is True
        assert len(validation_result["errors"]) == 0
        assert validation_result["task_count"] == 1
        assert validation_result["listener_count"] == 1
    
    @pytest.mark.asyncio
    async def test_email_agent_execution(self, email_agent):
        """测试Email Agent执行"""
        # 测试上下文
        context = {
            "to": "test@example.com",
            "subject": "测试邮件",
            "body": "这是测试内容"
        }
        
        # 执行Agent
        result = await email_agent.execute("发送邮件", context)
        
        # 验证结果
        assert result["success"] is True
        assert "邮件发送成功" in result["result"]
        assert result["context"]["email_sent"] is True
        assert "message_id" in result["context"]
    
    @pytest.mark.asyncio
    async def test_email_execution_engine(self, email_execution_engine):
        """测试邮件执行引擎"""
        # 创建测试计划
        plan_creator = EmailPlanCreator()
        plan_config = plan_creator.create_send_email_plan(
            recipient="test@example.com",
            subject="测试邮件",
            body="测试内容"
        )
        
        # 测试上下文
        context = {
            "user_request": "发送邮件给test@example.com",
            "to": "test@example.com",
            "subject": "测试邮件",
            "body": "测试内容"
        }
        
        # 执行计划
        execution = await email_execution_engine.execute_email_plan(plan_config, context)
        
        # 验证执行结果
        assert execution.status == "completed"
        assert execution.plan_id == plan_config["plan_id"]
        assert execution.user_request == context["user_request"]
        
        # 验证任务状态
        status_info = email_execution_engine.get_execution_status(execution.id)
        assert status_info is not None
        assert status_info["status"] == "completed"
        
        # 验证主任务已完成
        main_task_id = plan_config["main_task_id"]
        task_state = status_info["task_states"].get(main_task_id)
        assert task_state is not None
        assert task_state["status"] == "Done"
    
    def test_email_api_send_single_email(self, client):
        """测试发送单封邮件API"""
        # 测试请求数据
        request_data = {
            "recipient": "test@example.com",
            "subject": "测试邮件",
            "body": "这是测试邮件内容",
            "user_request": "发送邮件给测试用户"
        }
        
        # 发送请求
        response = client.post("/api/v1/email/send", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        
        response_data = response.json()
        assert "execution_id" in response_data
        assert "plan_id" in response_data
        assert response_data["status"] == "completed"
        assert response_data["task_count"] == 1
        assert "邮件发送请求已提交" in response_data["message"]
    
    def test_email_api_send_bulk_email(self, client):
        """测试批量发送邮件API"""
        # 测试请求数据
        request_data = {
            "recipients": ["user1@example.com", "user2@example.com", "user3@example.com"],
            "subject": "批量通知",
            "body": "这是批量通知邮件",
            "user_request": "批量发送通知邮件"
        }
        
        # 发送请求
        response = client.post("/api/v1/email/send/bulk", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        
        response_data = response.json()
        assert "execution_id" in response_data
        assert "plan_id" in response_data
        assert response_data["status"] == "completed"
        assert response_data["task_count"] > 1  # 应该包含主任务和多个子任务
        assert "批量邮件发送请求已提交" in response_data["message"]
    
    def test_email_api_validation(self, client):
        """测试邮件配置验证API"""
        # 测试请求数据
        request_data = {
            "recipient": "test@example.com",
            "subject": "测试邮件",
            "body": "测试内容"
        }
        
        # 发送验证请求
        response = client.post("/api/v1/email/validate", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        
        response_data = response.json()
        assert response_data["valid"] is True
        assert len(response_data["errors"]) == 0
        assert response_data["task_count"] == 1
        assert response_data["listener_count"] == 1
    
    def test_email_api_get_templates(self, client):
        """测试获取邮件模板API"""
        # 发送请求
        response = client.get("/api/v1/email/plans/templates")
        
        # 验证响应
        assert response.status_code == 200
        
        response_data = response.json()
        assert "templates" in response_data
        assert "simple_email" in response_data["templates"]
        assert "bulk_email" in response_data["templates"]
        
        # 验证简单邮件模板
        simple_template = response_data["templates"]["simple_email"]
        assert simple_template["name"] == "简单邮件发送"
        assert "recipient" in simple_template["parameters"]
        assert "subject" in simple_template["parameters"]
        assert "body" in simple_template["parameters"]
    
    def test_email_api_invalid_recipient(self, client):
        """测试无效收件人邮箱"""
        # 测试请求数据（无效邮箱）
        request_data = {
            "recipient": "invalid-email",
            "subject": "测试邮件",
            "body": "测试内容"
        }
        
        # 发送请求
        response = client.post("/api/v1/email/send", json=request_data)
        
        # 验证响应（应该返回400错误）
        assert response.status_code == 422  # FastAPI验证错误
    
    def test_email_api_bulk_email_limit(self, client):
        """测试批量邮件数量限制"""
        # 创建超过限制的收件人列表
        recipients = [f"user{i}@example.com" for i in range(101)]
        
        request_data = {
            "recipients": recipients,
            "subject": "批量邮件",
            "body": "批量内容"
        }
        
        # 发送请求
        response = client.post("/api/v1/email/send/bulk", json=request_data)
        
        # 验证响应（应该返回400错误）
        assert response.status_code == 400
        assert "不能超过100个" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_end_to_end_email_workflow(self, email_plan_creator, email_execution_engine):
        """端到端邮件发送工作流程测试"""
        # 1. 创建邮件发送计划
        plan_config = email_plan_creator.create_send_email_plan(
            recipient="endtoend@example.com",
            subject="端到端测试邮件",
            body="这是端到端测试邮件内容"
        )
        
        # 2. 验证计划配置
        validation_result = email_plan_creator.validate_email_plan(plan_config)
        assert validation_result["valid"] is True
        
        # 3. 准备执行上下文
        context = {
            "user_request": "发送邮件给endtoend@example.com",
            "to": "endtoend@example.com",
            "subject": "端到端测试邮件",
            "body": "这是端到端测试邮件内容"
        }
        
        # 4. 执行邮件发送计划
        execution = await email_execution_engine.execute_email_plan(plan_config, context)
        
        # 5. 验证执行结果
        assert execution.status == "completed"
        assert execution.plan_id == plan_config["plan_id"]
        
        # 6. 获取执行状态
        status_info = email_execution_engine.get_execution_status(execution.id)
        assert status_info["status"] == "completed"
        
        # 7. 验证任务状态
        main_task_id = plan_config["main_task_id"]
        task_state = status_info["task_states"].get(main_task_id)
        assert task_state["status"] == "Done"
        assert task_state["context"]["email_sent"] is True
        
        # 8. 清理执行记录
        email_execution_engine.cleanup_execution(execution.id)
        
        # 9. 验证清理结果
        status_info_after_cleanup = email_execution_engine.get_execution_status(execution.id)
        assert status_info_after_cleanup is None

class TestEmailErrorScenarios:
    """邮件发送错误场景测试"""
    
    @pytest.fixture
    def email_agent(self):
        """邮件Agent"""
        return EmailAgent()
    
    @pytest.mark.asyncio
    async def test_email_agent_invalid_context(self, email_agent):
        """测试Email Agent处理无效上下文"""
        # 无效上下文（缺少必要字段）
        invalid_context = {
            "invalid_field": "value"
        }
        
        # 执行Agent
        result = await email_agent.execute("发送邮件", invalid_context)
        
        # 验证结果
        assert result["success"] is False
        assert "无法从上下文中提取邮件信息" in result["error"]
    
    @pytest.mark.asyncio
    async def test_email_agent_invalid_email(self, email_agent):
        """测试Email Agent处理无效邮箱"""
        # 无效邮箱上下文
        invalid_context = {
            "to": "invalid-email-format",
            "subject": "测试",
            "body": "内容"
        }
        
        # 执行Agent
        result = await email_agent.execute("发送邮件", invalid_context)
        
        # 验证结果
        assert result["success"] is False
        assert "邮箱格式不正确" in result["error"]
    
    @pytest.mark.asyncio
    async def test_email_agent_empty_subject(self, email_agent):
        """测试Email Agent处理空主题"""
        # 空主题上下文
        empty_subject_context = {
            "to": "test@example.com",
            "subject": "",
            "body": "内容"
        }
        
        # 执行Agent
        result = await email_agent.execute("发送邮件", empty_subject_context)
        
        # 验证结果
        assert result["success"] is False
        assert "邮件主题不能为空" in result["error"]
    
    @pytest.mark.asyncio
    async def test_email_agent_empty_body(self, email_agent):
        """测试Email Agent处理空内容"""
        # 空内容上下文
        empty_body_context = {
            "to": "test@example.com",
            "subject": "测试",
            "body": ""
        }
        
        # 执行Agent
        result = await email_agent.execute("发送邮件", empty_body_context)
        
        # 验证结果
        assert result["success"] is False
        assert "邮件内容不能为空" in result["error"]
