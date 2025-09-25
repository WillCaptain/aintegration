"""
计划数据模型
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)

class PlanStatus(Enum):
    """计划状态枚举"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Plan:
    """计划模型"""
    id: str
    name: str
    description: str
    config: Dict[str, Any]
    status: str = PlanStatus.DRAFT.value
    main_task_id: Optional[str] = None
    created_at: datetime = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Plan':
        """从字典创建实例"""
        return cls(**data)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        import json
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Plan':
        """从JSON字符串创建实例"""
        import json
        data = json.loads(json_str)
        # 处理日期时间字段
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            data['updated_at'] = datetime.fromisoformat(data['updated_at']) if data['updated_at'] else None
        if 'started_at' in data:
            data['started_at'] = datetime.fromisoformat(data['started_at']) if data['started_at'] else None
        if 'completed_at' in data:
            data['completed_at'] = datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None
        return cls.from_dict(data)
    
    def is_active(self) -> bool:
        """检查计划是否处于活跃状态"""
        return self.status == PlanStatus.ACTIVE.value
    
    def is_completed(self) -> bool:
        """检查计划是否已完成"""
        return self.status == PlanStatus.COMPLETED.value
    
    def is_failed(self) -> bool:
        """检查计划是否失败"""
        return self.status == PlanStatus.FAILED.value
    
    def start(self):
        """启动计划"""
        if self.status == PlanStatus.DRAFT.value:
            self.status = PlanStatus.ACTIVE.value
            self.started_at = datetime.now()
            self.updated_at = datetime.now()
    
    def complete(self):
        """完成计划"""
        if self.status == PlanStatus.ACTIVE.value:
            self.status = PlanStatus.COMPLETED.value
            self.completed_at = datetime.now()
            self.updated_at = datetime.now()
    
    def fail(self, error_message: Optional[str] = None):
        """标记计划为失败"""
        if self.status == PlanStatus.ACTIVE.value:
            self.status = PlanStatus.FAILED.value
            self.completed_at = datetime.now()
            self.updated_at = datetime.now()
            if error_message:
                self.config["error_message"] = error_message
    
    def cancel(self):
        """取消计划"""
        if self.status in [PlanStatus.DRAFT.value, PlanStatus.ACTIVE.value]:
            self.status = PlanStatus.CANCELLED.value
            self.completed_at = datetime.now()
            self.updated_at = datetime.now()
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号路径，如 'metadata.author'"""
        if not key:
            return default
        parts = key.split(".")
        current: Any = self.config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current
    
    def set_config_value(self, key: str, value: Any):
        """设置配置值，支持点号路径，如 'metadata.author'"""
        if not key:
            return
        parts = key.split(".")
        target = self.config
        for part in parts[:-1]:
            if not isinstance(target.get(part), dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        self.updated_at = datetime.now()
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        return self.config.get("metadata", {})
    
    @metadata.setter
    def metadata(self, value: Dict[str, Any]):
        """设置元数据"""
        self.config["metadata"] = value
        self.updated_at = datetime.now()
    
    async def execute(self, plan_module: 'PlanModule') -> Dict[str, Any]:
        """执行计划，包括重新规划功能"""
        try:
            # 启动计划
            if not self.is_active():
                self.start()
                await plan_module.plan_manager.update_plan(self.id, {
                    "status": self.status,
                    "started_at": self.started_at
                })
            
            # 启动侦听引擎
            await plan_module.listener_engine.start_plan_execution(self.id)
            
            # 检查计划完成状态
            is_completed = await plan_module.listener_engine.check_plan_completion(self.id)
            
            if is_completed:
                return {
                    "success": True,
                    "status": "completed",
                    "plan_id": self.id,
                    "message": f"Plan {self.id} completed successfully"
                }
            else:
                return {
                    "success": True,
                    "status": "running",
                    "plan_id": self.id,
                    "message": f"Plan {self.id} is running"
                }
                
        except Exception as e:
            logger.error(f"Error executing plan {self.id}: {e}")
            self.fail(str(e))
            await plan_module.plan_manager.update_plan(self.id, {
                "status": self.status,
                "completed_at": self.completed_at,
                "config": self.config
            })
            return {
                "success": False,
                "status": "failed",
                "plan_id": self.id,
                "error": str(e)
            }
    
    async def replan(self, plan_module: 'PlanModule', new_config: Dict[str, Any]) -> Dict[str, Any]:
        """重新规划，更新计划配置并重新执行"""
        try:
            # 更新计划配置
            self.config.update(new_config)
            self.updated_at = datetime.now()
            
            # 保存更新
            await plan_module.plan_manager.update_plan(self.id, {
                "config": self.config,
                "updated_at": self.updated_at
            })
            
            # 重新执行计划
            return await self.execute(plan_module)
            
        except Exception as e:
            logger.error(f"Error replanning {self.id}: {e}")
            return {
                "success": False,
                "plan_id": self.id,
                "error": str(e)
            }