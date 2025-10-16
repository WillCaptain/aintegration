# PlanInstance执行追踪API

**版本**: 1.0  
**日期**: 2025-10-15  
**状态**: ✅ 已实现

## 📋 概述

`get_execution_trace()` 方法提供了一个简洁的API来访问计划执行的完整追踪信息，包括执行清单和验证摘要。

## 🔍 API签名

```python
def get_execution_trace(self) -> Dict[str, Any]:
    """
    获取计划执行追踪信息（执行清单+验证摘要）
    
    返回格式:
    {
        "checklist": [...],      # 执行清单
        "summary": {...},         # 验证摘要
        "verification_completed": bool  # 是否完成验证
    }
    """
```

## 📊 返回数据结构

### 完整返回格式

```python
{
    "checklist": [
        {
            "agent_id": "hr",
            "task_id": "002",
            "task_name": "新员工注册",
            "status": "executed_and_verified",  
            "tools_used": ["query_profile"],
            "icon": "✅"
        },
        {
            "agent_id": "it",
            "task_id": "003",
            "task_name": "申请电脑",
            "status": "executed_but_unverified",
            "reason": "no_verification_tool",
            "icon": "⚠️"
        },
        {
            "agent_id": "some_agent",
            "task_id": "004",
            "task_name": "某个任务",
            "status": "verification_failed",
            "tools_used": ["verify_task"],
            "icon": "❌"
        }
    ],
    "summary": {
        "overall_status": "passed",  # 或 "failed"
        "has_explicit_failure": false,
        "verified_count": 3,
        "unable_to_verify_count": 2,
        "failed_count": 0,
        "total_count": 5
    },
    "verification_completed": true
}
```

### Checklist条目状态

| 状态 | 含义 | 图标 |
|------|------|------|
| `executed_and_verified` | 任务执行成功且验证通过 | ✅ |
| `executed_but_unverified` | 任务执行成功但无法验证 | ⚠️ |
| `verification_failed` | 任务执行成功但验证失败 | ❌ |

### Summary字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `overall_status` | string | 整体状态：`"passed"` 或 `"failed"` |
| `has_explicit_failure` | boolean | 是否有明确的验证失败 |
| `verified_count` | int | 验证通过的数量 |
| `unable_to_verify_count` | int | 无法验证的数量 |
| `failed_count` | int | 验证失败的数量 |
| `total_count` | int | 总数量 |

## 💡 使用示例

### 示例1：基本使用

```python
# 获取执行追踪
plan_instance = await plan_module.get_plan_instance(plan_instance_id)
trace = plan_instance.get_execution_trace()

# 打印摘要
summary = trace["summary"]
print(f"执行状态: {summary['overall_status']}")
print(f"验证通过: {summary['verified_count']}/{summary['total_count']}")
print(f"无法验证: {summary['unable_to_verify_count']}")
print(f"验证失败: {summary['failed_count']}")

# 打印清单
for item in trace["checklist"]:
    print(f"{item['icon']} {item['agent_id']} - {item['task_name']}: {item['status']}")
```

### 示例2：检查验证完成状态

```python
trace = plan_instance.get_execution_trace()

if not trace["verification_completed"]:
    print("⚠️ 验证尚未完成，请等待PlannerAgent完成验证")
    return

if trace["summary"]["overall_status"] == "passed":
    print("✅ 计划执行成功！")
else:
    print("❌ 计划执行失败，请检查验证结果")
```

### 示例3：详细分析执行情况

```python
trace = plan_instance.get_execution_trace()
checklist = trace["checklist"]

# 找出所有验证通过的任务
verified_tasks = [item for item in checklist if item["status"] == "executed_and_verified"]
print(f"✅ 已验证的任务 ({len(verified_tasks)}):")
for item in verified_tasks:
    tools = ', '.join(item.get("tools_used", []))
    print(f"  - {item['task_name']} (使用工具: {tools})")

# 找出无法验证的任务
unverified_tasks = [item for item in checklist if item["status"] == "executed_but_unverified"]
print(f"\n⚠️ 无法验证的任务 ({len(unverified_tasks)}):")
for item in unverified_tasks:
    print(f"  - {item['task_name']} (原因: {item.get('reason', 'unknown')})")

# 找出验证失败的任务
failed_tasks = [item for item in checklist if item["status"] == "verification_failed"]
if failed_tasks:
    print(f"\n❌ 验证失败的任务 ({len(failed_tasks)}):")
    for item in failed_tasks:
        print(f"  - {item['task_name']}")
```

### 示例4：生成执行报告

```python
def generate_execution_report(plan_instance):
    """生成执行报告"""
    trace = plan_instance.get_execution_trace()
    
    report = []
    report.append("=" * 60)
    report.append(f"计划执行报告 - {plan_instance.plan_id}")
    report.append(f"实例ID: {plan_instance.id}")
    report.append(f"状态: {plan_instance.status}")
    report.append("=" * 60)
    
    # 添加摘要
    summary = trace["summary"]
    report.append(f"\n📊 执行摘要:")
    report.append(f"  整体状态: {summary['overall_status']}")
    report.append(f"  验证通过: {summary['verified_count']}")
    report.append(f"  无法验证: {summary['unable_to_verify_count']}")
    report.append(f"  验证失败: {summary['failed_count']}")
    report.append(f"  总计: {summary['total_count']}")
    
    # 添加详细清单
    report.append(f"\n📝 执行清单:")
    for item in trace["checklist"]:
        icon = item.get("icon", "")
        agent = item.get("agent_id", "")
        task = item.get("task_name", "")
        status = item.get("status", "")
        
        report.append(f"  {icon} {agent} - {task}")
        report.append(f"     状态: {status}")
        
        if item.get("tools_used"):
            tools = ', '.join(item["tools_used"])
            report.append(f"     验证工具: {tools}")
        
        if item.get("reason"):
            report.append(f"     原因: {item['reason']}")
    
    report.append("=" * 60)
    
    return "\n".join(report)

# 使用
report = generate_execution_report(plan_instance)
print(report)
```

**输出示例**:
```
============================================================
计划执行报告 - onboard_will_zhang
实例ID: inst_000001
状态: done
============================================================

📊 执行摘要:
  整体状态: passed
  验证通过: 3
  无法验证: 2
  验证失败: 0
  总计: 5

📝 执行清单:
  ✅ hr - 新员工注册
     状态: executed_and_verified
     验证工具: query_profile
  ✅ access - 门禁申请
     状态: executed_and_verified
     验证工具: query_access
  ⚠️ it - 申请电脑
     状态: executed_but_unverified
     原因: no_verification_tool
  ⚠️ email - 发送欢迎邮件
     状态: executed_but_unverified
     原因: no_verification_tool
  ✅ inventory - 电脑出库
     状态: executed_and_verified
     验证工具: outbound, check_outbound_status
============================================================
```

## 🎯 使用场景

### 1. Web API响应

```python
@app.get("/api/plan_instances/{plan_instance_id}/trace")
async def get_plan_trace(plan_instance_id: str):
    plan_instance = await plan_module.get_plan_instance(plan_instance_id)
    if not plan_instance:
        return {"error": "Plan instance not found"}
    
    return plan_instance.get_execution_trace()
```

### 2. 监控和告警

```python
# 定期检查执行状态
trace = plan_instance.get_execution_trace()

if trace["summary"]["failed_count"] > 0:
    # 发送告警
    send_alert(f"计划 {plan_instance.id} 有 {trace['summary']['failed_count']} 个任务验证失败")

if trace["summary"]["unable_to_verify_count"] > 0:
    # 记录警告
    logger.warning(f"计划 {plan_instance.id} 有 {trace['summary']['unable_to_verify_count']} 个任务无法验证")
```

### 3. 用户界面展示

```python
# 前端可以直接使用checklist渲染UI
trace = plan_instance.get_execution_trace()

for item in trace["checklist"]:
    # 根据status渲染不同的UI样式
    if item["status"] == "executed_and_verified":
        render_success_card(item)
    elif item["status"] == "executed_but_unverified":
        render_warning_card(item)
    else:
        render_error_card(item)
```

## 🔄 与旧API的对比

### 旧方式（复杂）
```python
# 需要深入context结构
main_task = plan_instance.get_main_task_instance()
verification_results = main_task.context.get("verification_results", {})
checklist = verification_results.get("_checklist", [])
summary = verification_results.get("_summary", {})
```

### 新方式（简洁）
```python
# 一个方法搞定
trace = plan_instance.get_execution_trace()
checklist = trace["checklist"]
summary = trace["summary"]
```

## ✅ 优势

1. **统一接口**: 所有执行追踪信息通过一个方法获取
2. **默认值处理**: 自动处理未完成验证的情况
3. **类型安全**: 返回结构清晰，易于使用
4. **向后兼容**: 不影响现有的context访问方式

---

**实现文件**: `src/models/plan_instance.py` (第534-589行)  
**相关功能**: PlannerAgent验证机制、Checklist生成

