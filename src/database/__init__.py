"""
数据库层

在测试或内存模式下，优先使用内存仓库以避免加载 SQLAlchemy。
"""

import os

USE_MEMORY = os.getenv("AINTEGRATION_DB", "memory").lower() in ("memory", "mem", "1", "true")

if USE_MEMORY:
    from .memory_repositories import (
        MemoryDatabaseConnection as DatabaseConnection,
        MemoryPlanRepository as PlanRepository,
        MemoryTaskRepository as TaskRepository,
        MemoryListenerRepository as ListenerRepository,
        MemoryExecutionRepository as ExecutionRepository,
    )
else:
    from .connection import DatabaseConnection
    from .repositories.plan_repository import PlanRepository
    from .repositories.task_repository import TaskRepository
    from .repositories.listener_repository import ListenerRepository
    from .repositories.execution_repository import ExecutionRepository

__all__ = [
    "DatabaseConnection",
    "PlanRepository",
    "TaskRepository", 
    "ListenerRepository",
    "ExecutionRepository"
]
