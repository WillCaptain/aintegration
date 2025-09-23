"""
MCP 客户端（WebSocket JSON-RPC，与项目内 mcp_server.py 对应）

通过 websockets 调用 JSON-RPC：ping、tools/register、tools/list、tools/execute。
"""
from __future__ import annotations

import logging
import json
from typing import Any, Dict, Optional

import websockets

from src.utils.config import load_config

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, base_url: Optional[str] = None, timeout_seconds: float = 30.0):
        cfg = load_config()
        if base_url is None:
            host = cfg.get("mcp_server.host", "localhost")
            port = cfg.get("mcp_server.port", 8004)
            protocol = cfg.get("mcp_server.protocol", "ws")
            base_url = f"{protocol}://{host}:{port}/ws"
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def _rpc(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        async with websockets.connect(self.base_url, open_timeout=self.timeout_seconds) as ws:
            await ws.send(json.dumps(payload))
            msg = await ws.recv()
            data = json.loads(msg)
            if "error" in data:
                raise RuntimeError(data["error"].get("message"))
            return data.get("result", {})

    async def ping(self) -> Dict[str, Any]:
        return await self._rpc("ping", {})

    async def register_tool(self, tool_definition: Dict[str, Any]) -> Dict[str, Any]:
        return await self._rpc("tools/register", tool_definition)

    async def list_tools(self) -> Dict[str, Any]:
        return await self._rpc("tools/list", {})

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        return await self._rpc("tools/execute", {"tool_name": tool_name, "parameters": parameters})


