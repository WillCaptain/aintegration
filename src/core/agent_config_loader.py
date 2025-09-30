"""
Agent 配置加载器

负责从 config/apps/ 目录加载所有 BizAgent 配置，
并自动注册到 A2A Server。

企业部署流程：
1. 配置 apps/ 目录下的所有应用 API 信息
2. 系统启动时自动扫描 apps/ 目录
3. 根据配置自动生成 BizAgent
4. 所有 BizAgent 自动注册到 A2A Server
"""

import os
import yaml
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentConfigLoader:
    """Agent 配置加载器"""
    
    def __init__(self, apps_dir: str = "config/apps"):
        self.apps_dir = Path(apps_dir)
        self.agent_configs: Dict[str, Dict[str, Any]] = {}
    
    def load_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """加载所有 Agent 配置"""
        if not self.apps_dir.exists():
            logger.warning(f"Apps directory not found: {self.apps_dir}")
            return {}
        
        self.agent_configs = {}
        
        # 扫描所有 YAML 配置文件
        for yaml_file in self.apps_dir.glob("*.yaml"):
            try:
                agent_config = self._load_agent_config(yaml_file)
                if agent_config:
                    agent_id = agent_config["name"]
                    self.agent_configs[agent_id] = agent_config
                    logger.info(f"Loaded agent config: {agent_id}")
            except Exception as e:
                logger.error(f"Failed to load agent config from {yaml_file}: {e}")
        
        logger.info(f"Loaded {len(self.agent_configs)} agent configurations")
        return self.agent_configs
    
    def _load_agent_config(self, yaml_file: Path) -> Optional[Dict[str, Any]]:
        """加载单个 Agent 配置文件"""
        with open(yaml_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config or "name" not in config:
            logger.warning(f"Invalid agent config in {yaml_file}: missing 'name' field")
            return None
        
        # 处理环境变量替换
        config = self._process_env_variables(config)
        
        # 生成 Agent 能力列表
        capabilities = self._extract_capabilities(config)
        config["capabilities"] = capabilities
        
        # 生成 A2A Agent 卡片
        agent_card = self._generate_agent_card(config)
        config["agent_card"] = agent_card
        
        return config
    
    def _process_env_variables(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """处理环境变量替换"""
        def replace_env_vars(obj):
            if isinstance(obj, str):
                # 简单的环境变量替换：${VAR:default}
                import re
                pattern = r'\$\{([^:}]+)(?::([^}]*))?\}'
                def replace_func(match):
                    var_name = match.group(1)
                    default_value = match.group(2) if match.group(2) is not None else ""
                    return os.getenv(var_name, default_value)
                return re.sub(pattern, replace_func, obj)
            elif isinstance(obj, dict):
                return {k: replace_env_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_env_vars(item) for item in obj]
            else:
                return obj
        
        return replace_env_vars(config)
    
    def _extract_capabilities(self, config: Dict[str, Any]) -> List[str]:
        """从工具配置中提取能力列表"""
        capabilities = []
        tools = config.get("tools", [])
        
        for tool in tools:
            if isinstance(tool, dict) and "name" in tool:
                capabilities.append(tool["name"])
        
        return capabilities
    
    def _generate_agent_card(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """生成 A2A Agent 卡片"""
        return {
            "agent_id": config["name"],
            "agent_name": config.get("display_name", config["name"]),
            "provider": "internal",
            "version": "1.0.0",
            "capabilities": config["capabilities"],
            "endpoints": {
                "execute": f"/agents/{config['name']}/execute"
            },
            "system_context": config.get("system_context", ""),
            "tools": config.get("tools", [])
        }
    
    def get_agent_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取指定 Agent 的配置"""
        return self.agent_configs.get(agent_id)
    
    def get_all_agent_cards(self) -> List[Dict[str, Any]]:
        """获取所有 Agent 卡片"""
        return [config["agent_card"] for config in self.agent_configs.values()]
    
    def reload_agents(self) -> Dict[str, Dict[str, Any]]:
        """重新加载所有 Agent 配置"""
        logger.info("Reloading agent configurations...")
        return self.load_all_agents()


# 全局实例
agent_config_loader = AgentConfigLoader()
