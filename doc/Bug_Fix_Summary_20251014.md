# Bug修复总结 - 2025-10-14

## 问题背景

运行`test_listener_chain_execution_sequence`测试时发现多个问题：
1. 侦听器被重复触发（create_employee_profile调用4次）
2. send_email被调用2次
3. PlannerAgent验证未执行（缺少query_*工具调用）

## 核心修复

### 1. 侦听器重复触发bug

**文件**：`src/core/listener_engine.py` (第62-110行)

**问题**：
```python
# 旧逻辑：只在第3个分支检查trigger_task_id
elif plan_instance and any(op in condition for op in ['.status', '&&', '||', '!=']):
    if self._evaluate_condition(condition, plan_instance):
        matched = True  # BUG：没检查trigger_task_id是否匹配！
```

**修复**：
```python
# 新逻辑：在所有检查前先验证trigger_task_id
if task_id not in listener_trigger_ids:
    continue  # 不匹配直接跳过

# 然后才检查条件
```

### 2. send_email重复调用

**文件**：`src/models/plan_instance.py` (第40, 217-228行)

**问题**：L004监听"004,005"，两个任务都Done时被触发2次

**修复**：
```python
# 添加已执行侦听器集合
_executed_listeners: Optional[set] = None

# 执行前检查
if listener.id in self._executed_listeners:
    continue
self._executed_listeners.add(listener.id)
```

### 3. PlannerAgent验证未触发

**文件**：`src/models/plan_instance.py` (第392-451行)

**问题**：`_publish_task_status_change_event`只记录日志，没有触发planner_callback

**修复**：
```python
def _publish_task_status_change_event(...):
    # 构建plan_context
    plan_context = {...}
    
    # 调用planner_callback
    result = planner_callback(plan_id, task_id, old_status, new_status, plan_context)
    
    # 创建异步任务
    if asyncio.iscoroutine(result):
        self._planner_verification_task = asyncio.create_task(result)
```

### 4. PlannerAgent完全泛化设计

**文件**：`src/agents/planner_agent.py` (第177-233行)

**关键设计原则**：
- ❌ 不硬编码系统列表（如["hr", "access", "inventory"]）
- ❌ 不硬编码工具映射（如create_employee_profile → query_profile）
- ✅ 从plan.listeners动态提取已执行的agent
- ✅ 通过success_output的task状态判断是否成功

**实现**：
```python
async def _extract_executed_agents_from_plan():
    # 遍历plan.listeners
    for listener_config in plan.listeners:
        target_task_id = listener_config['success_output']['task_id']
        task_instance = plan_instance.get_task_instance(target_task_id)
        
        if task_instance.status == "Done":
            agent_id = listener_config['agent_id']
            executed_agents.append({"agent_id": agent_id, "task_id": target_task_id})
```

### 5. A2A调用BizAgent

**文件**：`src/infrastructure/a2a_server.py` (第119-170行)

**问题**：把语义请求当作tool name直接调用Mock API

**修复**：
```python
async def _execute_agent_internal(agent, request):
    # 从AgentRuntime获取BizAgent
    context_prompt = f"{request.action}\n\n参数信息：\n..."
    
    # 调用ReactAgent执行
    result = await self._agent_runtime.execute_agent(agent_id, context_prompt)
    return result
```

### 6. 组件初始化和连接

**文件**：
- `src/core/plan_module.py` (第151, 226-228行)
- `src/infrastructure/adk_integration.py` (第348-393行)
- `tests/test_bl005_plan_execution_onboarding.py` (第298-329行)

**修复**：
```python
# PlanModule保存adk_integration引用
self.adk_integration = adk_integration

# 连接AgentRuntime和A2AServer
if self.adk_integration and self.a2a_client.a2a_server:
    self.a2a_client.a2a_server.set_agent_runtime(self.adk_integration)

# AgentRuntime加载agents
adk_integration.load_agents_from_config("config/apps")
```

### 7. 计划完成判断

**文件**：`src/models/plan_instance.py` (第192-213行)

**关键设计**：
```python
def _is_plan_completed():
    # 检查主任务Done
    if main_task.status != "Done":
        return False
    
    # 检查PlannerAgent验证完成
    if main_task.context.get("planner_verification") == "completed":
        return True
    
    # 主任务Done但验证未完成，继续等待
    return False
```

## 测试结果

**预期工具调用顺序**（共8个，每个1次）：
```
1. create_employee_profile  (L001: hr agent)
2. grant_access            (L002: access agent)
3. apply_computer          (L003: it agent)
4. outbound               (L005: inventory agent)
5. send_email             (L004: email agent)
--- PlannerAgent验证阶段 ---
6. query_profile          (验证hr)
7. query_access           (验证access)
8. check_outbound_status  (验证inventory)
```

## 设计文档

详细设计见：
- `doc/Planner_Verification_Design.md` - 验证机制完整设计
- `doc/System_Execution_Flow.md` - 执行流程文档（已更新）

---

**修复日期**：2025-10-14
**测试状态**：✅ 通过

