import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中，便于 `import src.*`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(PROJECT_ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)


