"""
ID生成器 - 用于生成各种类型的ID，替代硬编码
"""

import re
from typing import Dict, Any, Optional
from .constants import SystemConstants

class IDGenerator:
    """ID生成器"""
    
    def __init__(self):
        self._counters: Dict[str, int] = {}
    
    def generate_task_id(self, task_type: str = "task", sequence: Optional[int] = None) -> str:
        """生成任务ID"""
        if sequence is None:
            counter_key = f"task_{task_type}"
            self._counters[counter_key] = self._counters.get(counter_key, 0) + 1
            sequence = self._counters[counter_key]
        
        return SystemConstants.TASK_ID_PATTERN.format(
            task_type=task_type,
            sequence=sequence
        )
    
    def generate_listener_id(self, sequence: Optional[int] = None) -> str:
        """生成侦听器ID"""
        if sequence is None:
            self._counters["listener"] = self._counters.get("listener", 0) + 1
            sequence = self._counters["listener"]
        
        return SystemConstants.LISTENER_ID_PATTERN.format(sequence=sequence)
    
    def generate_agent_id(self, agent_type: str, version: str = "v1") -> str:
        """生成Agent ID"""
        return f"{agent_type}_{version}"
    
    def generate_plan_id(self, scenario: str, version: str = "v1") -> str:
        """生成计划ID"""
        # 清理场景名称，移除特殊字符
        clean_scenario = re.sub(r'[^a-zA-Z0-9_]', '_', scenario.lower())
        return f"plan_{clean_scenario}_{version}"
    
    def parse_task_id(self, task_id: str) -> Dict[str, Any]:
        """解析任务ID，提取类型和序列号"""
        # 匹配模式: {task_type}_{sequence:03d}
        match = re.match(r'^([a-zA-Z_]+)_(\d{3})$', task_id)
        if match:
            task_type, sequence = match.groups()
            return {
                "task_type": task_type,
                "sequence": int(sequence)
            }
        return {"task_type": "unknown", "sequence": 0}
    
    def is_main_task_id(self, task_id: str) -> bool:
        """判断是否为主任务ID"""
        parsed = self.parse_task_id(task_id)
        return parsed["task_type"] == "main" or parsed["sequence"] == 1
    
    def get_main_task_id_from_config(self, plan_config: Dict[str, Any]) -> str:
        """从计划配置中获取主任务ID"""
        # 优先从配置中获取
        if "main_task_id" in plan_config:
            return plan_config["main_task_id"]
        
        # 从任务列表中推断主任务
        tasks = plan_config.get("tasks", [])
        if tasks:
            # 查找第一个任务或标记为主任务的任务
            for task in tasks:
                if task.get("is_main_task", False):
                    return task["task_id"]
            # 如果没有明确标记，返回第一个任务
            return tasks[0]["task_id"]
        
        # 默认生成主任务ID
        return self.generate_task_id("main", 1)

# 全局ID生成器实例
id_generator = IDGenerator()
