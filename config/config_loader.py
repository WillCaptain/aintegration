# 配置适配器，兼容现有代码调用
from typing import Any
from functools import lru_cache

from src.utils.config import load_config

@lru_cache(maxsize=1)
def _cfg():
    return load_config()


def get(key: str, default: Any | None = None) -> Any:
    """获取配置项，若不存在返回 default。
    示例：get("google_adk.api_key")
    """
    return _cfg().get(key, default)


def require(key: str) -> Any:
    """获取必需的配置项，不存在则抛出异常。"""
    value = _cfg().get(key, None)
    if value is None:
        raise KeyError(f"Missing required config key: {key}")
    return value
