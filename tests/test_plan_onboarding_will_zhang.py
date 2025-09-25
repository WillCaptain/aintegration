import asyncio
import os
import json
import pytest
import pytest_asyncio

from tests.utils.mock_api import run_mock_api, MOCK_LOG_FILE
from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule
from src.infrastructure.mcp_server import MCPServer
from src.infrastructure.a2a_server import A2AServer
from src.infrastructure.adk_integration import AgentRuntime
from src.core.biz_agent import BizAgentModule


@pytest_asyncio.fixture
async def env_setup():
    os.environ.setdefault("MOCK_API_URL", "http://127.0.0.1:8009")
    # 清理日志
    if os.path.exists(MOCK_LOG_FILE):
        os.remove(MOCK_LOG_FILE)
    yield


@pytest.mark.asyncio
async def test_onboarding_will_zhang(env_setup):
    # 启动 Mock API
    mock_task = asyncio.create_task(run_mock_api(host="127.0.0.1", port=8009))

    # 启动 MCP/A2A 与 BizAgent
    mcp_server = MCPServer(host="127.0.0.1", port=8004)
    _ = mcp_server.load_tools_from_directory("config/apps")
    a2a_server = A2AServer(host="127.0.0.1", port=8005)
    runtime = AgentRuntime(api_key="")
    biz_module = BizAgentModule(mcp_server=mcp_server, a2a_server=a2a_server, adk_integration=runtime)

    # 启动 BizAgent 模块（会注册 agent 到 A2A）
    await biz_module.start()

    # 初始化 PlanModule
    db = MemoryDatabaseConnection()
    plan_module = PlanModule(db.plan_repo, db.task_repo, db.listener_repo, adk_integration=runtime)
    await plan_module.start()

    # 构造基于设计文档的入职 Plan（简化版）
    plan_config = {
        "plan_id": "onboard_will_zhang",
        "name": "新员工入职-张威",
        "description": "根据设计文档的示例，使用 BizAgent 执行入职流程",
        "main_task_id": "001",
        "tasks": [
            {"task_id": "001", "name": "新员工完成入职", "prompt": "新员工入职"},
            {"task_id": "002", "name": "新员工注册", "prompt": "在HR系统注册"},
            {"task_id": "003", "name": "申请电脑", "prompt": "在IT系统申请电脑"},
            {"task_id": "005", "name": "门禁申请", "prompt": "开通门禁"},
        ],
        "listeners": [
            {
                "listener_id": "L001",
                "trigger_task_id": "001",
                "trigger_condition": "001.status == Running",
                "action_condition": "true",
                "listener_type": "agent",
                "agent_id": "hr_agent_v1",
                "action_prompt": "根据员工身份证号{001.context.id}、姓名{001.context.name}在HR系统中创建员工记录，确定员工级别",
                "success_output": {"task_id": "002", "status": "Done", "context": {"emp_id": "{{result.emp_id}}", "level": "{{result.level}}"}},
                "failure_output": {"task_id": "002", "status": "Error", "context": {"error": "HR系统连接失败"}},
            },
            {
                "listener_id": "L002",
                "trigger_task_id": "001",
                "trigger_condition": "001.status == Running",
                "action_condition": "true",
                "listener_type": "agent",
                "agent_id": "access_agent_v1",
                "action_prompt": "根据员工ID{001.context.id}为新员工申请门禁权限，输入员工姓名{001.context.name}",
                "success_output": {"task_id": "005", "status": "Done", "context": {"access_id": "{{result.access_id}}"}},
                "failure_output": {"task_id": "005", "status": "Error", "context": {"error": "门禁系统异常"}},
            },
            {
                "listener_id": "L003",
                "trigger_task_id": "002",
                "trigger_condition": "002.status == Done",
                "action_condition": "true",
                "listener_type": "agent",
                "agent_id": "it_agent_v1",
                "action_prompt": "根据员工ID{002.context.emp_id}和员工级别{002.context.level}申请相应配置的笔记本",
                "success_output": {"task_id": "003", "status": "NotStarted", "context": {"pc_model": "{{result.pc_model}}"}},
                "failure_output": {"task_id": "003", "status": "Error", "context": {"error": "IT系统维护中"}},
            },
        ]
    }

    plan_id = await plan_module.create_plan_from_config(plan_config)

    # 设置主任务上下文（will zhang）
    main_task = await plan_module.task_manager.get_task("001")
    main_task.set_context_value("id", "WZ001")
    main_task.set_context_value("name", "will zhang")
    main_task.set_context_value("email", "will.zhang@company.com")
    main_task.set_context_value("department", "工程部")
    await plan_module.task_manager.task_repo.update_status("001", main_task.status, main_task.context)

    # 启动执行
    result = await plan_module.execute_plan(plan_id)
    assert result["success"] is True

    # 等待引擎处理
    await asyncio.sleep(1.5)

    # 验证 HR 与 Access 已触发
    assert os.path.exists(MOCK_LOG_FILE)
    with open(MOCK_LOG_FILE, "r", encoding="utf-8") as f:
        lines = [json.loads(x) for x in f.readlines()]
    tool_names = [x.get("tool") for x in lines]
    assert "create_employee_profile" in tool_names or "grant_access" in tool_names

    # 清理
    await plan_module.stop()
    await biz_module.stop()
    mock_task.cancel()
    await asyncio.sleep(0.2)


