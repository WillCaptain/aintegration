# AIntegration 实现指南

## 1. 项目结构

```
aintegration/
├── src/
│   ├── core/                    # 核心模块
│   │   ├── __init__.py
│   │   ├── task_listener.py     # 任务侦听模块
│   │   ├── plan_module.py       # 计划模块
│   │   ├── planner.py           # Planner模块
│   │   └── atom_agent.py        # Atom Agent模块
│   ├── infrastructure/          # 基础设施
│   │   ├── __init__.py
│   │   ├── mcp_server.py        # MCP Server
│   │   ├── a2a_server.py        # A2A Server
│   │   └── adk_integration.py   # Google ADK集成
│   ├── models/                  # 数据模型
│   │   ├── __init__.py
│   │   ├── plan.py
│   │   ├── task.py
│   │   ├── listener.py
│   │   └── execution.py
│   ├── database/                # 数据库层
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── plan_repository.py
│   │   │   ├── task_repository.py
│   │   │   └── listener_repository.py
│   │   └── migrations/
│   ├── api/                     # API接口
│   │   ├── __init__.py
│   │   ├── planner_api.py
│   │   ├── task_api.py
│   │   └── plan_api.py
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── logger.py
│       └── config.py
├── tests/                       # 测试
│   ├── __init__.py
│   ├── test_task_listener.py
│   ├── test_plan_module.py
│   └── test_planner.py
├── config/                      # 配置文件
│   ├── development.yaml
│   ├── production.yaml
│   └── docker-compose.yml
├── requirements.txt
├── Dockerfile
└── README.md
```

## 2. 核心模块实现

### 2.1 任务侦听模块实现

```python
# src/core/task_listener.py
import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from ..models.task import Task, TaskStatus
from ..models.listener import Listener
from ..database.repositories.task_repository import TaskRepository
from ..database.repositories.listener_repository import ListenerRepository

logger = logging.getLogger(__name__)

@dataclass
class TaskUpdate:
    task_id: str
    status: str
    context: Dict

class TaskStateManager:
    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo
        self.status_change_callbacks = []
    
    async def update_task_status(self, task_id: str, status: str, context: Dict):
        """更新任务状态和上下文"""
        try:
            # 1. 获取当前状态
            current_task = await self.task_repo.get_by_id(task_id)
            old_status = current_task.status if current_task else None
            
            # 2. 更新数据库
            await self.task_repo.update_status(task_id, status, context)
            
            # 3. 触发状态变化事件
            await self._notify_status_changed(task_id, old_status, status, context)
            
            logger.info(f"Task {task_id} status updated: {old_status} -> {status}")
            
        except Exception as e:
            logger.error(f"Failed to update task {task_id} status: {e}")
            raise
    
    async def batch_update_tasks(self, updates: List[TaskUpdate]):
        """批量更新多个任务状态"""
        for update in updates:
            await self.update_task_status(update.task_id, update.status, update.context)
    
    def add_status_change_callback(self, callback):
        """添加状态变化回调"""
        self.status_change_callbacks.append(callback)
    
    async def _notify_status_changed(self, task_id: str, old_status: str, new_status: str, context: Dict):
        """通知状态变化"""
        for callback in self.status_change_callbacks:
            try:
                await callback(task_id, old_status, new_status, context)
            except Exception as e:
                logger.error(f"Callback error: {e}")

class ListenerScheduler:
    def __init__(self, listener_repo: ListenerRepository, agent_manager):
        self.listener_repo = listener_repo
        self.agent_manager = agent_manager
    
    async def on_task_status_changed(self, task_id: str, old_status: str, new_status: str, context: Dict):
        """任务状态变化事件处理"""
        try:
            # 1. 查找监听该任务状态变化的侦听器
            listeners = await self.listener_repo.get_by_trigger(task_id, new_status)
            
            logger.info(f"Found {len(listeners)} listeners for task {task_id} status {new_status}")
            
            # 2. 检查每个侦听器的触发条件
            for listener in listeners:
                if await self.evaluate_condition(listener, context):
                    await self.trigger_agent(listener, context)
                    
        except Exception as e:
            logger.error(f"Error processing status change for task {task_id}: {e}")
    
    async def evaluate_condition(self, listener: Listener, context: Dict) -> bool:
        """评估侦听器触发条件"""
        try:
            # 这里需要实现条件表达式解析器
            # 支持类似 "003.status == Done && 005.status == Done" 的条件
            return await self._parse_condition(listener.action_condition, context)
        except Exception as e:
            logger.error(f"Error evaluating condition for listener {listener.id}: {e}")
            return False
    
    async def _parse_condition(self, condition: str, context: Dict) -> bool:
        """解析条件表达式"""
        # 简化实现，实际需要更复杂的表达式解析器
        if condition == "true":
            return True
        
        # 解析多任务状态条件
        if "&&" in condition:
            parts = condition.split("&&")
            for part in parts:
                if not await self._evaluate_single_condition(part.strip(), context):
                    return False
            return True
        
        return await self._evaluate_single_condition(condition, context)
    
    async def _evaluate_single_condition(self, condition: str, context: Dict) -> bool:
        """评估单个条件"""
        # 例如: "003.status == Done"
        if ".status ==" in condition:
            task_id, status = condition.split(".status ==")
            task_id = task_id.strip()
            status = status.strip()
            
            # 从数据库获取任务状态
            task = await self.task_repo.get_by_id(task_id)
            return task and task.status == status
        
        return False
    
    async def trigger_agent(self, listener: Listener, context: Dict):
        """触发Agent执行"""
        try:
            logger.info(f"Triggering agent {listener.agent_id} for listener {listener.id}")
            
            # 1. 构建Agent输入上下文
            agent_context = await self._build_agent_context(listener, context)
            
            # 2. 调用Agent执行
            result = await self.agent_manager.execute_agent(
                listener.agent_id,
                listener.action_prompt,
                agent_context
            )
            
            # 3. 处理Agent返回结果
            await self._handle_agent_result(listener, result)
            
        except Exception as e:
            logger.error(f"Error triggering agent {listener.agent_id}: {e}")
            # 处理失败情况
            await self._handle_agent_failure(listener, e)
    
    async def _build_agent_context(self, listener: Listener, context: Dict) -> Dict:
        """构建Agent输入上下文"""
        # 解析action_prompt中的上下文变量引用
        # 例如: {001.context.id} -> 获取任务001的上下文中的id字段
        agent_context = {}
        
        # 这里需要实现上下文变量的解析和注入
        # 简化实现
        agent_context.update(context)
        
        return agent_context
    
    async def _handle_agent_result(self, listener: Listener, result: Dict):
        """处理Agent执行结果"""
        if result.get("success", False):
            # 成功情况
            output = listener.success_output
        else:
            # 失败情况
            output = listener.failure_output
        
        # 更新目标任务状态
        await self.task_repo.update_status(
            output["task_id"],
            output["status"],
            output["context"]
        )
    
    async def _handle_agent_failure(self, listener: Listener, error: Exception):
        """处理Agent执行失败"""
        output = listener.failure_output
        output["context"]["error"] = str(error)
        
        await self.task_repo.update_status(
            output["task_id"],
            output["status"],
            output["context"]
        )

class TaskListenerModule:
    def __init__(self, task_repo: TaskRepository, listener_repo: ListenerRepository, agent_manager):
        self.task_state_manager = TaskStateManager(task_repo)
        self.listener_scheduler = ListenerScheduler(listener_repo, agent_manager)
        
        # 注册状态变化回调
        self.task_state_manager.add_status_change_callback(
            self.listener_scheduler.on_task_status_changed
        )
    
    async def start(self):
        """启动任务侦听模块"""
        logger.info("Task Listener Module started")
    
    async def stop(self):
        """停止任务侦听模块"""
        logger.info("Task Listener Module stopped")
```

### 2.2 计划模块实现

```python
# src/core/plan_module.py
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from ..models.plan import Plan
from ..models.task import Task
from ..models.listener import Listener
from ..database.repositories.plan_repository import PlanRepository
from ..database.repositories.task_repository import TaskRepository
from ..database.repositories.listener_repository import ListenerRepository

logger = logging.getLogger(__name__)

class PlanManager:
    def __init__(self, plan_repo: PlanRepository):
        self.plan_repo = plan_repo
    
    async def create_plan(self, plan_config: Dict) -> str:
        """创建新的执行计划"""
        try:
            plan = Plan(
                id=plan_config.get("plan_id"),
                name=plan_config.get("name"),
                description=plan_config.get("prompt"),
                config=plan_config,
                created_at=datetime.now()
            )
            
            plan_id = await self.plan_repo.create(plan)
            logger.info(f"Created plan {plan_id}")
            return plan_id
            
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            raise
    
    async def update_plan(self, plan_id: str, updates: Dict):
        """更新计划配置"""
        try:
            await self.plan_repo.update(plan_id, updates)
            logger.info(f"Updated plan {plan_id}")
        except Exception as e:
            logger.error(f"Failed to update plan {plan_id}: {e}")
            raise
    
    async def get_plan(self, plan_id: str) -> Optional[Plan]:
        """获取计划详情"""
        return await self.plan_repo.get_by_id(plan_id)
    
    async def search_plans(self, criteria: Dict) -> List[Plan]:
        """搜索匹配的计划"""
        return await self.plan_repo.search(criteria)
    
    async def get_few_shot_examples(self) -> List[Dict]:
        """获取Few-shot学习示例"""
        # 从数据库或配置文件获取示例
        examples = await self.plan_repo.get_few_shot_examples()
        return examples

class TaskManager:
    def __init__(self, task_repo: TaskRepository):
        self.task_repo = task_repo
    
    async def create_task(self, task_config: Dict) -> str:
        """创建任务"""
        try:
            task = Task(
                id=task_config.get("task_id"),
                plan_id=task_config.get("plan_id"),
                name=task_config.get("name"),
                prompt=task_config.get("prompt"),
                status="NotStarted",
                context={"status": "NotStarted", "values": {}},
                created_at=datetime.now()
            )
            
            task_id = await self.task_repo.create(task)
            logger.info(f"Created task {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            raise
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取单个任务"""
        return await self.task_repo.get_by_id(task_id)
    
    async def get_plan_tasks(self, plan_id: str) -> List[Task]:
        """获取计划的所有任务"""
        return await self.task_repo.get_by_plan_id(plan_id)
    
    async def get_task_context(self, task_id: str) -> Dict:
        """获取任务上下文"""
        task = await self.get_task(task_id)
        return task.context if task else {}

class ListenerManager:
    def __init__(self, listener_repo: ListenerRepository):
        self.listener_repo = listener_repo
    
    async def create_listener(self, listener_config: Dict) -> str:
        """创建侦听器"""
        try:
            listener = Listener(
                id=listener_config.get("listener_id"),
                plan_id=listener_config.get("plan_id"),
                trigger_task_id=listener_config.get("trigger_task_id"),
                trigger_condition=listener_config.get("trigger_condition"),
                action_condition=listener_config.get("action_condition"),
                agent_id=listener_config.get("agent_id"),
                action_prompt=listener_config.get("action_prompt"),
                success_output=listener_config.get("success_output"),
                failure_output=listener_config.get("failure_output")
            )
            
            listener_id = await self.listener_repo.create(listener)
            logger.info(f"Created listener {listener_id}")
            return listener_id
            
        except Exception as e:
            logger.error(f"Failed to create listener: {e}")
            raise
    
    async def get_listeners_by_task(self, task_id: str) -> List[Listener]:
        """获取监听特定任务的侦听器"""
        return await self.listener_repo.get_by_trigger_task(task_id)
    
    async def get_listeners_by_trigger(self, task_id: str, status: str) -> List[Listener]:
        """获取特定触发条件的侦听器"""
        return await self.listener_repo.get_by_trigger(task_id, status)

class PlanModule:
    def __init__(self, plan_repo: PlanRepository, task_repo: TaskRepository, listener_repo: ListenerRepository):
        self.plan_manager = PlanManager(plan_repo)
        self.task_manager = TaskManager(task_repo)
        self.listener_manager = ListenerManager(listener_repo)
    
    async def start(self):
        """启动计划模块"""
        logger.info("Plan Module started")
    
    async def stop(self):
        """停止计划模块"""
        logger.info("Plan Module stopped")
```

### 2.3 数据模型实现

```python
# src/models/plan.py
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class Plan:
    id: str
    name: str
    description: str
    config: Dict
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Plan':
        return cls(**data)

# src/models/task.py
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional
from enum import Enum

class TaskStatus(Enum):
    NOT_STARTED = "NotStarted"
    RUNNING = "Running"
    DONE = "Done"
    ERROR = "Error"
    PENDING = "Pending"

@dataclass
class Task:
    id: str
    plan_id: str
    name: str
    prompt: str
    status: str
    context: Dict
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        return cls(**data)

# src/models/listener.py
from dataclasses import dataclass, asdict
from typing import Dict

@dataclass
class Listener:
    id: str
    plan_id: str
    trigger_task_id: str
    trigger_condition: str
    action_condition: str
    agent_id: str
    action_prompt: str
    success_output: Dict
    failure_output: Dict
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Listener':
        return cls(**data)
```

### 2.4 数据库仓库实现

```python
# src/database/repositories/plan_repository.py
import logging
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from ...models.plan import Plan

logger = logging.getLogger(__name__)

class PlanRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
    
    async def create(self, plan: Plan) -> str:
        """创建计划"""
        try:
            # 这里需要实现具体的数据库操作
            # 使用SQLAlchemy或类似的ORM
            pass
        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            raise
    
    async def get_by_id(self, plan_id: str) -> Optional[Plan]:
        """根据ID获取计划"""
        try:
            # 实现数据库查询
            pass
        except Exception as e:
            logger.error(f"Failed to get plan {plan_id}: {e}")
            raise
    
    async def update(self, plan_id: str, updates: Dict):
        """更新计划"""
        try:
            # 实现数据库更新
            pass
        except Exception as e:
            logger.error(f"Failed to update plan {plan_id}: {e}")
            raise
    
    async def search(self, criteria: Dict) -> List[Plan]:
        """搜索计划"""
        try:
            # 实现搜索逻辑
            pass
        except Exception as e:
            logger.error(f"Failed to search plans: {e}")
            raise
    
    async def get_few_shot_examples(self) -> List[Dict]:
        """获取Few-shot示例"""
        try:
            # 从数据库获取示例数据
            pass
        except Exception as e:
            logger.error(f"Failed to get few-shot examples: {e}")
            raise
```

## 3. 配置文件

```yaml
# config/development.yaml
database:
  url: "postgresql://user:password@localhost:5432/aintegration"
  pool_size: 10
  max_overflow: 20

redis:
  url: "redis://localhost:6379/0"
  
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

mcp_server:
  host: "localhost"
  port: 8004
  protocol: "http"

a2a_server:
  host: "localhost"
  port: 8005
  protocol: "a2a"

google_adk:
  api_key: "your-api-key"
  model: "gemini-pro"
  
agents:
  hr_agent:
    system_prompt: "你是一个HR系统的专业代理"
    allowed_tools: ["create_employee", "update_employee"]
    
  finance_agent:
    system_prompt: "你是一个财务系统的专业代理"
    allowed_tools: ["enroll_payroll", "create_payroll_account"]
```

## 4. 依赖管理

```txt
# requirements.txt
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
asyncpg==0.29.0
redis==5.0.1
pydantic==2.5.0
python-multipart==0.0.6
python-dotenv==1.0.0
google-generativeai==0.3.2
httpx==0.25.2
pytest==7.4.3
pytest-asyncio==0.21.1
```

## 5. 启动脚本

```python
# main.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from src.core.task_listener import TaskListenerModule
from src.core.plan_module import PlanModule
from src.api.planner_api import router as planner_router

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局模块实例
task_listener_module = None
plan_module = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global task_listener_module, plan_module
    
    # 启动时初始化
    logger.info("Starting AIntegration system...")
    
    # 初始化数据库连接
    # 初始化各个模块
    # task_listener_module = TaskListenerModule(...)
    # plan_module = PlanModule(...)
    
    # 启动模块
    # await task_listener_module.start()
    # await plan_module.start()
    
    logger.info("AIntegration system started")
    
    yield
    
    # 关闭时清理
    logger.info("Stopping AIntegration system...")
    # await task_listener_module.stop()
    # await plan_module.stop()
    logger.info("AIntegration system stopped")

# 创建FastAPI应用
app = FastAPI(
    title="AIntegration API",
    description="企业集成代理框架",
    version="1.0.0",
    lifespan=lifespan
)

# 注册路由
app.include_router(planner_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

*这个实现指南提供了具体的Python代码实现，补充了原文档中缺失的技术细节。*
