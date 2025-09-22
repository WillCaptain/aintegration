"""
Plan API接口
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["plans"])

class PlanResponse(BaseModel):
    """计划响应模型"""
    id: str
    name: str
    description: str
    config: Dict
    created_at: str
    updated_at: Optional[str] = None

class PlanCreate(BaseModel):
    """计划创建模型"""
    name: str
    description: str
    config: Dict

class PlanUpdate(BaseModel):
    """计划更新模型"""
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict] = None

# 依赖注入函数（需要在实际应用中实现）
def get_plan_manager():
    """获取Plan管理器实例"""
    # 这里应该返回实际的Plan管理器实例
    return None

@router.post("/", response_model=PlanResponse)
async def create_plan(
    plan_data: PlanCreate,
    plan_manager = Depends(get_plan_manager)
):
    """创建计划"""
    try:
        logger.info(f"Creating plan: {plan_data.name}")
        
        if not plan_manager:
            raise HTTPException(status_code=500, detail="Plan manager not available")
        
        # 构建计划配置
        plan_config = {
            "name": plan_data.name,
            "prompt": plan_data.description,
            "config": plan_data.config
        }
        
        # 创建计划
        plan_id = await plan_manager.create_plan(plan_config)
        
        # 获取创建的计划
        plan = await plan_manager.get_plan(plan_id)
        
        return PlanResponse(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            config=plan.config,
            created_at=plan.created_at.isoformat() if plan.created_at else "",
            updated_at=plan.updated_at.isoformat() if plan.updated_at else None
        )
        
    except Exception as e:
        logger.error(f"Error creating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str,
    plan_manager = Depends(get_plan_manager)
):
    """获取计划"""
    try:
        logger.info(f"Getting plan: {plan_id}")
        
        if not plan_manager:
            raise HTTPException(status_code=500, detail="Plan manager not available")
        
        plan = await plan_manager.get_plan(plan_id)
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        return PlanResponse(
            id=plan.id,
            name=plan.name,
            description=plan.description,
            config=plan.config,
            created_at=plan.created_at.isoformat() if plan.created_at else "",
            updated_at=plan.updated_at.isoformat() if plan.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: str,
    plan_update: PlanUpdate,
    plan_manager = Depends(get_plan_manager)
):
    """更新计划"""
    try:
        logger.info(f"Updating plan: {plan_id}")
        
        if not plan_manager:
            raise HTTPException(status_code=500, detail="Plan manager not available")
        
        # 获取当前计划
        plan = await plan_manager.get_plan(plan_id)
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # 构建更新数据
        updates = {}
        if plan_update.name is not None:
            updates["name"] = plan_update.name
        if plan_update.description is not None:
            updates["description"] = plan_update.description
        if plan_update.config is not None:
            updates["config"] = plan_update.config
        
        # 更新计划
        if updates:
            await plan_manager.update_plan(plan_id, updates)
        
        # 返回更新后的计划
        updated_plan = await plan_manager.get_plan(plan_id)
        
        return PlanResponse(
            id=updated_plan.id,
            name=updated_plan.name,
            description=updated_plan.description,
            config=updated_plan.config,
            created_at=updated_plan.created_at.isoformat() if updated_plan.created_at else "",
            updated_at=updated_plan.updated_at.isoformat() if updated_plan.updated_at else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[PlanResponse])
async def list_plans(
    limit: int = Query(100, description="Maximum number of plans to return"),
    offset: int = Query(0, description="Number of plans to skip"),
    plan_manager = Depends(get_plan_manager)
):
    """列出计划"""
    try:
        logger.info(f"Listing plans with limit={limit}, offset={offset}")
        
        if not plan_manager:
            raise HTTPException(status_code=500, detail="Plan manager not available")
        
        # 获取计划列表
        plans = await plan_manager.plan_repo.list_all(limit=limit, offset=offset)
        
        return [
            PlanResponse(
                id=plan.id,
                name=plan.name,
                description=plan.description,
                config=plan.config,
                created_at=plan.created_at.isoformat() if plan.created_at else "",
                updated_at=plan.updated_at.isoformat() if plan.updated_at else None
            )
            for plan in plans
        ]
        
    except Exception as e:
        logger.error(f"Error listing plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=List[PlanResponse])
async def search_plans(
    query: str = Query(..., description="Search query"),
    plan_manager = Depends(get_plan_manager)
):
    """搜索计划"""
    try:
        logger.info(f"Searching plans with query: {query}")
        
        if not plan_manager:
            raise HTTPException(status_code=500, detail="Plan manager not available")
        
        # 构建搜索条件
        criteria = {
            "query": query
        }
        
        # 搜索计划
        plans = await plan_manager.search_plans(criteria)
        
        return [
            PlanResponse(
                id=plan.id,
                name=plan.name,
                description=plan.description,
                config=plan.config,
                created_at=plan.created_at.isoformat() if plan.created_at else "",
                updated_at=plan.updated_at.isoformat() if plan.updated_at else None
            )
            for plan in plans
        ]
        
    except Exception as e:
        logger.error(f"Error searching plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: str,
    plan_manager = Depends(get_plan_manager)
):
    """删除计划"""
    try:
        logger.info(f"Deleting plan: {plan_id}")
        
        if not plan_manager:
            raise HTTPException(status_code=500, detail="Plan manager not available")
        
        # 检查计划是否存在
        plan = await plan_manager.get_plan(plan_id)
        
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # 删除计划
        await plan_manager.plan_repo.delete(plan_id)
        
        return {"message": "Plan deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))
