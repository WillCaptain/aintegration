"""
邮件发送计划创建器

专门用于创建邮件发送相关的计划
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..models.plan import Plan
from ..models.task import Task
from ..models.listener import Listener

logger = logging.getLogger(__name__)

class EmailPlanCreator:
    """邮件发送计划创建器"""
    
    def __init__(self):
        self.agent_id = "email_agent_v1"
    
    def create_send_email_plan(
        self,
        recipient: str,
        subject: str,
        body: str,
        plan_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建发送邮件的计划"""
        try:
            # 生成计划ID
            if not plan_id:
                plan_id = f"email_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 生成任务ID
            task_id = f"task_{plan_id.split('_')[-1]}"
            
            # 生成侦听器ID
            listener_id = f"listener_{plan_id.split('_')[-1]}"
            
            # 创建计划配置
            plan_config = {
                "plan_id": plan_id,
                "name": f"发送邮件给{recipient}",
                "prompt": f"向{recipient}发送邮件：{subject}",
                "main_task_id": task_id,
                "tasks": [
                    {
                        "task_id": task_id,
                        "name": "发送邮件",
                        "prompt": f"向{recipient}发送邮件",
                        "plan_id": plan_id
                    }
                ],
                "listeners": [
                    {
                        "listener_id": listener_id,
                        "plan_id": plan_id,
                        "trigger_task_id": task_id,
                        "trigger_condition": f"{task_id}.status == Running",
                        "action_condition": "true",
                        "agent_id": self.agent_id,
                        "action_prompt": f"向用户{recipient}发送邮件，主题：{subject}，内容：{body}",
                        "success_output": {
                            "task_id": task_id,
                            "status": "Done",
                            "context": {
                                "email_sent": True,
                                "recipient": recipient,
                                "subject": subject,
                                "sent_at": None  # 将在执行时填入
                            }
                        },
                        "failure_output": {
                            "task_id": task_id,
                            "status": "Error",
                            "context": {
                                "email_sent": False,
                                "error": "邮件发送失败",
                                "recipient": recipient
                            }
                        }
                    }
                ],
                "metadata": {
                    "type": "email_sending",
                    "recipient": recipient,
                    "subject": subject,
                    "created_at": datetime.now().isoformat(),
                    "creator": "EmailPlanCreator"
                }
            }
            
            logger.info(f"创建邮件发送计划: {plan_id} -> {recipient}")
            return plan_config
            
        except Exception as e:
            logger.error(f"创建邮件发送计划时发生错误: {e}")
            raise
    
    def create_bulk_email_plan(
        self,
        recipients: list,
        subject: str,
        body: str,
        plan_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """创建批量发送邮件的计划"""
        try:
            # 生成计划ID
            if not plan_id:
                plan_id = f"bulk_email_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 创建主任务
            main_task_id = "task_main"
            main_task = {
                "task_id": main_task_id,
                "name": "批量发送邮件",
                "prompt": f"向{len(recipients)}个收件人发送邮件",
                "plan_id": plan_id
            }
            
            # 为每个收件人创建子任务
            tasks = [main_task]
            listeners = []
            
            for i, recipient in enumerate(recipients):
                task_id = f"task_{i+1:03d}"
                listener_id = f"listener_{i+1:03d}"
                
                # 创建子任务
                task = {
                    "task_id": task_id,
                    "name": f"发送邮件给{recipient}",
                    "prompt": f"向{recipient}发送邮件",
                    "plan_id": plan_id
                }
                tasks.append(task)
                
                # 创建侦听器
                listener = {
                    "listener_id": listener_id,
                    "plan_id": plan_id,
                    "trigger_task_id": task_id,
                    "trigger_condition": f"{task_id}.status == Running",
                    "action_condition": "true",
                    "agent_id": self.agent_id,
                    "action_prompt": f"向用户{recipient}发送邮件，主题：{subject}，内容：{body}",
                    "success_output": {
                        "task_id": task_id,
                        "status": "Done",
                        "context": {
                            "email_sent": True,
                            "recipient": recipient,
                            "subject": subject
                        }
                    },
                    "failure_output": {
                        "task_id": task_id,
                        "status": "Error",
                        "context": {
                            "email_sent": False,
                            "error": "邮件发送失败",
                            "recipient": recipient
                        }
                    }
                }
                listeners.append(listener)
            
            # 创建主任务完成的侦听器
            completion_listener = {
                "listener_id": "listener_completion",
                "plan_id": plan_id,
                "trigger_task_id": f"task_001",  # 监听第一个子任务
                "trigger_condition": f"task_001.status == Done",
                "action_condition": "true",  # 这里需要更复杂的条件来检查所有任务
                "agent_id": "planner",
                "action_prompt": "检查所有邮件发送任务是否完成",
                "success_output": {
                    "task_id": main_task_id,
                    "status": "Done",
                    "context": {
                        "bulk_email_completed": True,
                        "total_recipients": len(recipients),
                        "completed_count": len(recipients)
                    }
                },
                "failure_output": {
                    "task_id": main_task_id,
                    "status": "Pending",
                    "context": {
                        "bulk_email_completed": False,
                        "total_recipients": len(recipients),
                        "completed_count": 0
                    }
                }
            }
            listeners.append(completion_listener)
            
            plan_config = {
                "plan_id": plan_id,
                "name": f"批量发送邮件给{len(recipients)}个收件人",
                "prompt": f"向{len(recipients)}个收件人发送邮件：{subject}",
                "main_task_id": main_task_id,
                "tasks": tasks,
                "listeners": listeners,
                "metadata": {
                    "type": "bulk_email_sending",
                    "recipients": recipients,
                    "subject": subject,
                    "created_at": datetime.now().isoformat(),
                    "creator": "EmailPlanCreator"
                }
            }
            
            logger.info(f"创建批量邮件发送计划: {plan_id} -> {len(recipients)}个收件人")
            return plan_config
            
        except Exception as e:
            logger.error(f"创建批量邮件发送计划时发生错误: {e}")
            raise
    
    def validate_email_plan(self, plan_config: Dict[str, Any]) -> Dict[str, Any]:
        """验证邮件发送计划"""
        try:
            errors = []
            warnings = []
            
            # 检查必需字段
            required_fields = ["plan_id", "name", "prompt", "main_task_id", "tasks", "listeners"]
            for field in required_fields:
                if field not in plan_config:
                    errors.append(f"缺少必需字段: {field}")
            
            # 检查任务配置
            if "tasks" in plan_config:
                for task in plan_config["tasks"]:
                    if not all(key in task for key in ["task_id", "name", "prompt"]):
                        errors.append("任务配置缺少必需字段")
            
            # 检查侦听器配置
            if "listeners" in plan_config:
                for listener in plan_config["listeners"]:
                    required_listener_fields = [
                        "listener_id", "trigger_task_id", "action_condition",
                        "agent_id", "action_prompt", "success_output", "failure_output"
                    ]
                    for field in required_listener_fields:
                        if field not in listener:
                            errors.append(f"侦听器配置缺少字段: {field}")
            
            # 检查邮件相关信息
            if plan_config.get("metadata", {}).get("type") == "email_sending":
                if "recipient" not in plan_config.get("metadata", {}):
                    warnings.append("邮件计划缺少收件人信息")
            
            is_valid = len(errors) == 0
            
            return {
                "valid": is_valid,
                "errors": errors,
                "warnings": warnings,
                "plan_id": plan_config.get("plan_id"),
                "task_count": len(plan_config.get("tasks", [])),
                "listener_count": len(plan_config.get("listeners", []))
            }
            
        except Exception as e:
            logger.error(f"验证邮件计划时发生错误: {e}")
            return {
                "valid": False,
                "errors": [f"验证过程发生错误: {str(e)}"],
                "warnings": [],
                "plan_id": None,
                "task_count": 0,
                "listener_count": 0
            }
