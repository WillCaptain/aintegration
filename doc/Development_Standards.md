# 开发规范与最佳实践

**版本**: v1.0  
**日期**: 2025-10-15  
**项目**: AIntegration

---

## 🎯 概述

本文档定义了AIntegration项目的开发规范、代码标准、最佳实践和团队协作流程。

---

## 📁 项目结构

### 目录结构
```
aintegration/
├── src/                    # 源代码
│   ├── agents/            # AI Agent实现
│   ├── core/              # 核心业务逻辑
│   ├── models/            # 数据模型
│   ├── infrastructure/    # 基础设施
│   ├── api/               # API接口
│   └── utils/             # 工具函数
├── tests/                 # 测试代码
│   ├── unit/              # 单元测试
│   ├── integration/       # 集成测试
│   └── e2e/               # 端到端测试
├── config/                # 配置文件
├── docs/                  # 文档
├── examples/              # 示例代码
├── scripts/               # 脚本文件
├── requirements.txt       # Python依赖
├── pyproject.toml         # 项目配置
├── Dockerfile             # Docker配置
├── docker-compose.yml     # Docker Compose配置
└── README.md              # 项目说明
```

### 命名规范
- **文件名**: 使用小写字母和下划线 (snake_case)
- **目录名**: 使用小写字母和下划线 (snake_case)
- **类名**: 使用大驼峰命名 (PascalCase)
- **函数/变量名**: 使用小写字母和下划线 (snake_case)
- **常量**: 使用大写字母和下划线 (UPPER_CASE)

---

## 🐍 Python开发规范

### 代码风格
- **格式化工具**: Black (行长度88字符)
- **代码检查**: flake8 + mypy
- **导入顺序**: 标准库 → 第三方库 → 本地模块

### 示例代码
```python
# ✅ 好的示例
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from fastapi import HTTPException
from pydantic import BaseModel

from ..models.plan import Plan
from ..core.plan_module import PlanModule

logger = logging.getLogger(__name__)

class PlanInstance(BaseModel):
    """计划实例模型"""
    id: str
    plan_id: str
    status: str
    created_at: datetime
    
    def get_execution_trace(self) -> Dict[str, Any]:
        """获取执行追踪信息"""
        return {
            "plan_id": self.plan_id,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }

# ❌ 不好的示例
from src.models.plan import Plan
import datetime
from typing import *
from fastapi import *

def get_execution_trace(self):
    return {"plan_id": self.plan_id}
```

### 类型注解
```python
# ✅ 使用类型注解
async def create_plan_instance(
    plan: Plan,
    prompt: str,
    user_id: Optional[str] = None
) -> PlanInstance:
    """创建计划实例"""
    pass

# ✅ 复杂类型注解
from typing import Union, Callable, Dict, Any

def process_data(
    data: Dict[str, Any],
    processor: Callable[[Dict[str, Any]], bool]
) -> Union[str, None]:
    """处理数据"""
    pass
```

### 异常处理
```python
# ✅ 好的异常处理
async def execute_plan(plan_id: str) -> Dict[str, Any]:
    """执行计划"""
    try:
        plan = await plan_repo.get_by_id(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")
        
        result = await plan.execute()
        logger.info(f"Plan {plan_id} executed successfully")
        return {"success": True, "result": result}
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error executing plan {plan_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ❌ 不好的异常处理
async def execute_plan(plan_id: str):
    try:
        # 业务逻辑
        pass
    except:
        pass  # 吞掉所有异常
```

### 文档字符串
```python
async def continue_plan(
    plan_instance_id: str,
    provided_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    继续执行暂停的计划实例
    
    Args:
        plan_instance_id: 计划实例ID
        provided_params: 用户提供的参数，格式为 {param_name: param_value}
    
    Returns:
        执行结果，包含success状态和相关信息
        
    Raises:
        ValueError: 当计划实例不存在或状态不正确时
        HTTPException: 当发生内部错误时
        
    Example:
        >>> result = await continue_plan(
        ...     "inst_001",
        ...     {"computer_model": "MacBook Pro"}
        ... )
        >>> print(result["success"])
        True
    """
    pass
```

---

## 🌐 API开发规范

### RESTful API设计
```python
# ✅ 好的API设计
@router.post("/plans/{plan_instance_id}/continue")
async def continue_plan(
    plan_instance_id: str,
    params: ContinuePlanRequest,
    current_user: User = Depends(get_current_user)
) -> ContinuePlanResponse:
    """继续执行暂停的计划"""
    pass

@router.get("/plans/{plan_instance_id}/trace")
async def get_execution_trace(
    plan_instance_id: str,
    current_user: User = Depends(get_current_user)
) -> ExecutionTraceResponse:
    """获取执行追踪信息"""
    pass

# ❌ 不好的API设计
@router.post("/continue_plan")
async def continue_plan(request: dict):
    """继续计划"""
    pass
```

### 请求/响应模型
```python
# ✅ 使用Pydantic模型
class ContinuePlanRequest(BaseModel):
    """继续计划请求"""
    parameters: Dict[str, Any]
    comment: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "parameters": {
                    "computer_model": "MacBook Pro",
                    "department": "engineering"
                },
                "comment": "为张三申请电脑"
            }
        }

class ContinuePlanResponse(BaseModel):
    """继续计划响应"""
    success: bool
    status: str
    message: str
    plan_instance_id: str
```

### 错误处理
```python
# ✅ 统一的错误处理
class AIntegrationException(Exception):
    """基础异常类"""
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)

class PlanNotFoundException(AIntegrationException):
    """计划未找到异常"""
    def __init__(self, plan_id: str):
        super().__init__(
            message=f"Plan {plan_id} not found",
            code="PLAN_NOT_FOUND"
        )

# 全局异常处理器
@app.exception_handler(PlanNotFoundException)
async def plan_not_found_handler(request: Request, exc: PlanNotFoundException):
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "timestamp": datetime.now().isoformat()
            }
        }
    )
```

---

## 🧪 测试规范

### 测试结构
```python
# tests/unit/test_plan_instance.py
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from src.models.plan_instance import PlanInstance, PlanInstanceStatus
from src.core.plan_module import PlanModule

class TestPlanInstance:
    """计划实例测试类"""
    
    @pytest.fixture
    def sample_plan_instance(self):
        """创建测试用的计划实例"""
        return PlanInstance(
            id="test_001",
            plan_id="plan_001",
            status=PlanInstanceStatus.RUNNING.value,
            created_at=datetime.now()
        )
    
    def test_get_execution_trace(self, sample_plan_instance):
        """测试获取执行追踪"""
        trace = sample_plan_instance.get_execution_trace()
        
        assert trace["plan_id"] == "plan_001"
        assert trace["status"] == "running"
        assert "created_at" in trace
    
    @pytest.mark.asyncio
    async def test_continue_plan_success(self):
        """测试继续计划成功场景"""
        with patch('src.core.plan_module.PlanModule.get_plan_instance') as mock_get:
            mock_get.return_value = AsyncMock(
                id="test_001",
                status=PlanInstanceStatus.PAUSE.value
            )
            
            plan_module = PlanModule()
            result = await plan_module.continue_plan("test_001", {"param": "value"})
            
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_continue_plan_not_found(self):
        """测试继续计划失败场景"""
        with patch('src.core.plan_module.PlanModule.get_plan_instance') as mock_get:
            mock_get.return_value = None
            
            plan_module = PlanModule()
            
            with pytest.raises(ValueError, match="Plan instance.*not found"):
                await plan_module.continue_plan("nonexistent", {})
```

### 测试数据管理
```python
# tests/fixtures/plan_fixtures.py
import pytest
from datetime import datetime

@pytest.fixture
def sample_plan_config():
    """示例计划配置"""
    return {
        "plan_id": "onboard_employee",
        "name": "员工入职流程",
        "description": "新员工入职完整流程",
        "tasks": [
            {
                "task_id": "create_profile",
                "name": "创建员工档案",
                "listeners": [
                    {
                        "listener_id": "hr_create_profile",
                        "type": "agent",
                        "agent_id": "hr_agent"
                    }
                ]
            }
        ]
    }

@pytest.fixture
async def sample_plan_instance(plan_module, sample_plan_config):
    """创建示例计划实例"""
    plan = await plan_module.create_plan_from_config(sample_plan_config)
    instance = await plan_module.start_plan_by_prompt(
        "为张三办理入职",
        plan.id
    )
    return instance
```

---

## 📝 日志规范

### 日志级别使用
```python
import logging

logger = logging.getLogger(__name__)

# ✅ 正确的日志级别使用
logger.debug("详细的调试信息，仅在开发时使用")
logger.info("一般信息，记录重要的业务流程")
logger.warning("警告信息，表示潜在问题")
logger.error("错误信息，表示处理失败")
logger.critical("严重错误，表示系统无法继续运行")

# ✅ 结构化日志
logger.info(
    "Plan execution started",
    extra={
        "plan_id": plan_id,
        "user_id": user_id,
        "execution_time": execution_time
    }
)

# ❌ 不好的日志
logger.info(f"Error: {error}")  # 错误应该用logger.error
print("Debug info")  # 不要用print，用logger.debug
```

### 日志格式
```python
# config/logging.py
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/aintegration.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "detailed"
        }
    },
    "loggers": {
        "": {
            "handlers": ["console", "file"],
            "level": "INFO"
        }
    }
}
```

---

## 🔧 工具配置

### 代码格式化工具
```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### 测试配置
```toml
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --tb=short
    --cov=src
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
```

---

## 🚀 部署规范

### Docker配置
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ ./src/
COPY config/ ./config/

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 环境配置
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/aintegration
      - REDIS_URL=redis://redis:6379
      - LOG_LEVEL=INFO
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=aintegration
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

---

## 📋 代码审查规范

### 审查清单
- [ ] **功能正确性**: 代码是否实现了预期功能
- [ ] **代码质量**: 是否符合编码规范
- [ ] **测试覆盖**: 是否有足够的测试
- [ ] **性能考虑**: 是否有性能问题
- [ ] **安全性**: 是否有安全漏洞
- [ ] **文档完整性**: 是否有必要的文档

### 审查流程
1. **自检**: 提交前进行自我检查
2. **工具检查**: 运行代码格式化和检查工具
3. **测试**: 确保所有测试通过
4. **提交**: 创建Pull Request
5. **审查**: 至少一名同事审查
6. **合并**: 审查通过后合并

---

## 🔄 Git工作流

### 分支策略
```
main (生产分支)
├── develop (开发分支)
├── feature/feature-name (功能分支)
├── bugfix/bug-description (修复分支)
└── hotfix/critical-fix (热修复分支)
```

### 提交信息规范
```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**:
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

**示例**:
```
feat(planner): add parameter pause and continue functionality

- Add PAUSE and CONTINUE status to PlanInstanceStatus
- Implement continue_plan() method in PlannerAgent
- Add parameter validation and error handling

Closes #123
```

---

## 📊 性能监控

### 关键指标
- **响应时间**: API平均响应时间 < 200ms
- **吞吐量**: 每秒处理请求数
- **错误率**: 错误率 < 1%
- **资源使用**: CPU、内存、磁盘使用率

### 监控工具
- **应用监控**: Prometheus + Grafana
- **日志监控**: ELK Stack
- **错误跟踪**: Sentry
- **性能分析**: APM工具

---

**遵循这些规范将确保代码质量、团队协作效率和项目的长期可维护性！**
