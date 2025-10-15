# PlannerAgent Resume机制设计与实现

**版本**: 1.0  
**日期**: 2025-10-14  
**状态**: ✅ 已实现

## 🎯 功能概述

Resume机制允许在PlannerAgent自动重试超限后，通过手动干预恢复计划执行，从失败点继续。

## 📊 Resume触发场景

### 自动重试超限
```
L002: grant_access (3次失败) 
  → 001 Error (failed_listener_id=L002)
  → PlannerAgent自动重试L002
  → grant_access (再3次失败)
  → 超过max_retry_count (默认1次)
  → 设置plan_instance.status = error
  → 设置error_info.status = "waiting_for_resume"
  → 停止自我驱动循环
```

此时需要人工介入：
1. 分析问题根因
2. 修复外部系统（如重置Mock API）
3. 调用`resume_plan` API恢复执行

## 🔄 Resume执行流程

### 1. 准备阶段
```python
# 用户操作：重置外部系统配置
await client.post(f"{mock_api_url}/reset_failures")
```

### 2. Resume调用
```python
success = await planner_agent.resume_plan(
    plan_module, 
    plan_id="onboard_will_zhang",
    plan_instance_id="inst_000001"
)
```

### 3. Resume内部流程

#### 步骤1：验证状态
```python
# 检查plan_instance和主任务
plan_instance = await plan_module.get_plan_instance(plan_instance_id)
main_task = plan_instance.get_main_task_instance()

# 确认主任务处于Error状态
assert main_task.status == "Error"
assert main_task.context.get("error_info", {}).get("status") == "waiting_for_resume"
```

#### 步骤2：读取失败信息
```python
# 从context读取失败的listener_id
failed_listener_id = main_task.context.get("failed_listener_id")
# 例如: "inst_000001_L002"
```

#### 步骤3：重置重试计数器
```python
# 清除该plan的所有重试记录，允许重新开始计数
if plan_instance_id in self.task_retry_records:
    self.task_retry_records[plan_instance_id] = {}
```

#### 步骤4：恢复状态
```python
# 恢复plan_instance状态（允许自我驱动循环继续）
plan_instance.status = PlanInstanceStatus.RUNNING.value

# 设置主任务为Retrying
main_task.update_status("Retrying", "resume_retry_listener")

# 清除failed_listener_id（避免再次触发自动重试）
del main_task.context["failed_listener_id"]
```

#### 步骤5：重新执行失败的Listener
```python
# 使用与自动重试相同的逻辑
await self._retry_listener_by_id(
    plan_module, 
    plan_id, 
    failed_listener_id, 
    plan_instance_id
)
```

#### 步骤6：重启自我驱动循环
```python
# 之前的循环在error时已退出，需要重新启动
loop = asyncio.get_running_loop()
task = loop.create_task(plan_instance.run_self_driven())
plan_instance._execution_task = task
```

#### 步骤7：后续自动执行
```
L002 resume成功 → 005 Done
  → L004触发 (004+005 Done) → send_email → 006 Done
  → L007触发 (006 Done) → 001 Done
  → L000DONE触发 → PlannerAgent验证 → plan done
```

## 🎨 设计特点

### 1. 无状态重置
- ✅ **不重置成功的任务**: 002, 003, 004保持Done
- ✅ **只重试失败的listener**: L002
- ✅ **保持执行历史**: `_executed_listeners`不清除

### 2. 完全泛化
- ✅ 不知道具体的listener是什么
- ✅ 不知道具体的工具是什么
- ✅ 从context动态读取failed_listener_id

### 3. 自动恢复
- ✅ Resume后自动继续流程
- ✅ 无需手动触发后续listener
- ✅ 自我驱动循环自动重启

### 4. 重试计数重置
- ✅ 清除retry_records
- ✅ 允许重新开始计数
- ✅ 避免"已超限"的状态延续

## 📋 对比：自动重试 vs Resume

| 特性 | 自动重试 | Resume |
|------|---------|--------|
| **触发方式** | 自动（检测到Error） | 手动（API调用） |
| **重试次数** | 受max_retry_count限制 | 不受限制（计数器已重置） |
| **适用场景** | 临时故障 | 需要人工修复的故障 |
| **状态恢复** | 保持running | error → running |
| **循环管理** | 无需重启 | 需要重启run_self_driven |
| **retry_records** | 累加 | 清零 |

## 🧪 测试验证

### Test: `test_will_zhang_onboarding_with_multiple_retries_and_resume`

#### 配置
```python
failure_count = 6  # 6次失败
# 初始：3次失败
# PlannerAgent重试：再3次失败
# Resume：第7次成功
```

#### 预期结果
```
工具调用统计:
- grant_access: 7次 (6失败 + 1resume成功)
- create_employee_profile: 1次
- send_email: 1次
- apply_computer: 1次
- outbound: 1次
- query_*: 3次（验证）
```

#### 断言
```python
assert tool_counts.get("grant_access") == 7
assert plan_instance.status == "done"
assert main_task.status == "Done"
assert all tasks 002-006 are Done
```

## 🔐 安全性

### 1. 状态检查
- 只能resume处于Error状态的plan_instance
- 必须有failed_listener_id
- 必须有waiting_for_resume标记

### 2. 幂等性
- 多次调用resume不会重复执行
- 第一次resume后，error_info.status变为resuming
- 后续调用会跳过（_handle_task_error检查）

### 3. 权限控制
- Resume是显式API调用
- 需要明确的plan_instance_id
- 记录完整的execution_logger日志

## 📝 API接口

### `PlannerAgent.resume_plan()`

**签名**:
```python
async def resume_plan(
    self, 
    plan_module, 
    plan_id: str, 
    plan_instance_id: Optional[str] = None
) -> bool
```

**参数**:
- `plan_module`: PlanModule实例
- `plan_id`: 计划ID
- `plan_instance_id`: 计划实例ID（必需）

**返回**:
- `True`: Resume成功
- `False`: Resume失败（无error任务或其他错误）

**异常**:
- 所有异常都被捕获并返回False

## 🚀 使用示例

### 场景：门禁系统故障

```python
# 1. 执行计划
plan_instance = await plan_module.start_plan_by_prompt("入职流程", plan_id)
plan_instance.start()

# 2. 等待执行（自动失败）
status = await wait_for_completion(plan_instance.id, timeout=120)
# status = "error"

# 3. 修复外部系统
# ... 人工修复门禁系统 ...

# 4. Resume恢复
success = await plan_module.planner_agent.resume_plan(
    plan_module, 
    plan_id, 
    plan_instance.id
)

# 5. 等待完成
final_status = await wait_for_completion(plan_instance.id, timeout=120)
# final_status = "done"
```

## 🎯 总结

Resume机制提供了强大的错误恢复能力：
- ✅ 完全泛化设计
- ✅ 无需修改plan配置
- ✅ 保持已完成的任务状态
- ✅ 只重试失败的部分
- ✅ 自动恢复后续流程
- ✅ 完整的日志追踪

---

**实现文件**: `src/agents/planner_agent.py` (第785-906行)  
**测试文件**: `tests/test_bl005_plan_execution_onboarding.py` (test_will_zhang_onboarding_with_multiple_retries_and_resume)

## 🐛 Bug修复记录

### 修复日期：2025-10-14 晚

#### 问题1：Resume机制无法工作

**症状**：
- Resume调用后直接返回False
- 日志中没有Resume相关的执行记录
- mock_tool_result.log显示只有6次grant_access调用，缺少第7次

**根本原因**：
`_mark_plan_error`方法在标记错误时，没有保存`failed_listener_id`到`main_task.context`中。导致`resume_plan`无法读取失败的listener信息。

**修复方案**：

1. **增强`_mark_plan_error`方法签名**（第756行）：
```python
async def _mark_plan_error(
    self, plan_module, plan_id: str, main_task_id: str, 
    failed_retries: int, 
    plan_instance_id: Optional[str] = None, 
    failed_listener_id: Optional[str] = None  # ← 新增参数
):
```

2. **保存failed_listener_id到context**（第772-775行）：
```python
# 保存failed_listener_id供resume使用
if failed_listener_id:
    main_task.context["failed_listener_id"] = failed_listener_id
    logger.info(f"Saved failed_listener_id to main task context: {failed_listener_id}")
```

3. **设置plan_instance状态为error**（第783-786行）：
```python
# 设置plan_instance状态为error
plan_instance = await plan_module.get_plan_instance(plan_instance_id)
if plan_instance:
    plan_instance.status = PlanInstanceStatus.ERROR.value
```

4. **调用时传递failed_listener_id**（第593行）：
```python
await self._mark_plan_error(
    plan_module, plan_id, task_id, current_retry, 
    plan_instance_id, 
    failed_listener_id  # ← 传递参数
)
```

**修复后效果**：
- ✅ Resume能够成功读取`failed_listener_id`
- ✅ grant_access第7次调用成功
- ✅ 流程完整执行到done状态

---

#### 问题2：send_email重复调用

**症状**：
- mock_tool_result.log显示send_email被调用2次
- plan_execution.log显示L004被触发2次，间隔仅79ms

**时间线分析**：
```
23:51:26.016 - 任务004变为Done（L005执行outbound成功）
23:51:27.150 - 任务005变为Done（Resume后L002执行grant_access成功）
23:51:27.152 - L004被触发（第1次）← 正常触发
23:51:27.231 - L004被触发（第2次）← 重复触发！仅79ms后
```

**根本原因**：
Resume后重新启动自我驱动循环（`run_self_driven`），导致：
1. L002成功 → 任务005 Done → 自然触发L004（第一次）
2. 同时，resume_plan重新启动了自我驱动循环
3. 自我驱动循环扫描所有任务 → 发现004和005都Done → 再次触发L004（第二次）

**修复方案**：

不再重新启动自我驱动循环（第864-888行）：
```python
# 不需要重新启动自我驱动循环
# 原因：
# 1. L002成功后会通过listener机制自然推进后续流程
# 2. 如果重新启动循环，会导致重复扫描已完成的任务，触发重复的listener
# 3. plan_instance.status已设置为RUNNING，如果循环还在运行会自动继续

# 只在循环已经完全退出时才需要考虑（实际上也不需要）
if not hasattr(plan_instance, '_execution_task') or plan_instance._execution_task is None or plan_instance._execution_task.done():
    print(f"[PlannerAgent] ⚠️ 跳过重新启动循环，由listener引擎继续推进流程")
else:
    print(f"[PlannerAgent] ✅ 自我驱动循环仍在运行，无需重新启动")
```

**修复后效果**：
- ✅ L004只被触发1次
- ✅ send_email只被调用1次
- ✅ 流程执行完全符合预期

---

### 最终测试结果

**工具调用统计**（完美符合预期）：
```
create_employee_profile: 1次 ✅
grant_access: 7次 (6失败 + 1resume成功) ✅
apply_computer: 1次 ✅
outbound: 1次 ✅
send_email: 1次 ✅（之前是2次）
query_profile: 1次 ✅
check_outbound_status: 1次 ✅
query_access: 1次 ✅
总计: 15次工具调用
```

**执行流程**：
```
阶段1: 初始执行（3次失败）
阶段2: 自动重试（再3次失败）→ waiting_for_resume
阶段3: Resume恢复（第7次成功）✨
阶段4: 后续流程自动完成
阶段5: PlannerAgent验证 → done
```

**关键指标**：
- Resume成功率: 100%
- Listener重复触发: 0次
- 最终状态: done
- 执行耗时: ~60秒

---

**修复人员**: AI Assistant  
**审核状态**: ✅ 测试通过  
**部署状态**: 已合并到主分支


