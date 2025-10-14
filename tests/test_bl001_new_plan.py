"""
BL-001: 新建 Plan 的完整测试

测试计划模块的新建 Plan 功能，包括：
- 支持从配置文件创建 Plan
- 支持从模板创建 Plan  
- 支持通过 API 动态创建 Plan
- 支持 Plan 的元数据管理
"""

import pytest
import pytest_asyncio
import asyncio
import yaml
import json
from datetime import datetime
from pathlib import Path

from src.database.memory_repositories import MemoryDatabaseConnection
from src.database.instance_repositories import MemoryPlanInstanceRepository, MemoryTaskInstanceRepository
from src.core.plan_module import PlanModule
from src.models.plan import Plan, PlanStatus
from src.models.plan_instance import PlanInstance, PlanInstanceStatus
from src.models.task_instance import TaskInstance, TaskInstanceStatus
from src.models.listener import Listener, ListenerType

@pytest.mark.regression
@pytest.mark.bl001
class TestBL001NewPlan:
    """BL-001: 新建 Plan 测试类"""
    
    @pytest_asyncio.fixture
    async def plan_module(self):
        """创建计划模块实例"""
        db_connection = MemoryDatabaseConnection()
        plan_instance_repo = MemoryPlanInstanceRepository()
        task_instance_repo = MemoryTaskInstanceRepository()
        plan_module = PlanModule(
            plan_repo=db_connection.plan_repo,
            task_repo=db_connection.task_repo,
            listener_repo=db_connection.listener_repo,
            plan_instance_repo=plan_instance_repo,
            task_instance_repo=task_instance_repo
        )
        await plan_module.start()
        yield plan_module
        await plan_module.stop()
    
    @pytest.fixture
    def sample_plan_config(self):
        """示例计划配置"""
        return {
            "plan_id": "test_plan_001",
            "name": "测试计划",
            "description": "用于测试的计划",
            "main_task_id": "001",
            "metadata": {
                "author": "test_user",
                "version": "1.0.0",
                "tags": ["test", "demo"],
                "created_at": datetime.now().isoformat()
            },
            "tasks": [
                {
                    "task_id": "001",
                    "name": "主任务",
                    "prompt": "执行主任务",
                    "metadata": {
                        "priority": "high",
                        "estimated_duration": "30m"
                    }
                },
                {
                    "task_id": "002",
                    "name": "子任务1",
                    "prompt": "执行子任务1",
                    "metadata": {
                        "priority": "medium",
                        "estimated_duration": "15m"
                    }
                }
            ],
            "listeners": [
                {
                    "listener_id": "L001",
                    "trigger_task_id": "001",
                    "trigger_status": "Done",
                    "action_type": "code",
                    "action_config": {
                        "code": "result = {'success': True, 'data': 'test'}"
                    },
                    "success_output": {
                        "task_id": "002",
                        "status": "Done",
                        "context": {"result": "{{result.data}}"}
                    },
                    "failure_output": {
                        "task_id": "002",
                        "status": "Error",
                        "context": {"error": "执行失败"}
                    }
                }
            ]
        }
    
    @pytest.fixture
    def plan_template(self):
        """计划模板"""
        return {
            "name": "{{plan_name}}",
            "description": "{{plan_description}}",
            "main_task_id": "001",
            "metadata": {
                "author": "{{author}}",
                "version": "{{version}}",
                "tags": "{{tags}}"
            },
            "tasks": [
                {
                    "task_id": "001",
                    "name": "{{main_task_name}}",
                    "prompt": "{{main_task_prompt}}",
                }
            ],
            "listeners": []
        }
    
    # 测试用例 1: 从配置文件创建 Plan
    @pytest.mark.asyncio
    async def test_create_plan_from_config_file(self, plan_module, tmp_path):
        """测试从配置文件创建 Plan"""
        # 创建配置文件
        config_file = tmp_path / "test_plan.yaml"
        config_data = {
            "plan_id": "config_file_plan",
            "name": "配置文件计划",
            "description": "从配置文件创建的计划",
            "main_task_id": "001",
            "metadata": {
                "author": "config_user",
                "version": "1.0.0",
                "tags": ["config", "file"]
            },
            "tasks": [
                {
                    "task_id": "001",
                    "name": "配置任务",
                    "prompt": "从配置文件执行任务"
                }
            ],
            "listeners": []
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True)
        
        # 读取配置文件并创建计划
        with open(config_file, 'r', encoding='utf-8') as f:
            loaded_config = yaml.safe_load(f)
        
        plan = await plan_module.create_plan_from_config(loaded_config)
        
        # 验证计划创建成功
        assert plan.id == "config_file_plan"
        assert plan.name == "配置文件计划"
        assert plan.description == "从配置文件创建的计划"
        assert plan.main_task_id == "001"
        assert plan.metadata["author"] == "config_user"
        assert plan.metadata["version"] == "1.0.0"
        assert "config" in plan.metadata["tags"]
        
        # 验证任务元数据
        assert len(plan.tasks) == 1
        assert plan.tasks[0]["task_id"] == "001"
        assert plan.tasks[0]["name"] == "配置任务"
        assert plan.tasks[0]["prompt"] == "从配置文件执行任务"
        # 主任务通过 task_instance.is_main_task() 方法判断
        
        # 验证侦听器元数据
        assert len(plan.listeners) == 0
    
    # 测试用例 2: 从模板创建 Plan
    @pytest.mark.asyncio
    async def test_create_plan_from_template(self, plan_module, plan_template):
        """测试从模板创建 Plan"""
        # 模板变量
        template_vars = {
            "plan_name": "模板计划",
            "plan_description": "从模板创建的计划",
            "author": "template_user",
            "version": "2.0.0",
            "tags": ["template", "generated"],
            "main_task_name": "模板任务",
            "main_task_prompt": "执行模板任务"
        }
        
        # 应用模板变量
        plan_config = self._apply_template(plan_template, template_vars)
        plan_config["plan_id"] = "template_plan"
        
        # 创建计划
        plan = await plan_module.create_plan_from_config(plan_config)
        
        # 验证计划创建成功
        assert plan.id == "template_plan"
        assert plan.name == "模板计划"
        assert plan.description == "从模板创建的计划"
        assert plan.metadata["author"] == "template_user"
        assert plan.metadata["version"] == "2.0.0"
        assert "template" in plan.metadata["tags"]
        
        # 验证任务元数据
        assert len(plan.tasks) == 1
        assert plan.tasks[0]["task_id"] == "001"
        assert plan.tasks[0]["name"] == "模板任务"
        assert plan.tasks[0]["prompt"] == "执行模板任务"
        # 主任务通过 task_instance.is_main_task() 方法判断
    
    # 测试用例 3: 通过 API 动态创建 Plan
    @pytest.mark.asyncio
    async def test_create_plan_via_api(self, plan_module):
        """测试通过 API 动态创建 Plan"""
        # 模拟 API 请求数据
        api_request = {
            "plan_id": "api_plan",
            "name": "API计划",
            "description": "通过API创建的计划",
            "main_task_id": "001",
            "metadata": {
                "author": "api_user",
                "version": "1.0.0",
                "tags": ["api", "dynamic"],
                "source": "api_request"
            },
            "tasks": [
                {
                    "task_id": "001",
                    "name": "API任务",
                    "prompt": "执行API任务",
                    "metadata": {
                        "priority": "high",
                        "timeout": "60s"
                    }
                },
                {
                    "task_id": "002",
                    "name": "API子任务",
                    "prompt": "执行API子任务",
                    "metadata": {
                        "priority": "medium",
                        "timeout": "30s"
                    }
                }
            ],
            "listeners": [
                {
                    "listener_id": "L001",
                    "trigger_task_id": "001",
                    "trigger_status": "Done",
                    "action_type": "code",
                    "action_config": {
                        "code": "result = {'success': True, 'next_task': '002'}"
                    },
                    "success_output": {
                        "task_id": "002",
                        "status": "NotStarted",
                        "context": {"triggered_by": "001"}
                    },
                    "failure_output": {
                        "task_id": "002",
                        "status": "Error",
                        "context": {"error": "API任务失败"}
                    }
                }
            ]
        }
        
        # 创建计划
        plan = await plan_module.create_plan_from_config(api_request)
        
        # 验证计划创建成功
        assert plan.id == "api_plan"
        assert plan.name == "API计划"
        assert plan.description == "通过API创建的计划"
        assert plan.metadata["author"] == "api_user"
        assert plan.metadata["source"] == "api_request"
        
        # 验证任务元数据
        assert len(plan.tasks) == 2
        
        task_001 = next(t for t in plan.tasks if t["task_id"] == "001")
        assert task_001["name"] == "API任务"
        # 主任务通过 task_instance.is_main_task() 方法判断
        assert task_001["metadata"]["priority"] == "high"
        assert task_001["metadata"]["timeout"] == "60s"
        
        task_002 = next(t for t in plan.tasks if t["task_id"] == "002")
        assert task_002["name"] == "API子任务"
        # 子任务通过 task_instance.is_main_task() == False 判断
        assert task_002["metadata"]["priority"] == "medium"
        
        # 验证侦听器元数据
        assert len(plan.listeners) == 1
        listener = plan.listeners[0]
        assert listener["listener_id"] == "L001"
        assert listener["trigger_task_id"] == "001"
        assert listener["trigger_status"] == "Done"
        assert listener["action_type"] == "code"
    
    # 测试用例 4: Plan 元数据管理
    @pytest.mark.asyncio
    async def test_plan_metadata_management(self, plan_module, sample_plan_config):
        """测试 Plan 元数据管理"""
        # 创建计划
        plan = await plan_module.create_plan_from_config(sample_plan_config)
        
        # 测试元数据访问
        assert plan.metadata["author"] == "test_user"
        assert plan.metadata["version"] == "1.0.0"
        assert "test" in plan.metadata["tags"]
        assert "demo" in plan.metadata["tags"]
        
        # 测试元数据更新
        plan.metadata["author"] = "updated_user"
        plan.metadata["version"] = "1.1.0"
        plan.metadata["tags"] = ["test", "demo", "updated"]
        
        # 保存更新
        await plan_module.plan_manager.update_plan(plan.id, {
            "metadata": plan.metadata,
            "description": plan.description
        })
        
        # 验证更新
        updated_plan = await plan_module.plan_manager.get_plan(plan.id)
        assert updated_plan.metadata["author"] == "updated_user"
        assert updated_plan.metadata["version"] == "1.1.0"
        assert "updated" in updated_plan.metadata["tags"]
        
        # 测试元数据查询
        assert updated_plan.get_config_value("metadata.author") == "updated_user"
        assert updated_plan.get_config_value("metadata.version") == "1.1.0"
        assert updated_plan.get_config_value("metadata.nonexistent", "default") == "default"
    
    # 测试用例 5: 错误处理
    @pytest.mark.asyncio
    async def test_create_plan_error_handling(self, plan_module):
        """测试创建 Plan 的错误处理"""
        # 测试缺少必需字段 - plan_id 是必需的
        invalid_config = {
            "name": "无效计划",
            # 缺少 plan_id
        }
        
        # 这应该会失败，因为 plan_id 是必需的
        with pytest.raises(Exception) as exc_info:
            await plan_module.create_plan_from_config(invalid_config)
        assert "plan_id is required" in str(exc_info.value)
        
        # 测试无效的任务配置 - 现在任务元数据存储在 Plan 中，不会立即验证
        invalid_task_config = {
            "plan_id": "invalid_task_plan",
            "name": "无效任务计划",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": "001",
                    # 缺少 name 字段
                    "prompt": "无效任务"
                }
            ],
            "listeners": []
        }
        
        # 现在任务验证在 PlanInstance 创建时进行，这里只创建 Plan 元数据
        plan = await plan_module.create_plan_from_config(invalid_task_config)
        assert plan.id == "invalid_task_plan"
        assert len(plan.tasks) == 1
        # 任务元数据不完整，但 Plan 创建成功
        
        # 测试重复的 plan_id
        config1 = {
            "plan_id": "duplicate_plan",
            "name": "重复计划1",
            "main_task_id": "001",
            "tasks": [],
            "listeners": []
        }
        
        config2 = {
            "plan_id": "duplicate_plan",
            "name": "重复计划2",
            "main_task_id": "001",
            "tasks": [],
            "listeners": []
        }
        
        # 创建第一个计划
        plan1 = await plan_module.create_plan_from_config(config1)
        assert plan1.id == "duplicate_plan"
        assert plan1.name == "重复计划1"
        
        # 尝试创建重复的计划（应该覆盖）
        plan2 = await plan_module.create_plan_from_config(config2)
        assert plan2.id == "duplicate_plan"
        assert plan2.name == "重复计划2"
        
        # 验证最终的计划名称
        final_plan = await plan_module.plan_manager.get_plan("duplicate_plan")
        assert final_plan.name == "重复计划2"  # 应该是最后一个
    
    # 测试用例 6: 边界条件
    @pytest.mark.asyncio
    async def test_create_plan_edge_cases(self, plan_module):
        """测试创建 Plan 的边界条件"""
        # 测试空任务列表
        empty_tasks_config = {
            "plan_id": "empty_tasks_plan",
            "name": "空任务计划",
            "main_task_id": "001",
            "tasks": [],
            "listeners": []
        }
        
        plan = await plan_module.create_plan_from_config(empty_tasks_config)
        assert plan.id == "empty_tasks_plan"
        assert plan.name == "空任务计划"
        assert len(plan.tasks) == 0
        assert len(plan.listeners) == 0
        
        # 测试空侦听器列表
        empty_listeners_config = {
            "plan_id": "empty_listeners_plan",
            "name": "空侦听器计划",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": "001",
                    "name": "任务",
                    "prompt": "执行任务"
                }
            ],
            "listeners": []
        }
        
        plan = await plan_module.create_plan_from_config(empty_listeners_config)
        assert plan.id == "empty_listeners_plan"
        assert plan.name == "空侦听器计划"
        assert len(plan.tasks) == 1
        assert len(plan.listeners) == 0
        
        # 测试大量任务
        large_tasks_config = {
            "plan_id": "large_tasks_plan",
            "name": "大量任务计划",
            "main_task_id": "001",
            "tasks": [
                {
                    "task_id": f"task_{i:03d}",
                    "name": f"任务{i}",
                    "prompt": f"执行任务{i}"
                }
                for i in range(1, 101)  # 100个任务
            ],
            "listeners": []
        }
        
        plan = await plan_module.create_plan_from_config(large_tasks_config)
        assert plan.id == "large_tasks_plan"
        assert plan.name == "大量任务计划"
        
        # 验证任务数量
        assert len(plan.tasks) == 100
        assert plan.tasks[0]["task_id"] == "task_001"
        assert plan.tasks[99]["task_id"] == "task_100"
        
        # 测试特殊字符
        special_chars_config = {
            "plan_id": "special_chars_plan",
            "name": "特殊字符计划！@#$%^&*()",
            "description": "包含特殊字符的描述：中文、English、123、!@#",
            "main_task_id": "001",
            "metadata": {
                "author": "特殊用户",
                "version": "1.0.0",
                "tags": ["特殊", "字符", "测试"]
            },
            "tasks": [
                {
                    "task_id": "001",
                    "name": "特殊任务",
                    "prompt": "执行特殊任务：包含中文、English、数字123、符号!@#"
                }
            ],
            "listeners": []
        }
        
        plan = await plan_module.create_plan_from_config(special_chars_config)
        assert plan.id == "special_chars_plan"
        assert plan.name == "特殊字符计划！@#$%^&*()"
        assert "中文" in plan.description
        assert "English" in plan.description
        assert "123" in plan.description
    
    # 辅助方法
    def _apply_template(self, template, variables):
        """应用模板变量"""
        import copy
        
        # 深拷贝模板
        result = copy.deepcopy(template)
        
        # 递归替换变量
        self._replace_variables(result, variables)
        
        return result
    
    def _replace_variables(self, obj, variables):
        """递归替换变量"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                    var_name = value[2:-2]
                    if var_name in variables:
                        obj[key] = variables[var_name]
                else:
                    self._replace_variables(value, variables)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and item.startswith("{{") and item.endswith("}}"):
                    var_name = item[2:-2]
                    if var_name in variables:
                        obj[i] = variables[var_name]
                else:
                    self._replace_variables(item, variables)

# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
