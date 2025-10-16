# TODO分配系统设计

**版本**: v1.0  
**日期**: 2025-10-15  
**特性**: BL-014.3 - TODO分配系统

---

## 🎯 功能概述

### 核心需求
当Plan执行过程中需要人工干预时（如参数输入、审批等），系统自动生成TODO任务并分配给相应的角色人员，支持任务跟踪、状态更新和客户端集成。

### 使用场景
1. **参数输入**: 电脑申请需要选择型号 → 生成TODO分配给IT经理
2. **审批流程**: 大额采购需要审批 → 生成TODO分配给采购经理
3. **信息确认**: 员工信息需要HR确认 → 生成TODO分配给HR专员
4. **异常处理**: 系统异常需要人工处理 → 生成TODO分配给系统管理员

---

## 🏗️ 架构设计

### 系统组件
```
┌─────────────────────────────────────────────────────────┐
│                    TODO分配系统                         │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ TODO管理器   │ │ 分配引擎     │ │ 通知系统     │       │
│  │ TodoManager │ │ Assignment  │ │ Notification│       │
│  │             │ │ Engine      │ │ System      │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ 权限管理     │ │ 状态跟踪     │ │ 客户端集成   │       │
│  │ Permission  │ │ Status      │ │ Client      │       │
│  │ Manager     │ │ Tracker     │ │ Integration │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 数据流
```
Plan执行 → 需要人工干预 → 生成TODO → 智能分配 → 通知用户 → 用户处理 → 更新状态 → 继续Plan执行
```

---

## 💻 详细实现

### 1. 数据模型

#### TODO任务模型
```python
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

@dataclass
class TodoAssignment:
    """TODO分配记录"""
    id: str
    todo_id: str
    assignee_id: str
    assigned_at: datetime
    assigned_by: str  # 系统或用户ID
    assignment_reason: str
    status: str  # 'active', 'reassigned', 'cancelled'
```

### 2. TODO管理器

```python
class TodoManager:
    """TODO管理器"""
    
    def __init__(self, todo_repo, user_manager, notification_service):
        self.todo_repo = todo_repo
        self.user_manager = user_manager
        self.notification_service = notification_service
        self.assignment_engine = AssignmentEngine()
    
    async def create_parameter_todo(self, 
                                  plan_instance_id: str,
                                  listener_id: str,
                                  parameter_config: Dict[str, Any]) -> TodoTask:
        """创建参数输入TODO"""
        
        # 1. 确定分配策略
        assignee = await self._determine_assignee(parameter_config)
        
        # 2. 创建TODO任务
        todo = TodoTask(
            id=f"todo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
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
            context={}
        )
        
        # 3. 保存TODO
        await self.todo_repo.create(todo)
        
        # 4. 发送通知
        await self._send_notification(todo)
        
        return todo
    
    async def create_approval_todo(self,
                                 plan_instance_id: str,
                                 listener_id: str,
                                 approval_config: Dict[str, Any]) -> TodoTask:
        """创建审批TODO"""
        
        todo = TodoTask(
            id=f"todo_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            title=f"审批: {approval_config.get('title', '未知审批')}",
            description=approval_config.get('description', ''),
            type='approval',
            priority=approval_config.get('priority', 'medium'),
            assignee_id=approval_config.get('assignee_id'),
            assignee_role=approval_config.get('assignee_role'),
            plan_instance_id=plan_instance_id,
            listener_id=listener_id,
            parameter_config=approval_config,
            status='pending',
            created_at=datetime.now(),
            due_date=approval_config.get('due_date'),
            context={}
        )
        
        await self.todo_repo.create(todo)
        await self._send_notification(todo)
        
        return todo
    
    async def _determine_assignee(self, config: Dict[str, Any]) -> Dict[str, str]:
        """确定分配策略"""
        
        # 1. 基于参数类型的默认分配
        param_type = config.get('assignee_hint', {}).get('type')
        
        if param_type == 'hr':
            return await self._find_user_by_role('hr_manager')
        elif param_type == 'it':
            return await self._find_user_by_role('it_manager')
        elif param_type == 'finance':
            return await self._find_user_by_role('finance_manager')
        
        # 2. 基于工作流的分配
        workflow_stage = config.get('workflow_stage')
        if workflow_stage:
            return await self._find_user_by_workflow_stage(workflow_stage)
        
        # 3. 默认分配给当前用户
        return {"user_id": "current_user", "role": "user"}
    
    async def _find_user_by_role(self, role: str) -> Dict[str, str]:
        """根据角色查找用户"""
        users = await self.user_manager.get_users_by_role(role)
        if users:
            # 选择工作负载最轻的用户
            return {
                "user_id": self._select_least_busy_user(users),
                "role": role
            }
        return {"user_id": "system", "role": "system"}
    
    async def _select_least_busy_user(self, users: List[User]) -> str:
        """选择工作负载最轻的用户"""
        user_todo_counts = {}
        for user in users:
            count = await self.todo_repo.count_pending_todos(user.id)
            user_todo_counts[user.id] = count
        
        return min(user_todo_counts, key=user_todo_counts.get)
    
    async def _send_notification(self, todo: TodoTask):
        """发送通知"""
        await self.notification_service.send_todo_notification(
            todo.assignee_id,
            {
                "todo_id": todo.id,
                "title": todo.title,
                "type": todo.type,
                "priority": todo.priority,
                "due_date": todo.due_date.isoformat() if todo.due_date else None
            }
        )
```

### 3. 分配引擎

```python
class AssignmentEngine:
    """分配引擎"""
    
    async def smart_assign(self, 
                          todo_type: str,
                          config: Dict[str, Any],
                          context: Dict[str, Any]) -> Dict[str, str]:
        """智能分配策略"""
        
        if todo_type == 'parameter_input':
            return await self._assign_parameter_input(config, context)
        elif todo_type == 'approval':
            return await self._assign_approval(config, context)
        elif todo_type == 'review':
            return await self._assign_review(config, context)
        
        return {"user_id": "system", "role": "system"}
    
    async def _assign_parameter_input(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
        """参数输入分配策略"""
        
        # 基于参数类型分配
        param_type = config.get('parameter_type')
        if param_type == 'computer_spec':
            return await self._find_user_by_role('it_manager')
        elif param_type == 'employee_info':
            return await self._find_user_by_role('hr_manager')
        elif param_type == 'budget_approval':
            return await self._find_user_by_role('finance_manager')
        
        # 基于部门分配
        department = context.get('department')
        if department:
            return await self._find_user_by_department(department)
        
        return {"user_id": "current_user", "role": "user"}
    
    async def _assign_approval(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, str]:
        """审批分配策略"""
        
        amount = config.get('amount', 0)
        if amount > 10000:  # 大额审批
            return await self._find_user_by_role('finance_director')
        elif amount > 1000:  # 中额审批
            return await self._find_user_by_role('finance_manager')
        else:  # 小额审批
            return await self._find_user_by_role('department_manager')
```

### 4. 客户端集成

```python
class TodoClientIntegration:
    """TODO客户端集成"""
    
    def __init__(self, todo_manager):
        self.todo_manager = todo_manager
    
    async def get_user_todos(self, user_id: str) -> List[TodoTask]:
        """获取用户的TODO列表"""
        return await self.todo_manager.todo_repo.get_user_todos(user_id)
    
    async def get_workflow_todos(self, plan_instance_id: str) -> List[TodoTask]:
        """获取工作流程中的TODO"""
        return await self.todo_manager.todo_repo.get_workflow_todos(plan_instance_id)
    
    async def complete_todo(self, todo_id: str, completion_data: Dict[str, Any]) -> bool:
        """完成TODO"""
        todo = await self.todo_manager.todo_repo.get_by_id(todo_id)
        if not todo:
            return False
        
        # 更新TODO状态
        todo.status = 'completed'
        todo.completed_at = datetime.now()
        todo.completion_data = completion_data
        
        await self.todo_manager.todo_repo.update(todo_id, {
            "status": todo.status,
            "completed_at": todo.completed_at,
            "completion_data": todo.completion_data
        })
        
        # 通知Plan继续执行
        if todo.type == 'parameter_input':
            await self._continue_plan_execution(todo, completion_data)
        
        return True
    
    async def _continue_plan_execution(self, todo: TodoTask, completion_data: Dict[str, Any]):
        """继续Plan执行"""
        # 调用PlannerAgent的continue_plan方法
        await self.todo_manager.planner_agent.continue_plan(
            todo.plan_instance_id,
            completion_data.get('parameters', {})
        )
```

---

## 🎨 前端集成

### 客户端TODO处理
```javascript
class TodoHandler {
    constructor() {
        this.todoList = [];
        this.currentUser = null;
    }
    
    async loadUserTodos() {
        const response = await fetch('/api/todos/user');
        this.todoList = await response.json();
        this.renderTodoList();
    }
    
    async handleTodoClick(todoId) {
        const todo = this.todoList.find(t => t.id === todoId);
        
        if (todo.type === 'parameter_input') {
            // 如果是参数输入TODO，显示参数表单
            await this.showParameterForm(todo);
        } else if (todo.type === 'approval') {
            // 如果是审批TODO，显示审批界面
            await this.showApprovalForm(todo);
        }
    }
    
    async showParameterForm(todo) {
        // 检查是否在当前工作流程中
        if (this.isInCurrentWorkflow(todo.plan_instance_id)) {
            // 在工作流程中，直接显示参数表单
            showStructuredParameterForm(todo.parameter_config);
        } else {
            // 不在工作流程中，打开TODO详情页面
            window.open(`/todos/${todo.id}`, '_blank');
        }
    }
    
    async completeTodo(todoId, result) {
        const response = await fetch(`/api/todos/${todoId}/complete`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({result: result})
        });
        
        if (response.ok) {
            // 更新本地TODO列表
            await this.loadUserTodos();
            // 如果是在工作流程中，继续执行
            if (result.plan_instance_id) {
                await this.continuePlanExecution(result.plan_instance_id, result.parameters);
            }
        }
    }
}

// 工作流程中的TODO显示
function integrateTodosInWorkflow() {
    const todoHandler = new TodoHandler();
    
    // 检查当前工作流程是否有待处理的TODO
    async function checkWorkflowTodos(planInstanceId) {
        const response = await fetch(`/api/todos/workflow/${planInstanceId}`);
        const todos = await response.json();
        
        if (todos.length > 0) {
            // 显示TODO提示
            showTodoNotification(todos);
        }
    }
    
    function showTodoNotification(todos) {
        const notification = document.createElement('div');
        notification.className = 'todo-notification';
        notification.innerHTML = `
            <div class="todo-notification-content">
                <h4>📋 有待处理的任务</h4>
                <ul>
                    ${todos.map(todo => `
                        <li>
                            <button onclick="handleTodoClick('${todo.id}')">
                                ${todo.title} (${todo.priority})
                            </button>
                        </li>
                    `).join('')}
                </ul>
            </div>
        `;
        
        document.body.appendChild(notification);
    }
}
```

---

## 📊 API设计

### TODO管理API
```python
@router.get("/todos/user")
async def get_user_todos(
    user_id: str = None,
    status: str = None,
    type: str = None,
    todo_manager = Depends(get_todo_manager)
):
    """获取用户的TODO列表"""
    todos = await todo_manager.get_user_todos(
        user_id=user_id,
        status=status,
        type=type
    )
    return todos

@router.get("/todos/workflow/{plan_instance_id}")
async def get_workflow_todos(
    plan_instance_id: str,
    todo_manager = Depends(get_todo_manager)
):
    """获取工作流程中的TODO"""
    todos = await todo_manager.get_workflow_todos(plan_instance_id)
    return todos

@router.post("/todos/{todo_id}/complete")
async def complete_todo(
    todo_id: str,
    completion_data: Dict[str, Any],
    todo_manager = Depends(get_todo_manager)
):
    """完成TODO"""
    success = await todo_manager.complete_todo(todo_id, completion_data)
    return {"success": success}

@router.post("/todos/{todo_id}/reassign")
async def reassign_todo(
    todo_id: str,
    new_assignee_id: str,
    reason: str,
    todo_manager = Depends(get_todo_manager)
):
    """重新分配TODO"""
    success = await todo_manager.reassign_todo(todo_id, new_assignee_id, reason)
    return {"success": success}
```

---

## 📈 实施计划

### Phase 1: 核心功能（2周）
- [ ] 实现TodoTask数据模型
- [ ] 实现TodoManager核心功能
- [ ] 实现分配引擎
- [ ] 实现基础API

### Phase 2: 客户端集成（1周）
- [ ] 前端TODO组件开发
- [ ] 工作流程集成
- [ ] 通知系统集成

### Phase 3: 高级功能（1周）
- [ ] 智能分配策略优化
- [ ] 权限控制完善
- [ ] 监控和报告功能

---

## 🎯 验收标准

1. **功能完整性**:
   - ✅ 能够自动生成TODO任务
   - ✅ 智能分配策略工作正常
   - ✅ 客户端集成流畅
   - ✅ 状态跟踪准确

2. **性能要求**:
   - ✅ TODO分配响应时间 < 500ms
   - ✅ 支持1000+并发TODO处理
   - ✅ 通知延迟 < 1秒

3. **用户体验**:
   - ✅ 界面友好直观
   - ✅ 操作简单便捷
   - ✅ 状态更新及时

---

**TODO分配系统将实现真正的任务自动化管理，让AI员工能够与人类员工无缝协作！**
