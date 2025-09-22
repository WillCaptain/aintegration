"""
Task API接口
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

class TaskResponse(BaseModel):
    """任务响应模型"""
    id: str
    plan_id: str
    name: str
    prompt: str
    status: str
    context: Dict
    created_at: str
    updated_at: Optional[str] = None

class TaskUpdate(BaseModel):
    """任务更新模型"""
    status: Optional[str] = None
    context: Optional[Dict] = None

# 依赖注入函数（需要在实际应用中实现）
def get_task_manager():
    """获取Task管理器实例"""
    # 这里应该返回实际的Task管理器实例
    return None

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    task_manager = Depends(get_task_manager)
):
    """获取单个任务"""
    try:
        logger.info(f"Getting task: {task_id}")
        
        if not task_manager:
            raise HTTPException(status_code=500, detail="Task manager not available")
        
        task = await task_manager.get_task(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskResponse(
            id=task.id,
            plan_id=task.plan_id,
            name=task.name,
            prompt=task.prompt,
            status=task.status,
            context=task.context,
            created_at=task.created_at.isoformat() if task.created_at else "",
            updated_at=task.updated_at.isoformat() if task.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plan/{plan_id}", response_model=List[TaskResponse])
async def get_plan_tasks(
    plan_id: str,
    task_manager = Depends(get_task_manager)
):
    """获取计划的所有任务"""
    try:
        logger.info(f"Getting tasks for plan: {plan_id}")
        
        if not task_manager:
            raise HTTPException(status_code=500, detail="Task manager not available")
        
        tasks = await task_manager.get_plan_tasks(plan_id)
        
        return [
            TaskResponse(
                id=task.id,
                plan_id=task.plan_id,
                name=task.name,
                prompt=task.prompt,
                status=task.status,
                context=task.context,
                created_at=task.created_at.isoformat() if task.created_at else "",
                updated_at=task.updated_at.isoformat() if task.updated_at else None
            )
            for task in tasks
        ]
        
    except Exception as e:
        logger.error(f"Error getting plan tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    task_manager = Depends(get_task_manager)
):
    """更新任务"""
    try:
        logger.info(f"Updating task: {task_id}")
        
        if not task_manager:
            raise HTTPException(status_code=500, detail="Task manager not available")
        
        # 获取当前任务
        task = await task_manager.get_task(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 更新任务
        updates = {}
        if task_update.status is not None:
            updates["status"] = task_update.status
        if task_update.context is not None:
            updates["context"] = task_update.context
        
        if updates:
            await task_manager.task_repo.update(task_id, updates)
        
        # 返回更新后的任务
        updated_task = await task_manager.get_task(task_id)
        
        return TaskResponse(
            id=updated_task.id,
            plan_id=updated_task.plan_id,
            name=updated_task.name,
            prompt=updated_task.prompt,
            status=updated_task.status,
            context=updated_task.context,
            created_at=updated_task.created_at.isoformat() if updated_task.created_at else "",
            updated_at=updated_task.updated_at.isoformat() if updated_task.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}/context")
async def get_task_context(
    task_id: str,
    task_manager = Depends(get_task_manager)
):
    """获取任务上下文"""
    try:
        logger.info(f"Getting task context: {task_id}")
        
        if not task_manager:
            raise HTTPException(status_code=500, detail="Task manager not available")
        
        context = await task_manager.get_task_context(task_id)
        
        return {
            "task_id": task_id,
            "context": context
        }
        
    except Exception as e:
        logger.error(f"Error getting task context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by task status"),
    limit: int = Query(100, description="Maximum number of tasks to return"),
    offset: int = Query(0, description="Number of tasks to skip"),
    task_manager = Depends(get_task_manager)
):
    """列出任务"""
    try:
        logger.info(f"Listing tasks with status={status}, limit={limit}, offset={offset}")
        
        if not task_manager:
            raise HTTPException(status_code=500, detail="Task manager not available")
        
        # 这里应该实现任务列表查询
        # 简化实现，返回空列表
        return []
        
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
