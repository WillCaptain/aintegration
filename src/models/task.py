"""
任务数据模型
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional
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
    """任务模型"""
    id: str
    plan_id: str
    name: str
    prompt: str
    status: str
    context: Dict
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        """从字典创建实例"""
        return cls(**data)
    
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
