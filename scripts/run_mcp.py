#!/usr/bin/env python3
import os

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None

from src.utils.config import load_config
from src.infrastructure.mcp_server import MCPServer


def main():
    if load_dotenv is not None:
        load_dotenv()

    cfg = load_config()
    host = cfg.get("mcp_server.host", "127.0.0.1")
    port = int(cfg.get("mcp_server.port", 8004))

    server = MCPServer(host=host, port=port)

    # 使用 uvicorn 运行 FastAPI app（含 /ws）
    import uvicorn

    uvicorn.run(server.app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()


