"""
Mock Agent 用于测试侦听器引擎

模拟BizAgent的行为，返回预定义的响应
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MockAgent:
    """Mock Agent 用于测试"""
    
    def __init__(self, responses: Optional[Dict[str, str]] = None):
        """
        初始化Mock Agent
        
        Args:
            responses: 预定义的响应映射 {prompt_key: response_json}
        """
        self.responses = responses or {}
        self.call_history = []
    
    async def execute_agent(self, agent_id: str, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行Agent"""
        logger.info(f"MockAgent executing agent {agent_id} with prompt: {prompt[:100]}...")
        
        # 记录调用历史
        self.call_history.append({
            "agent_id": agent_id,
            "prompt": prompt,
            "context": context,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # 查找预定义响应
        for key, response in self.responses.items():
            if key in prompt:
                try:
                    result = json.loads(response)
                    logger.info(f"MockAgent returning predefined response: {result}")
                    return result
                except json.JSONDecodeError:
                    logger.warning(f"MockAgent invalid JSON response: {response}")
                    return {"success": True, "result": response}
        
        # 默认响应
        default_response = {
            "success": True,
            "result": f"MockAgent executed {agent_id}",
            "context": {"mock": True}
        }
        logger.info(f"MockAgent returning default response: {default_response}")
        return default_response
    
    async def execute_agent_with_context(self, agent_id: str, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用上下文执行Agent"""
        return await self.execute_agent(agent_id, prompt, context)
    
    def get_call_history(self) -> list:
        """获取调用历史"""
        return self.call_history.copy()
    
    def clear_history(self):
        """清空调用历史"""
        self.call_history.clear()

class MockAgentRuntime:
    """Mock AgentRuntime 用于测试"""
    
    def __init__(self, mock_agent: MockAgent):
        self.mock_agent = mock_agent
    
    async def execute_agent(self, agent_id: str, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行Agent"""
        return await self.mock_agent.execute_agent(agent_id, prompt, context)
    
    async def execute_agent_with_context(self, agent_id: str, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用上下文执行Agent"""
        return await self.mock_agent.execute_agent_with_context(agent_id, prompt, context)

# 预定义的测试响应
TEST_RESPONSES = {
    "启动任务B": json.dumps({
        "success": True,
        "target_task": "task_b",
        "target_status": "Running",
        "context": {"triggered_by": "agent_listener_1", "method": "agent"}
    }),
    "完成任务C": json.dumps({
        "success": True,
        "target_task": "task_c", 
        "target_status": "Done",
        "context": {"triggered_by": "agent_listener_2", "method": "agent"}
    }),
    "混合驱动": json.dumps({
        "success": True,
        "target_task": "task_c",
        "target_status": "Done", 
        "context": {"triggered_by": "agent_listener", "method": "agent"}
    })
}

def create_mock_agent_runtime(responses: Optional[Dict[str, str]] = None) -> MockAgentRuntime:
    """创建Mock AgentRuntime"""
    mock_agent = MockAgent(responses or TEST_RESPONSES)
    return MockAgentRuntime(mock_agent)
