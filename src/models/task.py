"""
任务数据模型
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum

class TaskStatus(Enum):
    """任务状态枚举"""
    NOT_STARTED = "NotStarted"
    RUNNING = "Running"
    DONE = "Done"
    ERROR = "Error"
    PENDING = "Pending"

@dataclass
class Task:
    """任务模型（元数据模板）"""
    id: str
    plan_id: str
    name: str
    prompt: str
    # 注意：Task 是元数据模板，没有 status 和 context 属性
    # 运行时状态存储在 TaskInstance 中
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_main_task: bool = False
    parent_task_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        """从字典创建实例"""
        # 过滤掉不存在的字段（向后兼容）
        filtered_data = {k: v for k, v in data.items() if k in ['id', 'plan_id', 'name', 'prompt', 'created_at', 'updated_at', 'is_main_task', 'parent_task_id']}
        return cls(**filtered_data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Task':
        """从JSON字符串创建实例"""
        import json
        data = json.loads(json_str)
        # 处理日期时间字段
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            data['updated_at'] = datetime.fromisoformat(data['updated_at']) if data['updated_at'] else None
        return cls.from_dict(data)
    
    def is_completed(self) -> bool:
        """检查任务是否完成"""
        return self.status == TaskStatus.DONE.value
    
    def is_failed(self) -> bool:
        """检查任务是否失败"""
        return self.status == TaskStatus.ERROR.value
    
    def is_pending(self) -> bool:
        """检查任务是否等待中"""
        return self.status == TaskStatus.PENDING.value
    
    def update_status(self, new_status: str, context_updates: Optional[Dict[str, Any]] = None):
        """更新任务状态和上下文"""
        self.status = new_status
        if context_updates:
            self.context.update(context_updates)
        self.updated_at = datetime.now()
    
    def get_context_value(self, key: str, default: Any = None) -> Any:
        """获取上下文中的值"""
        return self.context.get("values", {}).get(key, default)
    
    def set_context_value(self, key: str, value: Any):
        """设置上下文中的值"""
        if "values" not in self.context:
            self.context["values"] = {}
        self.context["values"][key] = value
        self.updated_at = datetime.now()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        return self.context.get("metadata", {})
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]):
        """设置元数据"""
        self.context["metadata"] = value
        self.updated_at = datetime.now()
    
    def can_transition_to(self, target_status: str) -> bool:
        """检查是否可以转换到目标状态 - 允许任意状态转换"""
        return True
