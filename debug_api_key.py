#!/usr/bin/env python3
"""
调试API密钥加载过程
"""
import os
from dotenv import load_dotenv
from config.config_loader import ConfigLoader

def debug_api_key_loading():
    print("=== 调试API密钥加载过程 ===")
    
    # 1. 检查环境变量
    print(f"1. 直接检查环境变量 DEEPSEEK_API_KEY: {os.getenv('DEEPSEEK_API_KEY')}")
    
    # 2. 检查.env文件
    print(f"2. 检查.env文件是否存在: {os.path.exists('.env')}")
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            content = f.read()
            print(f"   .env文件内容:")
            for line in content.split('\n'):
                if 'DEEPSEEK' in line:
                    print(f"   {line}")
    
    # 3. 加载.env文件
    print("3. 加载.env文件...")
    load_dotenv()
    print(f"   加载后 DEEPSEEK_API_KEY: {os.getenv('DEEPSEEK_API_KEY')}")
    
    # 3.1 强制覆盖加载.env文件
    print("3.1 强制覆盖加载.env文件...")
    load_dotenv(override=True)
    print(f"   强制覆盖后 DEEPSEEK_API_KEY: {os.getenv('DEEPSEEK_API_KEY')}")
    
    # 4. 使用ConfigLoader
    print("4. 使用ConfigLoader加载配置...")
    config_loader = ConfigLoader('config/development.yaml')
    deepseek_config = config_loader.get('deepseek')
    print(f"   deepseek配置: {deepseek_config}")
    
    if deepseek_config and 'api_key' in deepseek_config:
        print(f"   api_key值: {deepseek_config['api_key']}")
        print(f"   api_key类型: {type(deepseek_config['api_key'])}")
        print(f"   api_key长度: {len(deepseek_config['api_key']) if deepseek_config['api_key'] else 0}")
    
    # 5. 检查所有环境变量
    print("5. 检查所有包含DEEPSEEK的环境变量:")
    for key, value in os.environ.items():
        if 'DEEPSEEK' in key.upper():
            print(f"   {key}: {value}")

if __name__ == "__main__":
    debug_api_key_loading()
