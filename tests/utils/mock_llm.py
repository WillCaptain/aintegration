"""
Mock LLM Client for testing
"""
from typing import Dict, List, Optional, Any
from src.infrastructure.llm_client import LLMClient

class MockLLMClient(LLMClient):
    """Mock LLM Client for testing - 总是返回None，触发容错逻辑"""
    
    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """Mock generate - 返回简单文本"""
        return "Mock LLM response"
    
    async def propose_tool_call(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """Mock propose_tool_call - 根据prompt内容智能选择工具"""
        print(f"[MockLLM] propose_tool_call called with prompt length: {len(prompt)}")
        print(f"[MockLLM] Prompt content: {prompt[:200]}...")  # 显示prompt的前200个字符
        if tools:
            tool_names = [tool.get('name') if tool and isinstance(tool, dict) else str(tool) for tool in tools]
            print(f"[MockLLM] Available tools: {tool_names}")
        else:
            print(f"[MockLLM] No tools provided")
        
        # 根据prompt内容智能选择工具
        if tools:
            # 处理ReactAgent传递的工具格式：[{"function_declarations": [schema...]}]
            if isinstance(tools, list) and len(tools) > 0 and isinstance(tools[0], dict) and "function_declarations" in tools[0]:
                tool_names = [tool.get('name') for tool in tools[0]["function_declarations"] if isinstance(tool, dict)]
            else:
                # 处理简单的工具名称列表
                tool_names = [tool.get('name') if tool and isinstance(tool, dict) else str(tool) for tool in tools]
            
            # 根据prompt内容选择工具
            if "创建合同联系人" in prompt or "联系人" in prompt:
                selected_tool = "create_contact"
            elif "基于联系人信息创建合同" in prompt or "创建合同" in prompt:
                selected_tool = "create_contract"
            elif "完成合同签署流程" in prompt or "签署合同" in prompt or "签署" in prompt:
                selected_tool = "sign_contract"
            else:
                # 默认选择第一个可用工具
                selected_tool = tool_names[0] if tool_names else None
            
            if selected_tool and selected_tool in tool_names:
                print(f"[MockLLM] Selected tool: {selected_tool}")
                return {
                    "name": selected_tool,
                    "args": {}
                }
        
        print(f"[MockLLM] No suitable tool found, returning None")
        return None