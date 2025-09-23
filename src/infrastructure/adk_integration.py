"""
Google ADK集成

Agent开发框架集成
"""
import os
import logging
from typing import Dict, List, Optional, Any, Callable
from config import config_loader
from .llm_client import build_llm_client
from .mcp_client import MCPClient
logger = logging.getLogger(__name__)

class ReactAgent:
    """ReAct智能体实现"""
    
    def __init__(self, 
                 system_prompt: str, 
                 tools: List[str], 
                 model: str = "gemini-pro",
                 tool_registry: Optional[Dict[str, Callable[..., Any]]] = None,
                 tool_schemas: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model = model
        self.tool_registry = tool_registry or {}
        # 可选：Google ADK 原生函数声明（JSON Schema）。键为工具名，值为 function_declaration 结构
        self.tool_schemas = tool_schemas or {}
        self.conversation_history = []
        # 最大工具调用步数（从配置读取，默认3）
        try:
            self.max_steps = int(config_loader.get("google_adk.max_steps", 3))
        except Exception:
            self.max_steps = 3
        # 构建 LLM 客户端（可插拔 provider）
        self.llm = self._initialize_llm_client()
        self.mcp = MCPClient()
        # 预构建工具声明（若提供）
        self._tools_declarations = self._build_tool_declarations()
    
    def _initialize_llm_client(self):
        """根据配置初始化可插拔 LLM 客户端。"""
        provider = config_loader.get("llm.provider", "google")
        model_name = self.model or config_loader.get("llm.model")
        llm = build_llm_client(provider=provider, model_name=model_name)
        logger.info("ReactAgent 使用 provider=%s, model=%s", provider, model_name)
        return llm

    

    def _build_tool_declarations(self) -> Optional[List[Dict[str, Any]]]:
        """将提供的 tool_schemas 转为 Gemini tools 结构。
        期望的每个 schema 形如：
        {
          "name": "tool_name",
          "description": "...",
          "parameters": { ...json schema... }
        }
        返回格式：[{"function_declarations": [schema1, schema2, ...]}]
        若无有效 schema，返回 None。
        """
        try:
            declarations: List[Dict[str, Any]] = []
            for tool_name in self.tools:
                schema = self.tool_schemas.get(tool_name)
                if not schema:
                    continue
                # 最少需要 name
                if "name" not in schema:
                    schema = {"name": tool_name, **schema}
                declarations.append(schema)
            if not declarations:
                return None
            return [{"function_declarations": declarations}]
        except Exception as e:
            logger.debug("Failed to build tool declarations: %s", e)
            return None

    async def execute(self, context: str) -> Dict:
        """执行Agent任务"""
        try:
            # 工具循环（最多 max_steps）
            running_summary = []
            cur_prompt = self._build_full_prompt(context)

            for step_index in range(self.max_steps):
                # 让模型先提议是否需要调用工具
                proposed = await self.llm.propose_tool_call(cur_prompt, tools=self._tools_declarations)
                if not proposed:
                    # 无函数调用建议，直接生成最终回答
                    final_text = await self._generate_response(cur_prompt)
                    result = self._process_response(final_text)
                    break

                tool_name = proposed.get("name")
                tool_args = proposed.get("arguments", {})
                # 统一通过 MCP 执行
                tool_output = await self.mcp.execute_tool(tool_name, tool_args)

                running_summary.append({"step": step_index + 1, "action": tool_name, "args": tool_args, "output": tool_output})

                # 将工具输出拼接进后续提示，继续下一轮
                cur_prompt = f"{cur_prompt}\n\n[工具调用结果 step={step_index+1} tool={tool_name}]\n{tool_output}"
            else:
                # 达到最大步数后，生成总结
                final_text = await self._generate_response(cur_prompt)
                result = self._process_response(final_text)
            
            # 记录对话历史
            self.conversation_history.append({
                "context": context,
                "response": result.get("response"),
                "result": result,
                "trace": running_summary,
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing ReactAgent: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_full_prompt(self, context: str) -> str:
        """构建完整的提示"""
        tools_description = "\n".join([f"- {tool}" for tool in self.tools])
        
        return f"""
{self.system_prompt}

可用工具：
{tools_description}

请根据以下上下文执行任务：

{context}

请按照以下格式响应：
1. 思考：分析当前情况
2. 行动：选择合适的工具和参数
3. 观察：分析行动结果
4. 结论：总结执行结果

请开始执行：
"""
    
    async def _generate_response(self, prompt: str) -> str:
        """生成响应"""
        # 纯 Gemini 路径

        # 调用 Gemini：若有 tools 声明，传入以启用原生函数调用提示（单轮）。
        tools_kw = self._tools_declarations if self._tools_declarations else None
        text = await self.llm.generate(prompt, tools=tools_kw)
        return text
    
    def _process_response(self, response: str) -> Dict:
        """处理响应"""
        # 解析响应，提取工具调用和结果
        # 简化实现，实际需要更复杂的解析逻辑
        return {
            "success": True,
            "response": response,
            "tools_used": self._extract_tools_used(response),
            "result": self._extract_result(response)
        }
    
    def _extract_tools_used(self, response: str) -> List[str]:
        """提取使用的工具"""
        # 简化实现，从响应中提取工具名称
        tools_used = []
        for tool in self.tools:
            if tool in response:
                tools_used.append(tool)
        return tools_used
    
    def _extract_result(self, response: str) -> str:
        """提取执行结果"""
        # 简化实现，返回最后一部分作为结果
        lines = response.strip().split('\n')
        if lines:
            return lines[-1]
        return "执行完成"

class ADKIntegration:
    """Google ADK集成"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.agents = {}
        self._initialize_adk()
    
    def _initialize_adk(self):
        """初始化ADK"""
        logger.info("ADK container initialized (provider via LLMClient)")
    
    def create_react_agent(self, config: Dict) -> ReactAgent:
        """创建ReAct Agent"""
        try:
            agent = ReactAgent(
                system_prompt=config["system_prompt"],
                tools=config["tools"],
                model=config.get("model", "gemini-pro"),
                tool_registry=config.get("tool_registry", {}),
                tool_schemas=config.get("tool_schemas", {}),
            )
            
            agent_id = config.get("agent_id", f"agent_{len(self.agents)}")
            self.agents[agent_id] = agent
            
            logger.info(f"Created ReactAgent: {agent_id}")
            return agent
            
        except Exception as e:
            logger.error(f"Failed to create ReactAgent: {e}")
            raise
    
    def get_agent(self, agent_id: str) -> Optional[ReactAgent]:
        """获取Agent"""
        return self.agents.get(agent_id)
    
    def list_agents(self) -> List[str]:
        """列出所有Agent"""
        return list(self.agents.keys())
    
    async def execute_agent(self, agent_id: str, context: str) -> Dict:
        """执行Agent"""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        return await agent.execute(context)
