# AIntegration 企业部署指南

## 概述

AIntegration 是一个企业级自动化集成平台，通过配置驱动的方式实现业务流程自动化。本指南详细说明如何将 AIntegration 部署到企业环境中。

## 系统架构

```
企业环境
├── AIntegration 核心服务
│   ├── A2A Server (Agent-to-Agent 通信中心)
│   ├── MCP Server (工具调用管理)
│   ├── PlanModule (计划执行引擎)
│   ├── PlannerAgent (智能验证器)
│   └── ListenerEngine (事件驱动引擎)
├── 业务系统集成
│   ├── HR 系统 (员工管理)
│   ├── IT 系统 (设备管理)
│   ├── 门禁系统 (权限管理)
│   ├── 库存系统 (资产管理)
│   └── 邮件系统 (通知服务)
└── 配置管理
    ├── config/apps/ (业务系统配置)
    └── config/plans/ (业务流程配置)
```

## 部署步骤

### 第一阶段：环境准备

#### 1.1 服务器要求
- **操作系统**: Linux (推荐 Ubuntu 20.04+ 或 CentOS 8+)
- **Python**: 3.9+ 
- **内存**: 最低 4GB，推荐 8GB+
- **存储**: 最低 20GB，推荐 50GB+
- **网络**: 能够访问企业内网各业务系统

#### 1.2 依赖安装
```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装系统依赖 (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y python3-dev python3-pip nginx supervisor

# 安装系统依赖 (CentOS/RHEL)
sudo yum update
sudo yum install -y python3-devel python3-pip nginx supervisor
```

#### 1.3 数据库配置
```bash
# 可选：配置 PostgreSQL 数据库 (生产环境推荐)
# 当前使用内存数据库，适合测试和小规模部署
```

### 第二阶段：系统配置

#### 2.1 业务系统配置
在 `config/apps/` 目录下配置各个业务系统的 API 信息：

**HR 系统配置** (`config/apps/hr.yaml`):
```yaml
name: hr
system_context: "HR 系统负责员工档案管理"
tools:
  - name: create_employee_profile
    description: 创建员工档案
    endpoint: ${HR_API_URL}/api/employees
    parameters:
      type: object
      properties:
        id: { type: string }
        name: { type: string }
        department: { type: string }
      required: [id, name, department]
  - name: query_profile
    description: 查询员工档案信息
    endpoint: ${HR_API_URL}/api/employees/query
    parameters:
      type: object
      properties:
        employee_id: { type: string }
        employee_name: { type: string }
      required: [employee_id, employee_name]
```

**IT 系统配置** (`config/apps/it.yaml`):
```yaml
name: it
system_context: "IT 系统负责设备申请和管理"
tools:
  - name: apply_computer
    description: 申请电脑设备
    endpoint: ${IT_API_URL}/api/devices/apply
    parameters:
      type: object
      properties:
        emp_id: { type: string }
        level: { type: string }
      required: [emp_id, level]
```

**门禁系统配置** (`config/apps/access.yaml`):
```yaml
name: access
system_context: "门禁系统负责员工权限管理"
tools:
  - name: grant_access
    description: 授予门禁权限
    endpoint: ${ACCESS_API_URL}/api/permissions/grant
    parameters:
      type: object
      properties:
        emp_id: { type: string }
        name: { type: string }
      required: [emp_id, name]
  - name: query_access
    description: 查询门禁权限状态
    endpoint: ${ACCESS_API_URL}/api/permissions/query
    parameters:
      type: object
      properties:
        employee_id: { type: string }
        employee_name: { type: string }
      required: [employee_id, employee_name]
```

**库存系统配置** (`config/apps/inventory.yaml`):
```yaml
name: inventory
system_context: "库存系统负责设备出库管理"
tools:
  - name: outbound
    description: 创建出库单
    endpoint: ${INVENTORY_API_URL}/api/outbound/create
    parameters:
      type: object
      properties:
        pc_model: { type: string }
      required: [pc_model]
  - name: check_outbound_status
    description: 查询出库状态
    endpoint: ${INVENTORY_API_URL}/api/outbound/status
    parameters:
      type: object
      properties:
        employee_id: { type: string }
        employee_name: { type: string }
      required: [employee_id, employee_name]
```

**邮件系统配置** (`config/apps/email.yaml`):
```yaml
name: email
system_context: "邮件系统负责通知发送"
tools:
  - name: send_email
    description: 发送邮件
    endpoint: ${EMAIL_API_URL}/api/send
    parameters:
      type: object
      properties:
        to: { type: string }
        subject: { type: string }
        body: { type: string }
      required: [to, subject, body]
```

#### 2.2 环境变量配置
创建 `.env` 文件：
```bash
# 业务系统 API 端点
HR_API_URL=http://hr.company.com/api
IT_API_URL=http://it.company.com/api
ACCESS_API_URL=http://access.company.com/api
INVENTORY_API_URL=http://inventory.company.com/api
EMAIL_API_URL=http://email.company.com/api

# AIntegration 服务配置
AINTEGRATION_HOST=0.0.0.0
AINTEGRATION_PORT=8000
A2A_SERVER_PORT=8001
MCP_SERVER_PORT=8002

# 数据库配置 (可选)
DATABASE_URL=postgresql://user:password@localhost:5432/aintegration

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=/var/log/aintegration/aintegration.log
```

### 第三阶段：业务流程配置

#### 3.1 入职流程配置
创建 `config/plans/onboarding.yaml`:
```yaml
plan_id: employee_onboarding
name: 员工入职流程
description: 新员工入职的完整自动化流程
main_task_id: "001"

tasks:
  - task_id: "001"
    name: "主任务"
    prompt: "新员工入职主流程"
    status: "NotStarted"
  - task_id: "002"
    name: "创建员工档案"
    prompt: "在HR系统中创建员工档案"
    status: "NotStarted"
  # ... 其他任务配置

listeners:
  - listener_id: "L001"
    trigger_task_id: "001"
    trigger_condition: "001.status == Running"
    listener_type: "agent"
    agent_id: "hr"
    action_prompt: "根据员工信息创建档案"
    success_output:
      task_id: "002"
      status: "Done"
  # ... 其他侦听器配置
```

#### 3.2 其他业务流程
- 离职流程 (`config/plans/offboarding.yaml`)
- 设备申请流程 (`config/plans/device_request.yaml`)
- 权限变更流程 (`config/plans/permission_change.yaml`)

### 第四阶段：服务部署

#### 4.1 创建系统服务
创建 `/etc/systemd/system/aintegration.service`:
```ini
[Unit]
Description=AIntegration Enterprise Platform
After=network.target

[Service]
Type=simple
User=aintegration
WorkingDirectory=/opt/aintegration
Environment=PATH=/opt/aintegration/venv/bin
ExecStart=/opt/aintegration/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 4.2 创建用户和目录
```bash
# 创建系统用户
sudo useradd -r -s /bin/false aintegration

# 创建应用目录
sudo mkdir -p /opt/aintegration
sudo mkdir -p /var/log/aintegration
sudo mkdir -p /etc/aintegration

# 设置权限
sudo chown -R aintegration:aintegration /opt/aintegration
sudo chown -R aintegration:aintegration /var/log/aintegration
sudo chown -R aintegration:aintegration /etc/aintegration
```

#### 4.3 部署应用
```bash
# 复制应用文件
sudo cp -r . /opt/aintegration/
sudo chown -R aintegration:aintegration /opt/aintegration

# 复制配置文件
sudo cp config/*.yaml /etc/aintegration/
sudo cp .env /etc/aintegration/

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable aintegration
sudo systemctl start aintegration
```

### 第五阶段：监控和运维

#### 5.1 日志监控
```bash
# 查看服务状态
sudo systemctl status aintegration

# 查看日志
sudo journalctl -u aintegration -f

# 查看应用日志
tail -f /var/log/aintegration/aintegration.log
```

#### 5.2 健康检查
```bash
# 检查 A2A Server
curl http://localhost:8001/health

# 检查 MCP Server
curl http://localhost:8002/health

# 检查主服务
curl http://localhost:8000/health
```

#### 5.3 性能监控
- 监控内存使用情况
- 监控 CPU 使用率
- 监控网络连接数
- 监控任务执行时间

## 安全考虑

### 网络安全
- 使用 HTTPS 进行 API 通信
- 配置防火墙规则
- 使用 VPN 或专网连接

### 认证授权
- 为每个业务系统配置 API 密钥
- 实现 OAuth 2.0 或 JWT 认证
- 配置访问控制列表 (ACL)

### 数据安全
- 加密敏感配置信息
- 定期备份配置和日志
- 实现审计日志

## 扩展和维护

### 添加新的业务系统
1. 在 `config/apps/` 下创建新的 YAML 配置文件
2. 重启 AIntegration 服务
3. 验证 Agent 注册成功

### 添加新的业务流程
1. 在 `config/plans/` 下创建新的 YAML 配置文件
2. 通过 API 或管理界面加载计划
3. 测试流程执行

### 版本升级
1. 备份当前配置和数据
2. 停止服务
3. 更新代码
4. 验证配置兼容性
5. 重启服务

## 故障排除

### 常见问题
1. **Agent 注册失败**: 检查业务系统 API 连接
2. **任务执行超时**: 调整超时配置
3. **内存不足**: 增加服务器内存或优化配置
4. **网络连接问题**: 检查防火墙和网络配置

### 日志分析
- 查看错误日志定位问题
- 分析性能日志优化配置
- 监控业务日志确保流程正确

## 联系支持

- 技术支持: tech-support@company.com
- 文档更新: 本文档随项目推进持续更新
- 版本历史: 记录每次部署的变更内容

---

**文档版本**: v1.0  
**最后更新**: 2025-09-30  
**维护者**: AIntegration 开发团队
