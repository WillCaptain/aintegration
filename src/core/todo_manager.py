"""
TODO管理器

负责管理TODO任务的创建、分配、跟踪和完成
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.todo_task import TodoTask
from ..core.id_generator import id_generator
from ..utils.todo_logger import todo_logger

logger = logging.getLogger(__name__)

class TodoManager:
    """TODO管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TodoManager, cls).__new__(cls)
            cls._instance.todos: Dict[str, TodoTask] = {}
            cls._instance._todo_counter = 0
        return cls._instance
    
    def __init__(self):
        # 初始化已经在__new__中完成
        pass
    
    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def create_parameter_todo(self, 
                                  plan_instance_id: str,
                                  listener_id: str,
                                  parameter_config: Dict[str, Any]) -> TodoTask:
        """创建参数输入TODO"""
        
        # 生成TODO ID
        self._todo_counter += 1
        todo_id = f"todo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._todo_counter:03d}"
        
        # 确定分配策略
        assignee = await self._determine_assignee(parameter_config)
        
        # 创建TODO任务
        todo = TodoTask(
            id=todo_id,
            title=f"参数输入: {parameter_config.get('title', '未知参数')}",
            description=f"计划 {plan_instance_id} 需要输入参数",
            type='parameter_input',
            priority=self._determine_priority(parameter_config),
            assignee_id=assignee.get('user_id'),
            assignee_role=assignee.get('role'),
            plan_instance_id=plan_instance_id,
            listener_id=listener_id,
            parameter_config=parameter_config,
            status='pending',
            created_at=datetime.now(),
            due_date=self._calculate_due_date(parameter_config),
            completed_at=None,
            completion_data=None,
            context={}
        )
        
        # 保存TODO
        self.todos[todo_id] = todo
        
        # 记录TODO创建日志
        todo_logger.log_todo_created(
            todo_id=todo_id,
            plan_instance_id=plan_instance_id,
            listener_id=listener_id,
            parameter_config=parameter_config,
            assignee_id=assignee.get('user_id')
        )
        
        # 发送通知
        await self._send_notification(todo)
        
        logger.info(f"Created parameter TODO {todo_id} for plan {plan_instance_id}")
        return todo
    
    async def get_workflow_todos(self, plan_instance_id: str) -> List[TodoTask]:
        """获取工作流程中的TODO"""
        return [
            todo for todo in self.todos.values()
            if todo.plan_instance_id == plan_instance_id
        ]
    
    async def get_todo_by_id(self, todo_id: str) -> Optional[TodoTask]:
        """根据ID获取TODO"""
        return self.todos.get(todo_id)
    
    async def complete_todo(self, todo_id: str, completion_data: Dict[str, Any]) -> bool:
        """完成TODO"""
        todo = self.todos.get(todo_id)
        if not todo:
            logger.error(f"TODO {todo_id} not found")
            return False
        
        # 更新TODO状态
        todo.status = 'completed'
        todo.completed_at = datetime.now()
        todo.completion_data = completion_data
        
        # 记录TODO完成日志
        todo_logger.log_todo_completed(todo_id, completion_data)
        
        logger.info(f"Completed TODO {todo_id}")
        return True
    
    async def get_user_todos(self, user_id: str, status: Optional[str] = None) -> List[TodoTask]:
        """获取用户的TODO列表"""
        todos = [
            todo for todo in self.todos.values()
            if todo.assignee_id == user_id
        ]
        
        if status:
            todos = [todo for todo in todos if todo.status == status]
        
        return todos
    
    async def _determine_assignee(self, config: Dict[str, Any]) -> Dict[str, str]:
        """确定分配策略"""
        
        # 1. 基于参数类型的默认分配
        param_type = config.get('assignee_hint', {}).get('type')
        
        if param_type == 'contract':
            return {"user_id": "contract_manager", "role": "contract_manager"}
        elif param_type == 'hr':
            return {"user_id": "hr_manager", "role": "hr_manager"}
        elif param_type == 'it':
            return {"user_id": "it_manager", "role": "it_manager"}
        
        # 2. 基于工作流的分配
        workflow_stage = config.get('workflow_stage')
        if workflow_stage:
            return await self._find_user_by_workflow_stage(workflow_stage)
        
        # 3. 默认分配给当前用户
        return {"user_id": "current_user", "role": "user"}
    
    async def _find_user_by_workflow_stage(self, stage: str) -> Dict[str, str]:
        """根据工作流阶段查找用户"""
        stage_mapping = {
            "contract_creation": {"user_id": "contract_manager", "role": "contract_manager"},
            "employee_onboarding": {"user_id": "hr_manager", "role": "hr_manager"},
            "equipment_request": {"user_id": "it_manager", "role": "it_manager"}
        }
        
        return stage_mapping.get(stage, {"user_id": "current_user", "role": "user"})
    
    def _determine_priority(self, config: Dict[str, Any]) -> str:
        """确定优先级"""
        priority_hints = config.get('priority_hints', {})
        
        if priority_hints.get('urgent'):
            return 'urgent'
        elif priority_hints.get('high'):
            return 'high'
        elif priority_hints.get('low'):
            return 'low'
        else:
            return 'medium'
    
    def _calculate_due_date(self, config: Dict[str, Any]) -> Optional[datetime]:
        """计算截止日期"""
        from datetime import timedelta
        due_hours = config.get('due_hours', 24)  # 默认24小时
        return datetime.now() + timedelta(hours=due_hours)
    
    async def _send_notification(self, todo: TodoTask):
        """发送通知"""
        # 这里可以实现实际的通知逻辑
        logger.info(f"Notification sent for TODO {todo.id} to {todo.assignee_id}")
    
    async def get_todo_statistics(self) -> Dict[str, Any]:
        """获取TODO统计信息"""
        total = len(self.todos)
        pending = len([t for t in self.todos.values() if t.status == 'pending'])
        completed = len([t for t in self.todos.values() if t.status == 'completed'])
        
        return {
            "total": total,
            "pending": pending,
            "completed": completed,
            "completion_rate": completed / total if total > 0 else 0
        }
