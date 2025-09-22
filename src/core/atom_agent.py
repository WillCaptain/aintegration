"""
Atom Agent模块

负责具体业务逻辑执行，API调用
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from ..infrastructure.adk_integration import ADKIntegration
from ..infrastructure.mcp_server import MCPServer
from ..infrastructure.a2a_server import A2AServer

logger = logging.getLogger(__name__)

@dataclass
class AgentConfig:
    """Agent配置"""
    agent_id: str
    agent_name: str
    system_context: str
    allowed_tools: List[str]
    mcp_tools: List[Dict]

class BizAgent:
    """业务代理"""
    
    def __init__(self, config: AgentConfig, adk_integration: ADKIntegration):
        self.config = config
        self.adk_integration = adk_integration
        self.agent = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """初始化Agent"""
        try:
            self.agent = self.adk_integration.create_react_agent({
                "system_prompt": self.config.system_context,
                "tools": self.config.allowed_tools,
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
            
            # 1. 构建完整的输入上下文
            full_context = self._build_full_context(prompt, context)
            
            # 2. 调用大模型进行推理
            result = await self.agent.execute(full_context)
            
            # 3. 处理结果
            return self._process_result(result)
            
        except Exception as e:
            logger.error(f"Error executing agent {self.config.agent_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_full_context(self, prompt: str, context: Dict) -> str:
        """构建完整的输入上下文"""
        context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
        return f"""
{prompt}

上下文信息：
{context_str}

请根据上述信息和上下文执行相应的操作。
"""
    
    def _process_result(self, result) -> Dict:
        """处理执行结果"""
        # 简化实现，实际需要根据ADK返回格式处理
        return {
            "success": True,
            "result": result,
            "timestamp": None
        }

class AgentManager:
    """Agent管理器"""
    
    def __init__(self, mcp_server: MCPServer, a2a_server: A2AServer, adk_integration: ADKIntegration):
        self.mcp_server = mcp_server
        self.a2a_server = a2a_server
        self.adk_integration = adk_integration
        self.agents = {}
        self._initialize_agents()
    
    def _initialize_agents(self):
        """初始化所有Agent"""
        # 预定义的Agent配置
        agent_configs = [
            AgentConfig(
                agent_id="hr_agent_v1",
                agent_name="HR系统代理",
                system_context="你是一个HR系统的专业代理，负责处理员工相关的所有操作",
                allowed_tools=["create_employee", "update_employee", "get_employee_info"],
                mcp_tools=[
                    {
                        "name": "create_employee",
                        "endpoint": "https://hr-api.company.com/employees",
                        "method": "POST",
                        "schema": {}
                    }
                ]
            ),
            AgentConfig(
                agent_id="finance_agent_v1",
                agent_name="财务系统代理",
                system_context="你是一个财务系统的专业代理，负责处理财务相关的所有操作",
                allowed_tools=["enroll_payroll", "create_payroll_account"],
                mcp_tools=[]
            ),
            AgentConfig(
                agent_id="it_agent_v1",
                agent_name="IT系统代理",
                system_context="你是一个IT系统的专业代理，负责处理IT相关的所有操作",
                allowed_tools=["apply_computer", "create_user_account"],
                mcp_tools=[]
            )
        ]
        
        # 创建Agent实例
        for config in agent_configs:
            try:
                agent = BizAgent(config, self.adk_integration)
                self.agents[config.agent_id] = agent
                logger.info(f"Registered agent {config.agent_id}")
            except Exception as e:
                logger.error(f"Failed to register agent {config.agent_id}: {e}")
    
    async def execute_agent(self, agent_id: str, prompt: str, context: Dict) -> Dict:
        """执行指定Agent"""
        try:
            if agent_id not in self.agents:
                raise ValueError(f"Agent {agent_id} not found")
            
            agent = self.agents[agent_id]
            return await agent.execute(prompt, context)
            
        except Exception as e:
            logger.error(f"Error executing agent {agent_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def register_external_agent(self, agent_card: Dict):
        """注册外部Agent"""
        try:
            # 注册到A2A Server
            await self.a2a_server.register_agent(agent_card)
            logger.info(f"Registered external agent {agent_card.get('agent_id')}")
            
        except Exception as e:
            logger.error(f"Failed to register external agent: {e}")
            raise
    
    async def discover_agents(self) -> List[Dict]:
        """发现可用Agent"""
        try:
            return await self.a2a_server.discover_agents()
        except Exception as e:
            logger.error(f"Failed to discover agents: {e}")
            return []

class AtomAgentModule:
    """Atom Agent模块主类"""
    
    def __init__(self, mcp_server: MCPServer, a2a_server: A2AServer, adk_integration: ADKIntegration):
        self.mcp_server = mcp_server
        self.a2a_server = a2a_server
        self.adk_integration = adk_integration
        self.agent_manager = AgentManager(mcp_server, a2a_server, adk_integration)
    
    async def start(self):
        """启动Atom Agent模块"""
        try:
            # 启动MCP Server
            await self.mcp_server.start()
            
            # 启动A2A Server
            await self.a2a_server.start()
            
            # 注册所有Agent到A2A Server
            await self._register_all_agents()
            
            logger.info("Atom Agent Module started")
            
        except Exception as e:
            logger.error(f"Failed to start Atom Agent Module: {e}")
            raise
    
    async def stop(self):
        """停止Atom Agent模块"""
        try:
            await self.mcp_server.stop()
            await self.a2a_server.stop()
            logger.info("Atom Agent Module stopped")
        except Exception as e:
            logger.error(f"Error stopping Atom Agent Module: {e}")
    
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
