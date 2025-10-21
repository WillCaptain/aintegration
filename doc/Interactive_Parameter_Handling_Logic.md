# 交互式参数处理逻辑

## 概述

当Agent执行工具时遇到参数不足或错误的情况，系统需要暂停执行并生成TODO任务，等待用户输入参数后继续执行。

## 完整流程

### 1. L001执行失败阶段
- **触发条件**: Agent调用工具时参数不足
- **处理逻辑**: 
  - 设置任务001状态为`error`
  - 在任务上下文中设置`reason="missing_params"`
  - 包含缺失参数的元数据信息
- **代码位置**: `src/infrastructure/adk_integration.py` - `_execute_agent_tool`

### 2. 系统侦听器检测阶段
- **触发条件**: 检测到任务001状态变为`error`
- **处理逻辑**:
  - 根据`reason`字段分类处理
  - 如果是`missing_params`，生成参数输入TODO
  - 设置plan_instance状态为`error`，reason为`missing_params`
- **代码位置**: `src/core/task_driver.py` - `_execute_listener`

### 3. TODO生成阶段
- **触发条件**: 系统侦听器检测到`missing_params`错误
- **处理逻辑**:
  - 创建`TodoTask`，类型为`parameter_input`
  - 包含交互式表单配置
  - 关联到对应的listener和agent
- **代码位置**: `src/core/task_driver.py` - missing_params处理逻辑

### 4. 计划状态管理阶段
- **触发条件**: 系统侦听器处理完成
- **处理逻辑**:
  - 设置plan_instance状态为`error`
  - 设置reason为`missing_params`
  - 等待用户处理TODO
- **代码位置**: `src/models/plan_instance.py` - 状态管理逻辑

### 5. 恢复机制阶段
- **触发条件**: 用户完成TODO输入
- **处理逻辑**:
  - 调用`resume_plan`方法
  - 根据reason确定恢复策略
  - 重启对应的listener继续执行
- **代码位置**: `src/models/plan_instance.py` - `resume_plan`方法

## 关键组件

### TaskDriver
- 负责执行listener
- 检测`missing_params`错误
- 生成TODO任务

### TodoManager
- 管理TODO任务生命周期
- 提供参数输入接口

### PlanInstance
- 管理计划状态
- 提供resume机制

## 错误处理分类

### 工具调用失败 (005测试)
- reason: `tool_call_failure`
- 处理: 重试机制

### 参数缺失/错误 (006测试)
- reason: `missing_params`
- 处理: 生成TODO，等待用户输入

## 状态转换

```
任务001: NotStarted → Running → Error (reason: missing_params)
计划实例: running → error (reason: missing_params)
TODO: pending → completed
计划实例: error → running (resume后)
任务001: Error → Running → Done
```

## 实现要点

1. **统一日志**: 所有日志写入`plan_execution.log`
2. **错误分类**: 根据reason字段进行不同处理
3. **状态管理**: 清晰的计划实例状态转换
4. **恢复机制**: 基于reason的智能恢复策略
