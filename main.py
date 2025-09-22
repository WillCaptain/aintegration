"""
AIntegration主应用入口

企业集成代理框架的主应用程序
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.utils.logger import setup_logging, get_logger
from src.utils.config import load_config
from src.api import planner_router, task_router, plan_router
from src.api.email_api import router as email_router

# 设置日志
setup_logging()
logger = get_logger(__name__)

# 全局模块实例
task_listener_module = None
plan_module = None
planner_module = None
atom_agent_module = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global task_listener_module, plan_module, planner_module, atom_agent_module
    
    try:
        # 启动时初始化
        logger.info("Starting AIntegration system...")
        
        # 加载配置
        config = load_config()
        logger.info("Configuration loaded successfully")
        
        # 初始化数据库连接
        # TODO: 实现数据库连接初始化
        logger.info("Database connection initialized")
        
        # 初始化各个模块
        # TODO: 实现模块初始化
        logger.info("Core modules initialized")
        
        # 启动模块
        # TODO: 启动各个模块
        logger.info("Core modules started")
        
        logger.info("AIntegration system started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start AIntegration system: {e}")
        raise
    
    finally:
        # 关闭时清理
        logger.info("Stopping AIntegration system...")
        
        # 停止各个模块
        # TODO: 停止各个模块
        logger.info("Core modules stopped")
        
        # 关闭数据库连接
        # TODO: 关闭数据库连接
        logger.info("Database connection closed")
        
        logger.info("AIntegration system stopped")

# 创建FastAPI应用
app = FastAPI(
    title="AIntegration API",
    description="企业集成代理框架 - AI Agent辅助下的ESB整合方案",
    version="1.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(planner_router, prefix="/api/v1")
app.include_router(task_router, prefix="/api/v1")
app.include_router(plan_router, prefix="/api/v1")
app.include_router(email_router, prefix="/api/v1")

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to AIntegration",
        "version": "1.0.0",
        "description": "企业集成代理框架 - AI Agent辅助下的ESB整合方案",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "AIntegration",
        "version": "1.0.0",
        "timestamp": None  # TODO: 添加实际时间戳
    }

@app.get("/info")
async def system_info():
    """系统信息"""
    return {
        "name": "AIntegration",
        "version": "1.0.0",
        "description": "企业集成代理框架",
        "architecture": {
            "core_modules": [
                "TaskListenerModule",
                "PlanModule", 
                "PlannerModule",
                "AtomAgentModule"
            ],
            "infrastructure": [
                "MCPServer",
                "A2AServer",
                "ADKIntegration"
            ]
        },
        "features": [
            "侦听驱动的任务流转",
            "智能计划生成",
            "外部Agent集成",
            "事件驱动执行"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    
    # 从配置加载服务器设置
    try:
        config = load_config()
        host = config.get_string("api.host", "0.0.0.0")
        port = config.get_int("api.port", 8000)
        
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=True,  # 开发模式
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise
