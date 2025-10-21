#!/usr/bin/env python3
"""
直接测试 MCP Client 调用 Mock API
"""
import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath('.'))

from src.infrastructure.mcp_client import MCPClient

async def test_mcp_direct():
    """直接测试 MCP Client 调用"""
    print("=== 直接测试 MCP Client 调用 Mock API ===")
    
    # 创建 MCP Client
    mcp_client = MCPClient("http://127.0.0.1:8009")
    
    # 测试调用 create_contact 工具
    print("\n1. 测试调用 create_contact 工具...")
    result = await mcp_client.execute_tool("call_tool", {
        "endpoint": "http://127.0.0.1:8009/tool",
        "tool": "create_contact",
        "args": {}
    })
    print(f"结果: {result}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    asyncio.run(test_mcp_direct())
