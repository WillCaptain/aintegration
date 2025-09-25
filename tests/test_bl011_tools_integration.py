import asyncio
import contextlib
import os
import json
import pytest
import pytest_asyncio

from src.infrastructure.mcp_server import MCPServer
from src.infrastructure.mcp_client import MCPClient
from src.infrastructure.adk_integration import ReactAgent
from tests.utils.mock_api import run_mock_api, MOCK_LOG_FILE


@pytest.fixture(scope="class")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.mark.regression
@pytest.mark.bl011
class TestBL011ToolsIntegration:
    @pytest_asyncio.fixture(scope="class")
    async def mcp_server_once(self):
        """类内仅启动一次 MCP Server，并复用。"""
        server = MCPServer(host="127.0.0.1", port=8004)
        task = asyncio.create_task(server.run_async())
        # 等待就绪
        client = MCPClient(base_url="http://127.0.0.1:8004/mcp")
        for _ in range(50):
            try:
                await client.ping()
                break
            except Exception:
                await asyncio.sleep(0.1)
        try:
            yield server
        finally:
            # 不主动关闭，避免端口抖动；若需要可改为关闭。
            if False:
                task.cancel()
                with contextlib.suppress(Exception):
                    await asyncio.sleep(0.1)
    @pytest_asyncio.fixture(scope="class")
    async def mock_api_once(self):
        """确保 Mock API 在本函数期间可用：若已在运行则复用，未运行则启动一次并保留至会话结束。"""
        import httpx
        log_dir = os.path.dirname(MOCK_LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)

        async def is_up() -> bool:
            try:
                await asyncio.sleep(0)
                _ = httpx.post("http://127.0.0.1:8009/tool", json={"tool": "probe", "args": {}}, timeout=1)
                return True
            except Exception:
                return False

        already_running = await is_up()
        task = None
        if not already_running:
            # 仅在首次启动时清理旧日志
            if os.path.exists(MOCK_LOG_FILE):
                os.remove(MOCK_LOG_FILE)
            task = asyncio.create_task(run_mock_api(host="127.0.0.1", port=8009))
            # 等待端口就绪（主动探测，最长 ~6s）
            for _ in range(60):
                if await is_up():
                    break
                await asyncio.sleep(0.1)

        try:
            yield
        finally:
            # 类结束时不主动关闭，避免端口抖动；下次类用例会复用现有实例。
            # 如需显式关闭，可在此取消 task。
            if False and task is not None:
                task.cancel()
                with contextlib.suppress(Exception):
                    await asyncio.sleep(0.1)
    @pytest.mark.asyncio
    async def test_app_tools_loading_email(self, mock_api_once, mcp_server_once):
        # 确保配置文件存在
        assert os.path.exists("config/apps/email.yaml")

        # 复用类级 MCP Server，并从目录加载工具
        res = mcp_server_once.load_tools_from_directory("config/apps")
        assert res.get("success") is True
        # 至少注册了 send_email
        assert res.get("loaded", 0) >= 1

        # 客户端连通性
        client = MCPClient(base_url="http://127.0.0.1:8004/mcp")
        for _ in range(10):
            try:
                await client.ping()
                break
            except Exception:
                await asyncio.sleep(0.2)
        tools = (await client.list_tools()).get("tools") or []
        # 仅统一工具 call_tool
        assert any(t.get("name") == "call_tool" for t in tools)

        # Agent 通过 app_name 自动加载工具
        agent = ReactAgent(
            system_prompt="你是一个Email Agent，按提示发送邮件。",
            app_name="email",
        )
        # 直接执行，提示中含完整参数
        prompt = "请向邮箱地址 a@b.com 发送邮件。主题：hi；正文：hello。"
        result = await agent.execute(prompt)
        assert result.get("success") is True

        # 校验日志记录已写入
        await asyncio.sleep(0.5)
        assert os.path.exists(MOCK_LOG_FILE)
        with open(MOCK_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) >= 1
        last = json.loads(lines[-1])
        assert last.get("tool") in ("send_email", "call_tool", "send_email")
        # 如果是 send_email 应包含以下参数
        args = last.get("args") or {}
        assert args.get("to") == "a@b.com"
        assert args.get("subject") == "hi"
        assert args.get("body") == "hello"
        # 无需在此关闭 MCP Server（类级复用）

    @pytest.mark.asyncio
    async def test_email_agent_send_via_mcp(self, mock_api_once, mcp_server_once):
        # 复用 MCP Server（类级）
        try:
            
            # 1) 通过真实 MCPClient 连接服务器
            mcp = MCPClient(base_url="http://127.0.0.1:8004/mcp")
            
            # 等待服务就绪（重试）
            for _ in range(10):
                try:
                    await mcp.ping()
                    break
                except Exception:
                    await asyncio.sleep(0.2)
            
            # 2) （可选）检查统一工具存在
            tools = (await mcp.list_tools()).get("tools") or []
            assert any(t.get("name") == "call_tool" for t in tools)

            # 3) 配置 Email Agent（测试中直接配置）
            agent = ReactAgent(
                system_prompt="你是一个Email Agent，按提示发送邮件。",
                tools=["send_email"],
                tool_registry={},
                tool_schemas={
                    "send_email": {
                        "name": "send_email",
                        "description": "发送电子邮件",
                        "endpoint": "http://127.0.0.1:8009/tool",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "to": {"type": "string"},
                                "subject": {"type": "string"},
                                "body": {"type": "string"},
                            },
                            "required": ["to", "subject", "body"],
                        },
                    }
                },
            )

            # 4) 提示词（真实调用 LLM + 经由 MCP 执行 mock 工具）
            prompt = "给Will Zhang 的邮件地址will@gmail.com发送邮件。主题为：测试，内容为：测试发送邮件"
            result = await agent.execute(prompt)

            assert result.get("success") is True

            # 校验 Mock API 日志
            await asyncio.sleep(0.5)
            assert os.path.exists(MOCK_LOG_FILE)
            with open(MOCK_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) >= 1
            last = json.loads(lines[-1])
            assert last.get("tool") == "send_email"
            largs = last.get("args", {})
            assert largs.get("to") == "will@gmail.com"
            assert isinstance(largs.get("subject"), str) and len(largs.get("subject", "")) > 0
        
        finally:
            pass

    @pytest.mark.asyncio
    async def test_dynamic_register_tool(self, mock_api_once, mcp_server_once):
        # 复用 MCP 服务器
        try:
            # 动态注册 send_email 工具（仅存元数据，调用统一用 call_tool）
            tool_def = {
                "name": "send_email",
                "description": "发送电子邮件（动态注册）",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["to", "subject", "body"],
                },
                "response_schema": {"type": "object"},
                "endpoint": "http://127.0.0.1:8009/tool",
            }

            reg_result = mcp_server_once.register_tool(tool_def)
            assert reg_result.get("success") is True

            # 通过官方客户端封装（MCPClient）连接并列出工具
            client = MCPClient(base_url="http://127.0.0.1:8004/mcp")

            # 重试等待服务就绪
            for _ in range(10):
                try:
                    await client.ping()
                    break
                except Exception:
                    await asyncio.sleep(0.2)

            list_result = await client.list_tools()
            assert list_result.get("success") is True
            tools = list_result.get("tools") or []
            assert any(t.get("name") == "call_tool" for t in tools)

            # 通过 call_tool 转发到 Mock API，并校验日志
            call_params = {
                "endpoint": "http://127.0.0.1:8009/tool",
                "tool": "send_email",
                "args": {"to": "a@b.com", "subject": "hi", "body": "hello"},
            }
            _ = await client.execute_tool("call_tool", call_params)
            # 验证日志
            await asyncio.sleep(0.5)
            assert os.path.exists(MOCK_LOG_FILE)
            with open(MOCK_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) >= 1
            last = json.loads(lines[-1])
            assert last.get("tool") == "send_email"
            assert last.get("args", {}).get("to") == "a@b.com"
            assert last.get("args", {}).get("subject") == "hi"
            assert last.get("args", {}).get("body") == "hello"

        finally:
            pass
