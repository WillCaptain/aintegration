"""
执行日志记录器 - 记录计划执行的完整时间线
"""
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
import threading

class ExecutionLogger:
    """计划执行日志记录器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.log_file = None
            self.initialized = True
    
    def set_log_file(self, log_file: str):
        """设置日志文件路径"""
        self.log_file = log_file
        # 清空或创建日志文件
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== Plan Execution Log Started at {datetime.now().isoformat()} ===\n\n")
    
    def log(self, event_type: str, details: Dict[str, Any]):
        """记录日志条目"""
        if not self.log_file:
            return
        
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            **details
        }
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                # 写入可读格式
                f.write(f"[{timestamp}] {event_type}\n")
                for key, value in details.items():
                    if isinstance(value, (dict, list)):
                        f.write(f"  {key}: {json.dumps(value, ensure_ascii=False)}\n")
                    else:
                        f.write(f"  {key}: {value}\n")
                f.write("\n")
        except Exception as e:
            print(f"Failed to write execution log: {e}")
    
    def task_status_change(self, plan_id: str, task_id: str, old_status: str, new_status: str, 
                          triggered_by: Optional[str] = None, reason: Optional[str] = None, 
                          context: Optional[Dict[str, Any]] = None):
        """记录任务状态变化"""
        log_data = {
            "plan_id": plan_id,
            "task_id": task_id,
            "old_status": old_status,
            "new_status": new_status,
            "triggered_by": triggered_by or "system"
        }
        if reason:
            log_data["reason"] = reason
        if context:
            # 过滤掉可能导致循环引用的字段
            safe_context = {}
            for key, value in context.items():
                try:
                    # 尝试序列化来检测循环引用
                    import json
                    json.dumps(value)
                    safe_context[key] = value
                except (TypeError, ValueError):
                    # 如果无法序列化，转换为字符串
                    if key == "execution_result":
                        # 对于execution_result，只保留基本信息
                        if isinstance(value, dict):
                            safe_context[key] = {
                                "success": value.get("success"),
                                "reason": value.get("reason"),
                                "response": value.get("response")
                            }
                        else:
                            safe_context[key] = str(value)
                    else:
                        safe_context[key] = str(value)
            log_data["context"] = safe_context
        self.log("TASK_STATUS_CHANGE", log_data)
    
    def listener_triggered(self, plan_id: str, listener_id: str, trigger_task_id: str, 
                          trigger_condition: str):
        """记录Listener被触发"""
        self.log("LISTENER_TRIGGERED", {
            "plan_id": plan_id,
            "listener_id": listener_id,
            "trigger_task_id": trigger_task_id,
            "trigger_condition": trigger_condition
        })
    
    def listener_executed(self, plan_id: str, listener_id: str, success: bool, 
                         target_updates: list):
        """记录Listener执行结果"""
        self.log("LISTENER_EXECUTED", {
            "plan_id": plan_id,
            "listener_id": listener_id,
            "success": success,
            "target_updates": target_updates
        })
    
    def tool_called(self, tool_name: str, args: Dict, success: bool, 
                   error: Optional[str] = None, attempt: int = 1):
        """记录工具调用"""
        self.log("TOOL_CALLED", {
            "tool_name": tool_name,
            "args": args,
            "success": success,
            "error": error,
            "attempt": attempt
        })
    
    def planner_decision(self, plan_id: str, decision_type: str, task_id: str, 
                        details: Dict[str, Any]):
        """记录Planner决策"""
        self.log("PLANNER_DECISION", {
            "plan_id": plan_id,
            "decision_type": decision_type,
            "task_id": task_id,
            **details
        })
    
    def plan_started(self, plan_id: str, main_task_id: str):
        """记录计划开始"""
        self.log("PLAN_STARTED", {
            "plan_id": plan_id,
            "main_task_id": main_task_id
        })
    
    def plan_completed(self, plan_id: str, status: str):
        """记录计划完成"""
        self.log("PLAN_COMPLETED", {
            "plan_id": plan_id,
            "status": status
        })

# 全局单例
execution_logger = ExecutionLogger()

