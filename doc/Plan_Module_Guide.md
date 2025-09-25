# 计划模块使用指南

## 概述

计划模块（Plan Module）是AIntegration框架的核心组件，负责管理复杂的业务流程执行。它采用侦听驱动的事件机制，通过任务状态变化触发智能体或代码执行，实现自动化的业务流程编排。

## 核心概念

### 1. 计划（Plan）
- **定义**：一个完整的业务流程执行计划，包含多个任务和侦听器
- **状态**：draft（草稿）、active（活跃）、completed（完成）、failed（失败）、cancelled（取消）
- **主任务**：计划的入口点，其完成表示整个计划完成

### 2. 任务（Task）
- **定义**：计划中的最小执行单元，代表一个具体的业务操作
- **状态**：NotStarted（未开始）、Running（运行中）、Done（已完成）、Error（错误）、Pending（等待中）
- **上下文**：任务执行时的数据环境，包含状态值和相关信息

### 3. 侦听器（Listener）
- **定义**：监听任务状态变化并执行相应操作的组件
- **类型**：
  - **智能体侦听器**：调用AI智能体执行任务
  - **代码侦听器**：执行Python代码片段
- **触发条件**：指定任务状态变化时触发
- **行动条件**：满足条件时才执行操作

### 4. 任务驱动器（TaskDriver）
- **功能**：执行智能体和代码，处理执行结果
- **支持**：ADK集成、LLM客户端、安全代码执行

### 5. 侦听引擎（ListenerEngine）
- **功能**：事件驱动的任务执行引擎
- **机制**：任务状态变化 → 触发侦听器 → 执行操作 → 更新任务状态 → 循环

## 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   计划模块       │    │   侦听引擎       │    │   任务驱动器     │
│   (PlanModule)  │    │ (ListenerEngine)│    │  (TaskDriver)   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   计划管理器     │    │   事件队列       │    │   智能体执行     │
│  (PlanManager)  │    │ (ExecutionQueue)│    │  (Agent Exec)   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   任务管理器     │    │   侦听器管理     │    │   代码执行       │
│  (TaskManager)  │    │(ListenerManager)│    │  (Code Exec)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 使用方式

### 1. 基本使用

```python
import asyncio
from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule

async def main():
    # 初始化数据库连接
    db_connection = MemoryDatabaseConnection()
    
    # 创建计划模块
    plan_module = PlanModule(
        plan_repo=db_connection.plan_repo,
        task_repo=db_connection.task_repo,
        listener_repo=db_connection.listener_repo
    )
    
    # 启动模块
    await plan_module.start()
    
    # 创建计划
    plan_config = {
        "plan_id": "my_plan_001",
        "name": "我的计划",
        "description": "计划描述",
        "main_task_id": "001",
        "tasks": [...],
        "listeners": [...]
    }
    
    plan_id = await plan_module.create_plan_from_config(plan_config)
    
    # 执行计划
    success = await plan_module.execute_plan(plan_id)
    
    # 停止模块
    await plan_module.stop()

asyncio.run(main())
```

### 2. 计划配置格式

```yaml
# 计划基本信息
plan_id: "employee_onboarding_v1"
name: "新员工入职计划"
description: "新员工入职的完整流程"
main_task_id: "001"

# 任务定义
tasks:
  - task_id: "001"
    name: "新员工完成入职"
    prompt: "新员工入职"
    is_main_task: true
    
  - task_id: "002"
    name: "新员工注册"
    prompt: "新员工在Hr系统中完成新员工注册"

# 侦听器定义
listeners:
  - listener_id: "L001"
    trigger_task_id: "001"
    trigger_condition: "001.status == Running"
    action_condition: "true"
    listener_type: "agent"  # 或 "code"
    agent_id: "hr_agent_v1"
    action_prompt: "根据员工信息创建员工记录"
    success_output:
      task_id: "002"
      status: "Done"
      context:
        emp_id: "{{result.emp_id}}"
    failure_output:
      task_id: "002"
      status: "Error"
      context:
        error: "HR系统连接失败"
```

### 3. 智能体侦听器

```yaml
listeners:
  - listener_id: "L001"
    trigger_task_id: "001"
    trigger_condition: "001.status == Running"
    action_condition: "true"
    listener_type: "agent"
    agent_id: "hr_agent_v1"
    action_prompt: "根据员工身份证号{001.context.id}、姓名{001.context.name}在HR系统中创建员工记录"
    success_output:
      task_id: "002"
      status: "Done"
      context:
        emp_id: "{{result.emp_id}}"
        level: "{{result.level}}"
    failure_output:
      task_id: "002"
      status: "Error"
      context:
        error: "HR系统连接失败"
```

### 4. 代码侦听器

```yaml
listeners:
  - listener_id: "L001"
    trigger_task_id: "001"
    trigger_condition: "001.status == Running"
    action_condition: "true"
    listener_type: "code"
    code_snippet: |
      # 检查出库单领取状态
      outbound_id = context.get('values', {}).get('outbound_id')
      if outbound_id:
          # 模拟检查领取状态
          import random
          picked_up = random.choice([True, False])
          if picked_up:
              result = {
                  'picked_up': True,
                  'pickup_time': '2024-01-01 10:00:00'
              }
          else:
              result = {
                  'picked_up': False,
                  'last_check': '2024-01-01 10:00:00'
              }
      else:
          result = {'error': 'No outbound_id found'}
    success_output:
      task_id: "002"
      status: "Done"
      context:
        picked_up: "{{result.picked_up}}"
    failure_output:
      task_id: "002"
      status: "Pending"
      context:
        picked_up: "{{result.picked_up}}"
```

## 核心特性

### 1. 事件驱动执行
- 任务状态变化自动触发相关侦听器
- 支持复杂的触发条件组合
- 异步并发执行多个侦听器

### 2. 智能体集成
- 支持内部和外部智能体
- 统一的智能体调用接口
- 上下文变量自动替换

### 3. 代码执行
- 安全的Python代码执行环境
- 支持复杂的业务逻辑
- 结果自动解析和传递

### 4. 异常处理
- 孤立状态变化自动检测
- Planner动态生成侦听器
- 完整的错误恢复机制

### 5. 状态管理
- 严格的任务状态转换规则
- 完整的执行历史记录
- 实时状态监控

## 高级功能

### 1. 孤立状态变化处理

当任务状态变化没有对应的侦听器时，系统会：
1. 检测到孤立状态变化
2. 通知Planner分析情况
3. 使用LLM生成合适的侦听器
4. 自动创建并注册新侦听器
5. 继续执行流程

### 2. 上下文变量替换

支持在提示词和代码中使用上下文变量：
- `{task_id.context.key}` - 任务上下文变量
- `{{result.key}}` - 执行结果变量
- 自动替换为实际值

### 3. 优先级控制

侦听器支持优先级设置：
- 数字越小优先级越高
- 相同触发条件的侦听器按优先级执行
- 支持并发和串行执行

### 4. 条件评估

支持复杂的条件表达式：
- 任务状态条件：`001.status == Done`
- 多任务条件：`003.status == Done && 005.status == Done`
- 任意状态：`Any`

## 最佳实践

### 1. 计划设计
- 保持任务粒度适中，避免过于复杂
- 合理设置主任务和子任务关系
- 使用描述性的任务和侦听器名称

### 2. 侦听器设计
- 每个侦听器只负责一个具体操作
- 明确定义成功和失败的处理逻辑
- 合理设置触发条件和行动条件

### 3. 错误处理
- 为每个侦听器定义失败输出
- 使用补偿机制处理错误情况
- 记录详细的错误信息

### 4. 性能优化
- 合理使用并发执行
- 避免不必要的轮询
- 优化上下文数据大小

## 监控和调试

### 1. 状态监控
```python
# 获取计划状态
status = await plan_module.get_plan_status(plan_id)
print(f"计划状态: {status['plan_status']}")
for task in status['tasks']:
    print(f"任务 {task['task_id']}: {task['status']}")
```

### 2. 日志记录
- 所有操作都有详细的日志记录
- 支持不同级别的日志输出
- 便于问题排查和性能分析

### 3. 测试支持
- 完整的单元测试覆盖
- 模拟执行环境
- 自动化测试工具

## 扩展开发

### 1. 自定义智能体
- 实现标准的智能体接口
- 注册到A2A Server
- 支持动态发现和调用

### 2. 自定义条件评估器
- 扩展条件表达式语法
- 支持更复杂的业务规则
- 集成外部系统状态

### 3. 自定义执行器
- 支持新的执行类型
- 集成外部执行环境
- 提供统一的执行接口

## 故障排除

### 1. 常见问题
- **侦听器不触发**：检查触发条件和行动条件
- **任务状态不更新**：检查状态转换规则
- **智能体执行失败**：检查智能体配置和网络连接

### 2. 调试技巧
- 启用详细日志记录
- 使用状态监控接口
- 检查执行队列状态

### 3. 性能问题
- 监控执行队列长度
- 检查侦听器执行时间
- 优化数据库查询

## 总结

计划模块提供了强大而灵活的业务流程编排能力，通过事件驱动的机制实现了高度自动化的业务处理。合理使用其特性可以大大简化复杂业务流程的实现和维护。
