#!/usr/bin/env python3
"""
运行 MCP 服务器（使用官方 FastMCP）
"""

import asyncio
from fastmcp import FastMCP

# 创建MCP服务器
mcp = FastMCP("AIntegration MCP Server")

@mcp.tool()
def verify_tool(message: str) -> str:
    """验证工具，用于测试MCP连接"""
    return f"Verified: {message}"

@mcp.tool()
def greet(name: str) -> str:
    """问候工具"""
    return f"Hello, {name}!"

async def main():
    print("Starting MCP Server...")
    await mcp.run_http_async(host="127.0.0.1", port=8004)

if __name__ == "__main__":
    asyncio.run(main())
