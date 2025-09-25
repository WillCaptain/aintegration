"""
计划模块使用示例

演示如何使用计划模块创建和执行计划
"""

import asyncio
import logging
import yaml
from pathlib import Path

from src.database.memory_repositories import MemoryDatabaseConnection
from src.core.plan_module import PlanModule
from src.infrastructure.adk_integration import AgentRuntime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """主函数"""
    try:
        # 1. 初始化数据库连接
        db_connection = MemoryDatabaseConnection()
        
        # 2. 初始化ADK集成（可选）
        adk_integration = None  # 这里可以初始化 AgentRuntime
        
        # 3. 创建计划模块
        plan_module = PlanModule(
            plan_repo=db_connection.plan_repo,
            task_repo=db_connection.task_repo,
            listener_repo=db_connection.listener_repo,
            adk_integration=adk_integration
        )
        
        # 4. 启动计划模块
        await plan_module.start()
        
        # 5. 加载计划配置
        config_path = Path("config/plans/employee_onboarding.yaml")
        with open(config_path, 'r', encoding='utf-8') as f:
            plan_config = yaml.safe_load(f)
        
        # 6. 创建计划
        plan_id = await plan_module.create_plan_from_config(plan_config)
        logger.info(f"Created plan: {plan_id}")
        
        # 7. 设置初始上下文（模拟新员工信息）
        initial_context = {
            "001": {
                "id": "EMP001",
                "name": "张三",
                "email": "zhangsan@company.com",
                "department": "技术部"
            }
        }
        
        # 8. 更新主任务上下文
        main_task = await plan_module.task_manager.get_task("001")
        if main_task:
            main_task.set_context_value("id", initial_context["001"]["id"])
            main_task.set_context_value("name", initial_context["001"]["name"])
            main_task.set_context_value("email", initial_context["001"]["email"])
            main_task.set_context_value("department", initial_context["001"]["department"])
            await plan_module.task_manager.task_repo.update_status(
                "001", 
                main_task.status, 
                main_task.context
            )
        
        # 9. 执行计划
        result = await plan_module.execute_plan(plan_id)
        if result["success"]:
            logger.info(f"Plan {plan_id} execution started successfully")
        else:
            logger.error(f"Failed to start plan {plan_id}: {result.get('error', 'Unknown error')}")
            return
        
        # 10. 监控计划执行
        await monitor_plan_execution(plan_module, plan_id)
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # 11. 停止计划模块
        await plan_module.stop()

async def monitor_plan_execution(plan_module: PlanModule, plan_id: str, max_wait_time: int = 60):
    """监控计划执行"""
    logger.info(f"Monitoring plan {plan_id} execution...")
    
    start_time = asyncio.get_event_loop().time()
    
    while True:
        # 检查是否超时
        if asyncio.get_event_loop().time() - start_time > max_wait_time:
            logger.warning(f"Plan {plan_id} monitoring timed out after {max_wait_time} seconds")
            break
        
        # 获取计划状态
        status = await plan_module.get_plan_status(plan_id)
        if not status:
            logger.error(f"Failed to get status for plan {plan_id}")
            break
        
        # 打印当前状态
        logger.info(f"Plan Status: {status['plan_status']}")
        for task in status['tasks']:
            logger.info(f"  Task {task['task_id']} ({task['name']}): {task['status']}")
        
        # 检查是否完成
        if status['plan_status'] in ['completed', 'failed', 'cancelled']:
            logger.info(f"Plan {plan_id} finished with status: {status['plan_status']}")
            break
        
        # 等待一段时间再检查
        await asyncio.sleep(2)

async def demo_orphaned_change_handling():
    """演示孤立状态变化的处理"""
    logger.info("Demonstrating orphaned change handling...")
    
    # 这里可以添加演示代码，展示当任务状态变化没有对应侦听器时的处理
    pass

if __name__ == "__main__":
    asyncio.run(main())
