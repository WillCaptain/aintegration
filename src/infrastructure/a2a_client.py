"""
A2A Client 抽象与默认实现

- A2AClient: 面向 Planner 的能力发现与调用接口
- DefaultA2AClient: 适配本项目内置的 A2AServer（内存实现）

后续可无缝替换为 Google 官方 A2A SDK/标准实现，只需替换本文件实现。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class A2AClient:
    """A2A 客户端抽象接口"""

    async def list_agents(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def execute(self, agent_id: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def find_agent_by_capability(self, capability: str) -> Optional[str]:
        """根据能力名寻找可用 agent_id"""
        agents = await self.list_agents()
        for agent in agents:
            caps = (agent or {}).get("capabilities") or []
            if capability in caps:
                return agent.get("agent_id")
        return None


class DefaultA2AClient(A2AClient):
    """默认实现：适配项目内置的 A2AServer（内存目录）"""

    def __init__(self, a2a_server: Optional["A2AServer"] = None):
        # 允许为空，便于在部分测试中不启用 A2A
        self.a2a_server = a2a_server

    async def list_agents(self) -> List[Dict[str, Any]]:
        if not self.a2a_server:
            return []
        return await self.a2a_server.discover_agents()

    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        if not self.a2a_server:
            return None
        return await self.a2a_server.get_agent(agent_id)

    async def execute(self, agent_id: str, action: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if not self.a2a_server:
            logger.warning("A2A server not configured; returning stub response")
            return {"success": False, "error": "a2a_not_configured"}
        try:
            return await self.a2a_server.execute_agent(agent_id, action, parameters)
        except Exception as e:
            logger.error(f"A2A execute failed: {e}")
            return {"success": False, "error": str(e)}


