"""
Agent 执行运行时（统一封装 LLM 与 MCP 调用）

原 adk_integration 更名为 agent_runtime：抽象一个通用 AgentRuntime
供 BizAgent 使用来创建 ReAct 风格的执行器。
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from config.config_loader import config_loader
from .llm_client import build_llm_client
from .mcp_client import MCPClient
logger = logging.getLogger(__name__)

class ReactAgent:
    """ReAct智能体实现"""
    
    def __init__(self, 
                 system_prompt: str, 
                 tools: Optional[List[str]] = None,
                 tool_registry: Optional[Dict[str, Callable[..., Any]]] = None,
                 tool_schemas: Optional[Dict[str, Dict[str, Any]]] = None,
                 app_name: Optional[str] = None,
    ):
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.tool_registry = tool_registry or {}
        self.tool_schemas: Dict[str, Dict[str, Any]] = tool_schemas or {}
        self.app_name = app_name
        self.conversation_history = []
        # 工具循环最大步数
        try:
            self.max_steps = int(config_loader.get("google_adk.max_steps", 3))
        except Exception:
            self.max_steps = 3
        # 可插拔 LLM 与 MCP 客户端
        self.llm = build_llm_client(
            provider=config_loader.get("llm.provider"),
            model_name= config_loader.get("llm.model")
        )
        self.mcp = MCPClient()
        # 如果提供 app_name，则从 config/apps/<app_name>.yaml 加载工具 schema
        if self.app_name and not self.tool_schemas:
            try:
                import os, yaml
                cfg_path = os.path.join("config", "apps", f"{self.app_name}.yaml")
                with open(cfg_path, "r", encoding="utf-8") as f:
                    app_cfg = yaml.safe_load(f) or {}
                tools_list = app_cfg.get("tools") or []
                for td in tools_list:
                    name = td.get("name")
                    if not name:
                        continue
                    self.tool_schemas[name] = td
                    if name not in self.tools:
                        self.tools.append(name)
            except Exception as e:
                logger.warning("加载应用工具失败 app=%s: %s", self.app_name, e)

        # 工具声明（用于 function calling 提示）
        self._tools_declarations = self._build_tool_declarations()
        # 移除直连 Google 模型，统一通过 llm_client 调用

    # LangChain 相关逻辑已移除

    async def execute(self, context: str) -> Dict:
        """执行Agent任务"""
        try:
            # 工具循环 + 最终回答
            running_summary: List[Dict[str, Any]] = []
            cur_prompt = self._build_full_prompt(context)
            # 工具失败自动重试次数（通用，不特化工具）
            try:
                self.max_retries = int(config_loader.get("google_adk.max_tool_retries", 3))
            except Exception:
                self.max_retries = 3

            for step_index in range(self.max_steps):
                logger.debug("[Agent] step=%d prompt(head)=%r", step_index+1, cur_prompt[:300])
                print(f"[ReactAgent] 步骤 {step_index+1}: 开始调用 propose_tool_call")
                print(f"[ReactAgent] 步骤 {step_index+1}: LLM调用前，prompt长度={len(cur_prompt)}")
                proposed = await self.llm.propose_tool_call(cur_prompt, tools=self._tools_declarations)
                print(f"[ReactAgent] 步骤 {step_index+1}: LLM已调用，propose_tool_call 完成，结果: {proposed}")
                if not proposed:
                    print(f"[ReactAgent] 步骤 {step_index+1}: LLM返回None，未建议工具调用")
                    print(f"[ReactAgent] 当前prompt内容: {cur_prompt[:500]}...")
                    
                    # 保存完整prompt到文件用于调试
                    import os
                    from datetime import datetime
                    debug_dir = "tests/.artifacts"
                    os.makedirs(debug_dir, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    prompt_file = f"{debug_dir}/llm_none_prompt_{timestamp}.txt"
                    with open(prompt_file, 'w', encoding='utf-8') as f:
                        f.write(f"=== LLM返回None时的完整Prompt ===\n")
                        f.write(f"时间: {datetime.now().isoformat()}\n")
                        f.write(f"步骤: {step_index+1}\n\n")
                        f.write(cur_prompt)
                    print(f"[ReactAgent] 完整prompt已保存到: {prompt_file}")
                    
                    # 容错：从提示词中提取 '使用xxx工具' 作为工具名，进行一次直接调用
                    import re
                    m = re.search(r"使用\s*([A-Za-z0-9_\-]+)\s*工具", cur_prompt)
                    if m:
                        tool_name = m.group(1)
                        tool_args = {}
                        print(f"[ReactAgent] 未获得建议，容错直接调用解析到的工具: {tool_name}")
                        schema = self.tool_schemas.get(tool_name, {})
                        endpoint = schema.get("endpoint")
                        if isinstance(endpoint, str):
                            import os
                            def _repl(m2):
                                var, default = m2.group(1), m2.group(2) or ""
                                return os.getenv(var, default)
                            endpoint = re.sub(r"\$\{([^:}]+):?([^}]*)\}", _repl, endpoint)
                        call_params = {
                            "endpoint": endpoint or "",
                            "tool": tool_name,
                            "args": tool_args,
                        }
                        last_error = None
                        tool_output = None
                        for attempt in range(1, self.max_retries + 1):
                            exec_result = await self.mcp.execute_tool("call_tool", call_params)
                            if exec_result and exec_result.get("success"):
                                tool_output = exec_result
                                break
                            last_error = (exec_result or {}).get("error") or "unknown error"
                            logger.warning("[Agent] tool '%s' failed attempt %d/%d: %s", tool_name, attempt, self.max_retries, last_error)
                        if tool_output is None:
                            running_summary.append({
                                "step": step_index + 1,
                                "action": tool_name,
                                "args": tool_args,
                                "output": {"success": False, "error": last_error},
                            })
                            return {"success": False, "error": f"Tool '{tool_name}' failed after {self.max_retries} attempts: {last_error}"}
                        logger.debug("[Agent] (fallback) tool_output(head)=%r", (str(tool_output) or "")[:300])
                        running_summary.append({
                            "step": step_index + 1,
                            "action": tool_name,
                            "args": tool_args,
                            "output": tool_output,
                        })
                        cur_prompt = (
                            f"{cur_prompt}\n\n[工具调用结果 step={step_index+1} tool={tool_name}]\n"
                            f"{tool_output}\n\n请基于以上结果给出最终答复。"
                        )
                        print(f"[ReactAgent] (fallback) 工具调用成功，重新组合提示词，准备调用 LLM 生成最终答复")
                        final_text = await self.llm.generate(cur_prompt, tools=self._tools_declarations)
                        print(f"[ReactAgent] (fallback) LLM 生成完成，结果: {final_text[:200] if final_text else 'None'}...")
                        logger.debug("[Agent] final_text(head)=%r", (final_text or "")[:300])
                        result = self._process_response(final_text)
                        break
                    else:
                        logger.debug("[Agent] no tool proposed; stop without tool call")
                        print(f"[ReactAgent] 步骤 {step_index+1}: 没有工具建议，调用 generate 生成最终答复")
                        final_text = await self.llm.generate(cur_prompt, tools=self._tools_declarations)
                        print(f"[ReactAgent] 步骤 {step_index+1}: generate 完成，结果: {final_text[:200] if final_text else 'None'}...")
                        logger.debug("[Agent] final_text(head)=%r", (final_text or "")[:300])
                        result = self._process_response(final_text)
                        break
                tool_name = proposed.get("name")
                tool_args = proposed.get("arguments", {})

                # 强制遵循 action_prompt 中的“使用X工具”指示，覆盖 LLM 提议
                try:
                    import re
                    m_force = re.search(r"使用\s*([A-Za-z0-9_\-]+)\s*工具", cur_prompt)
                    if m_force:
                        forced_tool = m_force.group(1)
                        if forced_tool:
                            tool_name = forced_tool
                            # 若无参数则给空对象，保证能直连 Mock API 记录日志
                            if not isinstance(tool_args, dict):
                                tool_args = {}
                except Exception:
                    pass
                logger.debug("[Agent] proposed tool=%s args=%s", tool_name, tool_args)

                # 统一通过 call_tool 转发，endpoint 来自 schema
                schema = self.tool_schemas.get(tool_name, {})
                endpoint = schema.get("endpoint")
                if isinstance(endpoint, str):
                    # 解析 ${VAR:default}
                    import re, os
                    def _repl(m):
                        var, default = m.group(1), m.group(2) or ""
                        return os.getenv(var, default)
                    endpoint = re.sub(r"\$\{([^:}]+):?([^}]*)\}", _repl, endpoint)

                call_params = {
                    "endpoint": endpoint or "",
                    "tool": tool_name,
                    "args": tool_args or {},
                }
                # 通用重试：仅在失败时重试，成功即收敛
                last_error: Optional[str] = None
                tool_output: Any = None
                print(f"[ReactAgent] 准备循环调用工具 {tool_name}，max_retries={self.max_retries}")
                for attempt in range(1, self.max_retries + 1):
                    print(f"[ReactAgent] 工具调用循环 attempt {attempt}/{self.max_retries}")
                    exec_result = await self.mcp.execute_tool("call_tool", call_params)
                    print(f"[ReactAgent] MCP返回结果: {exec_result}")
                    
                    # 检查内层result.success（Mock API的真实结果）
                    inner_result = exec_result.get("output", {}).get("result", {}) if exec_result else {}
                    inner_success = inner_result.get("success", False) if isinstance(inner_result, dict) else False
                    print(f"[ReactAgent] 内层result.success={inner_success}")
                    
                    if exec_result and inner_success:
                        tool_output = exec_result
                        print(f"[ReactAgent] 工具调用成功（内层检查），跳出循环")
                        break
                    
                    # 提取错误信息（可能在内层result）
                    last_error = inner_result.get("error") if isinstance(inner_result, dict) else (exec_result or {}).get("error", "unknown error")
                    print(f"[ReactAgent] 工具调用失败，error={last_error}")
                    logger.warning("[Agent] tool '%s' failed attempt %d/%d: %s", tool_name, attempt, self.max_retries, last_error)
                if tool_output is None:
                    # 多次失败后返回错误
                    running_summary.append({
                        "step": step_index + 1,
                        "action": tool_name,
                        "args": tool_args,
                        "output": {"success": False, "error": last_error},
                    })
                    return {"success": False, "error": f"Tool '{tool_name}' failed after {self.max_retries} attempts: {last_error}"}

                logger.debug("[Agent] tool_output(head)=%r", (str(tool_output) or "")[:300])
                running_summary.append({
                    "step": step_index + 1,
                    "action": tool_name,
                    "args": tool_args,
                    "output": tool_output,
                })
                # 成功一次后收敛
                cur_prompt = (
                    f"{cur_prompt}\n\n[工具调用结果 step={step_index+1} tool={tool_name}]\n"
                    f"{tool_output}\n\n请基于以上结果给出最终答复。"
                )
                print(f"[ReactAgent] 工具调用成功，重新组合提示词，准备调用 LLM 生成最终答复")
                print(f"[ReactAgent] 重新组合的提示词: {cur_prompt[:200]}...")
                
                final_text = await self.llm.generate(cur_prompt, tools=self._tools_declarations)
                print(f"[ReactAgent] LLM 生成完成，结果: {final_text[:200] if final_text else 'None'}...")
                
                logger.debug("[Agent] final_text(head)=%r", (final_text or "")[:300])
                result = self._process_response(final_text)
                print(f"[ReactAgent] 处理响应完成，最终结果: {result}")
                break
            else:
                # 达到步数上限后给出总结
                final_text = await self.llm.generate(cur_prompt, tools=self._tools_declarations)
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
        """生成响应：统一通过 llm_client 生成。"""
        return await self.llm.generate(prompt, tools=self._tools_declarations)

    def _build_tool_declarations(self) -> Optional[List[Dict[str, Any]]]:
        """将 tool_schemas 转换为 LLM 可理解的 function_declarations 列表包装。
        返回格式：[{"function_declarations": [schema...]}] 或 None
        """
        try:
            decls: List[Dict[str, Any]] = []
            for name in self.tools:
                schema = self.tool_schemas.get(name)
                if not schema:
                    continue
                if "name" not in schema:
                    schema = {"name": name, **schema}
                decls.append(schema)
            if not decls:
                return None
            return [{"function_declarations": decls}]
        except Exception:
            return None
    
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

class AgentRuntime:
    """Agent 执行运行时（代替 ADKIntegration 名称）"""
    
    def __init__(self, mcp_client_or_api_key):
        # 兼容两种初始化方式：mcp_client对象或api_key字符串
        if isinstance(mcp_client_or_api_key, str):
            self.api_key = mcp_client_or_api_key
            self.mcp_client = None
        else:
            # 传入的是MCPClient对象
            self.mcp_client = mcp_client_or_api_key
            self.api_key = None
        
        self.agents = {}
        self._initialize_adk()
    
    def _initialize_adk(self):
        """初始化运行时（兼容旧 ADK 接口占位）"""
        logger.info("AgentRuntime initialize (using LLM client abstraction)")
    
    def load_agents_from_config(self, config_dir: str = "config/apps"):
        """从config目录加载所有BizAgent"""
        from ..core.agent_config_loader import agent_config_loader
        
        logger.info(f"Loading agents from {config_dir}")
        agent_configs = agent_config_loader.load_all_agents()
        
        for agent_id, agent_config in agent_configs.items():
            try:
                # 创建ReactAgent
                tools = [tool.get("name") for tool in agent_config.get("tools", []) if tool.get("name")]
                tool_schemas = {}
                for tool in agent_config.get("tools", []):
                    if tool.get("name"):
                        tool_schemas[tool["name"]] = tool
                
                react_agent = self.create_react_agent({
                    "agent_id": agent_id,
                    "system_prompt": agent_config.get("system_context", f"你是{agent_id}代理"),
                    "tools": tools,
                    "tool_schemas": tool_schemas
                })
                
                logger.info(f"Loaded agent {agent_id} with {len(tools)} tools: {tools}")
            except Exception as e:
                logger.error(f"Failed to load agent {agent_id}: {e}")
        
        logger.info(f"AgentRuntime loaded {len(self.agents)} agents")
        return len(self.agents)
    
    def create_react_agent(self, config: Dict) -> ReactAgent:
        """创建ReAct Agent"""
        try:
            agent = ReactAgent(
                system_prompt=config["system_prompt"],
                tools=config["tools"],
                tool_registry=config.get("tool_registry", {}),
                tool_schemas=config.get("tool_schemas", {}),
                app_name=config.get("agent_id")
            )
            
            # 如果有mcp_client，设置给agent
            if self.mcp_client:
                agent.mcp_client = self.mcp_client
            
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

    async def execute_agent_with_context(self, agent_id: str, action_prompt: str, plan_context: Dict[str, Any]) -> Dict:
        """携带结构化上下文执行：使用ReactAgent的完整执行流程（包含重试逻辑）。"""
        print(f"[AgentRuntime] execute_agent_with_context 被调用，agent_id={agent_id}")
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        # 统一使用ReactAgent的execute方法，确保重试逻辑生效
        full_context = f"{action_prompt}\n\n上下文信息：{plan_context}"
        print(f"[AgentRuntime] 调用 agent.execute，context长度={len(full_context)}")
        result = await agent.execute(full_context)
        print(f"[AgentRuntime] agent.execute 完成，result keys={list(result.keys()) if isinstance(result, dict) else 'not dict'}")
        return result
