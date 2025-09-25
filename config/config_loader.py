import os
import yaml
import logging
from typing import Optional, Any, Dict

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    简单的配置读取器，读取 project-root/config/{env}.yaml。
    优先使用环境变量（大写 KEY），否则读取 yaml 顶层键。
    """
    def __init__(self, config_dir: str = "config", env: Optional[str] = None):
        self.config_dir = config_dir
        self.env = env or os.getenv("APP_ENV", "development")
        self._data: Dict[str, Any] = {}
        self.load()

    def _path(self) -> str:
        return os.path.join(self.config_dir, f"{self.env}.yaml")

    def load(self) -> None:
        path = self._path()
        if not os.path.exists(path):
            self._data = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config file {path}: {e}")
            self._data = {}

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        支持：
        - 直接环境变量覆盖：尝试 KEY.upper()，以及用下划线替代点的形式 key.replace('.', '_').upper()
        - 点分路径访问 YAML 中的嵌套值，如 "google_adk.api_key"
        - 返回解析后的值（占位符已被替换）
        """
        # 先尝试环境变量覆盖
        env_candidates = [key.upper(), key.replace(".", "_").upper()]
        for name in env_candidates:
            env_val = os.getenv(name)
            if env_val is not None:
                return env_val

        # 遍历点分路径
        parts = key.split(".")
        node: Any = self._data
        for p in parts:
            if not isinstance(node, dict) or p not in node:
                return default
            node = node[p]
        return node

    def reload(self, env: Optional[str] = None) -> None:
        if env:
            self.env = env
        self.load()

config_loader: ConfigLoader = ConfigLoader()

__all__ = ["ConfigLoader", "config_loader"]