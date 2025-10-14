#!/usr/bin/env python3
"""
单独测试API密钥获取
"""

import os
import asyncio
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_config_loader():
    """测试config_loader的API密钥获取"""
    from config.config_loader import config_loader
    
    print("=== Config Loader 测试 ===")
    print(f"Environment DEEPSEEK_API_KEY: {repr(os.getenv('DEEPSEEK_API_KEY'))}")
    print(f"Config deepseek.api_key: {repr(config_loader.get('deepseek.api_key'))}")
    print(f"Config LLM provider: {config_loader.get('llm.provider')}")
    print(f"Config LLM model: {config_loader.get('llm.model')}")

def test_llm_client_creation():
    """测试LLM客户端创建"""
    from src.infrastructure.llm_client import build_llm_client
    
    print("\n=== LLM Client 创建测试 ===")
    try:
        client = build_llm_client()
        print(f"Client type: {type(client)}")
        print(f"API Key: {client.api_key[:10] if client.api_key else 'Empty'}...")
        print(f"Base URL: {client.base_url}")
        print(f"Model: {client.model_name}")
        return client
    except Exception as e:
        print(f"Error creating client: {e}")
        return None

async def test_api_call():
    """测试API调用"""
    print("\n=== API 调用测试 ===")
    
    # 直接测试API调用
    import httpx
    import json
    
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("No API key found in environment")
        return
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': 'deepseek-chat',
        'messages': [{'role': 'user', 'content': 'Hello'}],
        'max_tokens': 10
    }
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post('https://api.deepseek.com/v1/chat/completions', 
                                   headers=headers, json=payload)
            print(f'Status: {resp.status_code}')
            if resp.status_code == 200:
                print('API call successful!')
                data = resp.json()
                print(f'Response: {data.get("choices", [{}])[0].get("message", {}).get("content", "")}')
            else:
                print(f'API call failed: {resp.text}')
    except Exception as e:
        print(f'API call error: {e}')

async def test_llm_client_call():
    """测试LLM客户端调用"""
    print("\n=== LLM Client 调用测试 ===")
    
    client = test_llm_client_creation()
    if not client:
        return
    
    try:
        result = await client.propose_tool_call('Hello', [])
        print(f'LLM Client result: {result}')
    except Exception as e:
        print(f'LLM Client error: {e}')

if __name__ == "__main__":
    print("开始API密钥测试...")
    
    # 测试配置加载
    test_config_loader()
    
    # 测试LLM客户端创建
    test_llm_client_creation()
    
    # 测试API调用
    asyncio.run(test_api_call())
    
    # 测试LLM客户端调用
    asyncio.run(test_llm_client_call())
    
    print("\n测试完成!")
