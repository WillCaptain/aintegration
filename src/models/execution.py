"""
执行记录数据模型
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class ExecutionLogEntry:
    """执行日志条目"""
    timestamp: datetime
    event: str
    details: Dict
    task_id: Optional[str] = None

@dataclass
class Execution:
    """执行记录模型"""
    id: str
    user_request: str
    plan_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    execution_log: List[ExecutionLogEntry] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.execution_log is None:
            self.execution_log = []
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        # 处理执行日志
        if self.execution_log:
            data['execution_log'] = [entry.to_dict() for entry in self.execution_log]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Execution':
        """从字典创建实例"""
        # 处理执行日志
        if 'execution_log' in data and data['execution_log']:
            log_entries = [ExecutionLogEntry.from_dict(entry) for entry in data['execution_log']]
            data['execution_log'] = log_entries
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Execution':
        """从JSON字符串创建实例"""
        import json
        data = json.loads(json_str)
        # 处理日期时间字段
        if 'start_time' in data:
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data:
            data['end_time'] = datetime.fromisoformat(data['end_time']) if data['end_time'] else None
        return cls.from_dict(data)
    
    def add_log_entry(self, event: str, details: Dict, task_id: Optional[str] = None):
        """添加日志条目"""
        entry = ExecutionLogEntry(
            timestamp=datetime.now(),
            event=event,
            details=details,
            task_id=task_id
        )
        self.execution_log.append(entry)
    
    def is_completed(self) -> bool:
        """检查执行是否完成"""
        return self.status == "completed"
    
    def is_failed(self) -> bool:
        """检查执行是否失败"""
        return self.status == "failed"
    
    def is_running(self) -> bool:
        """检查执行是否运行中"""
        return self.status == "running"
    
    def get_duration(self) -> Optional[float]:
        """获取执行时长（秒）"""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
