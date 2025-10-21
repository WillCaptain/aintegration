"""
pytest 配置文件
提供共享的测试 fixtures
"""
import asyncio
import pytest
import pytest_asyncio
import os
import socket
import httpx
from typing import Dict, Any, Tuple
from tests.utils.mock_api import run_mock_api, MOCK_LOG_FILE
from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule
from src.infrastructure.mcp_server import MCPServer
from src.infrastructure.mcp_client import MCPClient
from src.infrastructure.adk_integration import AgentRuntime
from src.infrastructure.a2a_server import A2AServer
from src.infrastructure.a2a_client import DefaultA2AClient


def get_free_port() -> int:
    """获取可用端口"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest_asyncio.fixture
async def env_setup():
    """环境设置 - 清理环境变量和日志文件"""
    # 由各测试动态设置 MOCK_API_URL，避免端口冲突
    if "MOCK_API_URL" in os.environ:
        os.environ.pop("MOCK_API_URL")
    # 清理日志
    if os.path.exists(MOCK_LOG_FILE):
        os.remove(MOCK_LOG_FILE)
    yield


@pytest_asyncio.fixture
async def mock_api_server():
    """动态端口的 Mock API 服务器 fixture"""
    mock_port = get_free_port()
    os.environ["MOCK_API_URL"] = f"http://127.0.0.1:{mock_port}"
    
    # 启动 Mock API 服务器
    mock_task = asyncio.create_task(run_mock_api(host="127.0.0.1", port=mock_port))
    
    # 等待服务器启动
    await asyncio.sleep(1)
    
    # 验证服务器是否就绪
    for i in range(10):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{mock_port}/docs")
                if response.status_code == 200:
                    print(f"Mock API 已就绪 (端口: {mock_port})")
                    break
        except Exception:
            await asyncio.sleep(0.5)
    
    yield mock_port, mock_task
    
    # 清理
    mock_task.cancel()
    try:
        await mock_task
    except asyncio.CancelledError:
        pass


@pytest_asyncio.fixture
async def mcp_server():
    """动态端口的 MCP 服务器 fixture"""
    mcp_port = get_free_port()
    
    server = MCPServer(host="127.0.0.1", port=mcp_port)
    server.load_tools_from_directory("config/apps")
    server_task = asyncio.create_task(server.run_async())
    
    # 等待服务器启动
    await asyncio.sleep(1)
    
    yield mcp_port, server, server_task
    
    # 清理
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass


@pytest_asyncio.fixture
async def full_test_environment(mock_api_server, mcp_server):
    """完整的测试环境 - 包含 Mock API 和 MCP Server"""
    mock_port, mock_task = mock_api_server
    mcp_port, mcp_server_instance, mcp_task = mcp_server
    
    # 创建数据库连接
    db = MemoryDatabaseConnection()
    
    # 创建AgentRuntime和A2AServer
    mcp_client = MCPClient(f"http://127.0.0.1:{mcp_port}")
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
    
    yield {
        "mock_port": mock_port,
        "mcp_port": mcp_port,
        "mock_task": mock_task,
        "mcp_task": mcp_task,
        "plan_module": plan_module,
        "adk_integration": adk_integration,
        "a2a_client": a2a_client,
        "mcp_client": mcp_client
    }
    
    # 清理
    await plan_module.stop()
    mock_task.cancel()
    mcp_task.cancel()
    try:
        await mock_task
    except asyncio.CancelledError:
        pass
    try:
        await mcp_task
    except asyncio.CancelledError:
        pass


@pytest_asyncio.fixture
async def mock_api_with_failures(mock_api_server):
    """带失败配置的 Mock API 服务器"""
    mock_port, mock_task = mock_api_server
    
    # 配置失败行为
    async def configure_failures(failures: Dict[str, int]):
        """配置特定工具的失败次数"""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"http://127.0.0.1:{mock_port}/configure_failures",
                json={"failures": failures}
            )
    
    yield mock_port, mock_task, configure_failures


@pytest_asyncio.fixture(scope="session")
async def mock_api_server_session():
    """会话级别的 Mock API 服务器 fixture（向后兼容）"""
    # 清理旧日志
    log_dir = os.path.dirname(MOCK_LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)
    if os.path.exists(MOCK_LOG_FILE):
        os.remove(MOCK_LOG_FILE)
    
    # 启动 Mock API 服务器
    mock_task = asyncio.create_task(run_mock_api(host="127.0.0.1", port=8009))
    
    # 等待服务器启动
    await asyncio.sleep(2)
    
    yield mock_task
    
    # 清理
    mock_task.cancel()
    try:
        await mock_task
    except asyncio.CancelledError:
        pass

@pytest_asyncio.fixture(scope="session")
async def mcp_server_session():
    """会话级别的 MCP 服务器 fixture（向后兼容）"""
    server = MCPServer(host="127.0.0.1", port=8004)
    server_task = asyncio.create_task(server.run_async())
    
    # 等待服务器启动
    await asyncio.sleep(2)
    
    yield server
    
    # 清理
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        pass

@pytest_asyncio.fixture(scope="class")
async def plan_module_class():
    """类级别 PlanModule（内存仓库），供需要复用实例的用例类使用。"""
    db = MemoryDatabaseConnection()
    mod = PlanModule(
        plan_repo=db.plan_repo,
        task_repo=db.task_repo,
        listener_repo=db.listener_repo,
    )
    await mod.start()
    yield mod
    await mod.stop()

@pytest_asyncio.fixture(scope="function")
async def plan_module_factory():
    """函数级 PlanModule 工厂：每次调用返回全新实例，供强隔离用例使用。"""
    db = MemoryDatabaseConnection()
    mod = PlanModule(
        plan_repo=db.plan_repo,
        task_repo=db.task_repo,
        listener_repo=db.listener_repo,
    )
    await mod.start()
    try:
        yield mod
    finally:
        await mod.stop()

