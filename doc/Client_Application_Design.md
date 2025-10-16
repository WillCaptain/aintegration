# AIntegration 客户端应用设计

**版本**: v1.0  
**日期**: 2025-10-15  
**目标**: 为小微企业提供简单易用的AI员工交互界面

---

## 🎯 设计理念

### 核心原则
1. **极简主义**: 老板不懂技术也能用
2. **对话优先**: 所有操作通过自然语言完成
3. **移动优先**: 老板随时随地可以操作
4. **可视化**: 一目了然看到AI员工在做什么

### 用户画像
- **主要用户**: 小微企业老板/创始人
- **技术水平**: 不一定懂技术
- **使用场景**: 手机为主，偶尔电脑
- **核心需求**: "我说，AI做"

---

## 📱 客户端架构

### 三端应用

```
┌─────────────────────────────────────────────┐
│            Web管理后台                       │
│  (PC端，管理员使用，查看数据、配置系统)      │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│         移动端App（iOS/Android）            │
│  (老板主要使用，对话式交互，查看进度)        │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│          微信小程序/企业微信                 │
│  (便捷入口，通知提醒，快速操作)              │
└─────────────────────────────────────────────┘
```

### 技术栈选择

**Web管理后台**:
```
前端: React + TypeScript + Ant Design Pro
后端: Python FastAPI（已有）
数据库: PostgreSQL
部署: Vercel / AWS
```

**移动端App**:
```
框架: React Native（一套代码，iOS+Android）
或: Flutter（性能更好）
推荐: React Native（与Web端技术栈统一）
```

**微信生态**:
```
小程序: 微信小程序原生
企业微信: 企业微信应用
```

---

## 🎨 核心界面设计

### 1. 移动端主界面（对话式）

```
┌─────────────────────────────────────┐
│  AIntegration                 👤   │
│─────────────────────────────────────│
│                                     │
│  💬 对话区                          │
│  ┌───────────────────────────────┐ │
│  │ 您好，我是AI助手小A           │ │
│  │ 有什么可以帮您？              │ │
│  └───────────────────────────────┘ │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ 张三明天入职      [我] 10:30  │ │
│  └───────────────────────────────┘ │
│                                     │
│  ┌───────────────────────────────┐ │
│  │ ✅ 收到！我已经启动入职流程： │ │
│  │                               │ │
│  │ 📋 入职清单:                  │ │
│  │ ✅ 创建员工档案（AI HR）      │ │
│  │ ⏳ 申请电脑设备（AI IT）      │ │
│  │ ⏳ 办理门禁卡（AI 行政）      │ │
│  │ ⏳ 录入工资系统（AI 财务）    │ │
│  │                               │ │
│  │ 预计30分钟完成                │ │
│  │ [查看详情]                    │ │
│  └───────────────────────────────┘ │
│                                     │
│─────────────────────────────────────│
│  快捷操作:                          │
│  [新员工入职] [设备采购]            │
│  [报销审批] [查看报表]              │
│─────────────────────────────────────│
│  [输入框] 💬 试试"帮我..."         │
└─────────────────────────────────────┘
```

### 2. 任务进度界面

```
┌─────────────────────────────────────┐
│  ← 入职流程详情                     │
│─────────────────────────────────────│
│  张三入职                           │
│  启动时间: 2025-10-15 10:30        │
│  预计完成: 2025-10-15 11:00        │
│─────────────────────────────────────│
│                                     │
│  📊 执行清单                        │
│                                     │
│  ✅ AI HR - 创建员工档案            │
│     已完成 10:32                    │
│     员工ID: WZ001                   │
│                                     │
│  ✅ AI 行政 - 办理门禁卡            │
│     已完成 10:35                    │
│     卡号: CARD001                   │
│                                     │
│  ⏳ AI IT - 申请电脑设备            │
│     进行中... 预计3分钟             │
│                                     │
│  ⏳ AI 财务 - 录入工资系统          │
│     等待中...                       │
│                                     │
│─────────────────────────────────────│
│  [取消流程] [查看日志]              │
└─────────────────────────────────────┘
```

### 3. AI员工状态面板

```
┌─────────────────────────────────────┐
│  AI员工团队                         │
│─────────────────────────────────────│
│                                     │
│  👔 AI HR - 小红                    │
│  🟢 在线  处理中: 张三入职          │
│  今日: 3个任务  本月: 45个任务      │
│  [查看详情]                         │
│                                     │
│  💻 AI IT - 小明                    │
│  🟢 在线  空闲                      │
│  今日: 1个任务  本月: 28个任务      │
│  [查看详情]                         │
│                                     │
│  💰 AI 财务 - 小芳                  │
│  🟡 繁忙  处理中: 月度报表          │
│  今日: 5个任务  本月: 120个任务     │
│  [查看详情]                         │
│                                     │
│  🛒 AI 采购 - 小李                  │
│  🟢 在线  空闲                      │
│  今日: 0个任务  本月: 15个任务      │
│  [查看详情]                         │
│                                     │
└─────────────────────────────────────┘
```

### 4. 数据看板（Web后台）

```
┌─────────────────────────────────────────────────┐
│  AIntegration 管理后台          [退出] [帮助]  │
├─────────────────────────────────────────────────┤
│  📊 本月概览                                    │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 完成任务  │ │ AI员工   │ │ 成本节省 │       │
│  │   148    │ │    6     │ │  ￥52K   │       │
│  │  ↑ 23%   │ │   活跃   │ │  本月    │       │
│  └──────────┘ └──────────┘ └──────────┘       │
│                                                 │
│  📈 任务趋势                                    │
│  [折线图：过去30天的任务完成量]                │
│                                                 │
│  🏃 AI员工工作量                                │
│  HR: ████████░░ 80%                            │
│  IT: ████░░░░░░ 40%                            │
│  财务: ██████████ 100% ⚠️ 建议升级             │
│  采购: ███░░░░░░░ 30%                          │
│                                                 │
│  📋 最近任务                                    │
│  ┌─────────────────────────────────────┐      │
│  │ ✅ 张三入职       AI HR  10:58 完成  │      │
│  │ ⏳ 月度财务关账   AI财务  进行中...  │      │
│  │ ✅ MacBook采购    AI采购 09:30 完成  │      │
│  └─────────────────────────────────────┘      │
│                                                 │
│  [查看全部] [导出报表]                         │
└─────────────────────────────────────────────────┘
```

---

## 🔧 技术实现

### API设计

#### 客户端核心API

**1. 发送对话消息**
```python
POST /api/chat
{
    "user_id": "user_001",
    "company_id": "company_001",
    "message": "张三明天入职"
}

Response:
{
    "success": true,
    "response": "收到！我已经启动入职流程",
    "plan_instance_id": "inst_000001",
    "estimated_completion": "2025-10-15 11:00"
}
```

**2. 获取执行进度**
```python
GET /api/plan_instances/{plan_instance_id}/trace

Response:
{
    "plan_id": "onboard_will_zhang",
    "status": "running",
    "checklist": [
        {
            "agent_id": "hr",
            "task_name": "创建员工档案",
            "status": "executed_and_verified",
            "icon": "✅",
            "completed_at": "2025-10-15 10:32"
        },
        {
            "agent_id": "it",
            "task_name": "申请电脑",
            "status": "in_progress",
            "icon": "⏳",
            "progress": 60
        }
    ],
    "summary": {
        "total_tasks": 5,
        "completed": 2,
        "in_progress": 1,
        "pending": 2
    }
}
```

**3. 获取AI员工状态**
```python
GET /api/ai_employees/{company_id}

Response:
{
    "employees": [
        {
            "id": "hr_001",
            "name": "AI HR - 小红",
            "type": "hr",
            "status": "busy",
            "current_task": "张三入职",
            "today_tasks": 3,
            "month_tasks": 45
        },
        ...
    ]
}
```

### 前端框架

#### React Native客户端结构
```
src/
├── screens/
│   ├── ChatScreen.tsx          # 主对话界面
│   ├── TaskDetailScreen.tsx    # 任务详情
│   ├── EmployeesScreen.tsx     # AI员工状态
│   └── DashboardScreen.tsx     # 数据看板
├── components/
│   ├── ChatMessage.tsx         # 对话气泡
│   ├── TaskChecklist.tsx       # 任务清单
│   ├── EmployeeCard.tsx        # AI员工卡片
│   └── ProgressBar.tsx         # 进度条
├── services/
│   ├── api.ts                  # API调用
│   ├── websocket.ts            # 实时通知
│   └── storage.ts              # 本地存储
└── utils/
    ├── auth.ts                 # 认证
    └── helpers.ts              # 工具函数
```

---

## 🚀 MVP开发计划

### Phase 1: 核心对话功能（2-3周）

**功能清单**:
- [x] 后端API（基于现有代码）
- [ ] 对话界面
- [ ] 任务启动
- [ ] 进度查看
- [ ] 基础认证

**技术实现**:
```python
# 1. 添加Chat API
@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 解析用户意图
    intent = await parse_intent(request.message)
    
    # 查找匹配的plan
    plan = await find_matching_plan(intent)
    
    # 启动plan
    plan_instance = await plan.start(prompt=request.message)
    plan_instance.start()
    
    # 返回响应
    return {
        "response": f"✅ 已启动{plan.name}",
        "plan_instance_id": plan_instance.id
    }

# 2. 添加进度查询API
@app.get("/api/plan_instances/{plan_instance_id}/trace")
async def get_trace(plan_instance_id: str):
    plan_instance = await plan_module.get_plan_instance(plan_instance_id)
    return plan_instance.get_execution_trace()
```

### Phase 2: AI员工管理（1-2周）

**功能清单**:
- [ ] AI员工列表
- [ ] 当前任务展示
- [ ] 工作统计
- [ ] 员工详情

### Phase 3: 数据看板（1-2周）

**功能清单**:
- [ ] 任务统计图表
- [ ] 成本节省计算
- [ ] 月度报表
- [ ] 导出功能

### Phase 4: 高级功能（后续迭代）

**功能清单**:
- [ ] 流程自定义
- [ ] 审批流
- [ ] 数据集成
- [ ] 多租户管理

---

## 💻 快速原型代码

### 简单的Web客户端（可立即开发）

**目录结构**:
```
client/
├── index.html              # 主页面
├── app.js                  # 应用逻辑
├── style.css               # 样式
└── config.js               # 配置
```

**核心代码框架**:

```html
<!-- index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIntegration - AI员工助手</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <!-- 头部 -->
        <header>
            <h1>🤖 AI员工助手</h1>
            <div class="company-info">
                <span id="company-name">我的公司</span>
                <button id="settings-btn">⚙️</button>
            </div>
        </header>

        <!-- 对话区 -->
        <div class="chat-area" id="chat-area">
            <div class="message ai-message">
                <div class="avatar">🤖</div>
                <div class="content">
                    您好！我是AI助手小A。您可以告诉我：<br>
                    • "张三明天入职"<br>
                    • "购买5台MacBook"<br>
                    • "查看本月财务报表"
                </div>
            </div>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
            <input type="text" id="message-input" placeholder="试试说：张三明天入职">
            <button id="send-btn">发送</button>
        </div>

        <!-- 快捷操作 -->
        <div class="quick-actions">
            <button class="quick-btn" data-action="新员工入职">👤 新员工入职</button>
            <button class="quick-btn" data-action="设备采购">💻 设备采购</button>
            <button class="quick-btn" data-action="报销审批">💰 报销审批</button>
            <button class="quick-btn" data-action="查看报表">📊 查看报表</button>
        </div>

        <!-- AI员工状态（可展开） -->
        <div class="employees-panel collapsed" id="employees-panel">
            <div class="panel-header" onclick="toggleEmployees()">
                <span>AI员工团队 (6人)</span>
                <span id="toggle-icon">▼</span>
            </div>
            <div class="panel-content" id="employees-content">
                <!-- AI员工列表 -->
            </div>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>
```

```javascript
// app.js
const API_BASE = 'http://localhost:8000';  // 后端API地址

// 发送消息
async function sendMessage(message) {
    try {
        const response = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                company_id: 'demo_company',
                user_id: 'demo_user',
                message: message
            })
        });
        
        const data = await response.json();
        
        // 显示AI回复
        addMessage('ai', data.response);
        
        // 如果启动了plan，显示进度跟踪
        if (data.plan_instance_id) {
            trackPlanProgress(data.plan_instance_id);
        }
    } catch (error) {
        addMessage('ai', '抱歉，出现了错误：' + error.message);
    }
}

// 跟踪plan进度
async function trackPlanProgress(planInstanceId) {
    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/plan_instances/${planInstanceId}/trace`);
            const trace = await response.json();
            
            // 更新进度显示
            updateProgressUI(trace);
            
            // 如果完成，停止轮询
            if (trace.summary.overall_status === 'passed') {
                clearInterval(interval);
                addMessage('ai', '✅ 任务已完成！');
            }
        } catch (error) {
            console.error('Failed to fetch progress:', error);
        }
    }, 2000);  // 每2秒查询一次
}

// 添加消息到界面
function addMessage(type, content) {
    const chatArea = document.getElementById('chat-area');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = type === 'ai' ? '🤖' : '👤';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'content';
    contentDiv.innerHTML = content;
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    chatArea.appendChild(messageDiv);
    
    // 滚动到底部
    chatArea.scrollTop = chatArea.scrollHeight;
}

// 事件监听
document.getElementById('send-btn').addEventListener('click', () => {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    if (message) {
        addMessage('user', message);
        sendMessage(message);
        input.value = '';
    }
});

// 快捷操作
document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const action = btn.dataset.action;
        addMessage('user', action);
        sendMessage(action);
    });
});
```

```css
/* style.css */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f5f5;
}

.container {
    max-width: 800px;
    margin: 0 auto;
    height: 100vh;
    display: flex;
    flex-direction: column;
    background: white;
}

header {
    padding: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.chat-area {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.message {
    display: flex;
    margin-bottom: 20px;
    animation: slideIn 0.3s ease;
}

.ai-message {
    justify-content: flex-start;
}

.user-message {
    justify-content: flex-end;
}

.avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    margin: 0 10px;
}

.content {
    max-width: 70%;
    padding: 12px 16px;
    border-radius: 12px;
    line-height: 1.5;
}

.ai-message .content {
    background: #f0f0f0;
}

.user-message .content {
    background: #667eea;
    color: white;
}

.input-area {
    display: flex;
    padding: 15px;
    border-top: 1px solid #e0e0e0;
}

#message-input {
    flex: 1;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 24px;
    font-size: 14px;
}

#send-btn {
    margin-left: 10px;
    padding: 12px 24px;
    background: #667eea;
    color: white;
    border: none;
    border-radius: 24px;
    cursor: pointer;
    font-size: 14px;
}

.quick-actions {
    display: flex;
    gap: 10px;
    padding: 10px 15px;
    overflow-x: auto;
    background: #fafafa;
}

.quick-btn {
    padding: 8px 16px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 20px;
    white-space: nowrap;
    cursor: pointer;
    font-size: 13px;
}

@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

---

## 📱 部署方案

### 快速部署（MVP）

**选项1: 纯Web应用**
- 优势：快速开发，无需审核
- 劣势：移动体验稍差
- 部署：Vercel/Netlify
- 成本：免费

**选项2: 微信小程序**
- 优势：用户基数大，推广容易
- 劣势：需要审核，功能受限
- 部署：微信开发者平台
- 成本：300元认证费

**选项3: React Native App**
- 优势：原生体验好
- 劣势：开发周期长，需要审核
- 部署：App Store + 应用宝
- 成本：开发者账号费用

**MVP推荐**: **微信小程序** + **Web应用**
- 微信小程序：移动端主入口
- Web应用：管理后台
- 开发周期：3-4周
- 成本：几乎为0

---

## 🎯 下一步

### 立即可做（本周）
1. 创建`/client`目录
2. 实现基础Web界面（HTML+JS）
3. 添加Chat API到后端
4. 本地测试对话流程

### 近期完成（1-2周）
1. 美化界面设计
2. 添加WebSocket实时更新
3. 实现进度追踪
4. 部署到测试环境

### 中期目标（1个月）
1. 微信小程序开发
2. 完整的数据看板
3. 用户注册登录
4. 多租户支持

---

**是否现在开始实现Web客户端？我可以帮您快速搭建一个可用的原型！**

