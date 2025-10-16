"""
系统常量定义
"""

from typing import Dict, Any
from enum import Enum

class SystemConstants:
    """系统常量"""
    
    # 默认主任务ID配置
    DEFAULT_MAIN_TASK_ID = "main_task"
    
    # 任务ID生成策略
    TASK_ID_PATTERN = "{task_type}_{sequence:03d}"
    
    # 侦听器ID生成策略  
    LISTENER_ID_PATTERN = "L{sequence:03d}"
    
    # 默认Agent配置
    DEFAULT_AGENT_CONFIG = {
        "hr_agent": {
            "id": "hr_agent",
            "name": "HR Agent",
            "version": "v1"
        },
        "email_agent": {
            "id": "email_agent", 
            "name": "Email Agent",
            "version": "v1"
        },
        "it_agent": {
            "id": "it_agent",
            "name": "IT Agent", 
            "version": "v1"
        }
    }
    
    # 默认业务场景配置
    DEFAULT_BUSINESS_SCENARIOS = {
        "employee_onboarding": {
            "name": "员工入职",
            "description": "新员工入职流程",
            "main_task_name": "员工入职完成"
        },
        "equipment_request": {
            "name": "设备申请",
            "description": "员工设备申请流程", 
            "main_task_name": "设备申请完成"
        },
        "leave_request": {
            "name": "请假申请",
            "description": "员工请假申请流程",
            "main_task_name": "请假申请完成"
        }
    }
    
    # 默认示例数据
    DEFAULT_SAMPLE_DATA = {
        "employee_name": "示例员工",
        "department": "示例部门",
        "position": "示例职位"
    }

class TaskStatus(Enum):
    """任务状态枚举"""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    PENDING = "pending"
    RETRYING = "retrying"

class PlanInstanceStatus(Enum):
    """计划实例状态枚举"""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    PAUSE = "pause"
    CONTINUE = "continue"

class ListenerType(Enum):
    """侦听器类型枚举"""
    AGENT = "agent"
    CODE = "code"
