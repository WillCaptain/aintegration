# AIntegration - 企业集成代理框架设计文档
## Enterprise Integrated Agent Framework
### AI Agent辅助下的ESB整合方案

## 1. 系统概述

### 1.1 项目背景
AIntegration是一个基于AI Agent的企业集成代理框架，通过将传统的ESB（企业服务总线）与AI Agent技术相结合，实现智能化的企业应用集成。该系统采用分层代理架构，从最原子的工具调用到复杂的业务流程编排，提供了一套完整的解决方案。

### 1.2 核心架构层次

#### 1.2.1 AtomAgent（原子代理）
- **功能**：最原子化的Agent，采用ReAct模式循环调用工具
- **特点**：
  - 可自编写或集成任意Agent Framework（如Google的Agent框架）
  - 专注于单一工具调用和反馈处理
  - 提供标准化的工具调用接口

#### 1.2.2 BizAgent（业务代理）
- **功能**：特定应用系统的代理，通过提示词和上下文实例化
- **特点**：
  - 每个BizAgent代表一个企业应用（如HrAgent、FinanceAgent等）
  - 包含完整的API信息和URL配置
  - 通过AgentCard注册到A2A Server供发现
- **示例**：HrAgent、PurchaseAgent、ContractAgent、FinanceAgent、ITAgent、InventoryAgent、AccessAgent

#### 1.2.3 PlanAgent（规划代理）
- **功能**：采用Reflex模式，通过蒙特卡洛选择方式制定和执行计划
- **驱动模式**：
  - **PrePlan Mode**：人为设计的预定义计划
  - **SelfPlan Mode**：通过提示词自动生成计划
  - **ResiliencePlan**：失败时自动重新规划

## 2. 系统设计约定

### 2.1 Plan设计约定

#### 2.1.1 主任务ID约定
- **约定**：每个Plan的主任务ID固定为 `"001"`
- **目的**：
  - 简化配置，无需在多处指定主任务ID
  - 为默认错误处理提供统一目标
  - 便于Planner快速定位主任务
- **应用场景**：
  - TaskDriver失败且无failure_output时，自动设置任务001为Error
  - Planner验证时默认查询任务001的状态
  - 计划完成判断以任务001的Done状态为准

#### 2.1.2 错误处理默认行为
- **约定**：Listener执行失败且未配置failure_output时，默认设置主任务（001）为Error
- **目的**：触发PlannerAgent的重试机制
- **Planner重试逻辑**：
  - 主任务Error → Planner从plan_run_logs找到导致Error的Listener
  - 重置主任务为NotStarted → 重新执行失败的Listener
  - 重试次数限制：max_retry_count（默认3次，可配置）
  - 超过限制 → 标记计划为"waiting_for_resume"状态

## 3. 系统架构

### 3.1 整体架构
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   HR系统         │    │   Finance系统    │    │   IT系统         │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   HrAgent       │    │   FinanceAgent  │    │   ITAgent        │
│   (BizAgent)    │    │   (BizAgent)    │    │   (BizAgent)     │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │     PlanAgent           │
                    │   (规划代理)            │
                    └─────────┬───────────────┘
                              │
                    ┌─────────▼───────────────┐
                    │      A2A Server         │
                    │   (Agent注册发现服务)    │
                    └─────────────────────────┘
                              │
                    ┌─────────▼───────────────┐
                    │     AtomAgent Pool      │
                    │   (原子代理池)          │
                    └─────────────────────────┘
```

### 2.2 核心组件详解

#### 2.2.1 Plan（计划）
**定义**：一个完整的业务流程执行计划，由多个任务和代理组成

**结构**：
- **Prompt**：计划的详细描述和上下文
- **Main Task**：主任务，其启动表示计划开始，完成表示计划结束
- **Tasks**：任务列表，每个任务包含状态和上下文
- **Agents**：参与执行的代理列表

**任务状态**：
- `NotStarted`：未开始
- `Running`：运行中
- `Done`：已完成
- `Error`：错误状态
- `Pending`：等待中

#### 2.2.2 Task（任务）
**定义**：计划中的最小执行单元

**属性**：
- **Prompt/Related Plan**：任务描述或关联的子计划
- **Status**：当前状态
- **Context**：任务上下文，包含状态值和相关信息

#### 2.2.3 Agent（代理）
**定义**：执行具体任务的智能代理

**属性**：
- **Prompt**：代理在该计划中的任务描述
- **Observing Tasks**：代理关注的任务列表
- **Trigger Condition**：代理启动条件
- **Target Task & Status**：代理执行后要更新的任务状态

#### 2.2.4 A2A Server（Agent-to-Agent Server）
**功能**：代理注册发现服务
- 管理所有BizAgent的AgentCard
- 提供服务发现和路由功能
- 维护代理健康状态
- **支持外部Agent集成**：允许第三方Agent通过标准协议接入

#### 2.2.5 外部Agent集成
**功能**：通过A2A协议连接任意外部Agent
- **集成方式**：
  - 支持标准Agent Framework（如Google Agent、OpenAI Agent等）
  - 通过AgentCard描述外部Agent能力
  - 统一的外部Agent调用接口
- **优势**：
  - 扩展EAI链条的能力边界
  - 利用现有AI Agent生态
  - 实现跨平台的Agent协作

## 3. 实际应用示例

### 3.1 新员工入职流程示例

#### 3.1.1 涉及的Agent
**内部BizAgent**：
- **HrAgent**：Tools: `create_employee_profile`, `update_employee_status`
- **FinanceAgent**：Tools: `enroll_payroll`, `create_payroll_account`
- **ITAgent**：Tools: `apply_computer`, `create_user_account`
- **InventoryAgent**：Tools: `outbound`, `check_outbound_status`
- **AccessAgent**：Tools: `grant_access`, `create_access_card`

**外部集成Agent示例**：
- **EmailAgent**：Tools: `send_welcome_email`, `send_notification`（通过A2A集成）
- **DocAgent**：Tools: `generate_contract`, `sign_document`（第三方文档处理Agent）
- **NotificationAgent**：Tools: `send_slack_message`, `create_calendar_event`（通知服务Agent）

#### 3.1.2 计划定义
```
Plan ID: 101
Prompt: 新员工入职计划 - 新员工入职将会在hr系统中注册新员工，发送欢迎消息；在财务系统中创建工资单；并且在IT系统中领取电脑；最后在门禁系统里申请门禁
Main Task: 001 (新员工完成入职)
```

#### 3.1.3 任务列表
| Task ID | Task Name | Prompt/Related Plan |
|---------|-----------|-------------------|
| 001 | 新员工完成入职 | 新员工入职 |
| 002 | 新员工注册 | 新员工在Hr系统中完成新员工注册 |
| 003 | 申请电脑 | 新员工在IT系统中完成电脑申请 |
| 004 | 电脑出库 | 电脑出库 |
| 005 | 门禁申请 | 新员工在门禁系统里完成门禁权限申请 |
| 006 | 发送欢迎邮件 | 通过EmailAgent发送新员工欢迎邮件 |
| 007 | 生成劳动合同 | 通过DocAgent生成并发送劳动合同 |

#### 3.1.4 侦听配置（Listener Configuration）
**定义**：每个侦听器只驱动一个Agent，完整描述该Agent的行动指导和反馈逻辑

| 侦听ID | 触发任务状态 | 侦听条件 | 行动条件 | 执行Agent | 行动指导Prompt | 成功反馈 | 失败反馈 |
|--------|-------------|----------|----------|-----------|---------------|----------|----------|
| L001 | 001: NotStarted → Running | 001.status == Running | true | HrAgent | 根据员工身份证号{001.context.id}、姓名{001.context.name}在HR系统中创建员工记录，确定员工级别 | 002: Done, context={emp_id:xxx, level:xxx} | 002: Error, context={error:"HR系统连接失败"} |
| L002 | 001: NotStarted → Running | 001.status == Running | true | AccessAgent | 根据员工ID{001.context.id}为新员工申请门禁权限，输入员工姓名{001.context.name} | 005: Done, context={access_id:xxx, card_no:xxx} | 005: Error, context={error:"门禁系统异常"} |
| L003 | 002: Any → Done | 002.status == Done | true | ITAgent | 根据员工ID{002.context.emp_id}和员工级别{002.context.level}申请相应配置的笔记本 | 003: NotStarted, context={pc_model:xxx, request_id:xxx} | 003: Error, context={error:"IT系统维护中"} |
| L004 | 002: Any → Done | 002.status == Done | true | EmailAgent | 向员工邮箱{002.context.email}发送新员工欢迎邮件，员工姓名{002.context.name}，部门{002.context.department} | 006: Done, context={email_sent:true, message_id:xxx} | 006: Error, context={error:"邮件服务不可用"} |
| L005 | 002: Any → Done | 002.status == Done | true | DocAgent | 为员工{002.context.name}生成劳动合同，员工ID{002.context.emp_id}，级别{002.context.level} | 007: Done, context={contract_id:xxx, signed:true} | 007: Error, context={error:"文档生成失败"} |
| L006 | 003: Any → NotStarted | 003.status == NotStarted | true | InventoryAgent | 根据IT申请{003.context.pc_model}创建电脑出库单，等待员工领取 | 003: Pending, context={outbound_id:xxx, pc_no:xxx} | 003: Error, context={error:"库存不足，型号{003.context.pc_model}缺货"} |
| L007 | 003: Any → Pending | 003.status == Pending | true | InventoryAgent | 检查出库单{003.context.outbound_id}的领取状态，员工是否已领取电脑{003.context.pc_no} | 003: Done, context={picked_up:true, pickup_time:xxx} | 003: Pending, context={picked_up:false, last_check:xxx} |
| L008 | 003,005,006,007: Any → Done | 任意任务状态变化 | 003.status == Done && 005.status == Done && 006.status == Done && 007.status == Done | Planner | 检查新员工入职手续完成情况：电脑领取{003.status}、门禁开通{005.status}、邮件发送{006.status}、合同生成{007.status} | 001: Done, context={onboarding_complete:true, completion_time:xxx} | 001: Pending, context={pending_tasks:[...]} |

#### 3.1.5 侦听驱动的执行流程
```
初始化：001.status = NotStarted

事件1：001.status = NotStarted → Running
┌─────────────────────────────────────────────────────────┐
│ 触发侦听器：L001, L002 (并行执行)                       │
│ ┌─────────────────┐    ┌─────────────────────────────┐  │
│ │ L001: HrAgent   │    │ L002: AccessAgent          │  │
│ │ 行动指导：创建员工记录                              │  │
│ │ 输入上下文：{001.context}                          │  │
│ │ 成功→002: Done   │    │ 成功→005: Done              │  │
│ │ 失败→002: Error  │    │ 失败→005: Error             │  │
│ └─────────────────┘    └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
    ↓
事件2：002.status = NotStarted → Done
┌─────────────────────────────────────────────────────────┐
│ 触发侦听器：L003, L004, L005 (并行执行)                 │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────┐ │
│ │ L003: ITAgent   │ │ L004: EmailAgent│ │ L005: DocAgent│ │
│ │ 行动指导：申请电脑                                   │ │
│ │ 输入上下文：{002.context}                           │ │
│ │ 成功→003: NotStarted│ │ 成功→006: Done  │ │ 成功→007: Done │ │
│ │ 失败→003: Error  │ │ 失败→006: Error  │ │ 失败→007: Error │ │
│ └─────────────────┘ └─────────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────┘
    ↓
事件3：003.status = NotStarted → NotStarted
┌─────────────────────────────────────────────────────────┐
│ 触发侦听器：L006                                        │
│ InventoryAgent: 创建出库单                              │
│ 行动指导：根据IT申请创建电脑出库单                       │
│ 输入上下文：{003.context}                               │
│ 成功→003: Pending, context={outbound_id:xxx}           │
│ 失败→003: Error, context={error:"库存不足"}            │
└─────────────────────────────────────────────────────────┘
    ↓
事件4：003.status = Pending → Pending (轮询中)
┌─────────────────────────────────────────────────────────┐
│ 触发侦听器：L007 (持续轮询)                             │
│ InventoryAgent: 检查领取状态                            │
│ 行动指导：检查出库单领取状态                             │
│ 输入上下文：{003.context}                               │
│ 已领取→003: Done, context={picked_up:true}             │
│ 未领取→003: Pending, context={picked_up:false}         │
└─────────────────────────────────────────────────────────┘
    ↓
事件5：任意任务状态变化 → 检查完成条件
┌─────────────────────────────────────────────────────────┐
│ 触发侦听器：L008                                        │
│ Planner: 检查入职完成情况                               │
│ 行动条件：003.status == Done && 005.status == Done     │
│ && 006.status == Done && 007.status == Done            │
│ 行动指导：检查所有入职手续完成情况                       │
│ 输入上下文：{003.context, 005.context, 006.context, 007.context} │
│ 全部完成→001: Done, context={onboarding_complete:true}  │
│ 未完成→001: Pending, context={pending_tasks:[...]}     │
└─────────────────────────────────────────────────────────┘
    ↓
完成：001.status = Done
```

#### 3.1.6 侦听机制核心原理
1. **一对一驱动**：每个侦听器只驱动一个Agent
2. **完整指导**：每个侦听器提供完整的行动指导和反馈逻辑
3. **上下文注入**：行动指导Prompt中包含具体的上下文变量（如{001.context.id}）
4. **双路径反馈**：明确定义成功和失败两种情况的任务状态更新
5. **条件检查**：支持复杂的多任务状态组合条件
6. **循环触发**：状态更新触发新的侦听器，直到Main Task完成

#### 3.1.7 侦听器设计原则
- **单一职责**：每个侦听器只负责一个Agent的一次行动
- **完整描述**：包含行动指导、输入上下文、输出状态和错误处理
- **上下文明确**：使用变量引用明确指定输入上下文来源
- **反馈完整**：成功和失败都有明确的状态更新和上下文设置

### 3.2 外部Agent集成机制

#### 3.2.1 A2A协议规范
**Agent-to-Agent通信协议**：
```yaml
a2a_protocol:
  version: "1.0"
  authentication:
    - oauth2
    - api_key
    - mutual_tls
  message_format:
    - json
    - protobuf
  capabilities:
    - tool_calling
    - state_management
    - error_handling
    - health_checking
```

#### 3.2.2 外部Agent注册流程
```
外部Agent → A2A Server
    ↓
1. 提供AgentCard描述
2. 验证认证凭据
3. 注册到Agent目录
4. 建立健康检查连接
    ↓
PlanAgent发现并使用
```

#### 3.2.3 AgentCard格式
```json
{
  "agent_id": "external_email_agent_v1",
  "agent_name": "EmailAgent",
  "provider": "external",
  "version": "1.0.0",
  "capabilities": [
    {
      "name": "send_welcome_email",
      "description": "发送新员工欢迎邮件",
      "parameters": {
        "employee_name": "string",
        "email": "string",
        "department": "string"
      },
      "response": {
        "success": "boolean",
        "message_id": "string"
      }
    }
  ],
  "endpoints": {
    "base_url": "https://api.emailagent.com/v1",
    "health_check": "/health",
    "execute": "/execute"
  },
  "authentication": {
    "type": "oauth2",
    "scope": ["send_email", "manage_templates"]
  }
}
```

#### 3.2.4 外部Agent调用示例
```python
# PlanAgent调用外部Agent示例
external_agent = A2AServer.get_agent("external_email_agent_v1")
result = external_agent.execute_tool(
    tool_name="send_welcome_email",
    parameters={
        "employee_name": task_context.get("employee_name"),
        "email": task_context.get("email"),
        "department": task_context.get("department")
    }
)
if result.success:
    update_task_status(task_id="006", status="Done", context=result)
else:
    update_task_status(task_id="006", status="Error", context=result)
```

### 3.3 数据模型

#### 3.3.1 Plan模型
```json
{
  "plan_id": "string",
  "prompt": "string",
  "main_task_id": "string",
  "tasks": [
    {
      "task_id": "string",
      "prompt": "string",
      "status": "NotStarted|Running|Done|Error|Pending",
      "context": {
        "status": "string",
        "values": {}
      }
    }
  ],
  "listeners": [
    {
      "listener_id": "string",
      "trigger_task_id": "string",
      "trigger_status_condition": "string",
      "action_condition": "string",
      "agent_id": "string",
      "action_prompt": "string",
      "success_output": {
        "task_id": "string",
        "status": "string",
        "context": {}
      },
      "failure_output": {
        "task_id": "string",
        "status": "string",
        "context": {}
      }
    }
  ]
}
```

#### 3.3.2 BizAgent模型
```json
{
  "agent_id": "string",
  "agent_name": "string",
  "application_name": "string",
  "api_endpoints": [
    {
      "path": "string",
      "method": "string",
      "parameters": {},
      "response_schema": {}
    }
  ],
  "tools": ["string"],
  "health_status": "healthy|unhealthy|unknown",
  "last_updated": "datetime"
}
```

## 4. 设计要点

### 4.1 核心设计原则

#### 4.1.1 侦听驱动（Listener-Driven）
- **机制**：任务状态变化触发侦听器，侦听器检查行动条件并执行Agent
- **核心流程**：
  1. 任务状态变化 → 触发侦听器
  2. 检查行动条件（可能是多个任务状态的组合）
  3. 条件满足 → Agent执行（接收所有相关上下文）
  4. 执行结果 → 更新目标任务状态
  5. 状态更新 → 触发新的侦听循环
- **优势**：
  - 事件驱动的自动化执行
  - 灵活的条件组合（多任务状态判断）
  - 上下文完整传递
  - 循环往复直到Main Task完成

#### 4.1.2 补偿机制（Compensation Mechanism）
- **触发条件**：当任务状态变为Error时
- **处理方式**：
  - 触发补偿Agent执行回滚操作
  - 或触发Planner重新规划（ResiliencePlan）
- **优势**：确保业务流程的完整性和一致性

#### 4.1.3 轮询机制（Polling Mechanism）
- **功能**：作为BizAgent的标准设计能力
- **用途**：捕获外部系统操作产生的关键状态变化
- **实现**：定期检查外部系统状态，更新任务上下文
- **示例**：InventoryAgent轮询电脑领取状态

#### 4.1.4 组合模式（Composition Pattern）
- **机制**：任务可以嵌套Plan，使复杂流程可层层分解
- **优势**：
  - 支持复杂业务流程的模块化设计
  - 提高代码复用性
  - 便于维护和扩展

### 4.2 技术特性

#### 4.2.1 MCP化工具集成
- **定义**：所有系统API都通过MCP（Model Context Protocol）标准化
- **优势**：
  - 统一的工具调用接口
  - 标准化的参数传递
  - 便于Agent框架集成

#### 4.2.2 多模式规划
- **PrePlan Mode**：预定义计划，适合标准化流程
- **SelfPlan Mode**：自动生成计划，适合动态场景
- **ResiliencePlan**：失败重规划，确保流程鲁棒性

#### 4.2.3 侦听引擎（Listener Engine）
- **原理**：基于任务状态变化的事件驱动机制
- **触发**：任务状态变化时自动触发相关侦听器
- **条件检查**：支持复杂的多任务状态组合条件
- **执行**：条件满足时启动Agent并传递完整上下文
- **循环**：Agent执行结果更新任务状态，触发新的侦听循环

#### 4.2.4 外部Agent集成机制
- **A2A协议**：标准化的Agent间通信协议
- **统一接口**：内部和外部Agent使用相同的调用方式
- **动态发现**：通过A2A Server自动发现可用Agent
- **能力扩展**：无缝集成第三方Agent生态
- **安全隔离**：外部Agent通过认证和授权机制隔离

## 5. 实施计划

### 5.1 阶段一：基础框架
- [ ] 设计AtomAgent接口规范
- [ ] 实现A2A Server（代理注册发现服务）
- [ ] 开发PlanAgent核心引擎
- [ ] 创建任务状态管理机制
- [ ] 设计A2A协议规范
- [ ] 开发侦听引擎（Listener Engine）

### 5.2 阶段二：BizAgent实现
- [ ] 开发标准BizAgent模板
- [ ] 实现MCP化工具集成
- [ ] 添加轮询机制支持
- [ ] 创建AgentCard注册机制
- [ ] 实现外部Agent集成接口

### 5.3 阶段三：规划引擎
- [ ] 实现PrePlan Mode
- [ ] 开发SelfPlan Mode
- [ ] 添加ResiliencePlan机制
- [ ] 创建计划执行引擎
- [ ] 实现侦听器配置和管理

### 5.4 阶段四：集成测试
- [ ] 新员工入职流程测试（包含外部Agent）
- [ ] 侦听器机制测试
- [ ] 外部Agent集成测试
- [ ] 补偿机制测试
- [ ] 性能压力测试
- [ ] 故障恢复测试

### 5.5 阶段五：生产部署
- [ ] 生产环境配置
- [ ] 监控仪表板
- [ ] 文档和培训
- [ ] 运维支持

## 6. 安全和合规

### 6.1 安全措施
- API访问控制和认证
- 数据加密传输
- 敏感信息脱敏
- 审计日志记录
- Agent间通信安全

### 6.2 合规要求
- 数据隐私保护（GDPR等）
- 行业标准合规
- 安全漏洞管理
- 定期安全评估

## 7. 监控和维护

### 7.1 监控指标
- 代理健康状态
- 任务执行状态
- 计划完成率
- API响应时间
- 错误率统计

### 7.2 运维支持
- 自动化部署
- 配置管理
- 备份和恢复
- 故障排除
- 计划版本管理

## 8. 扩展性考虑

### 8.1 水平扩展
- 代理实例复制
- 负载均衡
- 分布式部署
- 多租户支持

### 8.2 功能扩展
- 插件机制
- 自定义协议支持
- 第三方系统集成
- 可视化流程设计器
- 外部Agent生态集成
- 跨平台Agent协作
- 智能Agent推荐系统

---

*此文档为AIntegration企业集成代理框架的详细设计，基于AI Agent辅助下的ESB整合方案，需要根据具体需求和反馈进行持续完善。*
