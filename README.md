# AIntegration 企业集成代理框架

## 项目概述

AIntegration是一个基于AI Agent的企业集成代理框架，通过将传统的ESB（企业服务总线）与AI Agent技术相结合，实现智能化的企业应用集成。该系统采用分层代理架构，从最原子的工具调用到复杂的业务流程编排，提供了一套完整的解决方案。

## 文档结构

### 1. 设计文档
- **AIntegration_Design.md** - 详细的系统设计文档
  - 核心架构层次（AtomAgent、BizAgent、PlanAgent）
  - 侦听驱动的任务流转机制
  - 外部Agent集成机制
  - 新员工入职完整示例
  - 数据模型和设计要点

### 2. 架构文档
- **System_Architecture.md** - 系统架构设计文档
  - 模块化架构设计
  - 任务侦听模块详细设计
  - 计划模块功能规范
  - Atom Agent模块实现方案
  - Planner模块智能规划
  - 基础设施模块技术选型

## 核心特性

### 🎯 侦听驱动机制
- **一对一驱动**：每个侦听器只驱动一个Agent
- **完整指导**：提供详细的行动指导和反馈逻辑
- **上下文注入**：使用变量引用明确指定输入上下文
- **双路径反馈**：明确定义成功和失败的任务状态更新

### 🔄 事件驱动执行
- 任务状态变化触发侦听器
- 支持复杂的多任务状态组合条件
- 循环往复直到Main Task完成
- 完整的执行记录和回溯能力

### 🌐 外部Agent集成
- 标准化的A2A协议
- 统一的内部和外部Agent调用接口
- 动态Agent发现和管理
- 安全的认证和授权机制

### 🧠 智能规划
- PrePlan Mode：预定义计划
- SelfPlan Mode：自动生成计划
- ResiliencePlan：失败重规划
- Few-shot学习支持

## 技术栈

### 核心框架
- **Google ADK** - Agent开发框架（推荐）
- **MCP Server** - 工具注册和调用管理
- **A2A Server** - Agent注册发现和通信

### 开发技术
- **Python** - 主要开发语言
- **FastAPI** - Web框架
- **PostgreSQL** - 主数据库
- **Redis** - 缓存和消息队列
- **Docker** - 容器化部署

## 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone <repository-url>
cd aintegration

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动服务
```bash
# 使用Docker Compose启动所有服务
docker-compose up -d
```

### 3. 测试示例
```bash
# 发送新员工入职请求
curl -X POST http://localhost:8001/planner/execute \
  -H "Content-Type: application/json" \
  -d '{"request": "张三入职"}'
```

## 开发计划

### 阶段一：基础框架
- [ ] 设计AtomAgent接口规范
- [ ] 实现A2A Server
- [ ] 开发PlanAgent核心引擎
- [ ] 创建任务状态管理机制
- [ ] 设计A2A协议规范
- [ ] 开发侦听引擎

### 阶段二：BizAgent实现
- [ ] 开发标准BizAgent模板
- [ ] 实现MCP化工具集成
- [ ] 添加轮询机制支持
- [ ] 创建AgentCard注册机制
- [ ] 实现外部Agent集成接口

### 阶段三：规划引擎
- [ ] 实现PrePlan Mode
- [ ] 开发SelfPlan Mode
- [ ] 添加ResiliencePlan机制
- [ ] 创建计划执行引擎
- [ ] 实现侦听器配置和管理

### 阶段四：集成测试
- [ ] 新员工入职流程测试（包含外部Agent）
- [ ] 侦听器机制测试
- [ ] 外部Agent集成测试
- [ ] 补偿机制测试
- [ ] 性能压力测试
- [ ] 故障恢复测试

### 阶段五：生产部署
- [ ] 生产环境配置
- [ ] 监控仪表板
- [ ] 文档和培训
- [ ] 运维支持

## 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系方式

- 项目维护者：[您的姓名]
- 邮箱：[your.email@example.com]
- 项目链接：[https://github.com/yourusername/aintegration](https://github.com/yourusername/aintegration)

---

*此项目正在积极开发中，欢迎贡献代码和提出建议！*
