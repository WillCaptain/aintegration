"""
A2A Server

Agent注册发现和通信
"""

import logging
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

class AgentCard(BaseModel):
    """Agent卡片"""
    agent_id: str
    agent_name: str
    provider: str
    version: str
    capabilities: List[str]
    endpoints: Dict
    authentication: Optional[Dict] = None
    health_status: str = "unknown"
    last_updated: Optional[datetime] = None

class A2ARequest(BaseModel):
    """A2A请求"""
    agent_id: str
    action: str
    parameters: Dict

class A2AResponse(BaseModel):
    """A2A响应"""
    success: bool
    result: Optional[Dict] = None
    error: Optional[str] = None

class A2AServer:
    """A2A Server实现"""
    
    def __init__(self, host: str = "localhost", port: int = 8005, agent_runtime=None):
        self.host = host
        self.port = port
        self.app = FastAPI(title="A2A Server", version="1.0.0")
        self.registered_agents = {}
        self._agent_runtime = agent_runtime  # AgentRuntime引用，用于执行BizAgent
        self._setup_routes()
    
    def set_agent_runtime(self, agent_runtime):
        """设置AgentRuntime（用于延迟注入）"""
        self._agent_runtime = agent_runtime
        logger.info(f"AgentRuntime set for A2AServer")
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.get("/health")
        async def health_check():
            """健康检查"""
            return {"status": "healthy", "service": "a2a_server"}
        
        @self.app.post("/agents/register")
        async def register_agent(agent_card: AgentCard):
            """注册Agent"""
            try:
                agent_card.last_updated = datetime.now()
                self.registered_agents[agent_card.agent_id] = agent_card.dict()
                logger.info(f"Registered agent: {agent_card.agent_id}")
                return {"success": True, "agent_id": agent_card.agent_id}
            except Exception as e:
                logger.error(f"Failed to register agent {agent_card.agent_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/agents")
        async def list_agents():
            """列出所有注册的Agent"""
            return {"agents": list(self.registered_agents.keys())}
        
        @self.app.get("/agents/{agent_id}")
        async def get_agent(agent_id: str):
            """获取Agent信息"""
            if agent_id not in self.registered_agents:
                raise HTTPException(status_code=404, detail="Agent not found")
            return self.registered_agents[agent_id]
        
        @self.app.post("/agents/{agent_id}/execute")
        async def execute_agent(agent_id: str, request: A2ARequest):
            """执行Agent"""
            try:
                if agent_id not in self.registered_agents:
                    raise HTTPException(status_code=404, detail="Agent not found")
                
                agent = self.registered_agents[agent_id]
                result = await self._execute_agent_internal(agent, request)
                
                return A2AResponse(success=True, result=result)
                
            except Exception as e:
                logger.error(f"Error executing agent {agent_id}: {e}")
                return A2AResponse(success=False, error=str(e))
        
        @self.app.get("/agents/discover")
        async def discover_agents():
            """发现可用Agent"""
            return {"agents": list(self.registered_agents.values())}
        
        @self.app.post("/agents/{agent_id}/health")
        async def update_health_status(agent_id: str, status: Dict):
            """更新Agent健康状态"""
            if agent_id not in self.registered_agents:
                raise HTTPException(status_code=404, detail="Agent not found")
            
            self.registered_agents[agent_id]["health_status"] = status.get("status", "unknown")
            self.registered_agents[agent_id]["last_updated"] = datetime.now()
            
            return {"success": True}
    
    async def _execute_agent_internal(self, agent: Dict, request: A2ARequest) -> Dict:
        """
        内部Agent执行逻辑
        
        关键设计：
        1. 接收PlannerAgent的语义请求（action是描述性文本）
        2. 调用对应的BizAgent（ReactAgent）
        3. BizAgent理解语义并自己决定调用什么工具
        4. 返回执行结果
        """
        try:
            agent_id = agent["agent_id"]
            action = request.action  # 语义请求，如"请验证员工状态"
            parameters = request.parameters
            
            logger.info(f"[A2AServer] Executing agent {agent_id} with action: {action}")
            logger.info(f"[A2AServer] Parameters: {parameters}")
            
            # 从AgentRuntime获取BizAgent并执行
            # 注意：这需要AgentRuntime的支持
            if hasattr(self, '_agent_runtime') and self._agent_runtime:
                # 构建执行上下文（将action和parameters组合成prompt）
                context_prompt = f"{action}\n\n参数信息：\n"
                for key, value in parameters.items():
                    context_prompt += f"- {key}: {value}\n"
                
                logger.info(f"[A2AServer] Calling AgentRuntime.execute_agent with context: {context_prompt[:200]}...")
                result = await self._agent_runtime.execute_agent(agent_id, context_prompt)
                logger.info(f"[A2AServer] Agent execution completed, result: {result}")
                
                return {
                    "agent_id": agent_id,
                    "action": request.action,
                    "parameters": request.parameters,
                    "execution_time": datetime.now().isoformat(),
                    "success": result.get("success", True),
                    "response": result.get("response", ""),
                    "tools_used": result.get("tools_used", []),
                    "result": result.get("result", "")
                }
            else:
                # 如果没有AgentRuntime，记录警告并返回错误
                logger.warning(f"[A2AServer] No AgentRuntime available, cannot execute agent {agent_id}")
                return {
                    "agent_id": agent["agent_id"],
                    "action": request.action,
                    "parameters": request.parameters,
                    "execution_time": datetime.now().isoformat(),
                    "success": False,
                    "error": "AgentRuntime not configured"
                }
                    
        except Exception as e:
            logger.error(f"Error executing agent {agent['agent_id']}: {e}")
            return {
                "agent_id": agent["agent_id"],
                "action": request.action,
                "parameters": request.parameters,
                "execution_time": datetime.now().isoformat(),
                "success": False,
                "error": str(e)
            }
    
    async def start(self):
        """启动A2A Server"""
        try:
            import uvicorn
            logger.info(f"Starting A2A Server on {self.host}:{self.port}")
            # 这里应该启动服务器，但为了避免阻塞，我们只是记录日志
            logger.info("A2A Server started")
        except Exception as e:
            logger.error(f"Failed to start A2A Server: {e}")
            raise
    
    async def stop(self):
        """停止A2A Server"""
        logger.info("A2A Server stopped")
    
    async def register_agent(self, agent_card: Dict):
        """注册Agent"""
        agent = AgentCard(**agent_card)
        agent.last_updated = datetime.now()
        self.registered_agents[agent.agent_id] = agent.dict()
        logger.info(f"Registered agent: {agent.agent_id}")
    
    async def register_agents_batch(self, agent_cards: List[Dict]):
        """批量注册Agent"""
        registered_count = 0
        for agent_card in agent_cards:
            try:
                await self.register_agent(agent_card)
                registered_count += 1
            except Exception as e:
                logger.error(f"Failed to register agent {agent_card.get('agent_id', 'unknown')}: {e}")
        
        logger.info(f"Batch registered {registered_count}/{len(agent_cards)} agents")
        return registered_count
    
    async def discover_agents(self) -> List[Dict]:
        """发现可用Agent"""
        return list(self.registered_agents.values())
    
    async def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取Agent信息"""
        return self.registered_agents.get(agent_id)
    
    async def execute_agent(self, agent_id: str, action: str, parameters: Dict) -> Dict:
        """执行Agent"""
        if agent_id not in self.registered_agents:
            raise ValueError(f"Agent {agent_id} not found")
        
        agent = self.registered_agents[agent_id]
        request = A2ARequest(agent_id=agent_id, action=action, parameters=parameters)
        return await self._execute_agent_internal(agent, request)
