"""
日志配置工具
"""

import logging
import logging.config
import sys
from typing import Dict, Optional

def setup_logging(
    level: str = "INFO",
    format_string: Optional[str] = None,
    log_file: Optional[str] = None
) -> None:
    """设置日志配置"""
    
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 基础日志配置
    logging_config: Dict = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": format_string,
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": level,
                "formatter": "default",
                "stream": sys.stdout
            }
        },
        "root": {
            "level": level,
            "handlers": ["console"]
        },
        "loggers": {
            "aintegration": {
                "level": level,
                "handlers": ["console"],
                "propagate": False
            }
        }
    }
    
    # 如果指定了日志文件，添加文件处理器
    if log_file:
        logging_config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": "detailed",
            "filename": log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
        
        # 将文件处理器添加到根日志器和aintegration日志器
        logging_config["root"]["handlers"].append("file")
        logging_config["loggers"]["aintegration"]["handlers"].append("file")
    
    # 应用日志配置
    logging.config.dictConfig(logging_config)
    
    # 获取aintegration日志器并记录启动信息
    logger = logging.getLogger("aintegration")
    logger.info("Logging system initialized")

def get_logger(name: str) -> logging.Logger:
    """获取日志器"""
    return logging.getLogger(f"aintegration.{name}")
