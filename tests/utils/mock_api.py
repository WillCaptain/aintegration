import asyncio
import uvicorn
from fastapi import FastAPI, Request
from datetime import datetime
import json
import os

app = FastAPI(title="Mock System API")

LOG_DIR = "tests/.artifacts"
MOCK_LOG_FILE = os.path.join(LOG_DIR, "mock_tool_result.log")

@app.post("/tool")
async def handle_tool_call(request: Request):
    """
    接收工具调用请求，记录到文件，并返回模拟结果。
    请求格式: {"tool": str, "args": {...}}
    """
    payload = await request.json()
    tool_name = payload.get("tool")
    args = payload.get("args")
    timestamp = datetime.now().isoformat()

    log_entry = {
        "timestamp": timestamp,
        "tool": tool_name,
        "args": args,
        "source": "mock_api"
    }

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(MOCK_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return {"success": True, "message": f"Mock tool '{tool_name}' executed and logged."}

async def run_mock_api(host: str = "127.0.0.1", port: int = 8009):
    """运行 Mock API 服务器"""
    print(f"Starting Mock API server on http://{host}:{port}")
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    # 清理旧的日志文件
    os.makedirs(LOG_DIR, exist_ok=True)
    if os.path.exists(MOCK_LOG_FILE):
        os.remove(MOCK_LOG_FILE)
    asyncio.run(run_mock_api())


