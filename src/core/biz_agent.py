"""
Biz Agent模块

负责根据 apps 配置初始化 BizAgent，注册到 A2A，并通过 MCP 调用工具。
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from ..infrastructure.adk_integration import AgentRuntime
from ..infrastructure.mcp_server import MCPServer
from ..infrastructure.a2a_server import A2AServer
import os
import yaml

logger = logging.getLogger(__name__)

@dataclass
class BizAgentConfig:
    """BizAgent 配置"""
    agent_id: str
    agent_name: str
    system_context: str
    allowed_tools: List[str]
    mcp_tools: List[Dict]

class BizAgent:
    """业务代理"""
    
    def __init__(self, config: BizAgentConfig, adk_integration: AgentRuntime):
        self.config = config
        self.adk_integration = adk_integration
        self.agent = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """初始化Agent"""
        try:
            # 将 apps 配置的工具声明传递给运行时，便于函数调用（tool calling）
            tool_schemas = {}
            for td in (self.config.mcp_tools or []):
                name = td.get("name")
                if not name:
                    continue
                tool_schemas[name] = td
            self.agent = self.adk_integration.create_react_agent({
                "system_prompt": self.config.system_context,
                "tools": self.config.allowed_tools,
                "agent_id": self.config.agent_id,
                "tool_schemas": tool_schemas,
                "model": "gemini-pro"
            })
            logger.info(f"Initialized agent {self.config.agent_id}")
        except Exception as e:
            logger.error(f"Failed to initialize agent {self.config.agent_id}: {e}")
            raise
    
    async def execute(self, prompt: str, context: Dict) -> Dict:
        """执行Agent任务"""
        try:
            logger.info(f"Executing agent {self.config.agent_id} with prompt: {prompt[:100]}...")
            full_context = self._build_full_context(prompt, context)
            result = await self.agent.execute(full_context)
            return self._process_result(result)
        except Exception as e:
            logger.error(f"Error executing agent {self.config.agent_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_full_context(self, prompt: str, context: Dict) -> str:
        context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
        return f"""
{prompt}

上下文信息：
{context_str}

请根据上述信息和上下文执行相应的操作。
"""
    
    def _process_result(self, result) -> Dict:
        return {
            "success": True,
            "result": result,
            "timestamp": None
        }

class BizAgentManager:
    """BizAgent 管理器"""
    
    def __init__(self, mcp_server: MCPServer, a2a_server: A2AServer, adk_integration: AgentRuntime):
        self.mcp_server = mcp_server
        self.a2a_server = a2a_server
        self.adk_integration = adk_integration
        self.agents = {}
        self._initialize_agents()
    
    def _initialize_agents(self):
        """根据 config/apps 目录的配置动态初始化所有 BizAgent。"""
        apps_dir = os.path.join("config", "apps")
        if not os.path.isdir(apps_dir):
            logger.warning("Apps directory not found: %s", apps_dir)
            return

        def _load_app_config(path: str) -> dict:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error("Failed to load app config %s: %s", path, e)
                return {}

        for fname in os.listdir(apps_dir):
            if not (fname.endswith(".yaml") or fname.endswith(".yml")):
                continue
            path = os.path.join(apps_dir, fname)
            app_cfg = _load_app_config(path)
            if not app_cfg:
                continue

            app_name = (app_cfg.get("name") or os.path.splitext(fname)[0]).strip()
            tools = app_cfg.get("tools") or []
            tool_names = [t.get("name") for t in tools if t.get("name")]

            agent_id = f"{app_name}_agent_v1"
            agent_name = f"{app_name}系统代理"
            system_context = app_cfg.get(
                "system_context",
                f"你是一个{app_name}系统的专业代理，负责处理{app_name}相关的所有操作",
            )

            config = BizAgentConfig(
                agent_id=agent_id,
                agent_name=agent_name,
                system_context=system_context,
                allowed_tools=tool_names,
                mcp_tools=tools,
            )

            try:
                agent = BizAgent(config, self.adk_integration)
                self.agents[config.agent_id] = agent
                logger.info("Registered agent %s from %s", config.agent_id, fname)
            except Exception as e:
                logger.error("Failed to register agent %s: %s", config.agent_id, e)
    
    async def execute_agent(self, agent_id: str, prompt: str, context: Dict) -> Dict:
        try:
            if agent_id not in self.agents:
                raise ValueError(f"Agent {agent_id} not found")
            agent = self.agents[agent_id]
            return await agent.execute(prompt, context)
        except Exception as e:
            logger.error(f"Error executing agent {agent_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def register_external_agent(self, agent_card: Dict):
        try:
            await self.a2a_server.register_agent(agent_card)
            logger.info(f"Registered external agent {agent_card.get('agent_id')}")
        except Exception as e:
            logger.error(f"Failed to register external agent: {e}")
            raise
    
    async def discover_agents(self) -> List[Dict]:
        try:
            return await self.a2a_server.discover_agents()
        except Exception as e:
            logger.error(f"Failed to discover agents: {e}")
            return []

class BizAgentModule:
    """Biz Agent模块主类"""
    
    def __init__(self, mcp_server: MCPServer, a2a_server: A2AServer, adk_integration: AgentRuntime):
        self.mcp_server = mcp_server
        self.a2a_server = a2a_server
        self.adk_integration = adk_integration
        self.agent_manager = BizAgentManager(mcp_server, a2a_server, adk_integration)
    
    async def start(self):
        """启动 BizAgent 模块"""
        try:
            await self.mcp_server.start()
            await self.a2a_server.start()
            await self._register_all_agents()
            logger.info("BizAgent Module started")
        except Exception as e:
            logger.error(f"Failed to start BizAgent Module: {e}")
            raise
    
    async def stop(self):
        """停止 BizAgent 模块"""
        try:
            await self.mcp_server.stop()
            await self.a2a_server.stop()
            logger.info("BizAgent Module stopped")
        except Exception as e:
            logger.error(f"Error stopping BizAgent Module: {e}")
    
    async def _register_all_agents(self):
        """注册所有Agent到A2A Server"""
        for agent_id, agent in self.agent_manager.agents.items():
            agent_card = {
                "agent_id": agent_id,
                "agent_name": agent.config.agent_name,
                "provider": "internal",
                "version": "1.0.0",
                "capabilities": agent.config.allowed_tools,
                "endpoints": {
                    "execute": f"/agents/{agent_id}/execute"
                }
            }
            await self.a2a_server.register_agent(agent_card)


