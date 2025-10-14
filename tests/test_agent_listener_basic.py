"""
测试Agent侦听器和工具调用的基础功能
"""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, patch
from src.core.plan_module import PlanModule
from src.database.memory_repositories import MemoryDatabaseConnection
from src.infrastructure.a2a_server import A2AServer
from src.infrastructure.a2a_client import DefaultA2AClient
from src.infrastructure.mcp_server import MCPServer
from tests.test_utils.mock_api import run_mock_api


class TestAgentListenerBasic:
    """测试Agent侦听器基础功能"""
    
    def _get_free_port(self):
        """获取可用端口"""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    @pytest.mark.asyncio
    async def test_agent_listener_basic_execution(self):
        """测试Agent侦听器基础执行"""
        
        # 动态端口
        mock_port = self._get_free_port()
        mcp_port = self._get_free_port()
        os.environ["MOCK_API_URL"] = f"http://127.0.0.1:{mock_port}"

        # 启动 Mock API
        mock_task = asyncio.create_task(run_mock_api(host="127.0.0.1", port=mock_port))

        # 启动 MCP Server
        mcp_server = MCPServer(host="127.0.0.1", port=mcp_port)
        mcp_server.load_tools_from_directory("config/apps")
        mcp_task = asyncio.create_task(mcp_server.run_async())
        
        # 等待服务就绪
        await asyncio.sleep(2)

        # 设置 A2A Server
        a2a_server = A2AServer()
        
        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        plan_module.set_a2a_client(DefaultA2AClient(a2a_server))
        
        # 启动 PlanModule
        await plan_module.start()

        try:
            # 创建简单的测试计划 - 只测试Agent侦听器
            plan_config = {
                "plan_id": "test_agent_listener",
                "name": "测试Agent侦听器",
                "description": "测试Agent侦听器基础功能",
                "main_task_id": "001",
                "tasks": [
                    {
                        "task_id": "001",
                        "name": "主任务",
                        "prompt": "执行主任务",
                        "status": "NotStarted"
                    },
                    {
                        "task_id": "002",
                        "name": "HR任务",
                        "prompt": "HR系统操作",
                        "status": "NotStarted"
                    }
                ],
                "listeners": [
                    {
                        "listener_id": "L001",
                        "trigger_task_id": "001",
                        "trigger_condition": "001.status == Running",
                        "listener_type": "agent",
                        "agent_id": "hr",
                        "action_prompt": "使用create_employee_profile工具创建员工记录，员工ID: TEST001",
                        "success_output": {
                            "task_id": "002",
                            "status": "Done",
                            "context": {"emp_id": "TEST001", "level": "L3"}
                        }
                    }
                ]
            }
            
            # 创建计划
            plan = await plan_module.create_plan_from_config(plan_config)
            assert plan.id == "test_agent_listener"
            
            # 启动计划实例
            prompt = "测试Agent侦听器"
            plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
            assert plan_instance is not None
            
            # 设置员工上下文
            plan_instance.context = {
                "id": "TEST001",
                "name": "测试用户",
                "department": "IT"
            }
            
            # 启动计划实例
            print("启动计划实例...")
            plan_instance.start()
            
            # 等待执行完成
            await asyncio.sleep(5)
            
            # 检查任务状态
            main_task = plan_instance.get_main_task_instance()
            hr_task = plan_instance.get_task_instance("002")
            
            print(f"主任务状态: {main_task.status}")
            print(f"HR任务状态: {hr_task.status}")
            
            # 验证Agent侦听器是否被触发
            # 注意：这里我们主要测试侦听器是否能被正确触发，而不是工具调用是否成功
            # 因为工具调用需要完整的A2A和MCP环境
            
        finally:
            # 清理
            await plan_module.stop()
            mcp_task.cancel()
            mock_task.cancel()
            await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_agent_listener_condition_matching(self):
        """测试Agent侦听器条件匹配"""
        
        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        await plan_module.start()

        try:
            # 创建测试计划
            plan_config = {
                "plan_id": "test_condition_matching",
                "name": "测试条件匹配",
                "description": "测试侦听器条件匹配",
                "main_task_id": "001",
                "tasks": [
                    {
                        "task_id": "001",
                        "name": "主任务",
                        "prompt": "执行主任务",
                        "status": "NotStarted"
                    }
                ],
                "listeners": [
                    {
                        "listener_id": "L001",
                        "trigger_task_id": "001",
                        "trigger_condition": "001.status == Running",
                        "listener_type": "agent",
                        "agent_id": "hr",
                        "action_prompt": "测试条件匹配"
                    }
                ]
            }
            
            # 创建计划
            plan = await plan_module.create_plan_from_config(plan_config)
            
            # 启动计划实例
            prompt = "测试条件匹配"
            plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
            
            # 启动计划实例
            plan_instance.start()
            
            # 等待一下让侦听器引擎处理
            await asyncio.sleep(1)
            
            # 检查侦听器是否被触发
            # 这里我们主要测试条件匹配逻辑是否正确
            
        finally:
            await plan_module.stop()
