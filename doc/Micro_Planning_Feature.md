# 微动态规划功能说明

## 概述

微动态规划是 AIntegration 的智能错误恢复机制，让 PlannerAgent 能够自动处理任务失败、重试和计划恢复。这是向完全动态规划演进的第一步。

## 核心功能

### 1. 任务失败自动重试

当任务执行失败时，PlannerAgent 会自动重试该任务：

- **监控失败**: Planner 监听所有任务状态变化，捕获 Error 状态
- **智能重试**: 根据重试策略决定是否重试（默认最多 3 次）
- **状态重置**: 将失败任务重置为 NotStarted，触发侦听器重新执行
- **记录追踪**: 在任务上下文中记录重试次数和时间

**示例**:
```python
# 门禁申请失败
Task 005: Running -> Error (第1次失败)
Planner: 自动重试，重置为 NotStarted
Task 005: NotStarted -> Running (重试执行)
```

### 2. 超过重试次数的处理

当任务失败次数超过最大重试次数时：

- **子任务失败**: 将主任务设置为 Error 状态
- **主任务失败**: 保持 Error 状态，等待人工 resume
- **错误记录**: 在主任务上下文中记录错误信息

**示例**:
```python
# 任务失败超过 3 次
Task 005: Error (第3次失败)
Planner: 超过重试次数，设置主任务为 Error
Task 001: Running -> Error
主任务上下文: {
    "error_info": {
        "failed_retries": 3,
        "status": "waiting_for_resume",
        "message": "Task failed after 3 retries"
    }
}
```

### 3. 计划恢复 (Resume)

通过 API 或代码恢复错误状态的计划：

- **重置计数器**: 清除所有任务的重试计数
- **重新执行**: 触发错误任务重新执行
- **继续流程**: 从失败点继续执行后续流程

**API 端点**:
```http
POST /plans/{plan_id}/resume
```

**代码调用**:
```python
success = await plan_module.planner_agent.resume_plan(plan_module, plan_id)
```

## 工作流程

### 正常流程（单次失败后成功）

```
1. 任务执行 -> 失败 (Error)
2. Planner 监听到失败
3. 检查重试次数 (1 < 3)
4. 重置任务状态 (NotStarted)
5. 侦听器重新触发
6. 任务执行 -> 成功 (Done)
7. 流程继续
```

### 失败流程（超过重试次数）

```
1. 任务执行 -> 失败 (Error)
2. Planner 重试 -> 失败 (Error)  [第2次]
3. Planner 重试 -> 失败 (Error)  [第3次]
4. Planner: 超过重试次数
5. 主任务 -> Error 状态
6. 等待人工 resume
```

### Resume 流程

```
1. 人工检查和修复问题
2. 调用 resume API
3. Planner 重置重试计数器
4. 重新触发失败任务
5. 任务执行 -> 成功
6. 流程完成
```

## 配置说明

### 重试次数配置

```python
# 在 PlannerAgent 初始化时配置
planner_agent = PlannerAgent(
    a2a_client=a2a_client,
    llm_client=llm_client,
    max_retry_count=3  # 默认 3 次
)

# 运行时修改
plan_module.planner_agent.max_retry_count = 5
```

### 侦听器失败配置

代码侦听器通过 `result.success` 字段判断失败：

```yaml
listener:
  listener_type: code
  code_snippet: |
    # 返回失败
    result = {
        "success": False,
        "target_task": "002",
        "target_status": "Error",
        "context": {"error": "门禁系统故障"}
    }
  failure_output:
    task_id: "002"
    status: "Error"
    context: {"error": "门禁系统故障"}
```

## 测试验证

### 测试场景

1. **BL014: 基础重试测试**
   - 测试单任务失败重试
   - 验证重试计数正确

2. **BL005: 端到端重试测试**
   - Will Zhang 入职流程
   - 门禁失败 1 次后重试成功

3. **BL005: Resume 场景测试**
   - 多任务失败超过重试次数
   - Resume 后流程成功完成

### 测试结果

```
✅ test_task_failure_with_retry - 任务失败自动重试
✅ test_will_zhang_onboarding_with_retry_success - 门禁失败后重试成功  
✅ test_simple_retry_and_resume - 简化 Resume 场景
```

## 未来演进

### 短期优化
1. **智能重试策略**: 根据错误类型决定重试次数
2. **指数退避**: 重试间隔逐渐增加
3. **部分重试**: 只重试失败的步骤

### 中期演进
1. **LLM 决策**: 让 LLM 分析错误并决定重试策略
2. **动态调整**: 根据系统负载调整重试策略
3. **监控告警**: 集成监控系统，自动告警

### 长期目标（完全动态规划）
1. **自动诊断**: LLM 分析失败原因
2. **动态任务生成**: 自动生成修复任务
3. **自愈能力**: 系统自动修复问题
4. **学习优化**: 从历史失败中学习

## 技术细节

### 核心代码

**PlannerAgent 重试逻辑** (`src/agents/planner_agent.py`):
```python
async def _handle_task_error(self, plan_module, plan_id, task_id, ...):
    current_retry = self.task_retry_records[plan_id].get(task_id, 0)
    max_retries = await self._decide_retry_strategy(...)
    
    if current_retry < max_retries:
        # 重试
        await self._retry_task(plan_module, task_id, current_retry + 1)
    else:
        # 超过重试次数
        await self._mark_plan_error(...)
```

**TaskDriver 失败判断** (`src/core/task_driver.py`):
```python
def determine_task_updates(self, listener, execution_result):
    # 检查内部 result.success 字段
    if execution_result.get("success") and "result" in execution_result:
        inner_result = execution_result["result"]
        if isinstance(inner_result, dict) and "success" in inner_result:
            is_success = inner_result.get("success", False)
```

**Resume API** (`src/api/plan_api.py`):
```python
@router.post("/{plan_id}/resume")
async def resume_plan(plan_id: str, plan_manager = Depends(...)):
    success = await plan_manager.planner_agent.resume_plan(
        plan_manager, plan_id
    )
    return {"message": "Plan resumed successfully"}
```

## 业务价值

1. **提升可靠性**: 自动处理临时故障，减少人工干预
2. **降低成本**: 避免因临时故障导致的流程中断
3. **改善体验**: 用户无感知的自动恢复
4. **数据洞察**: 记录失败和重试数据，用于优化

---

**文档版本**: v1.0  
**创建日期**: 2025-09-30  
**维护者**: AIntegration 开发团队
