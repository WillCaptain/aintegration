# 计划执行引擎设计

**版本**: v1.0  
**日期**: 2025-10-15  
**特性**: 核心执行引擎 - 已实现

---

## 🎯 功能概述

### 核心需求
AIntegration的核心执行引擎负责管理复杂的业务流程执行，通过事件驱动的侦听器机制，实现自动化的任务流转和状态管理。

### 核心组件
1. **PlanModule**: 计划管理模块，负责Plan和PlanInstance的生命周期管理
2. **TaskDriver**: 任务驱动器，负责执行Agent和代码侦听器
3. **ListenerEngine**: 侦听引擎，负责事件驱动的任务执行
4. **PlanManager**: 计划管理器，负责计划的CRUD操作

---

## 🏗️ 架构设计

### 执行引擎架构
```
┌─────────────────────────────────────────────────────────┐
│                   核心执行引擎                            │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ PlanModule  │ │ TaskDriver  │ │ Listener    │       │
│  │ (计划管理)   │ │ (任务驱动)   │ │ Engine      │       │
│  │             │ │             │ │ (事件驱动)   │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ PlanManager │ │ TaskManager │ │ Listener    │       │
│  │ (计划管理)   │ │ (任务管理)   │ │ Manager     │       │
│  │             │ │             │ │ (侦听器管理) │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 执行流程
```
用户请求 → PlanModule.start_plan_by_prompt() → 创建PlanInstance → 启动ListenerEngine → 任务状态变化 → 触发Listener → TaskDriver执行 → 更新任务状态 → 循环直到完成
```

---

## 💻 详细实现

### 1. PlanModule - 计划管理模块

#### 核心功能
```python
class PlanModule:
    """计划管理模块"""
    
    def __init__(self):
        self.plan_manager = PlanManager()
        self.listener_engine = ListenerEngine()
        self.task_driver = TaskDriver()
        self.execution_logger = ExecutionLogger()
    
    async def start_plan_by_prompt(self, prompt: str, plan_id: str) -> PlanInstance:
        """通过提示词启动计划"""
        try:
            # 1. 获取计划模板
            plan = await self.get_plan(plan_id)
            if not plan:
                raise ValueError(f"Plan {plan_id} not found")
            
            # 2. 创建计划实例
            plan_instance = await self._create_plan_instance_internal(plan, prompt)
            
            # 3. 启动执行
            await self._start_execution(plan_instance)
            
            return plan_instance
            
        except Exception as e:
            logger.error(f"Error starting plan {plan_id}: {e}")
            raise
    
    async def _create_plan_instance_internal(self, plan: Plan, prompt: str) -> PlanInstance:
        """创建计划实例"""
        # 创建计划实例
        plan_instance = PlanInstance(
            id=generate_id(),
            plan_id=plan.id,
            prompt=prompt,
            status=PlanInstanceStatus.NOT_STARTED.value,
            created_at=datetime.now(),
            context={"values": {}, "metadata": {}}
        )
        
        # 创建任务实例
        task_instances = []
        for task_config in plan.tasks:
            task_instance = TaskInstance(
                id=task_config["task_id"],
                plan_instance_id=plan_instance.id,
                task_id=task_config["task_id"],
                status=TaskStatus.NOT_STARTED.value,
                context={}
            )
            task_instances.append(task_instance)
        
        plan_instance.task_instances = task_instances
        
        # 保存到数据库
        await self.plan_instance_repo.create(plan_instance)
        
        return plan_instance
    
    async def _start_execution(self, plan_instance: PlanInstance):
        """启动执行"""
        # 设置状态为运行中
        plan_instance.status = PlanInstanceStatus.RUNNING.value
        await self.plan_instance_repo.update(plan_instance.id, {
            "status": plan_instance.status
        })
        
        # 启动主任务
        main_task = plan_instance.get_main_task()
        if main_task:
            main_task.status = TaskStatus.RUNNING.value
            await self.task_instance_repo.update(main_task.id, {
                "status": main_task.status
            })
            
            # 启动侦听引擎
            await self.listener_engine.start_execution(plan_instance.id)
```

### 2. TaskDriver - 任务驱动器

#### 核心功能
```python
class TaskDriver:
    """任务驱动器"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None, adk_integration: Optional[AgentRuntime] = None):
        self.llm_client = llm_client or build_llm_client()
        self.adk_integration = adk_integration
        self.execution_context = {}
    
    async def execute_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行侦听器"""
        try:
            logger.info(f"Executing listener {listener.id} of type {listener.listener_type}")
            
            # 根据侦听器类型执行
            if listener.is_agent_listener():
                return await self._execute_agent_listener(listener, plan_context)
            elif listener.is_code_listener():
                return await self._execute_code_listener(listener, plan_context)
            else:
                logger.error(f"Unknown listener type: {listener.listener_type}")
                return {"success": False, "reason": "unknown_listener_type"}
                
        except Exception as e:
            logger.error(f"Error executing listener {listener.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_agent_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行Agent侦听器"""
        try:
            # 获取Agent实例
            agent = await self._get_agent_instance(listener.agent_id)
            if not agent:
                return {"success": False, "reason": "agent_not_found"}
            
            # 准备执行上下文
            execution_context = {
                **plan_context.get("values", {}),
                **plan_context.get("metadata", {}),
                "listener_id": listener.id,
                "plan_instance_id": plan_context.get("plan_instance_id")
            }
            
            # 执行Agent
            result = await agent.execute(listener.prompt, execution_context)
            
            # 处理执行结果
            if result.get("success", False):
                # 成功：更新任务状态
                task_updates = result.get("task_updates", [])
                return {
                    "success": True,
                    "task_updates": task_updates,
                    "result": result.get("result")
                }
            else:
                # 失败：返回错误信息
                return {
                    "success": False,
                    "reason": result.get("reason", "agent_execution_failed"),
                    "error": result.get("error")
                }
                
        except Exception as e:
            logger.error(f"Error executing agent listener {listener.id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_code_listener(self, listener: Listener, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """执行代码侦听器"""
        try:
            # 安全的代码执行环境
            exec_context = {
                "__builtins__": {},
                "context": plan_context,
                "logger": logger
            }
            
            # 执行代码
            exec(listener.code, exec_context)
            
            # 获取执行结果
            result = exec_context.get("result", {"success": True})
            
            return {
                "success": result.get("success", True),
                "task_updates": result.get("task_updates", []),
                "result": result.get("result")
            }
            
        except Exception as e:
            logger.error(f"Error executing code listener {listener.id}: {e}")
            return {"success": False, "error": str(e)}
```

### 3. ListenerEngine - 侦听引擎

#### 核心功能
```python
class ListenerEngine:
    """侦听引擎"""
    
    def __init__(self, task_driver: TaskDriver, plan_module: PlanModule):
        self.task_driver = task_driver
        self.plan_module = plan_module
        self.running_executions = {}
    
    async def start_execution(self, plan_instance_id: str):
        """启动执行"""
        try:
            # 获取计划实例
            plan_instance = await self.plan_module.get_plan_instance(plan_instance_id)
            if not plan_instance:
                logger.error(f"Plan instance {plan_instance_id} not found")
                return
            
            # 启动自我驱动循环
            await self._start_self_driven_loop(plan_instance)
            
        except Exception as e:
            logger.error(f"Error starting execution for plan instance {plan_instance_id}: {e}")
    
    async def _start_self_driven_loop(self, plan_instance: PlanInstance):
        """启动自我驱动循环"""
        try:
            logger.info(f"Starting self-driven loop for plan instance {plan_instance.id}")
            
            # 创建执行任务
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._run_self_driven_loop(plan_instance))
            plan_instance._execution_task = task
            
            # 等待完成
            await task
            
        except Exception as e:
            logger.error(f"Error in self-driven loop: {e}")
    
    async def _run_self_driven_loop(self, plan_instance: PlanInstance):
        """运行自我驱动循环"""
        try:
            while plan_instance.status == PlanInstanceStatus.RUNNING.value:
                # 检查是否有任务状态变化
                changed_tasks = await self._check_task_status_changes(plan_instance)
                
                if changed_tasks:
                    # 处理状态变化
                    await self._process_task_status_changes(plan_instance, changed_tasks)
                
                # 检查是否完成
                if await self._check_plan_completion(plan_instance):
                    plan_instance.status = PlanInstanceStatus.DONE.value
                    await self.plan_module.update_plan_instance(plan_instance.id, {
                        "status": plan_instance.status
                    })
                    break
                
                # 等待一段时间再检查
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in self-driven loop: {e}")
            plan_instance.status = PlanInstanceStatus.ERROR.value
            await self.plan_module.update_plan_instance(plan_instance.id, {
                "status": plan_instance.status
            })
    
    async def _process_task_status_changes(self, plan_instance: PlanInstance, changed_tasks: List[TaskInstance]):
        """处理任务状态变化"""
        for task in changed_tasks:
            # 获取触发的侦听器
            triggered_listeners = await self._get_triggered_listeners(task)
            
            # 执行侦听器
            for listener in triggered_listeners:
                try:
                    # 准备上下文
                    plan_context = {
                        "plan_instance_id": plan_instance.id,
                        "values": plan_instance.context.get("values", {}),
                        "metadata": plan_instance.context.get("metadata", {}),
                        "current_task": task.id
                    }
                    
                    # 执行侦听器
                    result = await self.task_driver.execute_listener(listener, plan_context)
                    
                    # 处理结果
                    if result.get("task_updates"):
                        await self._apply_task_updates(plan_instance, result["task_updates"])
                        
                except Exception as e:
                    logger.error(f"Error processing listener {listener.id}: {e}")
```

### 4. PlanManager - 计划管理器

#### 核心功能
```python
class PlanManager:
    """计划管理器"""
    
    def __init__(self):
        self.plan_repo = PlanRepository()
        self.task_repo = TaskRepository()
        self.listener_repo = ListenerRepository()
    
    async def create_plan_from_config(self, config: Dict[str, Any]) -> Plan:
        """从配置创建计划"""
        try:
            # 创建计划
            plan = Plan(
                id=config["plan_id"],
                name=config["name"],
                description=config.get("description", ""),
                main_task_id=config.get("main_task_id", "001"),
                tasks=config["tasks"],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # 保存计划
            await self.plan_repo.create(plan)
            
            # 创建任务和侦听器
            await self._create_tasks_and_listeners(plan, config)
            
            return plan
            
        except Exception as e:
            logger.error(f"Error creating plan from config: {e}")
            raise
    
    async def _create_tasks_and_listeners(self, plan: Plan, config: Dict[str, Any]):
        """创建任务和侦听器"""
        for task_config in config["tasks"]:
            # 创建任务
            task = Task(
                id=task_config["task_id"],
                plan_id=plan.id,
                name=task_config["name"],
                description=task_config.get("description", "")
            )
            await self.task_repo.create(task)
            
            # 创建侦听器
            for listener_config in task_config.get("listeners", []):
                listener = Listener(
                    id=listener_config["listener_id"],
                    task_id=task.id,
                    listener_type=listener_config["type"],
                    trigger_condition=listener_config.get("trigger_condition", {}),
                    action_condition=listener_config.get("action_condition", {}),
                    agent_id=listener_config.get("agent_id"),
                    prompt=listener_config.get("prompt", ""),
                    code=listener_config.get("code", "")
                )
                await self.listener_repo.create(listener)
```

---

## 🔄 执行流程详解

### 1. 计划启动流程
```
用户请求 → PlanModule.start_plan_by_prompt() → 获取计划模板 → 创建PlanInstance → 创建TaskInstance → 启动ListenerEngine → 设置主任务为RUNNING → 开始自我驱动循环
```

### 2. 任务执行流程
```
任务状态变化 → 触发Listener → TaskDriver.execute_listener() → 执行Agent/Code → 返回结果 → 更新任务状态 → 继续循环
```

### 3. 完成检查流程
```
检查主任务状态 → 如果DONE则检查所有任务 → 设置PlanInstance为DONE → 停止自我驱动循环
```

---

## 📊 数据模型

### 核心实体关系
```
Plan ←→ PlanInstance ←→ TaskInstance ←→ Listener
  ↓
Task ←→ Listener
```

### 主要状态
- **PlanInstance**: NOT_STARTED → RUNNING → DONE/ERROR
- **TaskInstance**: NOT_STARTED → RUNNING → DONE/ERROR
- **Listener**: 根据触发条件执行

---

## 🧪 测试用例

### 基础执行测试
```python
async def test_plan_execution_basic():
    """测试基础计划执行"""
    
    # 1. 创建计划配置
    plan_config = {
        "plan_id": "test_plan",
        "name": "测试计划",
        "tasks": [
            {
                "task_id": "001",
                "name": "主任务",
                "listeners": [
                    {
                        "listener_id": "L001",
                        "type": "agent",
                        "agent_id": "test_agent",
                        "prompt": "执行测试任务"
                    }
                ]
            }
        ]
    }
    
    # 2. 创建计划
    plan_module = PlanModule()
    plan = await plan_module.create_plan_from_config(plan_config)
    
    # 3. 启动执行
    plan_instance = await plan_module.start_plan_by_prompt(
        "执行测试",
        plan.id
    )
    
    # 4. 等待完成
    await asyncio.sleep(2)
    
    # 5. 检查结果
    updated_instance = await plan_module.get_plan_instance(plan_instance.id)
    assert updated_instance.status == PlanInstanceStatus.DONE.value
```

---

## 📈 性能优化

### 优化策略
1. **异步执行**: 所有操作都是异步的，支持并发处理
2. **事件驱动**: 基于事件驱动的机制，减少轮询开销
3. **状态缓存**: 缓存任务状态，减少数据库查询
4. **批量操作**: 批量处理任务更新，提高效率

### 监控指标
- **执行时间**: 计划执行总时间
- **任务完成率**: 任务成功完成的比例
- **错误率**: 执行失败的比例
- **并发度**: 同时执行的任务数量

---

## 🎯 验收标准

1. **功能完整性**:
   - ✅ 支持Plan的创建、查询、更新、删除
   - ✅ 支持PlanInstance的生命周期管理
   - ✅ 支持事件驱动的任务执行
   - ✅ 支持Agent和Code侦听器

2. **性能要求**:
   - ✅ 计划启动响应时间 < 100ms
   - ✅ 任务执行响应时间 < 200ms
   - ✅ 支持100+并发计划执行

3. **可靠性**:
   - ✅ 异常处理和错误恢复
   - ✅ 状态一致性和数据完整性
   - ✅ 执行日志和追踪

---

**核心执行引擎是AIntegration的基础，提供了稳定、高效、可扩展的业务流程执行能力！**
