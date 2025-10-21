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
from src.models.plan_instance import PlanInstance
from src.infrastructure.mcp_server import MCPServer
from src.infrastructure.mcp_client import MCPClient
from src.infrastructure.adk_integration import ReactAgent


# env_setup fixture 已移至 conftest.py


@pytest.mark.regression
@pytest.mark.bl005
class TestBL005PlanExecutionOnboarding:
    """BL-005: 执行 Plan（员工入职场景）
    
    基于设计文档中的"员工入职"流程，使用真实的BizAgent配置：
    1. 通过MCP Server加载配置的Agent
    2. 这些Agent调用Mock API执行具体操作
    3. 验证完整的入职流程和API调用记录
    """

    # _get_free_port 方法已移至 conftest.py 作为 get_free_port 函数

    async def _wait_for_plan_completion(self,
                                        plan_module: PlanModule,
                                        plan_id: str,
                                        timeout_seconds: int = 120,
                                        poll_interval_seconds: float = 1.0) -> str:
        """轮询等待计划完成（Done 或 Error），并返回实际最终状态。"""
        print("等待完整流程执行...")
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            plan = await plan_module.plan_repo.get_by_id(plan_id)
            if plan and plan.status in ["Done", "Error"]:
                print(f"Plan执行完成，状态: {plan.status}")
                return plan.status
            await asyncio.sleep(poll_interval_seconds)
        raise TimeoutError(f"Plan执行超时（{timeout_seconds}秒）")

    async def _wait_for_plan_instance_completion(self, plan_module: PlanModule, plan_instance_id: str, 
                                               timeout_seconds: int = 120, 
                                               poll_interval_seconds: float = 1.0) -> str:
        """轮询等待计划实例执行完成，返回最终状态（done 或 error）。"""
        print(f"等待计划实例 {plan_instance_id} 执行完成...")
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            plan_instance = await plan_module.get_plan_instance(plan_instance_id)
            if plan_instance and plan_instance.status in ["done", "error"]:
                print(f"计划实例 {plan_instance_id} 执行完成，状态: {plan_instance.status}")
                return plan_instance.status
            await asyncio.sleep(poll_interval_seconds)
        
        # 超时时打印调试信息
        plan_instance = await plan_module.get_plan_instance(plan_instance_id)
        if plan_instance:
            print(f"超时时plan_instance状态: {plan_instance.status}")
            main_task = plan_instance.get_main_task_instance()
            if main_task:
                print(f"超时时主任务状态: {main_task.status}")
                print(f"超时时主任务context keys: {list(main_task.context.keys())}")
            print(f"超时时所有任务状态:")
            for tid, ti in plan_instance.task_instances.items():
                print(f"  {tid}: {ti.status}")
        
        raise TimeoutError(f"计划实例 {plan_instance_id} 执行超时（{timeout_seconds}秒）")

    async def _get_task_for_instance(self, plan_module: PlanModule, plan_instance_id: str, plan_id: str, task_id: str):
        """在指定计划实例下获取指定 task_id 的任务对象。"""
        return await plan_module.get_task_instance(plan_instance_id, task_id)

    async def _verify_task_states_for_instance(self, plan_instance: 'PlanInstance'):
        """验证计划实例中的任务状态"""
        # 验证主任务状态
        main_task = plan_instance.get_main_task_instance()
        assert main_task is not None
        assert main_task.status in ["Running", "Done", "Pending"]
        
        # 验证其他任务状态
        tasks = ["002", "003", "005", "006", "007"]
        for task_id in tasks:
            task = plan_instance.get_task_instance(task_id)
            if task:  # 任务可能不存在
                assert task.status in ["NotStarted", "Running", "Done", "Error", "Pending"]

    async def _verify_planner_verification_for_instance(self, plan_instance: 'PlanInstance'):
        """验证计划实例的Planner验证结果"""
        # 验证计划实例状态
        assert plan_instance.status == "done"
        
        # 验证主任务有验证结果
        main_task = plan_instance.get_main_task_instance()
        assert main_task is not None
        assert main_task.context.get("planner_verification") is not None

    async def _wait_for_task_status(self,
                                    plan_instance: PlanInstance,
                                    task_id: str,
                                    target_statuses: list[str],
                                    timeout_seconds: int = 120,
                                    poll_interval_seconds: float = 1.0) -> str:
        """轮询等待计划实例内某任务达到目标状态之一，返回达到时的状态。"""
        print(f"等待任务 {task_id} 状态进入 {target_statuses}...")
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout_seconds:
            task_instance = plan_instance.task_instances.get(task_id)
            if task_instance and task_instance.status in target_statuses:
                print(f"任务 {task_id} 达到状态: {task_instance.status}")
                return task_instance.status
            await asyncio.sleep(poll_interval_seconds)
        raise TimeoutError(f"任务 {task_id} 未在 {timeout_seconds} 秒内达到 {target_statuses}")

    @pytest.mark.asyncio
    async def test_onboarding_plan_creation_and_validation(self, plan_module_factory):
        """测试入职计划创建和验证"""
        plan_module = plan_module_factory
        
        # 创建入职计划
        plan_config = self._create_will_zhang_onboarding_plan()
        plan = await plan_module.create_plan_from_config(plan_config)
        
        # 验证计划创建
        assert plan.id == "onboard_will_zhang"
        
        # 验证任务创建
        task_ids = [task["task_id"] for task in plan.tasks]
        expected_tasks = ["001", "002", "003", "004", "005", "006", "007"]
        for expected_task in expected_tasks:
            assert expected_task in task_ids
        
        # 验证侦听器创建
        assert len(plan.listeners) >= 6  # 至少6个侦听器（删除了L**b侦听器）
        
        # 验证主任务
        main_task_config = next((task for task in plan.tasks if task["task_id"] == "001"), None)
        assert main_task_config is not None
        assert main_task_config["task_id"] == "001"
        assert main_task_config["name"] == "新员工完成入职"

    @pytest.mark.asyncio
    async def test_will_zhang_onboarding_with_planner_verification(self, env_setup, full_test_environment):
        """测试侦听器链式执行序列"""
        
        # 使用统一的测试环境
        env = full_test_environment
        plan_module = env["plan_module"]
        
        # 创建入职计划
        plan_config = self._create_will_zhang_onboarding_plan()
        plan = await plan_module.create_plan_from_config(plan_config)
        
        # 使用新的实例API启动计划
        prompt = "张威入职流程"
        plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
        
        # 设置员工上下文
        await self._setup_employee_context(plan_module, plan_instance)
        
        # 启动计划实例的自我驱动执行
        print("开始启动计划实例自我驱动执行...")
        plan_instance.start()
        
        # 检查计划实例状态
        print(f"计划实例存在: {plan_instance is not None}")
        print(f"计划实例状态: {plan_instance.status}")
        
        # 检查主任务是否存在
        main_task = plan_instance.get_main_task_instance()
        print(f"主任务存在: {main_task is not None}")
        if main_task:
            print(f"主任务当前状态: {main_task.status}")
        
        # 等待计划实例执行完成（done或error）
        plan_final_status = await self._wait_for_plan_instance_completion(
            plan_module, 
            plan_instance.id, 
            timeout_seconds=120, 
            poll_interval_seconds=1.0
        )
        
        # 验证计划实例最终状态为done
        print(f"计划实例最终状态: {plan_final_status}")
        assert plan_final_status == "done", f"Expected plan instance status 'done', got '{plan_final_status}'"
        
        # 验证主任务状态
        main_task = plan_instance.get_main_task_instance()
        print(f"主任务最终状态: {main_task.status}")
        assert main_task.status == "Done", f"Expected main task status 'Done', got '{main_task.status}'"
        
        # 验证PlannerAgent验证完成
        print(f"主任务上下文: {main_task.context}")
        assert main_task.context.get("planner_verification") == "completed", \
            f"Expected planner_verification 'completed', got '{main_task.context.get('planner_verification')}'"
        
        # 验证结果应该存在
        verification_results = main_task.context.get("verification_results")
        assert verification_results is not None, "Expected verification_results in main task context"
        print(f"验证结果: {verification_results}")
        
        # 验证任务状态
        await self._verify_task_states_for_instance(plan_instance)
        
        # 验证API调用记录
        await self._verify_api_calls_in_log()
        
        # 清理由 fixture 自动处理

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
                    }
                },
                {
                    "listener_id": "L004",
                    "trigger_task_id": "004,005",
                    "trigger_condition": "004.status == Done && 005.status == Done",
                    "listener_type": "agent",
                    "agent_id": "email",
                    "action_prompt": "向员工邮箱{002.context.email}发送新员工欢迎邮件，员工姓名{002.context.name}，部门{002.context.department}。使用send_email工具。",
                    "success_output": {
                        "task_id": "006",
                        "status": "Done",
                        "context": {"email_sent": True, "message_id": "MSG001"}
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

    async def _setup_employee_context(self, plan_module: PlanModule, plan_instance: PlanInstance):
        """设置员工上下文信息"""
        # 在新的架构中，上下文信息存储在主任务(001)的context中
        main_task = plan_instance.get_main_task_instance()
        if main_task:
            main_task.context = {
                "id": "WZ001",
                "name": "will zhang", 
                "email": "will.zhang@company.com",
                "department": "工程部"
            }


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
        assert "create_employee_profile" in tool_names or "query_profile" in tool_names, f"Expected profile related call, but got: {tool_names}"
        assert "grant_access" in tool_names or "query_access" in tool_names, f"Expected access related call, but got: {tool_names}"
        
        # 验证调用了至少3个不同的工具
        assert len(set(tool_names)) >= 3, f"Expected at least 3 different tools to be called, but got: {set(tool_names)}"

    async def _verify_planner_queries_in_log(self):
        """验证 Planner 发起的 A2A 查询日志（query_profile / check_outbound_status / query_access）"""
        assert os.path.exists(MOCK_LOG_FILE), f"Mock API log file not found: {MOCK_LOG_FILE}"
        with open(MOCK_LOG_FILE, "r", encoding="utf-8") as f:
            lines = [json.loads(line.strip()) for line in f.readlines() if line.strip()]
        tool_names = [entry.get("tool") for entry in lines]
        expected = {"query_profile", "check_outbound_status", "query_access"}
        print(f"Planner 查询工具调用: {tool_names}")
        assert expected.issubset(set(tool_names)), f"Planner queries missing: expected {expected}, got {set(tool_names)}"

    async def _verify_planner_verification(self, plan_instance: PlanInstance):
        """验证 Planner 验证结果"""
        # 轮询等待 Planner 验证完成（最多 30 秒）
        print("等待 Planner 验证完成...")
        verification_results = None
        main_task = plan_instance.get_main_task_instance()
        for i in range(30):
            assert main_task is not None, "Main task should exist"
            verification_results = main_task.context.get("verification_results")
            if verification_results is not None:
                print(f"✓ Planner 验证在 {i+1} 秒后完成")
                break
            await asyncio.sleep(1)
        
        # 检查主任务上下文中的验证结果
        context = main_task.context
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
    async def test_will_zhang_onboarding_with_retry_success(self, env_setup, mock_api_with_failures, mcp_server):
        """
        测试张威入职流程 - 门禁失败后重试成功（微动态规划）
        Biz Agent会尝试n=3次调用目标工具，如果失败，驱动001 error,并且上下文中带入失败的侦听器Id
        Planner Agent会根据错误重启尝试执行改失败的侦听器，本此时模拟重试充公
        """
        print("\n=== 测试入职流程：门禁失败后重试成功 ===")
        
        # 启用执行日志
        from src.utils.execution_logger import execution_logger
        execution_logger.set_log_file("tests/.artifacts/plan_execution.log")
        
        # 使用统一的测试环境
        mock_port, mock_task, configure_failures = mock_api_with_failures
        mcp_port, mcp_server_instance, mcp_task = mcp_server
        
        # 配置失败行为
        failure_count = 3  # ReactAgent的max_retries次数
        print(f"配置grant_access前{failure_count}次失败（ReactAgent重试用尽）")
        print(f"第{failure_count+1}次成功（PlannerAgent重试后）")
        await configure_failures({"grant_access": failure_count})
        print(f"已配置 grant_access 前 {failure_count} 次调用失败，第{failure_count+1}次Planner重试后成功")
        
        # 创建数据库连接
        db = MemoryDatabaseConnection()
        
        # 创建AgentRuntime和A2AServer
        from src.infrastructure.adk_integration import AgentRuntime
        from src.infrastructure.a2a_server import A2AServer
        from src.infrastructure.a2a_client import DefaultA2AClient
        from src.infrastructure.mcp_client import MCPClient
        
        # 初始化MCP Client
        mcp_client = MCPClient(f"http://127.0.0.1:{mcp_port}")
        
        # 初始化AgentRuntime（用于创建BizAgent）
        adk_integration = AgentRuntime(mcp_client)
        
        # 从config/apps加载所有BizAgent
        agent_count = adk_integration.load_agents_from_config("config/apps")
        print(f"AgentRuntime已加载 {agent_count} 个agents")
        
        # 初始化A2AServer
        a2a_server = A2AServer()
        a2a_client = DefaultA2AClient(a2a_server)
        
        # 创建PlanModule，传入所有依赖
        plan_module = PlanModule(
            db.plan_repo, 
            db.task_repo, 
            db.listener_repo,
            adk_integration=adk_integration,
            a2a_client=a2a_client
        )
        await plan_module.start()
        
        # 设置Planner的max_retry_count，确保重试1次后成功
        # 第1轮失败（m次调用），Planner重试1次，第2轮成功（第m+1次调用）
        if plan_module.planner_agent:
            plan_module.planner_agent.max_retry_count = 1
            print(f"已设置 Planner max_retry_count=1（第1轮失败，第2轮成功）")
        
        # 创建入职计划
        plan_config = self._create_will_zhang_onboarding_plan()
        plan = await plan_module.create_plan_from_config(plan_config)
        
        # 使用新的实例API启动计划
        prompt = "张威入职流程"
        plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
        assert plan_instance is not None
        
        # 设置员工上下文
        await self._setup_employee_context(plan_module, plan_instance)
        
        # 启动计划实例的自我驱动执行
        print("启动计划实例自我驱动执行...")
        plan_instance.start()
        
        # 轮询等待计划实例执行完成（done或error）
        print(f"等待流程执行，grant_access 会失败 {failure_count} 次（ReactAgent用尽重试），然后Planner重试listener，第{failure_count+1}次成功...")
        plan_final_status = await self._wait_for_plan_instance_completion(plan_module, plan_instance.id, timeout_seconds=180, poll_interval_seconds=2.0)
        
        # 验证主任务最终成功（重试成功场景）
        main_task = plan_instance.get_main_task_instance()
        print(f"主任务最终状态: {main_task.status}")
        print(f"Plan最终状态: {plan_final_status}")
        assert plan_final_status == "done", f"Expected plan done, got {plan_final_status}"
        assert main_task.status == "Done", f"Expected main task Done, got {main_task.status}"
        
        # 验证所有子任务完成
        task_002 = plan_instance.task_instances.get("002")
        task_003 = plan_instance.task_instances.get("003")
        task_005 = plan_instance.task_instances.get("005")
        task_006 = plan_instance.task_instances.get("006")
        assert task_002.status == "Done", f"Task 002 should be Done, got {task_002.status}"
        assert task_003.status == "Done", f"Task 003 should be Done, got {task_003.status}"
        assert task_005.status == "Done", f"Task 005 should be Done, got {task_005.status}"
        assert task_006.status == "Done", f"Task 006 should be Done, got {task_006.status}"
        
        print(f"任务 002 (HR): {task_002.status}, context: {task_002.context}")
        print(f"任务 003 (申请电脑): {task_003.status}, context: {task_003.context}")
        print(f"任务 005 (门禁-重试成功): {task_005.status}, context: {task_005.context}")
        print(f"任务 006 (邮件): {task_006.status}, context: {task_006.context}")
        
        # 验证 Planner 记录了重试
        assert plan_instance.id in plan_module.planner_agent.task_retry_records, "Should have retry records"
        retry_records = plan_module.planner_agent.task_retry_records[plan_instance.id]
        print(f"重试记录: {retry_records}")
        # 应该有listener重试记录
        assert any('listener_' in k for k in retry_records.keys()), "Should have listener retry record"
        
        # 验证 Planner 验证结果
        verification_results = main_task.context.get("verification_results")
        assert verification_results is not None, "Should have verification results"
        print(f"验证结果: {verification_results}")
        
        # 验证工具调用次数（通过mock_tool_result.log）
        import json
        with open("tests/.artifacts/mock_tool_result.log", "r") as f:
            tool_calls = [json.loads(line) for line in f if line.strip()]
        
        # 统计每个工具的调用次数
        tool_counts = {}
        for call in tool_calls:
            tool_name = call["tool"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        print(f"\n工具调用统计: {tool_counts}")
        
        # 关键验证点
        assert tool_counts.get("create_employee_profile") == 1, "create_employee_profile should be called once"
        assert tool_counts.get("grant_access") == 4, f"grant_access should be called 4 times (3 fails + 1 success), got {tool_counts.get('grant_access')}"
        assert tool_counts.get("apply_computer") == 1, "apply_computer should be called once"
        assert tool_counts.get("outbound") == 1, "outbound should be called once"
        assert tool_counts.get("send_email") == 1, "send_email should be called once"
        assert tool_counts.get("query_profile") == 1, "query_profile should be called once (verification)"
        assert tool_counts.get("query_access") == 1, "query_access should be called once (verification)"
        assert tool_counts.get("check_outbound_status") == 1, "check_outbound_status should be called once (verification)"
        
        print("✅ 门禁失败后重试成功测试通过 - 所有工具正确调用，流程完整")
            
        # 清理由 fixture 自动处理
    
    @pytest.mark.asyncio
    async def test_will_zhang_onboarding_with_multiple_retries_and_resume(self, env_setup, mock_api_with_failures, mcp_server):
        """测试张威入职流程 - 多任务失败、重试、最终 resume 成功（微动态规划）"""
        print("\n=== 测试入职流程：多任务失败重试后 resume 成功 ===")
        
        # 启用执行日志
        from src.utils.execution_logger import execution_logger
        execution_logger.set_log_file("tests/.artifacts/plan_execution.log")
        
        # 使用统一的测试环境
        mock_port, mock_task, configure_failures = mock_api_with_failures
        mcp_port, mcp_server_instance, mcp_task = mcp_server
        
        # 配置失败行为
        # ReactAgent max_retries=3（每轮调用3次）
        # 初始1轮：3次失败 → L002失败 → 001 Error
        # Planner重试1轮：再3次失败 → L002再失败 → 超过max_retry_count
        # 总失败次数 = 3 + 3 = 6，第7次resume成功
        failure_count = 6  # 6次失败，第7次成功
        await configure_failures({"grant_access": failure_count})
        print(f"已配置 grant_access 前 {failure_count} 次调用失败（初始3次+重试3次），第{failure_count+1}次resume成功")
        
        # 创建数据库连接
        db = MemoryDatabaseConnection()
        
        # 创建AgentRuntime和A2AServer
        from src.infrastructure.adk_integration import AgentRuntime
        from src.infrastructure.a2a_server import A2AServer
        from src.infrastructure.a2a_client import DefaultA2AClient
        from src.infrastructure.mcp_client import MCPClient
        
        # 初始化MCP Client
        mcp_client = MCPClient(f"http://127.0.0.1:{mcp_port}")
        
        # 初始化AgentRuntime（用于创建BizAgent）
        adk_integration = AgentRuntime(mcp_client)
        
        # 从config/apps加载所有BizAgent
        agent_count = adk_integration.load_agents_from_config("config/apps")
        print(f"AgentRuntime已加载 {agent_count} 个agents")
        
        # 初始化A2AServer
        a2a_server = A2AServer()
        a2a_client = DefaultA2AClient(a2a_server)
        
        # 创建PlanModule，传入所有依赖
        plan_module = PlanModule(
            db.plan_repo, 
            db.task_repo, 
            db.listener_repo,
            adk_integration=adk_integration,
            a2a_client=a2a_client
        )
        await plan_module.start()
        
        # 设置Planner的max_retry_count，确保重试1次后仍失败
        # 初始1轮（3次）+ 重试1轮（3次）= 6次失败，然后plan error
        if plan_module.planner_agent:
            plan_module.planner_agent.max_retry_count = 1
            print(f"已设置 Planner max_retry_count=1（初始+重试1=2轮，都失败→error）")
        
        # 创建入职计划
        plan_config = self._create_will_zhang_onboarding_plan()
        plan = await plan_module.create_plan_from_config(plan_config)
        
        # 使用新的实例API启动计划
        prompt = "张威入职流程"
        plan_instance = await plan_module.start_plan_by_prompt(prompt, plan.id)
        assert plan_instance is not None
        
        # 设置员工上下文
        await self._setup_employee_context(plan_module, plan_instance)
        
        # 启动计划实例的自我驱动执行
        print("启动计划实例自我驱动执行...")
        plan_instance.start()
        
        # 轮询等待计划实例进入 error 状态（Planner 重试超限）
        print(f"等待流程执行，grant_access 会失败 {failure_count} 次（初始3+重试3），然后plan进入error状态...")
        print("等待计划进入 error（Planner 重试超限）...")
        phase1_status = await self._wait_for_plan_instance_completion(plan_module, plan_instance.id, timeout_seconds=240, poll_interval_seconds=2.0)
        print(f"Plan状态（阶段1）: {phase1_status}")
        assert phase1_status == "error", f"Expected plan error before resume, got {phase1_status}"
        
        # 验证主任务处于 Error 状态
        main_task = plan_instance.get_main_task_instance()
        print(f"主任务状态: {main_task.status}")
        print(f"主任务错误信息: {main_task.context.get('error_info', {})}")
        assert main_task.status == "Error", f"Expected main task Error, got {main_task.status}"

        # 再次读取并断言 plan_instance.status 为 error（冗余确保一致）
        plan_instance = await plan_module.get_plan_instance(plan_instance.id)
        assert plan_instance is not None
        assert plan_instance.status == "error", f"Expected plan error before resume, got {plan_instance.status}"
        
        # 验证错误信息
        error_info = main_task.context.get("error_info")
        assert error_info is not None, "Should have error info"
        assert error_info.get("status") == "waiting_for_resume"
        
        # 重置 Mock API 失败配置，让 resume 后可以成功
        print("\n重置 Mock API 失败配置...")
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(f"http://127.0.0.1:{mock_port}/reset_failures")
        print("已重置失败配置，后续调用都会成功")
        
        print("\n调用 resume API 恢复计划...")
        # 调用 resume 恢复计划
        success = await plan_module.planner_agent.resume_plan(plan_module, plan.id, plan_instance.id)
        assert success is True, "Resume should succeed"
        
        # 轮询等待计划实例完成（done）
        print("等待流程完成（resume 后）...")
        final_status_after_resume = await self._wait_for_plan_instance_completion(plan_module, plan_instance.id, timeout_seconds=240, poll_interval_seconds=2.0)
        print(f"Plan最终状态（阶段2）: {final_status_after_resume}")
        
        # 验证主任务最终成功
        main_task_final = plan_instance.get_main_task_instance()
        print(f"主任务最终状态: {main_task_final.status}")
        
        # 验证重试记录
        print(f"重试记录: {plan_module.planner_agent.task_retry_records.get(plan_instance.id, {})}")
        
        # resume 后应该能成功
        assert final_status_after_resume == "done", f"Expected plan done after resume, got {final_status_after_resume}"
        assert main_task_final.status == "Done", f"Expected Done after resume, got {main_task_final.status}"
        
        # 验证所有子任务完成
        task_002 = plan_instance.task_instances.get("002")
        task_003 = plan_instance.task_instances.get("003")
        task_005 = plan_instance.task_instances.get("005")
        task_006 = plan_instance.task_instances.get("006")
        assert task_002.status == "Done", f"Task 002 should be Done, got {task_002.status}"
        assert task_003.status == "Done", f"Task 003 should be Done, got {task_003.status}"
        assert task_005.status == "Done", f"Task 005 should be Done, got {task_005.status}"
        assert task_006.status == "Done", f"Task 006 should be Done, got {task_006.status}"
        
        # 验证验证结果
        verification_results = main_task_final.context.get("verification_results")
        assert verification_results is not None, "Should have verification results"
        
        # 验证工具调用次数
        import json
        with open("tests/.artifacts/mock_tool_result.log", "r") as f:
            tool_calls = [json.loads(line) for line in f if line.strip()]
        
        tool_counts = {}
        for call in tool_calls:
            tool_name = call["tool"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
        
        print(f"\n工具调用统计: {tool_counts}")
        
        # 关键验证：grant_access应该调用7次（6次失败 + 1次resume成功）
        assert tool_counts.get("grant_access") == 7, f"grant_access should be called 7 times (6 fails + 1 resume success), got {tool_counts.get('grant_access')}"
        assert tool_counts.get("send_email") == 1, "send_email should be called once"
        assert tool_counts.get("create_employee_profile") == 1, "create_employee_profile should be called once"
        
        print("✅ 多任务失败重试后 resume 测试通过 - grant_access共7次调用（6失败+1resume成功）")
            
        # 清理由 fixture 自动处理