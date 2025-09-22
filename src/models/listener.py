"""
侦听器数据模型
"""

from dataclasses import dataclass, asdict
from typing import Dict

@dataclass
class Listener:
    """侦听器模型"""
    id: str
    plan_id: str
    trigger_task_id: str
    trigger_condition: str
    action_condition: str
    agent_id: str
    action_prompt: str
    success_output: Dict
    failure_output: Dict
    
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
        return self.success_output.get("task_id", "")
    
    def get_success_target_status(self) -> str:
        """获取成功输出的目标状态"""
        return self.success_output.get("status", "")
    
    def get_failure_target_task(self) -> str:
        """获取失败输出的目标任务ID"""
        return self.failure_output.get("task_id", "")
    
    def get_failure_target_status(self) -> str:
        """获取失败输出的目标状态"""
        return self.failure_output.get("status", "")
