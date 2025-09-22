"""
Planner API接口
"""

import logging
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/planner", tags=["planner"])

class UserRequest(BaseModel):
    """用户请求模型"""
    request: str
    context: Optional[Dict] = None

class ExecutionResponse(BaseModel):
    """执行响应模型"""
    execution_id: str
    status: str
    message: str
    plan_id: Optional[str] = None

class ExecutionStatus(BaseModel):
    """执行状态模型"""
    execution_id: str
    status: str
    progress: Optional[Dict] = None
    error_message: Optional[str] = None

# 依赖注入函数（需要在实际应用中实现）
def get_planner_module():
    """获取Planner模块实例"""
    # 这里应该返回实际的Planner模块实例
    return None

@router.post("/execute", response_model=ExecutionResponse)
async def execute_request(
    request: UserRequest,
    planner_module = Depends(get_planner_module)
):
    """执行用户请求"""
    try:
        logger.info(f"Received user request: {request.request}")
        
        if not planner_module:
            raise HTTPException(status_code=500, detail="Planner module not available")
        
        # 执行请求
        execution = await planner_module.execute_request(request.request)
        
        return ExecutionResponse(
            execution_id=execution.id,
            status=execution.status,
            message="Request submitted successfully",
            plan_id=execution.plan_id
        )
        
    except Exception as e:
        logger.error(f"Error executing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}", response_model=ExecutionStatus)
async def get_execution_status(
    execution_id: str,
    planner_module = Depends(get_planner_module)
):
    """获取执行状态"""
    try:
        logger.info(f"Getting execution status: {execution_id}")
        
        if not planner_module:
            raise HTTPException(status_code=500, detail="Planner module not available")
        
        # 获取执行状态
        execution = await planner_module.execution_repo.get_by_id(execution_id)
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        return ExecutionStatus(
            execution_id=execution.id,
            status=execution.status,
            error_message=execution.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}/logs")
async def get_execution_logs(
    execution_id: str,
    planner_module = Depends(get_planner_module)
):
    """获取执行日志"""
    try:
        logger.info(f"Getting execution logs: {execution_id}")
        
        if not planner_module:
            raise HTTPException(status_code=500, detail="Planner module not available")
        
        # 获取执行记录
        execution = await planner_module.execution_repo.get_by_id(execution_id)
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        return {
            "execution_id": execution.id,
            "user_request": execution.user_request,
            "plan_id": execution.plan_id,
            "status": execution.status,
            "start_time": execution.start_time,
            "end_time": execution.end_time,
            "execution_log": [
                {
                    "timestamp": entry.timestamp,
                    "event": entry.event,
                    "details": entry.details,
                    "task_id": entry.task_id
                }
                for entry in execution.execution_log
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting execution logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    planner_module = Depends(get_planner_module)
):
    """取消执行"""
    try:
        logger.info(f"Cancelling execution: {execution_id}")
        
        if not planner_module:
            raise HTTPException(status_code=500, detail="Planner module not available")
        
        # 更新执行状态为取消
        await planner_module.execution_repo.update_status(
            execution_id, 
            "cancelled",
            "Execution cancelled by user"
        )
        
        return {"message": "Execution cancelled successfully"}
        
    except Exception as e:
        logger.error(f"Error cancelling execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))
