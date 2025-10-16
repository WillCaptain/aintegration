"""
配置管理器 - 管理各种配置，替代硬编码
"""

from typing import Dict, Any, Optional, List
from .constants import SystemConstants
from .id_generator import id_generator

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self._agent_configs: Dict[str, Dict[str, Any]] = SystemConstants.DEFAULT_AGENT_CONFIG.copy()
        self._scenario_configs: Dict[str, Dict[str, Any]] = SystemConstants.DEFAULT_BUSINESS_SCENARIOS.copy()
        self._sample_data: Dict[str, Any] = SystemConstants.DEFAULT_SAMPLE_DATA.copy()
    
    def get_agent_config(self, agent_type: str) -> Dict[str, Any]:
        """获取Agent配置"""
        return self._agent_configs.get(agent_type, {
            "id": id_generator.generate_agent_id(agent_type),
            "name": f"{agent_type.replace('_', ' ').title()} Agent",
            "version": "v1"
        })
    
    def register_agent_config(self, agent_type: str, config: Dict[str, Any]):
        """注册Agent配置"""
        self._agent_configs[agent_type] = config
    
    def get_scenario_config(self, scenario: str) -> Dict[str, Any]:
        """获取业务场景配置"""
        return self._scenario_configs.get(scenario, {
            "name": scenario.replace("_", " ").title(),
            "description": f"{scenario}流程",
            "main_task_name": f"{scenario}完成"
        })
    
    def register_scenario_config(self, scenario: str, config: Dict[str, Any]):
        """注册业务场景配置"""
        self._scenario_configs[scenario] = config
    
    def get_sample_data(self, key: str, default: Any = None) -> Any:
        """获取示例数据"""
        return self._sample_data.get(key, default)
    
    def set_sample_data(self, key: str, value: Any):
        """设置示例数据"""
        self._sample_data[key] = value
    
    def generate_plan_config(self, scenario: str, custom_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """生成计划配置"""
        scenario_config = self.get_scenario_config(scenario)
        
        # 基础配置
        config = {
            "plan_id": id_generator.generate_plan_id(scenario),
            "name": scenario_config["name"],
            "description": scenario_config["description"],
            "scenario": scenario,
            "main_task_id": id_generator.generate_task_id("main", 1),
            "tasks": []
        }
        
        # 应用自定义配置
        if custom_config:
            config.update(custom_config)
        
        return config
    
    def generate_task_config(self, task_type: str, sequence: int, 
                           name: str, description: str = "",
                           is_main_task: bool = False) -> Dict[str, Any]:
        """生成任务配置"""
        return {
            "task_id": id_generator.generate_task_id(task_type, sequence),
            "name": name,
            "description": description,
            "is_main_task": is_main_task,
            "listeners": []
        }
    
    def generate_listener_config(self, sequence: int, listener_type: str,
                               agent_id: Optional[str] = None,
                               prompt: str = "",
                               code: str = "") -> Dict[str, Any]:
        """生成侦听器配置"""
        config = {
            "listener_id": id_generator.generate_listener_id(sequence),
            "type": listener_type,
            "prompt": prompt
        }
        
        if listener_type == "agent" and agent_id:
            config["agent_id"] = agent_id
        elif listener_type == "code":
            config["code"] = code
        
        return config
    
    def create_employee_onboarding_config(self) -> Dict[str, Any]:
        """创建员工入职配置（示例）"""
        config = self.generate_plan_config("employee_onboarding")
        
        # 主任务
        main_task = self.generate_task_config(
            "main", 1, 
            "员工入职完成", 
            "新员工入职流程主任务",
            is_main_task=True
        )
        
        # 注册任务
        register_task = self.generate_task_config(
            "register", 2,
            "员工注册",
            "在HR系统中注册新员工"
        )
        
        # 分配设备任务
        equipment_task = self.generate_task_config(
            "equipment", 3,
            "设备分配", 
            "为新员工分配工作设备"
        )
        
        # 权限分配任务
        access_task = self.generate_task_config(
            "access", 4,
            "权限分配",
            "为新员工分配系统权限"
        )
        
        # 邮件通知任务
        email_task = self.generate_task_config(
            "email", 5,
            "邮件通知",
            "发送入职完成通知邮件"
        )
        
        config["tasks"] = [main_task, register_task, equipment_task, access_task, email_task]
        
        # 添加侦听器
        hr_agent_config = self.get_agent_config("hr_agent")
        
        # L001: 主任务触发HR注册
        main_task["listeners"].append(
            self.generate_listener_config(1, "agent", hr_agent_config["id"], "在HR系统中注册新员工")
        )
        
        # L002: 注册完成触发设备分配
        register_task["listeners"].append(
            self.generate_listener_config(2, "agent", "it_agent", "为新员工分配工作设备")
        )
        
        # L003: 设备分配完成触发权限分配
        equipment_task["listeners"].append(
            self.generate_listener_config(3, "agent", "access_agent", "为新员工分配系统权限")
        )
        
        # L004: 权限分配完成触发邮件通知
        access_task["listeners"].append(
            self.generate_listener_config(4, "agent", "email_agent", "发送入职完成通知邮件")
        )
        
        # L005: 邮件发送完成，标记主任务完成
        email_task["listeners"].append(
            self.generate_listener_config(5, "code", code="""
# 标记主任务完成
result = {
    "success": True,
    "task_updates": [
        {"task_id": config['main_task_id'], "status": "Done", "context": {}}
    ]
}
""")
        )
        
        return config

# 全局配置管理器实例
config_manager = ConfigManager()
