"""
侦听器数据模型
"""

from dataclasses import dataclass, asdict
from typing import Dict, Optional, Any, List
from enum import Enum

class ListenerType(Enum):
    """侦听器类型枚举"""
    AGENT = "agent"
    CODE = "code"

@dataclass
class Listener:
    """侦听器模型"""
    id: str
    plan_id: str
    trigger_task_id: str
    trigger_condition: str
    action_condition: str
    listener_type: str  # "agent" 或 "code"
    plan_instance_id: Optional[str] = None  # 所属计划实例ID（新增）
    agent_id: Optional[str] = None  # 当类型为agent时使用
    action_prompt: Optional[str] = None  # 当类型为agent时使用
    code_snippet: Optional[str] = None  # 当类型为code时使用
    success_output: Dict[str, Any] = None
    failure_output: Dict[str, Any] = None
    is_active: bool = True
    priority: int = 0  # 优先级，数字越小优先级越高
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Listener':
        """从字典创建实例"""
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Listener':
        """从JSON字符串创建实例"""
        import json
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def get_success_target_task(self) -> str:
        """获取成功输出的目标任务ID"""
        return self.success_output.get("task_id", "") if self.success_output else ""
    
    def get_success_target_status(self) -> str:
        """获取成功输出的目标状态"""
        return self.success_output.get("status", "") if self.success_output else ""
    
    def get_failure_target_task(self) -> str:
        """获取失败输出的目标任务ID"""
        return self.failure_output.get("task_id", "") if self.failure_output else ""
    
    def get_failure_target_status(self) -> str:
        """获取失败输出的目标状态"""
        return self.failure_output.get("status", "") if self.failure_output else ""
    
    def is_agent_listener(self) -> bool:
        """检查是否为智能体侦听器"""
        return self.listener_type == ListenerType.AGENT.value
    
    def is_code_listener(self) -> bool:
        """检查是否为代码侦听器"""
        return self.listener_type == ListenerType.CODE.value
    
    def get_success_context(self) -> Dict[str, Any]:
        """获取成功输出的上下文"""
        return self.success_output.get("context", {}) if self.success_output else {}
    
    def get_failure_context(self) -> Dict[str, Any]:
        """获取失败输出的上下文"""
        return self.failure_output.get("context", {}) if self.failure_output else {}
    
    def evaluate_trigger_condition(self, task_status: str) -> bool:
        """评估触发条件是否满足"""
        if not self.is_active:
            return False
        
        # 简化的条件评估，实际实现需要更复杂的表达式解析
        expected_condition = f"{self.trigger_task_id}.status == {task_status}"
        return expected_condition in self.trigger_condition or "Any" in self.trigger_condition
    
    def evaluate_action_condition(self, plan_context: Dict[str, Any]) -> bool:
        """兼容旧接口：已废弃，始终返回 True"""
        return True
