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
    elif tool_name == "create_contact":
        # 模拟创建合同联系人
        # 检查必需参数
        required_params = ["name", "phone", "id_card", "email", "region"]
        missing_params = []
        for param in required_params:
            if param not in args or not args[param]:
                missing_params.append(param)
        
        if missing_params:
            # 返回缺少参数的错误
            return {
                "success": False,
                "reason": "missing_params",
                "required_params": {
                    "name": {
                        "type": "input",
                        "label": "姓名",
                        "description": "联系人姓名",
                        "required": True
                    },
                    "phone": {
                        "type": "input", 
                        "label": "手机号码",
                        "description": "联系人手机号码",
                        "required": True
                    },
                    "id_card": {
                        "type": "input",
                        "label": "身份证号", 
                        "description": "联系人身份证号码",
                        "required": True
                    },
                    "email": {
                        "type": "input",
                        "label": "邮箱地址",
                        "description": "联系人邮箱地址", 
                        "required": True
                    },
                    "region": {
                        "type": "select",
                        "label": "所在地区",
                        "description": "联系人所在地区",
                        "required": True
                        # 不提供硬编码的options，让PlannerAgent使用ToolDiscovery智能发现
                    }
                },
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }
        
        # 所有参数都有，返回成功结果
        return {
            "success": True,
            "data": {
                "contact_id": f"CONTACT_{args['name']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "name": args["name"],
                "phone": args["phone"],
                "id_card": args["id_card"],
                "email": args["email"],
                "region": args["region"],
                "created_at": timestamp
            },
            "message": f"Contact created successfully for {args['name']}"
        }
    elif tool_name == "create_contract":
        # 模拟创建合同
        contact_id = args.get("contact_id")
        contract_type = args.get("contract_type")
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        
        if not contact_id or not contract_type or not start_date or not end_date:
            return {
                "success": False,
                "error": "Missing required parameters: contact_id, contract_type, start_date, end_date"
            }
        
        return {
            "success": True,
            "data": {
                "contract_id": f"CONTRACT_{contact_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "contact_id": contact_id,
                "contract_type": contract_type,
                "start_date": start_date,
                "end_date": end_date,
                "status": "draft",
                "created_at": timestamp
            },
            "message": "Contract created successfully"
        }
    elif tool_name == "sign_contract":
        # 模拟签署合同
        contract_id = args.get("contract_id")
        signer_name = args.get("signer_name")
        sign_date = args.get("sign_date")
        
        if not contract_id or not signer_name or not sign_date:
            return {
                "success": False,
                "error": "Missing required parameters: contract_id, signer_name, and sign_date"
            }
        
        return {
            "success": True,
            "data": {
                "signature_id": f"SIGN_{contract_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "contract_id": contract_id,
                "signer_name": signer_name,
                "sign_date": sign_date,
                "status": "signed",
                "signed_at": timestamp
            },
            "message": "Contract signed successfully"
        }
    elif tool_name == "get_china_regions":
        # 模拟获取中国地区列表工具
        level = args.get("level", "province")
        
        if level == "province":
            return {
                "success": True,
                "data": [
                    {"value": "北京市", "label": "北京市", "code": "110000"},
                    {"value": "上海市", "label": "上海市", "code": "310000"},
                    {"value": "广东省", "label": "广东省", "code": "440000"},
                    {"value": "江苏省", "label": "江苏省", "code": "320000"},
                    {"value": "浙江省", "label": "浙江省", "code": "330000"},
                    {"value": "山东省", "label": "山东省", "code": "370000"},
                    {"value": "河南省", "label": "河南省", "code": "410000"},
                    {"value": "四川省", "label": "四川省", "code": "510000"},
                    {"value": "湖北省", "label": "湖北省", "code": "420000"},
                    {"value": "湖南省", "label": "湖南省", "code": "430000"},
                    {"value": "河北省", "label": "河北省", "code": "130000"},
                    {"value": "山西省", "label": "山西省", "code": "140000"},
                    {"value": "辽宁省", "label": "辽宁省", "code": "210000"},
                    {"value": "吉林省", "label": "吉林省", "code": "220000"},
                    {"value": "黑龙江省", "label": "黑龙江省", "code": "230000"},
                    {"value": "安徽省", "label": "安徽省", "code": "340000"},
                    {"value": "福建省", "label": "福建省", "code": "350000"},
                    {"value": "江西省", "label": "江西省", "code": "360000"},
                    {"value": "广西壮族自治区", "label": "广西壮族自治区", "code": "450000"},
                    {"value": "海南省", "label": "海南省", "code": "460000"}
                ],
                "message": f"Retrieved {20} provinces/regions"
            }
        else:
            return {
                "success": True,
                "data": [],
                "message": f"Level {level} not supported"
            }
    elif tool_name == "get_region_list":
        # 模拟获取地区列表工具（common_tools agent）
        level = args.get("level", "province")
        
        if level == "province":
            return {
                "success": True,
                "data": [
                    {"value": "北京市", "label": "北京市", "code": "110000"},
                    {"value": "上海市", "label": "上海市", "code": "310000"},
                    {"value": "广东省", "label": "广东省", "code": "440000"},
                    {"value": "江苏省", "label": "江苏省", "code": "320000"},
                    {"value": "浙江省", "label": "浙江省", "code": "330000"},
                    {"value": "山东省", "label": "山东省", "code": "370000"},
                    {"value": "河南省", "label": "河南省", "code": "410000"},
                    {"value": "四川省", "label": "四川省", "code": "510000"},
                    {"value": "湖北省", "label": "湖北省", "code": "420000"},
                    {"value": "湖南省", "label": "湖南省", "code": "430000"}
                ],
                "message": f"Retrieved {10} provinces/regions"
            }
        else:
            return {
                "success": True,
                "data": [],
                "message": f"Level {level} not supported"
            }
    elif tool_name == "get_phone_operators":
        # 模拟获取手机运营商列表工具
        return {
            "success": True,
            "data": [
                {"value": "中国移动", "label": "中国移动", "pattern": "^1[3-9]\\d{9}$"},
                {"value": "中国联通", "label": "中国联通", "pattern": "^1[3-9]\\d{9}$"},
                {"value": "中国电信", "label": "中国电信", "pattern": "^1[3-9]\\d{9}$"}
            ],
            "message": "Retrieved 3 phone operators"
        }
    elif tool_name == "get_parameter_options":
        # 模拟通用参数选项获取工具（支持A2A调用）
        parameter_name = args.get("parameter_name", "")
        parameter_type = args.get("parameter_type", "select")
        
        if "region" in parameter_name.lower():
            return {
                "success": True,
                "options": [
                    {"value": "北京市", "label": "北京市", "code": "110000"},
                    {"value": "上海市", "label": "上海市", "code": "310000"},
                    {"value": "广东省", "label": "广东省", "code": "440000"},
                    {"value": "江苏省", "label": "江苏省", "code": "320000"},
                    {"value": "浙江省", "label": "浙江省", "code": "330000"}
                ],
                "message": f"Retrieved options for parameter {parameter_name}"
            }
        elif "phone" in parameter_name.lower():
            return {
                "success": True,
                "options": [
                    {"value": "中国移动", "label": "中国移动", "pattern": "^1[3-9]\\d{9}$"},
                    {"value": "中国联通", "label": "中国联通", "pattern": "^1[3-9]\\d{9}$"},
                    {"value": "中国电信", "label": "中国电信", "pattern": "^1[3-9]\\d{9}$"}
                ],
                "message": f"Retrieved options for parameter {parameter_name}"
            }
        else:
            return {
                "success": True,
                "options": [],
                "message": f"No options available for parameter {parameter_name}"
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


