# PlannerAgent验证机制设计文档

## 核心设计理念

### 完全泛化原则

**PlannerAgent不应该硬编码任何业务知识**：
- ❌ 不知道有哪些系统（如hr、inventory、access）
- ❌ 不知道有哪些工具（如query_profile、check_outbound_status）
- ❌ 不维护工具映射表（如create_employee_profile → query_profile）
- ✅ 所有信息都从**plan config**和**执行记录**中动态提取

## 验证流程详解

### 步骤1：触发验证

当主任务（001）状态变为Done时：
```
L007侦听器执行 → 任务001.status = Done → 
PlanInstance.update_task_status("001", "Done") →
_publish_task_status_change_event() →
planner_callback(plan_id, "001", old_status, "Done", plan_context)
```

### 步骤2：提取已执行的Agent

```python
async def _extract_executed_agents_from_plan(plan_module, plan_id, plan_instance_id):
    """从plan config动态提取已执行的agent"""
    
    # 1. 读取plan配置
    plan = await plan_module.plan_repo.get_by_id(plan_id)
    
    # 2. 遍历所有listeners
    for listener_config in plan.listeners:
        agent_id = listener_config.get('agent_id')
        success_output = listener_config.get('success_output', {})
        target_task_id = success_output.get('task_id')
        
        # 3. 检查该listener执行是否成功（通过success_output的task是否Done）
        task_instance = plan_instance.get_task_instance(target_task_id)
        if task_instance and task_instance.status == "Done":
            # 4. 记录该agent已执行
            executed_agents.append({
                "agent_id": agent_id,
                "task_id": target_task_id,
                "task_name": task_instance.name
            })
    
    return executed_agents
    # 返回示例：
    # [
    #   {"agent_id": "hr", "task_id": "002", "task_name": "新员工注册"},
    #   {"agent_id": "access", "task_id": "005", "task_name": "门禁申请"},
    #   {"agent_id": "it", "task_id": "003", "task_name": "申请电脑"},
    #   {"agent_id": "inventory", "task_id": "004", "task_name": "电脑出库"},
    #   {"agent_id": "email", "task_id": "006", "task_name": "发送欢迎邮件"}
    # ]
```

**关键设计**：
- 不遍历task_instances查找Done的任务
- 而是通过**listeners配置**找到执行了哪些agent
- 通过**success_output的task状态**判断是否成功

### 步骤3：发送验证请求

```python
async def _verify_all_systems(executed_agents, employee_ctx):
    """向所有已执行的agent发送验证请求"""
    
    for agent_info in executed_agents:
        agent_id = agent_info["agent_id"]  # 例如："hr"
        task_name = agent_info["task_name"]  # 例如："新员工注册"
        
        # 构建泛化的语义验证请求
        verification_action = f"请验证任务'{task_name}'是否成功完成。员工信息：姓名={name}, ID={id}"
        
        params = {
            "employee_id": employee_ctx["employee_id"],
            "employee_name": employee_ctx["employee_name"],
            "task_id": agent_info["task_id"],
            "task_name": task_name,
            "action": "verify_task_completion"
        }
        
        # 通过A2A发送请求
        result = await self.a2a.execute(agent_id, verification_action, params)
```

**示例请求**：
- 发给hr agent："请验证任务'新员工注册'是否成功完成。员工信息：姓名=will zhang, ID=WZ001"
- 发给access agent："请验证任务'门禁申请'是否成功完成。员工信息：姓名=will zhang, ID=WZ001"
- 发给inventory agent："请验证任务'电脑出库'是否成功完成。员工信息：姓名=will zhang, ID=WZ001"

### 步骤4：A2A Server处理

```python
# A2AServer.execute_agent()
async def execute_agent(agent_id, action, parameters):
    # 1. 从AgentRuntime获取BizAgent（ReactAgent）
    agent = self._agent_runtime.get_agent(agent_id)
    
    # 2. 构建执行上下文
    context_prompt = f"{action}\n\n参数信息：\n- employee_id: {params['employee_id']}\n..."
    
    # 3. 调用ReactAgent执行
    result = await agent.execute(context_prompt)
    
    # 4. 返回结果
    return {
        "success": result["success"],
        "response": result["response"],
        "tools_used": result["tools_used"]
    }
```

### 步骤5：BizAgent自主决策

**hr agent收到请求**：
```
请求："请验证任务'新员工注册'是否成功完成。员工信息：姓名=will zhang, ID=WZ001"

ReactAgent思考：
- 我有工具：create_employee_profile, query_profile
- 要验证新员工注册，应该调用query_profile
- 参数：employee_id=WZ001, employee_name=will zhang

行动：调用query_profile工具
返回：{"success": true, "verified": true, "tools_used": ["query_profile"]}
```

**access agent收到请求**：
```
请求："请验证任务'门禁申请'是否成功完成。员工信息：姓名=will zhang, ID=WZ001"

ReactAgent思考：
- 我有工具：grant_access, query_access
- 要验证门禁申请，应该调用query_access
- 参数：employee_id=WZ001, employee_name=will zhang

行动：调用query_access工具
返回：{"success": true, "verified": true, "tools_used": ["query_access"]}
```

### 步骤6：PlannerAgent收集结果

```python
verification_results = {
    "hr": {
        "verified": True,
        "response": "员工档案验证成功",
        "tools_used": ["query_profile"],
        "task_id": "002"
    },
    "access": {
        "verified": True,
        "response": "门禁权限验证成功",
        "tools_used": ["query_access"],
        "task_id": "005"
    },
    "inventory": {
        "verified": True,
        "response": "电脑出库验证成功",
        "tools_used": ["check_outbound_status"],
        "task_id": "004"
    }
}

# 更新主任务context
task_001.context["verification_results"] = verification_results
task_001.context["planner_verification"] = "completed"
```

## 组件交互图

```
┌────────────────────────────────────────────────────────────────────┐
│                          Plan Config                               │
│  listeners: [                                                      │
│    {listener_id: L001, agent_id: hr, success_output: {task: 002}} │
│    {listener_id: L002, agent_id: access, success_output: {...}}   │
│    {listener_id: L003, agent_id: it, success_output: {...}}       │
│  ]                                                                 │
└─────────────────────────┬──────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────────┐
│                   PlannerAgent（验证时）                           │
│  1. 读取plan.listeners配置                                         │
│  2. 检查每个listener的success_output.task_id状态                  │
│  3. 如果Done，说明该agent已执行                                    │
│  4. 提取: agent_id, task_id, task_name                            │
└─────────────────────────┬──────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────────┐
│                       A2A请求                                      │
│  PlannerAgent → A2AClient → A2AServer → AgentRuntime → BizAgent   │
│                                                                    │
│  请求内容（泛化语义）：                                             │
│  "请验证任务'新员工注册'是否成功完成。员工：will zhang, WZ001"    │
└─────────────────────────┬──────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────────┐
│                    BizAgent（ReactAgent）                          │
│  1. 接收语义请求                                                   │
│  2. 理解验证意图                                                   │
│  3. 查看自己的工具列表（来自app config）                           │
│  4. 决定调用query_profile工具                                      │
│  5. 通过MCP调用工具                                                │
│  6. 返回验证结果                                                   │
└─────────────────────────┬──────────────────────────────────────────┘
                          ↓
┌────────────────────────────────────────────────────────────────────┐
│                      验证结果                                       │
│  {                                                                 │
│    "success": true,                                                │
│    "response": "员工档案验证成功",                                 │
│    "tools_used": ["query_profile"]                                │
│  }                                                                 │
└────────────────────────────────────────────────────────────────────┘
```

## 关键代码路径

### 1. PlanModule初始化
```python
# tests/test_bl005_plan_execution_onboarding.py
adk_integration = AgentRuntime(mcp_client)
a2a_server = A2AServer()
a2a_client = DefaultA2AClient(a2a_server)

plan_module = PlanModule(
    plan_repo, task_repo, listener_repo,
    adk_integration=adk_integration,
    a2a_client=a2a_client
)
```

### 2. 连接AgentRuntime和A2AServer
```python
# src/core/plan_module.py
async def start():
    # 连接AgentRuntime到A2AServer
    if self.adk_integration and self.a2a_client.a2a_server:
        self.a2a_client.a2a_server.set_agent_runtime(self.adk_integration)
```

### 3. 任务状态更新触发回调
```python
# src/models/plan_instance.py
def update_task_status(task_id, new_status, reason):
    task_instance.update_status(new_status, reason)
    self._publish_task_status_change_event(task_instance, old_status, new_status, reason)

def _publish_task_status_change_event(...):
    # 触发planner_callback
    planner_callback = self._listener_engine._planner_callback
    result = planner_callback(plan_id, task_id, old_status, new_status, plan_context)
    if asyncio.iscoroutine(result):
        asyncio.create_task(result)
```

### 4. PlannerAgent验证
```python
# src/agents/planner_agent.py
async def on_task_status_change(...):
    if is_main_task and new_status == "Done":
        # 提取已执行的agent
        executed_agents = await self._extract_executed_agents_from_plan(...)
        
        # 验证所有系统
        verification_results = await self._verify_all_systems(executed_agents, employee_ctx)
        
        # 更新主任务context
        task_001.context["verification_results"] = verification_results
```

### 5. A2A调用BizAgent
```python
# src/infrastructure/a2a_server.py
async def _execute_agent_internal(agent, request):
    if self._agent_runtime:
        # 构建语义上下文
        context_prompt = f"{request.action}\n\n参数信息：\n..."
        
        # 调用BizAgent（ReactAgent）
        result = await self._agent_runtime.execute_agent(agent_id, context_prompt)
        return result
```

## 预期执行结果

在`mock_tool_result.log`中应该看到：

```json
{"tool": "create_employee_profile", "args": {...}}  // L001: hr agent创建档案
{"tool": "grant_access", "args": {...}}              // L002: access agent授权
{"tool": "apply_computer", "args": {...}}            // L003: it agent申请电脑
{"tool": "outbound", "args": {...}}                  // L005: inventory agent出库
{"tool": "send_email", "args": {...}}                // L004: email agent发邮件
{"tool": "query_profile", "args": {...}}             // PlannerAgent验证hr
{"tool": "query_access", "args": {...}}              // PlannerAgent验证access
{"tool": "check_outbound_status", "args": {...}}     // PlannerAgent验证inventory
```

## 设计优势

### 1. 完全泛化
- 新增业务系统无需修改PlannerAgent代码
- plan config决定一切

### 2. 自动发现
- 通过listeners配置自动发现执行了哪些agent
- 通过success_output判断是否成功

### 3. 智能决策
- BizAgent根据语义请求自主选择验证工具
- 无需PlannerAgent知道具体工具名

### 4. 松耦合
- PlannerAgent与具体业务逻辑完全解耦
- 通过A2A协议实现标准化通信

## 测试验证

在`test_listener_chain_execution_sequence`中验证：
1. ✅ 所有业务工具被正确调用（create_employee_profile等）
2. ✅ send_email只调用1次（防重复机制生效）
3. ✅ 主任务Done后触发PlannerAgent
4. ✅ PlannerAgent通过A2A调用各BizAgent验证
5. ✅ 验证工具被调用（query_profile、query_access、check_outbound_status）
6. ✅ 验证结果写入主任务context

## 实现文件清单

| 文件 | 修改内容 |
|------|---------|
| `src/agents/planner_agent.py` | 完全泛化验证逻辑：从plan config动态提取agent |
| `src/models/plan_instance.py` | 添加planner_callback触发和防重复执行机制 |
| `src/infrastructure/a2a_server.py` | 调用AgentRuntime执行BizAgent而非直接调用工具 |
| `src/core/plan_module.py` | 连接AgentRuntime和A2AServer |
| `tests/test_bl005_plan_execution_onboarding.py` | 正确初始化所有依赖组件 |
| `doc/System_Execution_Flow.md` | 添加验证机制设计文档 |

---

**设计日期**: 2025-10-13  
**版本**: v1.0  
**状态**: ✅ 已实现

