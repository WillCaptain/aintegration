"""
TODO日志记录器

记录所有生成的TODO，便于调试和监控
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class TodoLogger:
    """TODO日志记录器"""
    
    def __init__(self, log_file_path: str = "tests/.artifacts/todo_generation.log"):
        self.log_file_path = Path(log_file_path)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
    def log_todo_created(self, todo_id: str, plan_instance_id: str, listener_id: str, 
                        parameter_config: Dict[str, Any], assignee_id: str = None):
        """记录TODO创建"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "todo_created",
            "todo_id": todo_id,
            "plan_instance_id": plan_instance_id,
            "listener_id": listener_id,
            "assignee_id": assignee_id,
            "parameter_config": parameter_config,
            "interaction_fields": parameter_config.get("interaction_json", {}).get("fields", [])
        }
        
        self._write_log_entry(log_entry)
        logger.info(f"TODO created: {todo_id} for plan {plan_instance_id}")
    
    def log_todo_completed(self, todo_id: str, completion_data: Dict[str, Any]):
        """记录TODO完成"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "todo_completed",
            "todo_id": todo_id,
            "completion_data": completion_data
        }
        
        self._write_log_entry(log_entry)
        logger.info(f"TODO completed: {todo_id}")
    
    def log_todo_assigned(self, todo_id: str, assignee_id: str, assignee_role: str):
        """记录TODO分配"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "todo_assigned",
            "todo_id": todo_id,
            "assignee_id": assignee_id,
            "assignee_role": assignee_role
        }
        
        self._write_log_entry(log_entry)
        logger.info(f"TODO assigned: {todo_id} to {assignee_id} ({assignee_role})")
    
    def log_parameter_continue(self, plan_instance_id: str, todo_id: str, provided_params: Dict[str, Any]):
        """记录参数继续执行"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "parameter_continue",
            "plan_instance_id": plan_instance_id,
            "todo_id": todo_id,
            "provided_params": provided_params
        }
        
        self._write_log_entry(log_entry)
        logger.info(f"Parameter continue: plan {plan_instance_id} with todo {todo_id}")
    
    def _write_log_entry(self, log_entry: Dict[str, Any]):
        """写入日志条目"""
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + "\n" + "-" * 80 + "\n")
        except Exception as e:
            logger.error(f"Failed to write TODO log entry: {e}")
    
    def get_todo_logs(self, plan_instance_id: str = None) -> list:
        """获取TODO日志"""
        try:
            if not self.log_file_path.exists():
                return []
            
            logs = []
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # 按分隔符分割日志条目
            entries = content.split("-" * 80)
            for entry in entries:
                entry = entry.strip()
                if not entry:
                    continue
                    
                try:
                    log_entry = json.loads(entry)
                    if plan_instance_id is None or log_entry.get("plan_instance_id") == plan_instance_id:
                        logs.append(log_entry)
                except json.JSONDecodeError:
                    continue
            
            return logs
        except Exception as e:
            logger.error(f"Failed to read TODO logs: {e}")
            return []

# 全局TODO日志记录器实例
todo_logger = TodoLogger()
