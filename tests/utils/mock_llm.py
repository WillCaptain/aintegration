"""
Mock LLM - 用于测试的模拟大语言模型
快速返回预定义结果，避免真实LLM调用的延迟和不确定性
"""
import re
from typing import Dict, Any, Optional, List


class MockLLM:
    """模拟LLM，用于测试"""
    
    async def propose_tool_call(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, str]]:
        """从prompt中提取工具名，返回工具调用建议"""
        # 提取"使用XXX工具"
        m = re.search(r"使用\s*([A-Za-z0-9_\-]+)\s*工具", prompt)
        if not m:
            return None
        
        tool_name = m.group(1)
        
        # 验证工具是否在可用工具列表中
        if tools:
            # tools格式: [{"function_declarations": [{"name": "xxx", ...}]}]
            available_tools = []
            for tool_group in tools:
                if isinstance(tool_group, dict) and "function_declarations" in tool_group:
                    for func_decl in tool_group["function_declarations"]:
                        if isinstance(func_decl, dict):
                            available_tools.append(func_decl.get("name"))
            
            if tool_name not in available_tools:
                print(f"[MockLLM] 工具{tool_name}不在可用列表{available_tools}中")
                return None
        
        # 从prompt中提取参数
        args = {}
        # 提取{xxx}格式的参数
        param_matches = re.findall(r"\{([^}]+)\}", prompt)
        for param in param_matches:
            if ".id" in param:
                args["emp_id"] = f"{{{param}}}"
            elif ".name" in param:
                args["name"] = f"{{{param}}}"
            elif ".department" in param:
                args["department"] = f"{{{param}}}"
            elif ".pc_model" in param:
                args["pc_model"] = f"{{{param}}}"
        
        print(f"[MockLLM] propose_tool_call返回: tool={tool_name}, args={args}")
        return {"name": tool_name, "arguments": args}
    
    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """生成简单的响应文本"""
        print(f"[MockLLM] generate被调用，prompt长度={len(prompt)}")
        result = "操作已完成。"
        print(f"[MockLLM] generate返回: {result}")
        return result

