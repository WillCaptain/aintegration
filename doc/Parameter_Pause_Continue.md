# 参数暂停与继续功能设计

**版本**: v1.0  
**日期**: 2025-10-15  
**特性**: BL-014.1 - 参数暂停与继续

---

## 🎯 功能概述

### 核心需求
当Agent在执行过程中发现缺少必需参数时，PlanInstance应自动进入PAUSE状态，等待用户通过continue() API提供参数后继续执行。

### 使用场景
1. **设备申请**: "申请电脑" → 需要电脑型号(单选) → PAUSE → 用户选择"MacBook Pro" → 继续
2. **邮件发送**: "发送邮件给张三" → 需要邮件内容(文本域) → PAUSE → 用户输入内容 → 继续  
3. **账号创建**: "创建新员工账号" → 需要用户名(输入框)和部门(下拉框) → PAUSE → 用户填写表单 → 继续
4. **权限申请**: "申请系统权限" → 需要权限类型(多选)和期限(日期) → PAUSE → 用户选择 → 继续

### 与现有功能的区别
- **Resume**: 用于错误恢复，重新执行失败的listener
- **Continue**: 用于参数补充，从暂停点继续执行同一个listener

---

## 🏗️ 架构设计

### 状态机扩展

```
NOT_STARTED → RUNNING → DONE
                ↓
            PAUSE ← → ERROR
                ↓
            CONTINUE → RUNNING
```

### 新增状态
- **PAUSE**: PlanInstance暂停等待参数
- **CONTINUE**: 用户已提供参数，准备继续执行

### 核心组件

```
┌─────────────────────────────────────────────────────┐
│                PlannerAgent                         │
│  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │ on_task_status_ │  │ continue_plan()         │  │
│  │ change()        │  │ (新方法)                │  │
│  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│                PlanInstance                         │
│  status: PAUSE | CONTINUE                           │
│  context: {                                         │
│    paused_listener_id: "listener_001",             │
│    required_params: ["computer_model"]             │
│  }                                                  │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│                TaskDriver                           │
│  ┌─────────────────────────────────────────────┐   │
│  │ execute_listener()                          │   │
│  │ 返回: {success: false, reason: "missing_params", │
│  │       missing_params: ["computer_model"]}   │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## 💻 详细实现

### 1. 数据模型扩展

#### PlanInstanceStatus 枚举
```python
class PlanInstanceStatus(Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    PAUSE = "pause"        # 新增
    CONTINUE = "continue"  # 新增
```

#### PlanInstance context 结构
```python
# 暂停时的context结构
context = {
    "values": {...},           # 现有值
    "metadata": {...},         # 现有元数据
    "paused_listener_id": "listener_001",  # 暂停的listener
    "required_params": ["computer_model"],  # 缺少的参数
    "pause_reason": "missing_params",       # 暂停原因
    "pause_timestamp": "2025-10-15T10:30:00Z"
}

# continue时的context结构
context = {
    "values": {...},
    "metadata": {...},
    "paused_listener_id": "listener_001",
    "provided_params": {                    # 用户提供的参数
        "computer_model": "MacBook Pro"
    },
    "continue_timestamp": "2025-10-15T10:35:00Z"
}
```

### 2. TaskDriver 扩展

#### 执行结果扩展
```python
# 现有结果结构
result = {
    "success": True/False,
    "task_updates": [...],
    "error": "..."  # 可选
}

# 新增：缺少参数的结果
result = {
    "success": False,
    "reason": "missing_params",
    "required_params": {
        "computer_model": {
            "type": "radio",
            "label": "电脑型号",
            "description": "请选择所需的电脑型号",
            "options": [
                {"value": "MacBook Pro", "label": "MacBook Pro 14寸", "price": "¥18,999"},
                {"value": "ThinkPad X1", "label": "ThinkPad X1 Carbon", "price": "¥12,999"},
                {"value": "Dell XPS", "label": "Dell XPS 13", "price": "¥9,999"},
                {"value": "custom", "label": "其他型号（需填写）"}
            ],
            "required": True,
            "validation": {
                "type": "enum",
                "values": ["MacBook Pro", "ThinkPad X1", "Dell XPS", "custom"]
            }
        }
    },
    "task_updates": []  # 空，不更新任务状态
}
```

### 3. PlannerAgent 扩展

#### 新增 continue_plan() 方法
```python
async def continue_plan(self, plan_instance_id: str, provided_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    继续执行暂停的计划实例
    
    参数:
        plan_instance_id: 计划实例ID
        provided_params: 用户提供的参数
    
    返回:
        执行结果
    """
    try:
        # 获取计划实例
        plan_instance = await self.plan_module.get_plan_instance(plan_instance_id)
        if not plan_instance:
            return {"success": False, "error": f"Plan instance {plan_instance_id} not found"}
        
        # 检查状态
        if plan_instance.status != PlanInstanceStatus.PAUSE.value:
            return {"success": False, "error": f"Plan instance is not in PAUSE status, current: {plan_instance.status}"}
        
        # 获取暂停的listener
        paused_listener_id = plan_instance.context.get("paused_listener_id")
        if not paused_listener_id:
            return {"success": False, "error": "No paused listener found"}
        
        # 更新context，添加提供的参数
        plan_instance.context["provided_params"] = provided_params
        plan_instance.context["continue_timestamp"] = datetime.now().isoformat()
        plan_instance.status = PlanInstanceStatus.CONTINUE.value
        
        # 保存状态
        await self.plan_module.update_plan_instance(plan_instance_id, {
            "status": plan_instance.status,
            "context": plan_instance.context
        })
        
        # 获取暂停的listener
        listener = await self.plan_module.listener_repo.get_by_id(paused_listener_id)
        if not listener:
            return {"success": False, "error": f"Listener {paused_listener_id} not found"}
        
        # 重新执行listener（使用新参数）
        result = await self.task_driver.execute_listener(listener, plan_instance.context)
        
        # 处理执行结果
        if result.get('success', False):
            # 成功：继续正常流程
            plan_instance.status = PlanInstanceStatus.RUNNING.value
            # 清除暂停信息
            plan_instance.context.pop("paused_listener_id", None)
            plan_instance.context.pop("required_params", None)
            plan_instance.context.pop("pause_reason", None)
        else:
            # 失败：检查是否是新的参数缺失
            if result.get('reason') == 'missing_params':
                # 仍然缺少参数，保持PAUSE状态
                plan_instance.status = PlanInstanceStatus.PAUSE.value
                plan_instance.context["required_params"] = result.get("missing_params", [])
                plan_instance.context["pause_reason"] = "missing_params"
            else:
                # 其他错误，进入ERROR状态
                plan_instance.status = PlanInstanceStatus.ERROR.value
                plan_instance.context["error"] = result.get("error", "Unknown error")
        
        # 保存最终状态
        await self.plan_module.update_plan_instance(plan_instance_id, {
            "status": plan_instance.status,
            "context": plan_instance.context
        })
        
        return {
            "success": True,
            "status": plan_instance.status,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error continuing plan {plan_instance_id}: {e}")
        return {"success": False, "error": str(e)}
```

#### 修改 on_task_status_change()
```python
async def on_task_status_change(self, task_instance: TaskInstance, plan_context: Dict[str, Any]):
    """处理任务状态变化"""
    try:
        # 获取触发的listeners
        triggered_listeners = await self.listener_engine.get_triggered_listeners(task_instance)
        
        if not triggered_listeners:
            # 无listener触发，检查是否需要Planner介入
            await self._handle_no_listeners(task_instance, plan_context)
            return
        
        # 执行每个listener
        for listener in triggered_listeners:
            try:
                result = await self.task_driver.execute_listener(listener, plan_context)
                
                # 检查是否缺少参数
                if not result.get('success', False) and result.get('reason') == 'missing_params':
                    # 暂停计划实例
                    await self._pause_plan_for_params(listener, result, plan_context)
                    return  # 暂停后不再处理其他listener
                
                # 正常处理task_updates
                if result.get('task_updates'):
                    await self._apply_task_updates(result['task_updates'], plan_context)
                    
            except Exception as e:
                logger.error(f"Error processing listener {listener.id}: {e}")
                await self._handle_listener_error(listener, e, plan_context)
                
    except Exception as e:
        logger.error(f"Error handling task status change: {e}")

async def _pause_plan_for_params(self, listener: Listener, result: Dict, plan_context: Dict[str, Any]):
    """暂停计划等待参数"""
    try:
        plan_instance_id = plan_context.get("plan_instance_id")
        if not plan_instance_id:
            logger.error("No plan_instance_id in context")
            return
        
        # 更新计划实例状态为PAUSE
        plan_instance = await self.plan_module.get_plan_instance(plan_instance_id)
        if plan_instance:
            plan_instance.status = PlanInstanceStatus.PAUSE.value
            plan_instance.context.update({
                "paused_listener_id": listener.id,
                "required_params": result.get("required_params", {}),
                "pause_reason": "missing_params",
                "pause_timestamp": datetime.now().isoformat()
            })
            
            await self.plan_module.update_plan_instance(plan_instance_id, {
                "status": plan_instance.status,
                "context": plan_instance.context
            })
            
            logger.info(f"Plan instance {plan_instance_id} paused for missing params")
        
    except Exception as e:
        logger.error(f"Error pausing plan for params: {e}")
```

### 4. API 扩展

#### 新增 continue API
```python
@router.post("/plans/{plan_instance_id}/continue")
async def continue_plan(
    plan_instance_id: str,
    params: Dict[str, Any],
    planner_agent = Depends(get_planner_agent)
):
    """继续执行暂停的计划"""
    try:
        result = await planner_agent.continue_plan(plan_instance_id, params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 🧪 测试用例

### 测试场景1: 电脑申请缺少型号
```python
async def test_computer_application_missing_model():
    """测试电脑申请时缺少型号参数"""
    
    # 1. 启动计划（缺少电脑型号）
    plan_instance = await plan_module.start_plan_by_prompt(
        prompt="为张三申请电脑",
        plan_id="apply_computer"
    )
    
    # 2. 等待执行到IT Agent
    await asyncio.sleep(2)
    
    # 3. 检查状态应为PAUSE
    updated_instance = await plan_module.get_plan_instance(plan_instance.id)
    assert updated_instance.status == PlanInstanceStatus.PAUSE.value
    assert "computer_model" in updated_instance.context["required_params"]
    
    # 4. 提供参数继续执行
    continue_result = await planner_agent.continue_plan(
        plan_instance.id,
        {"computer_model": "MacBook Pro"}
    )
    
    # 5. 检查继续执行成功
    assert continue_result["success"] is True
    
    # 6. 最终检查状态
    final_instance = await plan_module.get_plan_instance(plan_instance.id)
    assert final_instance.status in [PlanInstanceStatus.RUNNING.value, PlanInstanceStatus.DONE.value]
```

---

## 🔄 与现有功能的关系

### 与Resume功能的区别
| 功能 | Resume | Continue |
|------|--------|----------|
| 触发条件 | 任务执行失败 | 缺少必需参数 |
| 目标状态 | ERROR → RUNNING | PAUSE → RUNNING |
| 执行方式 | 重新执行失败的listener | 继续执行暂停的listener |
| 参数处理 | 使用原有参数重试 | 使用新提供的参数 |

### 状态转换图
```
正常流程: NOT_STARTED → RUNNING → DONE
错误流程: RUNNING → ERROR → [Resume] → RUNNING
参数流程: RUNNING → PAUSE → [Continue] → RUNNING
```

---

## 📈 实施计划

### Phase 1: 核心功能（1周）
- [ ] 扩展PlanInstanceStatus枚举
- [ ] 修改TaskDriver返回missing_params结果
- [ ] 实现PlannerAgent.continue_plan()方法
- [ ] 添加_pause_plan_for_params()方法

### Phase 2: API集成（3天）
- [ ] 添加continue API端点
- [ ] 更新on_task_status_change()逻辑
- [ ] 添加状态检查逻辑

### Phase 3: 测试验证（3天）
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 端到端测试验证

---

## 🎯 验收标准

1. **功能完整性**:
   - ✅ Agent能识别缺少参数并返回missing_params
   - ✅ PlanInstance能正确进入PAUSE状态
   - ✅ continue() API能正确继续执行
   - ✅ 支持多次参数缺失场景

2. **测试覆盖**:
   - ✅ 单元测试覆盖核心逻辑
   - ✅ 集成测试验证端到端流程
   - ✅ 错误场景测试

3. **性能要求**:
   - ✅ PAUSE/Continue响应时间 < 1秒
   - ✅ 不影响正常执行流程性能

---

**这个功能将大大提升用户体验，让AI员工能够与用户进行交互式对话，而不是遇到问题就失败！**
