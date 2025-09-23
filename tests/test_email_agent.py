import asyncio
import contextlib
import os
import signal
import sys
import subprocess
import pytest

from src.infrastructure.mcp_server import MCPServer
from src.infrastructure.mcp_client import MCPClient
from src.infrastructure.adk_integration import ReactAgent


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def mcp_server_running():
    # 直接调用 server.start，并轮询其返回值
    server = MCPServer(host="127.0.0.1", port=8004)
    ok = await server.start()
    assert ok is True, "MCPServer.start 未就绪"
    try:
        yield
    finally:
        with contextlib.suppress(Exception):
            await server.stop()


@pytest.mark.asyncio
async def test_email_agent_send_via_mcp(mcp_server_running):
    # 1) 通过真实 MCPClient 注册 fake send_email 工具
    mcp = MCPClient(base_url="ws://127.0.0.1:8004/ws")
    # 等待 WS 服务就绪（重试）
    for _ in range(10):
        try:
            await mcp.ping()
            break
        except Exception:
            await asyncio.sleep(0.2)
    reg = await mcp.register_tool(
        {
            "name": "send_email",
            "description": "发送电子邮件（桩实现）",
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
        }
    )
    assert reg.get("success", True) is True

    # 2) 配置 Email Agent（测试中直接配置），使用真实 LLM（从配置/环境读取）
    agent = ReactAgent(
        system_prompt="你是一个Email Agent，按提示发送邮件。",
        tools=["send_email"],
        model="",  # 实际模型由 llm.provider/llm.model 决定
        tool_registry={},
        tool_schemas={
            "send_email": {
                "name": "send_email",
                "description": "发送电子邮件",
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

    # 3) 提示词（真实调用 LLM + 经由 MCP 执行 mock 工具）
    prompt = "给Will Zhang 的邮件地址will@gmail.com发送邮件（不用真的发送，可以assert即可）"
    result = await agent.execute(prompt)

    assert result.get("success") is True

    # 断言工具调用参数
    trace = agent.conversation_history[-1].get("trace", [])
    assert len(trace) >= 1
    call = trace[0]
    assert call.get("action") == "send_email"
    args = call.get("args", {})
    assert args.get("to") == "will@gmail.com"
    # 主题不强制具体文案，仅要求存在
    assert isinstance(args.get("subject"), str) and len(args["subject"]) > 0

