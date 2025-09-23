#!/usr/bin/env python3
import os
import sys
import subprocess

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None


def main():
    # 加载 .env（若存在）
    if load_dotenv is not None:
        load_dotenv()

    # 默认运行的测试选择器
    default_selectors = [
        "-k",
        "reactagent_mcp_stub or mcp_ws_smoke",
    ]

    # 若用户传入自定义 pytest 参数，使用用户参数；否则使用默认选择器
    pytest_args = sys.argv[1:] if len(sys.argv) > 1 else default_selectors

    # 可选开启 WS 冒烟
    os.environ.setdefault("RUN_WS_SMOKE", "1")

    # 运行 pytest
    cmd = [sys.executable, "-m", "pytest", *pytest_args]
    print("Running:", " ".join(cmd))
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()


