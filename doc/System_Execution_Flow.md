# 系统执行流程设计文档

## 概述

本文档描述了AIntegration框架的完整执行流程，包括系统启动、Agent注册、计划执行等关键步骤。

## 系统工作顺序

### 0. 系统启动阶段

1. **启动A2A Server**
   - 负责Agent注册、发现和通信
   - 提供Agent管理功能

2. **启动MCP Server**
   - 负责工具注册和调用
   - 加载config/apps目录下的系统配置

### 1. 系统配置加载阶段

**加载apps下的系统配置文件**
- 扫描`config/apps/`目录下的所有YAML配置文件
- 每个系统配置生成一个BizAgent
- 通过提示词将app的描述和工具集合传给BizAgent

**配置文件格式示例**：
```yaml
name: hr
system_context: "你是一个HR系统的专业代理，负责处理员工入职相关的所有操作"
tools:
  - name: create_employee_profile
    description: 在HR系统中创建员工档案
    endpoint: ${MOCK_API_URL:http://127.0.0.1:8009}/tool
    parameters:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        department:
          type: string
      required: [id, name, department]
```

### 2. 自动Agent注册阶段

**系统自动将BizAgent注册到A2A Server**
- 通过`AgentConfigLoader`加载所有配置
- 自动生成Agent卡片
- 批量注册到A2A Server
- **测试中不应该手动注册agent**

### 3. 测试执行阶段

**测试时启动Mock API Server**
- 提供模拟API响应
- 参考代码中的Mock API实现
- MCP Client调用工具时返回模拟结果
- 将执行结果写入log文件

## 关键组件

### AgentConfigLoader
- 位置：`src/core/agent_config_loader.py`
- 功能：从config/apps目录加载所有BizAgent配置
- 方法：
  - `load_all_agents()`: 加载所有Agent配置
  - `get_all_agent_cards()`: 生成Agent卡片

### PlanModule
- 位置：`src/core/plan_module.py`
- 功能：管理计划、任务、侦听器
- 方法：
  - `_auto_register_agents()`: 自动注册所有BizAgent到A2A Server
  - `start()`: 启动计划模块并自动注册agents

### MCP Server
- 位置：`src/infrastructure/mcp_server.py`
- 功能：管理工具注册和调用
- 方法：
  - `load_tools_from_directory()`: 从目录加载所有应用工具配置

## 测试最佳实践

1. **不要手动注册Agent**：让系统自动处理
2. **使用Mock API Server**：提供模拟响应
3. **检查日志文件**：验证执行结果
4. **遵循系统流程**：按照正确的启动顺序

## 配置文件结构

```
config/apps/
├── hr.yaml          # HR系统配置
├── access.yaml      # 门禁系统配置
├── it.yaml          # IT系统配置
├── email.yaml       # 邮件系统配置
├── inventory.yaml   # 库存系统配置
└── contract.yaml    # 合同系统配置
```

## 执行流程图

```
启动A2A Server
    ↓
启动MCP Server
    ↓
加载config/apps配置
    ↓
生成BizAgent
    ↓
自动注册到A2A Server
    ↓
启动PlanModule
    ↓
执行计划实例
    ↓
调用Mock API
    ↓
写入执行日志
```

## PlannerAgent验证机制设计

### 核心设计原则

**PlannerAgent不知道具体工具**：
- PlannerAgent不读取config/apps目录下的配置
- 不知道query_profile、query_access、check_outbound_status等具体工具名称
- 只知道需要向哪些系统（BizAgent）发送验证请求

### 验证流程

#### 1. 触发时机
当主任务（001）状态变为Done时：
```
L007 code侦听器执行 → 任务001状态变为Done → 
触发planner_callback → PlannerAgent.on_task_status_change()
```

#### 2. PlannerAgent的职责（完全泛化设计）

```python
# 第1步：从plan config中提取已执行的agent列表
executed_agents = await self._extract_executed_agents_from_plan(plan_module, plan_id, plan_instance_id)
# 返回：[{"agent_id": "hr", "task_id": "002", "task_name": "新员工注册"}, ...]

# 第2步：对每个agent发送验证请求
for agent_info in executed_agents:
    agent_id = agent_info["agent_id"]
    task_name = agent_info["task_name"]
    
    # 构建语义验证请求
    verification_action = f"请验证任务'{task_name}'是否成功完成。员工信息：姓名={name}, ID={id}"
    
    # 通过A2A发送请求
    await self.a2a.execute(agent_id, verification_action, params)
```

**关键设计原则**：
- ✅ **完全泛化**：不硬编码任何agent_id（如"hr"、"inventory"）
- ✅ **从配置提取**：通过plan.listeners配置动态发现执行了哪些agent
- ✅ **任务状态判断**：检查success_output对应的任务是否Done
- ✅ **语义请求**：发送任务级别的验证请求，不指定具体工具
- ✅ **BizAgent自主**：由BizAgent自己决定调用query_profile还是其他验证工具

#### 3. BizAgent的职责

各BizAgent收到验证请求后：
- **自己理解**验证请求的语义
- **自己决定**调用哪个验证工具
- **自己执行**工具调用
- **返回结果**给PlannerAgent

**示例**：
```
PlannerAgent → hr agent: "请验证员工WZ001的状态"
hr agent收到请求 → 理解语义 → 决定调用query_profile工具 → 执行调用 → 返回结果

PlannerAgent → access agent: "请验证员工WZ001的门禁状态"  
access agent收到请求 → 理解语义 → 决定调用query_access工具 → 执行调用 → 返回结果

PlannerAgent → inventory agent: "请验证员工WZ001的电脑出库状态"
inventory agent收到请求 → 理解语义 → 决定调用check_outbound_status工具 → 执行调用 → 返回结果
```

### 设计优势

1. **解耦性**：PlannerAgent与具体工具实现解耦
2. **扩展性**：新增验证工具无需修改PlannerAgent代码
3. **智能化**：各BizAgent根据语义自主决策
4. **灵活性**：不同系统可以用不同的验证方式

### 执行记录

PlannerAgent维护执行轨迹：
```python
self.plan_run_logs: Dict[str, List[Dict[str, Any]]] = {}
# 记录内容：
# - task_status_change: 任务状态变化
# - listener_update: 侦听器执行更新
# - verification_request: 验证请求
# - verification_result: 验证结果
```

### 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 任务001状态变为Done                                       │
│    PlanInstance.update_task_status("001", "Done")           │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. 发布状态变化事件                                          │
│    _publish_task_status_change_event()                      │
│    → 触发planner_callback                                   │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. PlannerAgent处理                                          │
│    PlannerAgent.on_task_status_change()                     │
│    → 识别主任务Done → 开始验证                              │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. 通过A2A发送验证请求                                       │
│    for agent_id in ["hr", "access", "inventory"]:          │
│        a2a.execute(agent_id, "请验证员工状态", params)      │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. BizAgent执行验证                                          │
│    hr agent → 调用 query_profile                            │
│    access agent → 调用 query_access                         │
│    inventory agent → 调用 check_outbound_status             │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. 返回验证结果                                              │
│    PlannerAgent收集所有结果 → 更新主任务context            │
│    task_001.context["verification_results"] = {...}        │
└─────────────────────────────────────────────────────────────┘
```

## 默认错误处理机制

### 错误侦听器（类似Done侦听器）

**设计原则**：与"001 Done触发验证"类似，"001 Error触发重试"也是默认机制

#### 1. 自动Error设置（无需配置）
```python
# TaskDriver默认行为：任何listener执行失败
if not is_success and not listener.failure_output:
    # 自动设置主任务001为Error
    updates.append({
        "task_id": "001",
        "status": "Error",
        "context": {
            "failed_listener_id": listener.id,  # 记录失败的侦听器
            "error": execution_result.get("error")
        }
    })
```

#### 2. 自动重试（默认侦听器）
```
001状态变为Error → 触发planner_callback → PlannerAgent.on_task_status_change()
  ↓
PlannerAgent._handle_task_error()
  ↓
从task_001.context读取failed_listener_id
  ↓
检查重试次数 < max_retry_count
  ↓
重置task_001.status = "Running"（清除Error）
  ↓
重新执行失败的侦听器
  ↓
成功 → 继续正常流程
失败 → 再次Error → 继续重试（直到达到max_retry_count）
```

#### 3. 重试流程示例
```
L002执行 → grant_access失败
  ↓
TaskDriver设置：
  task_001.status = "Error"
  task_001.context["failed_listener_id"] = "inst_000001_L002"
  ↓
PlannerAgent检测到Error
  ↓
读取failed_listener_id = "inst_000001_L002"
  ↓
重试次数1 < max_retry_count(3)
  ↓
重置：task_001.status = "Running"
清除：task_001.context["failed_listener_id"]
  ↓
重新执行L002 → grant_access
  ↓
成功 → task_005 = "Done" → 触发后续侦听器 → 继续执行
```

## 注意事项

1. **Agent ID匹配**：确保计划配置中的agent_id与配置文件中的name字段匹配
2. **环境变量**：正确设置MOCK_API_URL等环境变量
3. **端口管理**：测试时使用动态端口避免冲突
4. **资源清理**：测试完成后正确清理资源
5. **验证工具**：每个BizAgent的app配置应包含对应的验证工具（如query_profile）
6. **A2A通信**：PlannerAgent与BizAgent之间通过A2A协议通信，发送语义请求
7. **错误处理**：工具失败自动触发重试，无需在plan config中配置failure_output
8. **重试次数**：默认max_retry_count=3，可通过PlannerAgent配置调整
