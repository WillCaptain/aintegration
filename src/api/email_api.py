"""
邮件发送API接口

专门用于邮件发送功能的API端点
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from ..core.email_plan_creator import EmailPlanCreator
from ..core.email_execution_engine import EmailExecutionEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])

class SendEmailRequest(BaseModel):
    """发送邮件请求模型"""
    recipient: EmailStr
    subject: str
    body: str
    user_request: Optional[str] = None

class BulkEmailRequest(BaseModel):
    """批量发送邮件请求模型"""
    recipients: List[EmailStr]
    subject: str
    body: str
    user_request: Optional[str] = None

class EmailExecutionResponse(BaseModel):
    """邮件执行响应模型"""
    execution_id: str
    plan_id: str
    status: str
    message: str
    task_count: int

class EmailStatusResponse(BaseModel):
    """邮件状态响应模型"""
    execution_id: str
    status: str
    task_states: Dict[str, Dict[str, any]]
    error_message: Optional[str] = None

# 全局实例
email_plan_creator = EmailPlanCreator()
email_execution_engine = EmailExecutionEngine()

@router.post("/send", response_model=EmailExecutionResponse)
async def send_email(request: SendEmailRequest):
    """发送单封邮件"""
    try:
        logger.info(f"收到邮件发送请求: {request.recipient}")
        
        # 创建邮件发送计划
        plan_config = email_plan_creator.create_send_email_plan(
            recipient=str(request.recipient),
            subject=request.subject,
            body=request.body
        )
        
        # 验证计划配置
        validation_result = email_plan_creator.validate_email_plan(plan_config)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"计划配置无效: {validation_result['errors']}"
            )
        
        # 构建执行上下文
        context = {
            "user_request": request.user_request or f"发送邮件给{request.recipient}",
            "to": str(request.recipient),
            "subject": request.subject,
            "body": request.body
        }
        
        # 执行邮件发送计划
        execution = await email_execution_engine.execute_email_plan(plan_config, context)
        
        return EmailExecutionResponse(
            execution_id=execution.id,
            plan_id=plan_config["plan_id"],
            status=execution.status,
            message="邮件发送请求已提交",
            task_count=len(plan_config["tasks"])
        )
        
    except Exception as e:
        logger.error(f"发送邮件时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send/bulk", response_model=EmailExecutionResponse)
async def send_bulk_email(request: BulkEmailRequest):
    """批量发送邮件"""
    try:
        logger.info(f"收到批量邮件发送请求: {len(request.recipients)}个收件人")
        
        if len(request.recipients) > 100:
            raise HTTPException(
                status_code=400,
                detail="批量发送邮件数量不能超过100个"
            )
        
        # 创建批量邮件发送计划
        plan_config = email_plan_creator.create_bulk_email_plan(
            recipients=[str(recipient) for recipient in request.recipients],
            subject=request.subject,
            body=request.body
        )
        
        # 验证计划配置
        validation_result = email_plan_creator.validate_email_plan(plan_config)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"计划配置无效: {validation_result['errors']}"
            )
        
        # 构建执行上下文
        context = {
            "user_request": request.user_request or f"批量发送邮件给{len(request.recipients)}个收件人",
            "recipients": [str(recipient) for recipient in request.recipients],
            "subject": request.subject,
            "body": request.body
        }
        
        # 执行批量邮件发送计划
        execution = await email_execution_engine.execute_email_plan(plan_config, context)
        
        return EmailExecutionResponse(
            execution_id=execution.id,
            plan_id=plan_config["plan_id"],
            status=execution.status,
            message=f"批量邮件发送请求已提交，共{len(request.recipients)}个收件人",
            task_count=len(plan_config["tasks"])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量发送邮件时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}", response_model=EmailStatusResponse)
async def get_email_execution_status(execution_id: str):
    """获取邮件发送执行状态"""
    try:
        logger.info(f"获取邮件发送执行状态: {execution_id}")
        
        status_info = email_execution_engine.get_execution_status(execution_id)
        
        if not status_info:
            raise HTTPException(status_code=404, detail="执行记录未找到")
        
        return EmailStatusResponse(
            execution_id=status_info["execution_id"],
            status=status_info["status"],
            task_states=status_info["task_states"],
            error_message=status_info.get("error_message")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取邮件发送执行状态时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/executions/{execution_id}")
async def cancel_email_execution(execution_id: str):
    """取消邮件发送执行"""
    try:
        logger.info(f"取消邮件发送执行: {execution_id}")
        
        # 清理执行记录
        email_execution_engine.cleanup_execution(execution_id)
        
        return {"message": "邮件发送执行已取消"}
        
    except Exception as e:
        logger.error(f"取消邮件发送执行时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plans/templates")
async def get_email_plan_templates():
    """获取邮件发送计划模板"""
    try:
        templates = {
            "simple_email": {
                "name": "简单邮件发送",
                "description": "向单个收件人发送邮件",
                "parameters": ["recipient", "subject", "body"],
                "example": {
                    "recipient": "user@example.com",
                    "subject": "测试邮件",
                    "body": "这是一封测试邮件"
                }
            },
            "bulk_email": {
                "name": "批量邮件发送",
                "description": "向多个收件人发送相同邮件",
                "parameters": ["recipients", "subject", "body"],
                "example": {
                    "recipients": ["user1@example.com", "user2@example.com"],
                    "subject": "通知邮件",
                    "body": "这是通知内容"
                }
            }
        }
        
        return {"templates": templates}
        
    except Exception as e:
        logger.error(f"获取邮件计划模板时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate")
async def validate_email_config(request: SendEmailRequest):
    """验证邮件配置"""
    try:
        logger.info(f"验证邮件配置: {request.recipient}")
        
        # 创建临时计划配置进行验证
        plan_config = email_plan_creator.create_send_email_plan(
            recipient=str(request.recipient),
            subject=request.subject,
            body=request.body
        )
        
        # 验证计划配置
        validation_result = email_plan_creator.validate_email_plan(plan_config)
        
        return {
            "valid": validation_result["valid"],
            "errors": validation_result["errors"],
            "warnings": validation_result["warnings"],
            "plan_id": validation_result["plan_id"],
            "task_count": validation_result["task_count"],
            "listener_count": validation_result["listener_count"]
        }
        
    except Exception as e:
        logger.error(f"验证邮件配置时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
