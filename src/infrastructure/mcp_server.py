"""
MCP Server（使用官方 FastMCP）

基于官方 fastmcp.FastMCP 实现的简单 MCP 服务器
"""

import logging
from typing import Dict, Any
from fastmcp import FastMCP
import os
import yaml
import httpx

logger = logging.getLogger(__name__)

class MCPServer:
    """MCP Server实现（基于官方 FastMCP）"""
    
    def __init__(self, host: str = "localhost", port: int = 8004):
        self.host = host
        self.port = port
        self.server = FastMCP("AIntegration MCP Server")
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self._setup_tools()
    
    def _setup_tools(self):
        """设置默认工具"""
        @self.server.tool()
        def call_tool(endpoint: str, tool: str = "", args: dict | None = None) -> str:
            """统一转发工具：将调用转发到指定 endpoint。

            - endpoint: 目标API地址，支持占位符 ${VAR:default}
            - tool: 可选，传递工具名给下游API做审计/记录
            - args: 传递的参数对象
            """
            def _resolve_env_placeholders(value: str) -> str:
                import re, os as _os
                def repl(m):
                    var, default = m.group(1), m.group(2) or ""
                    return _os.getenv(var, default)
                return re.sub(r"\$\{([^:}]+):?([^}]*)\}", repl, value)

            try:
                resolved = _resolve_env_placeholders(endpoint)
                payload = {"tool": tool, "args": args or {}}
                resp = httpx.post(resolved, json=payload, timeout=15)
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError as e:
                logger.error("call_tool HTTP %s: %s", e.response.status_code, e.response.text)
                return f"HTTP {e.response.status_code}: {e.response.text}"
            except Exception as e:
                logger.error("call_tool failed: %s", e)
                return f"Error: {e}"
    
    def register_tool(self, tool_definition: Dict) -> Dict[str, Any]:
        """动态注册工具到FastMCP服务器"""
        tool_name = tool_definition.get("name")
        if not tool_name:
            return {"success": False, "error": "No tool name provided"}
        
        try:
            # 解析并固化 endpoint（支持 ${VAR:default}）
            endpoint = tool_definition.get("endpoint")
            if isinstance(endpoint, str) and endpoint:
                import re
                def repl(m):
                    var, default = m.group(1), m.group(2) or ""
                    return os.getenv(var, default)
                endpoint = re.sub(r"\$\{([^:}]+):?([^}]*)\}", repl, endpoint)
                tool_definition["endpoint"] = endpoint

            # 仅存储工具元数据，实际执行统一通过 call_tool
            self.registered_tools[tool_name] = tool_definition
            logger.info("Registered tool metadata only: %s", tool_name)
            return {"success": True, "message": f"Tool {tool_name} metadata stored"}
            
        except Exception as e:
            logger.error(f"Failed to register tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}

    def load_tools_from_directory(self, directory: str = "config/apps") -> Dict[str, Any]:
        """从目录加载所有应用工具配置，并注册工具。

        期望文件格式（YAML/JSON）：
        name: <app_name>
        tools:
          - name: <tool_name>
            description: <desc>
            parameters: { ... JSON Schema ... }
        """
        loaded: int = 0
        errors: Dict[str, str] = {}
        if not os.path.isdir(directory):
            return {"success": False, "error": f"Directory not found: {directory}"}
        for fname in os.listdir(directory):
            if not (fname.endswith(".yaml") or fname.endswith(".yml") or fname.endswith(".json")):
                continue
            path = os.path.join(directory, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                app_name = data.get("name") or os.path.splitext(fname)[0]
                for td in (data.get("tools") or []):
                    # 将工具名命名空间化：<app>.<tool>，避免跨应用冲突
                    tname = td.get("name")
                    if not tname:
                        continue
                    namespaced = dict(td)
                    namespaced["name"] = f"{app_name}.{tname}"
                    res = self.register_tool(td)
                    if res.get("success"):
                        loaded += 1
                    else:
                        errors[td.get("name", "<unknown>")] = res.get("error", "unknown error")
            except Exception as e:
                errors[fname] = str(e)
        return {"success": True, "loaded": loaded, "errors": errors}
    
    async def start(self):
        """异步启动（后台任务方式）"""
        import asyncio
        if getattr(self, "_bg_task", None):
            return
        self._bg_task = asyncio.create_task(self.run_async())
        await asyncio.sleep(0.1)

    async def stop(self):
        """异步停止（取消后台任务）"""
        task = getattr(self, "_bg_task", None)
        if task:
            task.cancel()
            try:
                await task
            except Exception:
                pass
            self._bg_task = None

    def run(self):
        """运行服务器（同步方法）"""
        logger.info(f"Running MCP Server on {self.host}:{self.port}")
        # 使用Streamable HTTP传输
        self.server.run(transport="streamable-http", host=self.host, port=self.port)
    
    async def run_async(self):
        """运行服务器（异步方法）"""
        logger.info(f"Running MCP Server on {self.host}:{self.port}")
        # 使用FastMCP的HTTP异步运行方法
        try:
            await self.server.run_http_async(host=self.host, port=self.port)
        except OSError as e:
            logger.error("MCP server bind error: %s", e)
            # 测试环境端口占用时，直接抛出由上层处理
            raise