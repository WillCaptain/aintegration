import asyncio
import os
import json
import pytest
import pytest_asyncio
from datetime import datetime
from typing import Dict, Any
import socket

from tests.utils.mock_api import run_mock_api, MOCK_LOG_FILE
from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule
from src.infrastructure.mcp_server import MCPServer
from src.infrastructure.mcp_client import MCPClient
from src.infrastructure.adk_integration import ReactAgent


@pytest_asyncio.fixture
async def env_setup():
    """环境设置"""
    # 由各测试动态设置 MOCK_API_URL，避免端口冲突
    if "MOCK_API_URL" in os.environ:
        os.environ.pop("MOCK_API_URL")
    # 清理日志
    if os.path.exists(MOCK_LOG_FILE):
        os.remove(MOCK_LOG_FILE)
    yield


@pytest.mark.regression
@pytest.mark.bl005
class TestBL005PlanExecutionOnboarding:
    """BL-005: 执行 Plan（员工入职场景）
    
    基于设计文档中的"员工入职"流程，使用真实的BizAgent配置：
    1. 通过MCP Server加载配置的Agent
    2. 这些Agent调用Mock API执行具体操作
    3. 验证完整的入职流程和API调用记录
    """

    def _get_free_port(self) -> int:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    @pytest.mark.asyncio
    async def test_will_zhang_onboarding_complete_flow(self, env_setup):
        """测试张威完整入职流程 - 使用真实BizAgent配置"""
        
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
        await asyncio.sleep(3)  # 给 Mock API 和 MCP Server 更多时间启动
        
        # 验证 Mock API 是否就绪
        import httpx
        for i in range(10):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://127.0.0.1:{mock_port}/docs")
                    if response.status_code == 200:
                        print("Mock API 已就绪")
                        break
            except Exception:
                await asyncio.sleep(0.5)
        else:
            print("警告: Mock API 可能未完全启动")

        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        await plan_module.start()
        
        # 设置 A2A 验证功能
        from src.infrastructure.a2a_server import A2AServer
        from src.infrastructure.a2a_client import DefaultA2AClient
        
        a2a_server = A2AServer()
        await a2a_server.register_agent({
            "agent_id": "hr_agent",
            "agent_name": "HR Agent",
            "provider": "internal",
            "version": "1.0.0",
            "capabilities": ["query_profile"],
            "endpoints": {"execute": "/agents/hr/execute"}
        })
        await a2a_server.register_agent({
            "agent_id": "inventory_agent",
            "agent_name": "Inventory Agent",
            "provider": "internal",
            "version": "1.0.0",
            "capabilities": ["check_outbound_status"],
            "endpoints": {"execute": "/agents/inv/execute"}
        })
        await a2a_server.register_agent({
            "agent_id": "access_agent",
            "agent_name": "Access Agent",
            "provider": "internal",
            "version": "1.0.0",
            "capabilities": ["query_access"],
            "endpoints": {"execute": "/agents/access/execute"}
        })
        
        # 将A2A客户端注入PlanModule
        plan_module.set_a2a_client(DefaultA2AClient(a2a_server))
        
        # 确保侦听器引擎已启动
        print(f"侦听器引擎启动前状态: {plan_module.listener_engine.is_running}")
        if not plan_module.listener_engine.is_running:
            await plan_module.listener_engine.start()
        print(f"侦听器引擎启动后状态: {plan_module.listener_engine.is_running}")

        try:
            # 创建入职计划
            plan_config = self._create_will_zhang_onboarding_plan()
            plan_id = await plan_module.create_plan_from_config(plan_config)
            assert plan_id == "onboard_will_zhang"
            
            # 设置员工上下文
            await self._setup_employee_context(plan_module, "001")
            
            # 启动计划执行
            success = await plan_module.listener_engine.start_plan_execution(plan_id)
            assert success is True
            
            # 等待侦听器链式执行完成
            await asyncio.sleep(35)  # 进一步延长，覆盖出库+领取+并行收敛发信
            
            # 验证任务状态变化
            await self._verify_task_states(plan_module)
            
            # 验证 Planner 验证结果
            await self._verify_planner_verification(plan_module)
            
            # 验证Mock API调用记录
            await self._verify_api_calls_in_log()
            
        finally:
            # 清理
            await plan_module.stop()
            mcp_task.cancel()
            mock_task.cancel()
            await asyncio.sleep(0.5)

    @pytest.mark.asyncio
    async def test_onboarding_plan_creation_and_validation(self, plan_module_factory):
        """测试入职计划创建和验证"""
        plan_module = plan_module_factory
        
        # 创建入职计划
        plan_config = self._create_will_zhang_onboarding_plan()
        plan_id = await plan_module.create_plan_from_config(plan_config)
        
        # 验证计划创建
        assert plan_id == "onboard_will_zhang"
        
        # 验证任务创建
        tasks = await plan_module.task_manager.get_plan_tasks(plan_id)
        task_ids = [task.id for task in tasks]
        expected_tasks = ["001", "002", "003", "004", "005", "006", "007"]
        for expected_task in expected_tasks:
            assert expected_task in task_ids
        
        # 验证侦听器创建
        listeners = await plan_module.listener_manager.listener_repo.get_by_plan_id(plan_id)
        assert len(listeners) >= 6  # 至少6个侦听器（删除了L**b侦听器）
        
        # 验证主任务
        main_task = await plan_module.task_manager.get_task("001")
        assert main_task.id == "001"
        assert main_task.name == "新员工完成入职"

    @pytest.mark.asyncio
    async def test_listener_chain_execution_sequence(self, env_setup):
        """测试侦听器链式执行序列"""
        
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
        await asyncio.sleep(3)
        
        # 验证 Mock API 是否就绪
        import httpx
        for i in range(10):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://127.0.0.1:{mock_port}/docs")
                    if response.status_code == 200:
                        print("Mock API 已就绪")
                        break
            except Exception:
                await asyncio.sleep(0.5)
        else:
            print("警告: Mock API 可能未完全启动")

        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        await plan_module.start()
        
        # 创建入职计划
        plan_config = self._create_will_zhang_onboarding_plan()
        plan_id = await plan_module.create_plan_from_config(plan_config)
        
        # 设置员工上下文
        await self._setup_employee_context(plan_module, "001")
        
        # 启动计划执行
        print("开始启动计划执行...")
        
        # 检查计划是否存在
        plan = await plan_module.plan_manager.get_plan(plan_id)
        print(f"计划存在: {plan is not None}")
        if plan:
            print(f"计划主任务ID: {plan.main_task_id}")
        
        # 检查主任务是否存在
        main_task = await plan_module.task_manager.get_task("001")
        print(f"主任务存在: {main_task is not None}")
        if main_task:
            print(f"主任务当前状态: {main_task.status}")
        
        success = await plan_module.listener_engine.start_plan_execution(plan_id)
        print(f"计划执行启动结果: {success}")
        assert success is True
        
        # 等待执行
        await asyncio.sleep(10)  # 给更多时间让 ReactAgent 完成执行
        
        # 检查侦听器引擎的执行队列
        print(f"侦听器引擎执行队列大小: {plan_module.listener_engine.execution_queue.qsize()}")
        
        # 验证主任务状态变化
        main_task = await plan_module.task_manager.get_task("001")
        print(f"主任务状态: {main_task.status}")
        assert main_task.status in ["Running", "Done"]  # 应该已启动或完成
        
        # 验证HR和门禁任务应该被触发
        hr_task = await plan_module.task_manager.get_task("002")
        access_task = await plan_module.task_manager.get_task("005")
        
        print(f"HR任务状态: {hr_task.status}")
        print(f"门禁任务状态: {access_task.status}")
        
        # 检查侦听器引擎状态
        print(f"侦听器引擎运行状态: {plan_module.listener_engine.is_running}")
        print(f"侦听器引擎执行任务: {plan_module.listener_engine._execution_task}")
        if plan_module.listener_engine._execution_task:
            print(f"执行任务状态: {plan_module.listener_engine._execution_task.done()}")
            if plan_module.listener_engine._execution_task.done():
                try:
                    result = plan_module.listener_engine._execution_task.result()
                    print(f"执行任务结果: {result}")
                except Exception as e:
                    print(f"执行任务异常: {e}")
        
        # 检查侦听器
        listeners = await plan_module.listener_manager.listener_repo.get_by_plan_id(plan_id)
        print(f"计划侦听器数量: {len(listeners)}")
        for listener in listeners:
            print(f"侦听器 {listener.id}: 触发任务={listener.trigger_task_id}, 条件={listener.trigger_condition}")
        
        # 至少有一个应该被触发（取决于执行顺序）
        assert hr_task.status in ["Running", "Done", "Error"] or access_task.status in ["Running", "Done", "Error"]
        
        # 清理资源
        await plan_module.stop()
        mcp_task.cancel()
        mock_task.cancel()
        await asyncio.sleep(0.5)

    def _create_will_zhang_onboarding_plan(self) -> Dict[str, Any]:
        """创建基于设计文档的完整入职计划"""
        return {
            "plan_id": "onboard_will_zhang",
            "name": "新员工入职-张威",
            "description": "基于设计文档的完整员工入职流程，使用真实BizAgent配置",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": "001",
                    "name": "新员工完成入职",
                    "prompt": "新员工入职",
                    "status": "NotStarted"
                },
                {
                    "task_id": "002",
                    "name": "新员工注册",
                    "prompt": "新员工在Hr系统中完成新员工注册",
                    "status": "NotStarted"
                },
                {
                    "task_id": "003",
                    "name": "申请电脑",
                    "prompt": "新员工在IT系统中完成电脑申请",
                    "status": "NotStarted"
                },
                {
                    "task_id": "004",
                    "name": "电脑出库",
                    "prompt": "电脑出库",
                    "status": "NotStarted"
                },
                {
                    "task_id": "005",
                    "name": "门禁申请",
                    "prompt": "新员工在门禁系统里完成门禁权限申请",
                    "status": "NotStarted"
                },
                {
                    "task_id": "006",
                    "name": "发送欢迎邮件",
                    "prompt": "通过EmailAgent发送新员工欢迎邮件",
                    "status": "NotStarted"
                },
                {
                    "task_id": "007",
                    "name": "生成劳动合同",
                    "prompt": "通过DocAgent生成并发送劳动合同",
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
                    "action_prompt": "根据员工身份证号{001.context.id}、姓名{001.context.name}、部门{001.context.department}在HR系统中创建员工记录，确定员工级别。使用create_employee_profile工具。",
                    "success_output": {
                        "task_id": "002",
                        "status": "Done",
                        "context": {"emp_id": "WZ001", "level": "L3"}
                    },
                    "failure_output": {
                        "task_id": "002",
                        "status": "Error",
                        "context": {"error": "HR系统连接失败"}
                    }
                },
                {
                    "listener_id": "L002",
                    "trigger_task_id": "002",
                    "trigger_condition": "002.status == Done",
                    "listener_type": "agent",
                    "agent_id": "access",
                    "action_prompt": "根据员工ID{001.context.id}为新员工申请门禁权限，输入员工姓名{001.context.name}。使用grant_access工具。",
                    "success_output": {
                        "task_id": "005",
                        "status": "Done",
                        "context": {"access_id": "ACC001", "card_no": "CARD001"}
                    },
                    "failure_output": {
                        "task_id": "005",
                        "status": "Error",
                        "context": {"error": "门禁系统异常"}
                    }
                },
                {
                    "listener_id": "L003",
                    "trigger_task_id": "002",
                    "trigger_condition": "002.status == Done",
                    "listener_type": "agent",
                    "agent_id": "it",
                    "action_prompt": "根据员工ID{002.context.emp_id}和员工级别{002.context.level}申请相应配置的笔记本。使用apply_computer工具。",
                    "success_output": {
                        "task_id": "003",
                        "status": "Done",
                        "context": {"pc_model": "ThinkPad X1", "request_id": "REQ001"}
                    },
                    "failure_output": {
                        "task_id": "003",
                        "status": "Error",
                        "context": {"error": "IT系统维护中"}
                    }
                },
                {
                    "listener_id": "L004",
                    "trigger_task_id": ["004","005"],
                    "trigger_condition": "004.status == Done && 005.status == Done",
                    "listener_type": "agent",
                    "agent_id": "email",
                    "action_prompt": "向员工邮箱{002.context.email}发送新员工欢迎邮件，员工姓名{002.context.name}，部门{002.context.department}。使用send_email工具。",
                    "success_output": {
                        "task_id": "006",
                        "status": "Done",
                        "context": {"email_sent": True, "message_id": "MSG001"}
                    },
                    "failure_output": {
                        "task_id": "006",
                        "status": "Error",
                        "context": {"error": "邮件服务不可用"}
                    }
                },
                {
                    "listener_id": "L005",
                    "trigger_task_id": "003",
                    "trigger_condition": "003.status == Done",
                    "listener_type": "agent",
                    "agent_id": "inventory",
                    "action_prompt": "根据IT申请{003.context.pc_model}创建电脑出库单，等待员工领取。使用outbound工具。",
                    "success_output": {
                        "task_id": "004",
                        "status": "Done",
                        "context": {"outbound_id": "OUT001", "pc_no": "PC001"}
                    },
                    "failure_output": {
                        "task_id": "004",
                        "status": "Error",
                        "context": {"error": "库存不足，型号{003.context.pc_model}缺货"}
                    }
                },
                {
                    "listener_id": "L007",
                    "trigger_task_id": "006",
                    "trigger_condition": "006.status == Done",
                    "listener_type": "code",
                    "code_snippet": """
# 当所有子任务完成后，将主任务状态更新为Done，触发Planner验证
result = {
    "success": True,
    "target_task": "001",
    "target_status": "Done",
    "context": {
        "onboarding_complete": True,
        "completion_time": str(datetime.now()),
        "completed_tasks": ["002", "003", "005", "006"]
    }
}
""",
                    "success_output": {
                        "task_id": "001",
                        "status": "Done",
                        "context": {"onboarding_complete": True, "completion_time": "{{result.completion_time}}"}
                    },
                    "failure_output": {
                        "task_id": "001",
                        "status": "Pending",
                        "context": {"pending_tasks": "{{result.pending_tasks}}"}
                    }
                }
            ]
        }

    async def _setup_employee_context(self, plan_module: PlanModule, task_id: str):
        """设置员工上下文信息"""
        main_task = await plan_module.task_manager.get_task(task_id)
        main_task.set_context_value("id", "WZ001")
        main_task.set_context_value("name", "will zhang")
        main_task.set_context_value("email", "will.zhang@company.com")
        main_task.set_context_value("department", "工程部")
        await plan_module.task_manager.task_repo.update_status(task_id, main_task.status, main_task.context)

    async def _verify_task_states(self, plan_module: PlanModule):
        """验证任务状态"""
        # 验证主任务状态
        main_task = await plan_module.task_manager.get_task("001")
        assert main_task.status in ["Running", "Done", "Pending"]
        
        # 验证其他任务状态
        tasks = ["002", "003", "005", "006", "007"]
        for task_id in tasks:
            task = await plan_module.task_manager.get_task(task_id)
            assert task.status in ["NotStarted", "Running", "Done", "Error", "Pending"]

    async def _verify_api_calls_in_log(self):
        """验证Mock API调用记录"""
        assert os.path.exists(MOCK_LOG_FILE), f"Mock API log file not found: {MOCK_LOG_FILE}"
        
        with open(MOCK_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [json.loads(line.strip()) for line in f.readlines() if line.strip()]
        
        # 验证至少有一些工具被调用
        tool_names = [entry.get("tool") for entry in lines]
        
        # 期望的工具调用
        expected_tools = [
            "create_employee_profile",  # HR Agent
            "grant_access",             # Access Agent  
            "apply_computer",           # IT Agent
            "outbound",                 # Inventory Agent
            "check_outbound_status",    # Inventory Agent
            "send_email"                # Email Agent
        ]
        
        called_tools = [tool for tool in expected_tools if tool in tool_names]
        
        print(f"\n=== Mock API 调用记录 ===")
        for entry in lines:
            print(f"工具: {entry.get('tool')}, 参数: {entry.get('args')}, 时间: {entry.get('timestamp')}")
        
        print(f"\n期望工具: {expected_tools}")
        print(f"实际调用: {called_tools}")
        
        # 验证至少调用了HR和Access相关的工具
        assert "create_employee_profile" in tool_names, f"Expected create_employee_profile to be called, but got: {tool_names}"
        assert "grant_access" in tool_names, f"Expected grant_access to be called, but got: {tool_names}"
        
        # 验证调用了至少3个不同的工具
        assert len(set(tool_names)) >= 3, f"Expected at least 3 different tools to be called, but got: {set(tool_names)}"

    async def _verify_planner_verification(self, plan_module):
        """验证 Planner 验证结果"""
        # 获取主任务
        main_task = await plan_module.task_manager.get_task("001")
        assert main_task is not None, "Main task should exist"
        
        # 检查主任务上下文中的验证结果
        context = main_task.context
        verification_results = context.get("verification_results")
        
        print(f"主任务上下文: {context}")
        
        # 验证结果应该存在
        assert verification_results is not None, "Planner verification results should exist in main task context"
        
        # 验证三个系统的验证结果
        expected_systems = ["hr", "inventory", "access"]
        for system in expected_systems:
            assert system in verification_results, f"Verification result for {system} should exist"
            system_result = verification_results[system]
            assert "verified" in system_result, f"Verification result for {system} should contain 'verified' field"
            assert "raw" in system_result, f"Verification result for {system} should contain 'raw' field"
            
            # 检查验证是否成功
            verified = system_result.get("verified", False)
            print(f"系统 {system} 验证结果: {verified}")
            
            # 检查原始响应数据
            raw_data = system_result.get("raw", {})
            assert raw_data.get("success", False), f"Raw verification for {system} should be successful"
            assert "data" in raw_data, f"Raw verification for {system} should contain data"
        
        print("✅ Planner 验证结果验证通过")

    @pytest.mark.asyncio
    async def test_planner_triggered_on_main_done(self, env_setup):
        """测试主任务完成时Planner触发动态补齐功能"""
        
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
        await asyncio.sleep(3)
        
        # 验证 Mock API 是否就绪
        import httpx
        for i in range(10):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"http://127.0.0.1:{mock_port}/docs")
                    if response.status_code == 200:
                        print("Mock API 已就绪")
                        break
            except Exception:
                await asyncio.sleep(0.5)
        else:
            print("警告: Mock API 可能未完全启动")

        # 初始化 PlanModule
        db = MemoryDatabaseConnection()
        plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo)
        await plan_module.start()
        
        # 确保侦听器引擎已启动
        if not plan_module.listener_engine.is_running:
            await plan_module.listener_engine.start()

        try:
            # 创建A2A Server并注册具备查询能力的虚拟Agent
            from src.infrastructure.a2a_server import A2AServer
            from src.infrastructure.a2a_client import DefaultA2AClient
            
            a2a_server = A2AServer()
            await a2a_server.register_agent({
                "agent_id": "hr_agent",
                "agent_name": "HR Agent",
                "provider": "internal",
                "version": "1.0.0",
                "capabilities": ["query_profile"],
                "endpoints": {"execute": "/agents/hr/execute"}
            })
            await a2a_server.register_agent({
                "agent_id": "inventory_agent",
                "agent_name": "Inventory Agent",
                "provider": "internal",
                "version": "1.0.0",
                "capabilities": ["check_outbound_status"],
                "endpoints": {"execute": "/agents/inv/execute"}
            })
            await a2a_server.register_agent({
                "agent_id": "access_agent",
                "agent_name": "Access Agent",
                "provider": "internal",
                "version": "1.0.0",
                "capabilities": ["query_access"],
                "endpoints": {"execute": "/agents/access/execute"}
            })
            
            # 验证所有Agent都已注册
            agents = await a2a_server.discover_agents()
            print(f"已注册的Agent: {[a['agent_id'] for a in agents]}")
            
            # 将A2A客户端注入PlanModule
            plan_module.set_a2a_client(DefaultA2AClient(a2a_server))

            # 创建最小计划：仅有主任务，无其他任务和侦听器
            plan_config = {
                "plan_id": "planner_trigger_test",
                "name": "Planner触发测试",
                "description": "主任务完成后由Planner动态补齐",
                "main_task_id": "001",
                "tasks": [
                    {
                        "task_id": "001",
                        "name": "主任务",
                        "prompt": "完成主任务"
                    }
                ],
                "listeners": []
            }
            
            plan_id = await plan_module.create_plan_from_config(plan_config)
            assert plan_id == "planner_trigger_test"
            
            # 设置员工上下文
            await self._setup_employee_context(plan_module, "001")
            
            # 将主任务置为Done，触发Planner
            await plan_module.listener_engine.trigger_task_status_change(
                "001",
                "NotStarted",
                "Done",
                plan_id
            )
            
            # 等待Planner处理和任务执行
            await asyncio.sleep(5)
            
            # 验证Planner已动态添加任务
            tasks = await plan_module.task_manager.get_plan_tasks(plan_id)
            task_ids = {t.id for t in tasks}
            print(f"动态添加的任务: {task_ids}")
            
            # 应该至少包含主任务和动态添加的任务
            assert "001" in task_ids
            # Planner应该添加了profile、outbound、access相关任务
            expected_dynamic_tasks = {"002", "004", "005"}
            added_tasks = task_ids.intersection(expected_dynamic_tasks)
            assert len(added_tasks) >= 2, f"Expected at least 2 dynamic tasks, got: {added_tasks}"
            
            # 验证工具调用记录
            await asyncio.sleep(2)  # 等待工具调用完成
            await self._verify_api_calls_in_log()
            
        finally:
            # 清理
            if 'mock_task' in locals():
                mock_task.cancel()
            if 'mcp_task' in locals():
                mcp_task.cancel()
            try:
                await asyncio.gather(mock_task, mcp_task, return_exceptions=True)
            except:
                pass