"""
配置管理工具
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path

class Config:
    """配置管理类"""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self._config = config_dict
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_string(self, key: str, default: str = "") -> str:
        """获取字符串配置"""
        value = self.get(key, default)
        return str(value) if value is not None else default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数配置"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔配置"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    def get_list(self, key: str, default: Optional[list] = None) -> list:
        """获取列表配置"""
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        return default or []
    
    def get_dict(self, key: str, default: Optional[dict] = None) -> dict:
        """获取字典配置"""
        value = self.get(key, default)
        if isinstance(value, dict):
            return value
        return default or {}

def load_config(config_file: Optional[str] = None) -> Config:
    """加载配置文件"""
    
    # 确定配置文件路径
    if config_file is None:
        # 按优先级查找配置文件
        possible_paths = [
            "config/development.yaml",
            "config/production.yaml",
            "config/config.yaml",
            "config.yaml"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                config_file = path
                break
        
        if config_file is None:
            raise FileNotFoundError("No configuration file found")
    
    # 检查文件是否存在
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    # 加载YAML配置文件
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML configuration file: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load configuration file: {e}")
    
    # 处理环境变量替换
    config_dict = _replace_env_variables(config_dict)
    
    return Config(config_dict)

def _replace_env_variables(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """替换配置中的环境变量"""
    if isinstance(config_dict, dict):
        return {k: _replace_env_variables(v) for k, v in config_dict.items()}
    elif isinstance(config_dict, list):
        return [_replace_env_variables(item) for item in config_dict]
    elif isinstance(config_dict, str):
        # 替换 ${VAR_NAME} 格式的环境变量
        import re
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_name = match.group(1)
            default_value = ""
            if ':' in var_name:
                var_name, default_value = var_name.split(':', 1)
            return os.getenv(var_name, default_value)
        
        return re.sub(pattern, replace_var, config_dict)
    else:
        return config_dict

def get_database_url() -> str:
    """获取数据库连接URL"""
    config = load_config()
    
    # 从配置中获取数据库信息
    db_host = config.get_string("database.host", "localhost")
    db_port = config.get_int("database.port", 5432)
    db_name = config.get_string("database.name", "aintegration")
    db_user = config.get_string("database.user", "postgres")
    db_password = config.get_string("database.password", "")
    
    # 构建数据库URL
    if db_password:
        return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        return f"postgresql+asyncpg://{db_user}@{db_host}:{db_port}/{db_name}"

def get_redis_url() -> str:
    """获取Redis连接URL"""
    config = load_config()
    
    redis_host = config.get_string("redis.host", "localhost")
    redis_port = config.get_int("redis.port", 6379)
    redis_db = config.get_int("redis.db", 0)
    redis_password = config.get_string("redis.password", "")
    
    if redis_password:
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        return f"redis://{redis_host}:{redis_port}/{redis_db}"
