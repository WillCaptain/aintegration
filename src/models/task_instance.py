"""
任务实例数据模型

任务实例表示任务在特定计划实例中的执行状态
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional, Any, List
from enum import Enum

logger = logging.getLogger(__name__)

class TaskInstanceStatus(Enum):
    """任务实例状态枚举"""
    NOT_STARTED = "NotStarted"
    RUNNING = "Running"
    DONE = "Done"
    ERROR = "Error"
    PENDING = "Pending"

@dataclass
class TaskInstance:
    """任务实例模型"""
    id: str  # task_instance_id (通常是 plan_instance_id + "_" + task_id)
    plan_instance_id: str  # 所属计划实例ID
    task_id: str  # 引用的任务定义ID
    plan_id: str  # 引用的计划定义ID
    name: str
    status: str = TaskInstanceStatus.NOT_STARTED.value
    parent_task_id: Optional[str] = None
    context: Dict[str, Any] = None  # 任务实例的运行时上下文
    status_trace: List[Dict[str, Any]] = None  # 状态变化轨迹
    
    def __post_init__(self):
        if self.status_trace is None:
            self.status_trace = []
        if self.context is None:
            self.context = {}
        # 初始化状态轨迹
        self._add_status_trace(self.status, "initialized")
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TaskInstance':
        """从字典创建实例"""
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TaskInstance':
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
        return self.status == TaskInstanceStatus.DONE.value
    
    def is_failed(self) -> bool:
        """检查任务是否失败"""
        return self.status == TaskInstanceStatus.ERROR.value
    
    def is_pending(self) -> bool:
        """检查任务是否等待中"""
        return self.status == TaskInstanceStatus.PENDING.value
    
    def is_main_task(self) -> bool:
        """检查是否为主任务（task_id == "001"）"""
        return self.task_id == "001"
    
    def update_status(self, new_status: str, reason: str = "manual_update"):
        """更新任务状态并记录轨迹（由外部驱动）"""
        if new_status != self.status:
            self.status = new_status
            self._add_status_trace(new_status, reason)
    
    def _add_status_trace(self, status: str, reason: str):
        """添加状态变化轨迹"""
        trace_entry = {
            "status": status,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "is_new": True  # 标记为新状态变化
        }
        self.status_trace.append(trace_entry)
    
    def get_status_history(self) -> List[Dict[str, Any]]:
        """获取状态变化历史"""
        return self.status_trace.copy()
    
    def get_last_status_change(self) -> Optional[Dict[str, Any]]:
        """获取最后一次状态变化"""
        return self.status_trace[-1] if self.status_trace else None
    
    # 注意：上下文现在跟随 PlanInstance，不再需要单独的上下文管理方法
    
    def can_transition_to(self, target_status: str) -> bool:
        """检查是否可以转换到目标状态 - 允许任意状态转换"""
        return True
