"""
MCP Client（基于FastMCP官方客户端）

使用官方FastMCP客户端，提供简化的接口用于我们的AI集成框架
"""

import logging
from typing import Dict, Any, Optional
from fastmcp import Client
from config.config_loader import config_loader

logger = logging.getLogger(__name__)

class MCPClient:
    """MCP Client实现（基于FastMCP官方客户端）"""
    
    def __init__(self, base_url: Optional[str] = None, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds
        
        if base_url:
            self.base_url = base_url
        else:
            # 从配置读取并解析占位符 ${VAR:default}
            import re, os

            def resolve(val, default=None):
                if val is None:
                    return default
                if isinstance(val, (int, float)):
                    return val
                s = str(val)
                def repl(m):
                    var, d = m.group(1), m.group(2) or ""
                    return os.getenv(var, d)
                return re.sub(r"\$\{([^:}]+):?([^}]*)\}", repl, s)

            host = resolve(config_loader.get("mcp_server.host", "127.0.0.1"), "127.0.0.1")
            port = resolve(config_loader.get("mcp_server.port", 8004), 8004)
            protocol = resolve(config_loader.get("mcp_server.protocol", "http"), "http")

            # 兜底：若解析后仍含占位符，使用本地默认
            if any(isinstance(x, str) and "${" in x for x in [host, str(port), protocol]):
                self.base_url = "http://127.0.0.1:8004/mcp"
            else:
                # 将 ws/wss/sse 归一到 http/https
                proto_lower = str(protocol).lower()
                if proto_lower in ("ws", "wss", "sse"):
                    protocol = "https" if proto_lower == "wss" else "http"
                # 确保协议格式正确
                if not str(protocol).startswith(('http://', 'https://')):
                    protocol = f"{protocol}://"
                self.base_url = f"{protocol}{host}:{port}/mcp"
        
        self._client: Optional[Client] = None
        logger.info(f"MCP Client initialized with URL: {self.base_url}")
    
    async def _ensure_client(self):
        """确保客户端已创建"""
        if self._client is None:
            self._client = Client(self.base_url)
    
    async def ping(self) -> bool:
        """检查MCP服务器连接"""
        try:
            await self._ensure_client()
            async with self._client:
                # 尝试列出工具来检查连接
                await self._client.list_tools()
                return True
        except Exception as e:
            logger.error(f"MCP ping failed: {e}")
            return False
    
    async def register_tool(self, tool_definition: Dict) -> Dict[str, Any]:
        """注册工具（工具已在服务器端预定义，这里只是确认）"""
        try:
            tool_name = tool_definition.get('name')
            logger.info(f"Checking tool availability: {tool_name}")
            
            # 检查工具是否在服务器上可用
            tools_result = await self.list_tools()
            if tools_result.get('success'):
                tools = tools_result.get('tools', [])
                for tool in tools:
                    if tool['name'] == tool_name:
                        logger.info(f"Tool {tool_name} is available on server")
                        return {"success": True, "message": f"Tool {tool_name} is available"}
                
                logger.warning(f"Tool {tool_name} not found on server")
                return {"success": False, "error": f"Tool {tool_name} not found on server"}
            else:
                return {"success": False, "error": "Failed to list tools from server"}
                    
        except Exception as e:
            logger.error(f"Tool registration check failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具"""
        try:
            print(f"[MCPClient] 开始执行工具: {tool_name}, 参数: {parameters}")
            logger.info(f"Executing {tool_name} with parameters: {parameters}")
            
            # 如果是 call_tool，直接调用 Mock API
            if tool_name == "call_tool":
                endpoint = parameters.get("endpoint", "")
                tool = parameters.get("tool", "")
                args = parameters.get("args", {})
                
                if endpoint and tool:
                    print(f"[MCPClient] 直接调用 Mock API: {endpoint}, 工具: {tool}")
                    import httpx
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.post(endpoint, json={
                            "tool": tool,
                            "args": args
                        })
                        response.raise_for_status()
                        result = response.json()
                        print(f"[MCPClient] Mock API 调用成功，结果: {result}")
                        return {
                            "success": True,
                            "output": {
                                "success": True,
                                "result": result,
                                "tool_name": tool
                            }
                        }
            
            # 其他情况使用原来的 MCP 客户端
            await self._ensure_client()
            print(f"[MCPClient] 客户端已确保，开始调用工具")
            
            async with self._client:
                print(f"[MCPClient] 进入客户端上下文，开始 call_tool")
                import asyncio
                try:
                    result = await asyncio.wait_for(
                        self._client.call_tool(tool_name, parameters),
                        timeout=self.timeout_seconds
                    )
                    print(f"[MCPClient] call_tool 完成，结果类型: {type(result)}")
                except asyncio.TimeoutError:
                    print(f"[MCPClient] call_tool 超时，超时时间: {self.timeout_seconds}秒")
                    raise Exception(f"Tool call timeout after {self.timeout_seconds} seconds")
                
                # 提取结果内容
                if hasattr(result, 'content') and result.content:
                    content = result.content[0].text if result.content else str(result)
                elif hasattr(result, 'data'):
                    content = result.data
                else:
                    content = str(result)
                
                print(f"[MCPClient] 工具执行成功，内容: {content[:200]}...")
                logger.info(f"Tool {tool_name} executed successfully")
                return {
                    "success": True,
                    "output": {
                        "success": True,
                        "result": content,
                        "tool_name": tool_name
                    }
                }
        except Exception as e:
            print(f"[MCPClient] 工具执行失败: {e}")
            logger.error(f"Tool execution failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def list_tools(self) -> Dict[str, Any]:
        """列出可用工具"""
        try:
            await self._ensure_client()
            async with self._client:
                tools = await self._client.list_tools()
                logger.info(f"Listed {len(tools)} tools from MCP server")
                return {
                    "success": True,
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                        }
                        for tool in tools
                    ]
                }
        except Exception as e:
            logger.error(f"List tools failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def close(self):
        """关闭MCP会话"""
        if self._client:
            # FastMCP客户端会在async with块中自动关闭
            self._client = None
        logger.info("MCP session closed")