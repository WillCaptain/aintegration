"""
MCP Server（仅官方风格的 WebSocket JSON-RPC）

- 仅提供 /ws WebSocket 端点：ping、tools/list、tools/register、tools/execute
- 仅保留 /health 简易健康检查
"""

import logging
import threading
import time
from typing import Dict, List, Optional, Any
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ToolDefinition(BaseModel):
    """工具定义（近似 MCP 工具声明）"""
    name: str
    description: str
    parameters: Dict
    response_schema: Dict
    endpoint: Optional[str] = None
    method: Optional[str] = None

# HTTP 执行/注册相关的数据模型已移除，仅保留 WS 使用的 ToolDefinition

class MCPServer:
    """MCP Server实现"""
    
    def __init__(self, host: str = "localhost", port: int = 8004):
        self.host = host
        self.port = port
        self.app = FastAPI(title="MCP Server", version="1.0.0")
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.active_ws: List[WebSocket] = []
        self._uvicorn_server = None
        self._thread: Optional[threading.Thread] = None
        self._setup_routes()
    
    def _setup_routes(self):
        """仅设置 /health 与 /ws"""
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "service": "mcp_server"}

        @self.app.websocket("/ws")
        async def ws_endpoint(ws: WebSocket):
            await ws.accept()
            self.active_ws.append(ws)
            try:
                while True:
                    data = await ws.receive_json()
                    rpc_id = data.get("id")
                    method = data.get("method")
                    params = data.get("params") or {}
                    try:
                        if method == "ping":
                            result = {"pong": True}
                        elif method == "tools/list":
                            result = {"tools": list(self.registered_tools.keys())}
                        elif method == "tools/register":
                            tool = ToolDefinition(**params)
                            self.registered_tools[tool.name] = tool.dict()
                            result = {"success": True, "tool_id": tool.name}
                        elif method == "tools/execute":
                            tool_name = params.get("tool_name")
                            parameters = params.get("parameters", {})
                            if tool_name not in self.registered_tools:
                                raise HTTPException(status_code=404, detail="Tool not found")
                            tool = self.registered_tools[tool_name]
                            exec_result = await self._execute_tool_internal(tool, parameters)
                            result = {"success": True, "result": exec_result}
                        else:
                            raise ValueError(f"Unknown method: {method}")
                        await ws.send_json({"jsonrpc": "2.0", "id": rpc_id, "result": result})
                    except HTTPException as he:
                        await ws.send_json({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": he.status_code, "message": he.detail}})
                    except Exception as e:
                        await ws.send_json({"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32000, "message": str(e)}})
            except WebSocketDisconnect:
                pass
            finally:
                if ws in self.active_ws:
                    self.active_ws.remove(ws)
    
    async def _execute_tool_internal(self, tool: Dict, parameters: Dict) -> Dict:
        # 这里可以：根据 endpoint/method 代理到后端系统；或调用内部实现
        # 先保留最小回声返回，确保端到端连通
        return {"tool_name": tool.get("name"), "parameters": parameters, "result": "success"}
    
    async def start(self) -> bool:
        """启动 MCP Server（后台线程运行 uvicorn），并进行健康检查。"""
        try:
            import uvicorn
            logger.info(f"Starting MCP Server on {self.host}:{self.port}")
            config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
            self._uvicorn_server = uvicorn.Server(config)

            def _run():
                try:
                    self._uvicorn_server.run()
                except Exception as e:  # pragma: no cover
                    logger.error("Uvicorn run error: %s", e)

            self._thread = threading.Thread(target=_run, name="mcp-uvicorn", daemon=True)
            self._thread.start()

            # 健康检查：HTTP /health
            deadline = time.time() + 10.0
            while time.time() < deadline:
                try:
                    with httpx.Client(timeout=0.5) as client:
                        resp = client.get(f"http://{self.host}:{self.port}/health")
                        if resp.status_code == 200:
                            logger.info("MCP Server READY")
                            return True
                except Exception:
                    pass
                time.sleep(0.2)
            logger.error("MCP Server failed to become ready in time")
            return False
        except Exception as e:
            logger.error(f"Failed to start MCP Server: {e}")
            return False
    
    async def stop(self):
        """停止MCP Server（通知 uvicorn 退出并等待线程结束）。"""
        logger.info("Stopping MCP Server")
        try:
            if self._uvicorn_server is not None:
                self._uvicorn_server.should_exit = True
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=2.0)
        finally:
            logger.info("MCP Server stopped")
    
    async def register_tool(self, tool_definition: Dict):
        """注册工具"""
        tool = ToolDefinition(**tool_definition)
        self.registered_tools[tool.name] = tool.dict()
        logger.info(f"Registered tool: {tool.name}")
    
    async def execute_tool(self, tool_name: str, parameters: Dict) -> Dict:
        """执行工具"""
        if tool_name not in self.registered_tools:
            raise ValueError(f"Tool {tool_name} not found")
        
        tool = self.registered_tools[tool_name]
        return await self._execute_tool_internal(tool, parameters)
