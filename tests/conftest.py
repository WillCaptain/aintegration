"""
pytest 配置文件
提供共享的测试 fixtures
"""
import asyncio
import pytest
import pytest_asyncio
import os
from tests.utils.mock_api import run_mock_api, MOCK_LOG_FILE
from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule


@pytest_asyncio.fixture(scope="session")
async def mock_api_server():
    """共享的 Mock API 服务器 fixture"""
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
async def mcp_server():
    """共享的 MCP 服务器 fixture"""
    from src.infrastructure.mcp_server import MCPServer
    
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

