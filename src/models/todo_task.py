"""
TODO任务模型
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class TodoTask:
    """TODO任务"""
    id: str
    title: str
    description: str
    type: str  # 'parameter_input', 'approval', 'review', 'confirmation'
    priority: str  # 'low', 'medium', 'high', 'urgent'
    assignee_id: Optional[str]  # 分配的用户ID
    assignee_role: Optional[str]  # 分配的角色
    plan_instance_id: str
    listener_id: str
    parameter_config: Dict[str, Any]  # 参数配置或审批配置
    status: str  # 'pending', 'in_progress', 'completed', 'cancelled', 'expired'
    created_at: datetime
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    completion_data: Optional[Dict[str, Any]]  # 完成时的数据
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "assignee_id": self.assignee_id,
            "assignee_role": self.assignee_role,
            "plan_instance_id": self.plan_instance_id,
            "listener_id": self.listener_id,
            "parameter_config": self.parameter_config,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "completion_data": self.completion_data,
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TodoTask':
        """从字典创建实例"""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            type=data["type"],
            priority=data["priority"],
            assignee_id=data.get("assignee_id"),
            assignee_role=data.get("assignee_role"),
            plan_instance_id=data["plan_instance_id"],
            listener_id=data["listener_id"],
            parameter_config=data["parameter_config"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            completion_data=data.get("completion_data"),
            context=data.get("context", {})
        )
