# AIntegration 系统架构设计文档

## 1. 系统架构概述

### 1.1 整体架构图
```
┌─────────────────────────────────────────────────────────────────┐
│                        用户请求层                                │
│  "张三入职" → Planner模块 → 查找/创建Plan → 启动执行            │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                        核心执行层                                │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐│
│ │   计划模块       │    │  任务侦听模块    │    │  Atom Agent模块 ││
│ │ (Plan Module)   │    │(Task Listener) │    │ (Atom Agents)   ││
│ └─────────────────┘    └─────────────────┘    └─────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                        基础设施层                                │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐│
│ │   MCP Server    │    │   A2A Server    │    │   ADK Framework ││
│ │  (工具注册)      │    │ (Agent注册发现) │    │  (智能体框架)   ││
│ └─────────────────┘    └─────────────────┘    └─────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│                        数据存储层                                │
│ ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐│
│ │   Plan DB       │    │   Task DB       │    │   Execution DB  ││
│ │  (计划持久化)    │    │ (任务持久化)    │    │ (执行记录)      ││
│ └─────────────────┘    └─────────────────┘    └─────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 模块交互流程图
```
用户请求: "张三入职"
    ↓
┌─────────────────────────────────────────────────────────────────┐
│                        Planner模块                              │
│ 1. 理解意图 → 2. 搜索匹配Plan → 3. 创建新Plan → 4. 启动执行    │
└─────────────────────────────────────────────────────────────────┘
    ↓ (启动Plan执行)
┌─────────────────────────────────────────────────────────────────┐
│                        任务侦听模块                              │
│ 1. 接收Agent输出 → 2. 更新任务状态 → 3. 触发侦听器 → 4. 启动Agent│
└─────────────────────────────────────────────────────────────────┘
    ↓ (Agent执行请求)
┌─────────────────────────────────────────────────────────────────┐
│                        Atom Agent模块                           │
│ 1. 接收执行指令 → 2. 调用MCP工具 → 3. 执行API调用 → 4. 返回结果 │
└─────────────────────────────────────────────────────────────────┘
    ↓ (返回执行结果)
┌─────────────────────────────────────────────────────────────────┐
│                        任务侦听模块                              │
│ 5. 处理Agent结果 → 6. 更新任务状态 → 7. 触发下一轮侦听循环      │
└─────────────────────────────────────────────────────────────────┘
    ↓ (循环执行直到Main Task完成)
┌─────────────────────────────────────────────────────────────────┐
│                        执行完成                                  │
│ 记录执行日志 → 更新执行状态 → 返回结果给用户                    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 核心模块职责
- **Planner模块**：智能规划，处理用户请求，创建和调整执行计划
- **任务侦听模块**：事件驱动的任务状态管理和Agent调度
- **计划模块**：Plan和Task的持久化管理
- **Atom Agent模块**：具体业务逻辑执行，API调用
- **基础设施模块**：提供Agent框架、工具注册、服务发现等支持

## 2. 任务侦听模块 (Task Listener Module)

### 2.1 模块职责
- **任务状态管理**：接收Agent输出，更新任务状态和上下文
- **侦听器调度**：状态变化时触发相关侦听器
- **条件检查**：评估侦听器的触发条件
- **Agent启动**：条件满足时启动对应的Agent

### 2.2 核心组件

#### 2.2.1 任务状态管理器 (Task State Manager)
```python
class TaskStateManager:
    def update_task_status(self, task_id: str, status: str, context: dict):
        """更新任务状态和上下文"""
        # 1. 更新数据库中的任务状态
        # 2. 触发状态变化事件
        # 3. 通知侦听器调度器
        pass
    
    def get_task_context(self, task_id: str) -> dict:
        """获取任务上下文"""
        pass
    
    def batch_update_tasks(self, updates: List[TaskUpdate]):
        """批量更新多个任务状态"""
        pass
```

#### 2.2.2 侦听器调度器 (Listener Scheduler)
```python
class ListenerScheduler:
    def on_task_status_changed(self, task_id: str, old_status: str, new_status: str):
        """任务状态变化事件处理"""
        # 1. 查找监听该任务状态变化的侦听器
        # 2. 检查每个侦听器的触发条件
        # 3. 条件满足时启动对应的Agent
        pass
    
    def evaluate_condition(self, listener: Listener, context: dict) -> bool:
        """评估侦听器触发条件"""
        # 支持复杂的多任务状态组合条件
        pass
    
    def trigger_agent(self, listener: Listener, context: dict):
        """触发Agent执行"""
        # 1. 构建Agent输入上下文
        # 2. 调用Agent执行
        # 3. 处理Agent返回结果
        pass
```

### 2.3 执行流程
```
Agent输出 → 任务状态管理器 → 更新任务状态 → 触发侦听器调度器
    ↓
侦听器调度器 → 查找相关侦听器 → 检查触发条件 → 启动Agent
    ↓
Agent执行 → 返回结果 → 循环执行
```

## 3. 计划模块 (Plan Module)

### 3.1 模块职责
- **Plan管理**：Plan的创建、编辑、持久化
- **Task管理**：Task的定义、状态跟踪、上下文管理
- **侦听器管理**：侦听器配置的存储和查询
- **查询接口**：提供丰富的查询接口支持Agent获取上下文

### 3.2 核心组件

#### 3.2.1 Plan管理器 (Plan Manager)
```python
class PlanManager:
    def create_plan(self, plan_config: dict) -> str:
        """创建新的执行计划"""
        pass
    
    def update_plan(self, plan_id: str, updates: dict):
        """更新计划配置"""
        pass
    
    def get_plan(self, plan_id: str) -> Plan:
        """获取计划详情"""
        pass
    
    def search_plans(self, criteria: dict) -> List[Plan]:
        """搜索匹配的计划"""
        pass
```

#### 3.2.2 Task管理器 (Task Manager)
```python
class TaskManager:
    def create_task(self, task_config: dict) -> str:
        """创建任务"""
        pass
    
    def update_task(self, task_id: str, updates: dict):
        """更新任务"""
        pass
    
    def get_task(self, task_id: str) -> Task:
        """获取单个任务"""
        pass
    
    def get_plan_tasks(self, plan_id: str) -> List[Task]:
        """获取计划的所有任务"""
        pass
    
    def get_task_context(self, task_id: str) -> dict:
        """获取任务上下文"""
        pass
```

#### 3.2.3 侦听器管理器 (Listener Manager)
```python
class ListenerManager:
    def create_listener(self, listener_config: dict) -> str:
        """创建侦听器"""
        pass
    
    def get_listeners_by_task(self, task_id: str) -> List[Listener]:
        """获取监听特定任务的侦听器"""
        pass
    
    def get_listeners_by_trigger(self, task_id: str, status: str) -> List[Listener]:
        """获取特定触发条件的侦听器"""
        pass
```

### 3.3 Few-shot学习支持
```json
{
  "few_shot_examples": [
    {
      "scenario": "新员工入职",
      "plan_template": {
        "tasks": [...],
        "listeners": [...]
      },
      "modification_guide": "如何根据具体需求修改计划"
    }
  ]
}
```

## 4. Atom Agent模块

### 4.1 模块职责
- **API工具注册**：将IT系统API注册到MCP Server
- **Agent实现**：基于ReAct模式的智能体
- **系统隔离**：每个Agent只访问授权的API
- **Agent注册**：向A2A Server注册Agent能力

### 4.2 技术选型

#### 4.2.1 Agent框架选择
**推荐：Google ADK (Agent Development Kit)**
- ✅ 完整的ReAct实现
- ✅ 工具调用标准化
- ✅ 上下文管理完善
- ✅ 与MCP协议兼容
- ✅ 企业级支持和文档

**备选方案：**
- LangChain Agent
- AutoGen
- CrewAI

#### 4.2.2 Agent实现架构
```python
class BizAgent:
    def __init__(self, agent_config: dict):
        self.agent_id = agent_config['agent_id']
        self.system_context = agent_config['system_context']
        self.allowed_tools = agent_config['allowed_tools']
        self.mcp_client = MCPClient()
        self.a2a_client = A2AClient()
    
    def execute(self, prompt: str, context: dict) -> dict:
        """执行Agent任务"""
        # 1. 构建系统上下文
        # 2. 调用大模型进行推理
        # 3. 执行工具调用
        # 4. 返回执行结果
        pass
    
    def register_tools(self):
        """注册允许的工具"""
        for tool in self.allowed_tools:
            self.mcp_client.register_tool(tool)
    
    def register_to_a2a(self):
        """向A2A Server注册"""
        agent_card = self.build_agent_card()
        self.a2a_client.register_agent(agent_card)
```

### 4.3 Agent配置示例
```json
{
  "agent_id": "hr_agent_v1",
  "agent_name": "HR系统代理",
  "system_context": "你是一个HR系统的专业代理，负责处理员工相关的所有操作",
  "allowed_tools": [
    "create_employee",
    "update_employee",
    "get_employee_info"
  ],
  "mcp_tools": [
    {
      "name": "create_employee",
      "endpoint": "https://hr-api.company.com/employees",
      "method": "POST",
      "schema": {...}
    }
  ]
}
```

## 5. Planner模块

### 5.1 模块职责
- **请求处理**：接收用户请求，理解意图
- **计划查找**：搜索现有的匹配计划
- **计划创建**：基于Few-shot学习创建新计划
- **执行监控**：监控计划执行，处理异常
- **计划调整**：根据执行情况动态调整计划

### 5.2 核心组件

#### 5.2.1 请求处理器 (Request Handler)
```python
class RequestHandler:
    def process_request(self, user_request: str) -> ExecutionPlan:
        """处理用户请求"""
        # 1. 理解用户意图
        # 2. 搜索匹配的计划
        # 3. 如果找到，直接执行
        # 4. 如果没找到，创建新计划
        pass
    
    def understand_intent(self, request: str) -> dict:
        """理解用户意图"""
        pass
    
    def search_matching_plans(self, intent: dict) -> List[Plan]:
        """搜索匹配的计划"""
        pass
```

#### 5.2.2 计划生成器 (Plan Generator)
```python
class PlanGenerator:
    def create_plan_from_intent(self, intent: dict) -> Plan:
        """根据意图创建计划"""
        # 1. 使用Few-shot学习
        # 2. 参考现有计划模板
        # 3. 生成任务和侦听器配置
        pass
    
    def adapt_plan_template(self, template: Plan, requirements: dict) -> Plan:
        """适配计划模板"""
        pass
```

#### 5.2.3 执行监控器 (Execution Monitor)
```python
class ExecutionMonitor:
    def monitor_execution(self, execution_id: str):
        """监控计划执行"""
        # 1. 跟踪任务执行状态
        # 2. 检测异常情况
        # 3. 触发计划调整
        pass
    
    def handle_execution_error(self, execution_id: str, error: Exception):
        """处理执行错误"""
        # 1. 分析错误原因
        # 2. 决定是否需要重新规划
        # 3. 启动ResiliencePlan
        pass
```

### 5.3 执行记录和回溯
```json
{
  "execution_id": "exec_001",
  "user_request": "张三入职",
  "plan_id": "plan_101",
  "start_time": "2024-01-01T10:00:00Z",
  "status": "running",
  "execution_log": [
    {
      "timestamp": "2024-01-01T10:00:00Z",
      "event": "plan_started",
      "details": {...}
    },
    {
      "timestamp": "2024-01-01T10:01:00Z",
      "event": "task_status_changed",
      "task_id": "001",
      "old_status": "NotStarted",
      "new_status": "Running"
    }
  ]
}
```

## 6. 基础设施模块

### 6.1 MCP Server
**职责**：工具注册和调用管理
```yaml
mcp_server:
  version: "1.0"
  features:
    - tool_registration
    - tool_discovery
    - tool_execution
    - authentication
  protocols:
    - http
    - websocket
    - grpc
```

### 6.2 A2A Server
**职责**：Agent注册发现和通信
```yaml
a2a_server:
  version: "1.0"
  features:
    - agent_registration
    - agent_discovery
    - agent_communication
    - health_monitoring
  protocols:
    - a2a_protocol_v1
    - http_rest
    - websocket
```

### 6.3 Google ADK集成
```python
class ADKIntegration:
    def __init__(self):
        self.adk_client = GoogleADKClient()
    
    def create_react_agent(self, config: dict) -> ReactAgent:
        """创建ReAct Agent"""
        return self.adk_client.create_agent(
            system_prompt=config['system_prompt'],
            tools=config['tools'],
            model=config['model']
        )
```

## 7. 数据存储设计

### 7.1 数据库架构
```sql
-- 计划表
CREATE TABLE plans (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255),
    description TEXT,
    config JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 任务表
CREATE TABLE tasks (
    id VARCHAR(255) PRIMARY KEY,
    plan_id VARCHAR(255),
    name VARCHAR(255),
    prompt TEXT,
    status VARCHAR(50),
    context JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 侦听器表
CREATE TABLE listeners (
    id VARCHAR(255) PRIMARY KEY,
    plan_id VARCHAR(255),
    trigger_task_id VARCHAR(255),
    trigger_condition VARCHAR(500),
    action_condition VARCHAR(500),
    agent_id VARCHAR(255),
    action_prompt TEXT,
    success_output JSON,
    failure_output JSON
);

-- 执行记录表
CREATE TABLE executions (
    id VARCHAR(255) PRIMARY KEY,
    user_request TEXT,
    plan_id VARCHAR(255),
    status VARCHAR(50),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    execution_log JSON
);
```

## 8. 部署架构

### 8.1 微服务部署
```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Planner       │  │  Task Listener  │  │  Plan Module    │
│   Service       │  │  Service        │  │  Service        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Atom Agent    │  │   MCP Server    │  │   A2A Server    │
│   Service       │  │   Service       │  │   Service       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 8.2 容器化部署
```yaml
# docker-compose.yml
version: '3.8'
services:
  planner-service:
    image: aintegration/planner:latest
    ports:
      - "8001:8000"
  
  task-listener-service:
    image: aintegration/task-listener:latest
    ports:
      - "8002:8000"
  
  plan-module-service:
    image: aintegration/plan-module:latest
    ports:
      - "8003:8000"
  
  mcp-server:
    image: aintegration/mcp-server:latest
    ports:
      - "8004:8000"
  
  a2a-server:
    image: aintegration/a2a-server:latest
    ports:
      - "8005:8000"
```

## 9. 技术选型详细说明

### 9.1 Google ADK vs 其他Agent框架对比

| 框架 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| **Google ADK** | ✅ 完整的ReAct实现<br>✅ 企业级支持<br>✅ 与MCP兼容<br>✅ 文档完善 | ❌ 相对较新<br>❌ 社区较小 | **推荐**：企业级应用 |
| **LangChain** | ✅ 社区活跃<br>✅ 生态丰富<br>✅ 文档详细 | ❌ 性能开销大<br>❌ 版本变化快 | 原型开发 |
| **AutoGen** | ✅ 多Agent协作<br>✅ 对话式交互 | ❌ 复杂度过高<br>❌ 学习曲线陡峭 | 复杂协作场景 |
| **CrewAI** | ✅ 角色分工明确<br>✅ 易于理解 | ❌ 功能相对简单<br>❌ 扩展性有限 | 简单任务编排 |

### 9.2 MCP Server技术栈
```yaml
mcp_implementation:
  language: "Python/Node.js"
  framework: "FastAPI/Express.js"
  protocol: "HTTP/WebSocket"
  authentication: "JWT/OAuth2"
  database: "PostgreSQL/MongoDB"
  caching: "Redis"
  monitoring: "Prometheus/Grafana"
```

### 9.3 A2A Server技术栈
```yaml
a2a_implementation:
  language: "Python"
  framework: "FastAPI"
  protocol: "A2A Protocol v1"
  service_discovery: "Consul/etcd"
  load_balancer: "HAProxy/Nginx"
  message_queue: "RabbitMQ/Kafka"
```

## 10. 监控和运维

### 10.1 关键指标
- **执行成功率**：计划执行成功的比例
- **平均执行时间**：从开始到完成的时间
- **Agent响应时间**：Agent执行的平均时间
- **错误率**：执行过程中出现的错误比例

### 10.2 日志和追踪
- **结构化日志**：使用JSON格式记录所有关键事件
- **分布式追踪**：跟踪请求在整个系统中的执行路径
- **性能监控**：监控各个模块的性能指标

---

*此文档为AIntegration系统的详细架构设计，涵盖了所有核心模块的设计和实现细节。*
