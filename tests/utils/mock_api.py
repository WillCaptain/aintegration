import asyncio
import uvicorn
from fastapi import FastAPI, Request
from datetime import datetime
import json
import os

app = FastAPI(title="Mock System API")

LOG_DIR = "tests/.artifacts"
MOCK_LOG_FILE = os.path.join(LOG_DIR, "mock_tool_result.log")

# 失败控制：{tool_name: failure_count} - 指定工具前N次调用失败
failure_config = {}
# 调用计数器：{tool_name: call_count}
call_counters = {}

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

    # 检查是否应该模拟失败
    if tool_name in call_counters:
        call_counters[tool_name] += 1
    else:
        call_counters[tool_name] = 1
    
    will_fail = False
    failure_reason = None
    if tool_name in failure_config:
        failure_count = failure_config[tool_name]
        current_count = call_counters[tool_name]
        if current_count <= failure_count:
            will_fail = True
            failure_reason = f"Mock failure for {tool_name} (attempt {current_count}/{failure_count})"
    
    # 记录工具调用（包括成功和失败）
    log_entry = {
        "timestamp": timestamp,
        "tool": tool_name,
        "args": args,
        "source": "mock_api",
        "success": not will_fail,
        "attempt": call_counters.get(tool_name, 1)
    }
    
    if will_fail:
        log_entry["error"] = failure_reason
        log_entry["status"] = "failed"
    else:
        log_entry["status"] = "success"

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(MOCK_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    # 如果应该失败，返回失败结果
    if will_fail:
        return {
            "success": False,
            "error": failure_reason
        }

    # 根据工具名称返回不同的模拟结果
    if tool_name == "query_profile":
        # 模拟查询员工档案状态
        employee_id = args.get("employee_id", "unknown")
        return {
            "success": True, 
            "data": {
                "verified": True,  # 假设档案已创建
                "employee_id": employee_id,
                "profile_exists": True,
                "profile_complete": True
            },
            "message": f"Profile verification for {employee_id}"
        }
    elif tool_name == "check_outbound_status":
        # 模拟查询电脑出库状态
        employee_id = args.get("employee_id", "unknown")
        return {
            "success": True,
            "data": {
                "verified": True,  # 假设电脑已出库
                "employee_id": employee_id,
                "outbound_completed": True,
                "computer_serial": "PC-001"
            },
            "message": f"Outbound verification for {employee_id}"
        }
    elif tool_name == "query_access":
        # 模拟查询门禁状态
        employee_id = args.get("employee_id", "unknown")
        return {
            "success": True,
            "data": {
                "verified": True,  # 假设门禁已开通
                "employee_id": employee_id,
                "access_granted": True,
                "access_level": "employee"
            },
            "message": f"Access verification for {employee_id}"
        }
    else:
        # 其他工具调用
        return {"success": True, "message": f"Mock tool '{tool_name}' executed and logged."}

@app.post("/configure_failures")
async def configure_failures(request: Request):
    """配置工具失败行为"""
    global failure_config, call_counters
    payload = await request.json()
    failure_config = payload.get("failures", {})
    call_counters = {}  # 重置计数器
    return {"message": "Failure configuration updated", "config": failure_config}

@app.post("/reset_failures")
async def reset_failures():
    """重置失败配置"""
    global failure_config, call_counters
    failure_config = {}
    call_counters = {}
    return {"message": "Failure configuration reset"}

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


