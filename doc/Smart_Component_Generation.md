# 智能组件生成系统设计

**版本**: v1.0  
**日期**: 2025-10-15  
**特性**: BL-014.2 - 智能组件生成系统

---

## 🎯 功能概述

### 核心需求
BizAgent需要智能判断生成哪种UI组件类型，支持多种组件类型（radio/checkbox/input/list/combobox等），并能够从工具列表和A2A查询获取动态数据源（优先选择本智能体的工具列表，然后选择A2A询问）。

### 支持的组件类型
- **input**: 文本输入框
- **textarea**: 多行文本域
- **select**: 下拉选择框
- **radio**: 单选按钮组
- **checkbox**: 复选框组（支持多选）
- **combobox**: 可搜索组合框
- **list**: 列表选择器
- **password**: 密码输入框
- **date**: 日期选择器
- **time**: 时间选择器
- **number**: 数字输入框
- **email**: 邮箱输入框
- **url**: URL输入框
- **file**: 文件上传
- **range**: 滑块选择器

### 使用场景
1. **电脑申请**: 询问库存智能体获取可用电脑型号 → 生成radio组件
2. **部门选择**: 询问HR智能体获取部门列表 → 生成select组件
3. **技能选择**: 询问通识智能体获取技能列表 → 生成checkbox组件
4. **用户搜索**: 询问用户智能体搜索用户 → 生成combobox组件
5. **城市搜索**: 询问通识智能体获得城市列表 → 生成combobox组件

---

## 🏗️ 架构设计

### 系统组件
```
┌─────────────────────────────────────────────────────────┐
│               智能组件生成系统                          │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ 决策引擎     │ │ 数据源管理   │ │ 组件生成器   │       │
│  │ Decision    │ │ Data Source │ │ Component   │       │
│  │ Engine      │ │ Manager     │ │ Generator   │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ 工具管理器   │ │ A2A客户端   │ │ 缓存系统     │       │
│  │ Tool        │ │ A2A Client  │ │ Cache       │       │
│  │ Manager     │ │             │ │ System      │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 数据流
```
参数定义 → 智能决策 → 数据源查询 → 组件生成 → 前端渲染
```

---

## 💻 详细实现

### 1. 组件类型决策引擎

```python
class ComponentTypeDecisionEngine:
    """组件类型决策引擎"""
    
    def __init__(self):
        self.name_hints = {
            'password': 'password',
            'email': 'email',
            'phone': 'tel',
            'url': 'url',
            'date': 'date',
            'time': 'time',
            'amount': 'number',
            'quantity': 'number',
            'age': 'number',
            'rating': 'range',
            'price': 'number',
            'count': 'number'
        }
    
    async def determine_component_type(self, param_name: str, param_context: Dict[str, Any]) -> str:
        """根据参数名称和上下文智能判断组件类型"""
        
        # 1. 基于参数名称的启发式规则
        param_name_lower = param_name.lower()
        if param_name_lower in self.name_hints:
            return self.name_hints[param_name_lower]
        
        # 2. 基于上下文的智能判断
        if param_context.get('options') and len(param_context['options']) <= 5:
            return 'radio'  # 选项少用单选
        elif param_context.get('options') and len(param_context['options']) > 5:
            return 'select'  # 选项多用下拉
        elif param_context.get('allow_multiple'):
            return 'checkbox'  # 允许多选用复选框
        elif param_context.get('searchable'):
            return 'combobox'  # 可搜索用组合框
        elif param_context.get('is_list'):
            return 'list'  # 列表类型
        
        # 3. 基于数据源的判断
        data_source = param_context.get('data_source')
        if data_source:
            return await self._decide_by_data_source(data_source)
        
        # 4. 基于参数类型的判断
        param_type = param_context.get('type')
        if param_type:
            return await self._decide_by_param_type(param_type)
        
        # 5. 默认判断
        return 'input'
    
    async def _decide_by_data_source(self, data_source: Dict[str, Any]) -> str:
        """基于数据源决定组件类型"""
        source_type = data_source.get('type')
        
        if source_type == 'enum':
            values = data_source.get('values', [])
            return 'select' if len(values) > 3 else 'radio'
        elif source_type == 'dynamic':
            return 'combobox'  # 动态数据用组合框
        elif source_type == 'search':
            return 'combobox'  # 搜索类型用组合框
        elif source_type == 'file':
            return 'file'  # 文件类型
        elif source_type == 'boolean':
            return 'radio'  # 布尔类型用单选
        
        return 'input'
    
    async def _decide_by_param_type(self, param_type: str) -> str:
        """基于参数类型决定组件类型"""
        type_mapping = {
            'string': 'input',
            'text': 'textarea',
            'number': 'number',
            'integer': 'number',
            'float': 'number',
            'boolean': 'radio',
            'date': 'date',
            'datetime': 'datetime',
            'email': 'email',
            'url': 'url',
            'password': 'password',
            'file': 'file',
            'array': 'checkbox',
            'object': 'input'
        }
        
        return type_mapping.get(param_type, 'input')
```

### 2. 数据源管理器

```python
class DataSourceManager:
    """数据源管理器"""
    
    def __init__(self, tool_manager, a2a_client, cache_manager):
        self.tool_manager = tool_manager
        self.a2a_client = a2a_client
        self.cache_manager = cache_manager
    
    async def get_options_for_param(self, param_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取参数选项数据"""
        
        data_source = param_config.get('data_source', {})
        source_type = data_source.get('type')
        
        # 检查缓存
        cache_key = f"options_{hash(str(data_source))}"
        cached_options = await self.cache_manager.get(cache_key)
        if cached_options:
            return cached_options
        
        options = []
        
        if source_type == 'static':
            options = data_source.get('options', [])
        
        elif source_type == 'tool_list':
            # 从工具列表获取
            options = await self._get_from_tool_list(data_source)
        
        elif source_type == 'a2a_query':
            # 通过A2A查询其他Agent
            options = await self._get_from_a2a(data_source)
        
        elif source_type == 'database':
            # 从数据库查询
            options = await self._get_from_database(data_source)
        
        elif source_type == 'enum':
            # 枚举类型
            options = await self._format_enum_options(data_source.get('values', []))
        
        elif source_type == 'search':
            # 搜索类型（用于combobox）
            options = await self._get_search_options(data_source)
        
        # 缓存结果
        if options:
            await self.cache_manager.set(cache_key, options, ttl=300)  # 5分钟缓存
        
        return options
    
    async def _get_from_tool_list(self, data_source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从工具列表获取选项"""
        tool_category = data_source.get('category')
        tools = await self.tool_manager.get_tools_by_category(tool_category)
        
        return [
            {
                "value": tool.id,
                "label": tool.name,
                "description": tool.description,
                "icon": tool.icon,
                "category": tool.category,
                "metadata": tool.metadata
            }
            for tool in tools
        ]
    
    async def _get_from_a2a(self, data_source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """通过A2A查询其他Agent获取选项"""
        target_agent = data_source.get('agent_id')
        query_method = data_source.get('method')
        query_params = data_source.get('params', {})
        
        try:
            # 通过A2A调用其他Agent的方法
            response = await self.a2a_client.call_agent_method(
                target_agent, 
                query_method, 
                query_params
            )
            
            if response.get('success'):
                return response.get('options', [])
            else:
                logger.error(f"A2A query failed: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Error querying A2A agent {target_agent}: {e}")
            return []
    
    async def _get_from_database(self, data_source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从数据库查询获取选项"""
        table = data_source.get('table')
        fields = data_source.get('fields', ['id', 'name'])
        where_clause = data_source.get('where', {})
        
        # 这里应该调用数据库查询
        # 简化实现
        return []
    
    async def _format_enum_options(self, values: List[Any]) -> List[Dict[str, Any]]:
        """格式化枚举选项"""
        return [
            {
                "value": value,
                "label": str(value).title(),
                "description": f"选择 {value}"
            }
            for value in values
        ]
    
    async def _get_search_options(self, data_source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取搜索选项（用于combobox）"""
        search_endpoint = data_source.get('endpoint')
        search_field = data_source.get('search_field', 'name')
        
        # 返回空的搜索选项，实际搜索在用户输入时进行
        return []
```

### 3. 智能参数定义生成器

```python
class SmartParameterGenerator:
    """智能参数定义生成器"""
    
    def __init__(self, decision_engine, data_source_manager):
        self.decision_engine = decision_engine
        self.data_source_manager = data_source_manager
    
    async def generate_parameter_definition(self, param_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """智能生成参数定义"""
        
        # 1. 决策组件类型
        component_type = await self.decision_engine.determine_component_type(param_name, context)
        
        # 2. 获取数据源
        data_source = context.get('data_source')
        options = []
        if data_source:
            options = await self.data_source_manager.get_options_for_param({
                'data_source': data_source
            })
        
        # 3. 生成基础参数定义
        param_definition = {
            "type": component_type,
            "label": context.get('label', self._generate_label(param_name)),
            "description": context.get('description', ''),
            "required": context.get('required', True),
            "validation": self._generate_validation(param_name, component_type, context)
        }
        
        # 4. 根据组件类型添加特定属性
        if component_type in ['radio', 'select', 'checkbox', 'combobox', 'list']:
            param_definition["options"] = options
            param_definition["searchable"] = component_type == 'combobox'
            param_definition["allow_multiple"] = component_type == 'checkbox'
        
        # 5. 添加UI提示
        param_definition["ui_hints"] = self._generate_ui_hints(context)
        
        # 6. 添加依赖关系
        if context.get('dependencies'):
            param_definition["dependencies"] = context['dependencies']
        
        return param_definition
    
    def _generate_label(self, param_name: str) -> str:
        """生成参数标签"""
        # 简单的标签生成逻辑
        label_mapping = {
            'computer_model': '电脑型号',
            'department': '部门',
            'position': '职位',
            'start_date': '入职日期',
            'skills': '技能',
            'email': '邮箱地址',
            'phone': '电话号码',
            'amount': '金额',
            'description': '描述'
        }
        
        return label_mapping.get(param_name, param_name.replace('_', ' ').title())
    
    def _generate_validation(self, param_name: str, component_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成验证规则"""
        validation = {
            "type": "string"
        }
        
        if component_type == 'number':
            validation = {
                "type": "number",
                "min": context.get('min_value'),
                "max": context.get('max_value')
            }
        elif component_type == 'email':
            validation = {"type": "email"}
        elif component_type == 'url':
            validation = {"type": "url"}
        elif component_type in ['radio', 'select', 'checkbox']:
            options = context.get('data_source', {}).get('options', [])
            if options:
                validation = {
                    "type": "enum",
                    "values": [opt['value'] for opt in options]
                }
        
        return validation
    
    def _generate_ui_hints(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成UI提示"""
        return {
            "width": context.get('ui_width', 'full'),
            "height": context.get('ui_height', 'auto'),
            "group": context.get('ui_group', 'default'),
            "icon": context.get('icon'),
            "color": context.get('color')
        }
```

### 4. Agent集成示例

```python
class ITAgent:
    """IT Agent示例"""
    
    def __init__(self, param_generator):
        self.param_generator = param_generator
    
    async def apply_for_computer(self, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """申请电脑设备"""
        try:
            # 检查必需参数
            computer_model = plan_context.get("values", {}).get("computer_model")
            if not computer_model:
                # 检查是否在continue阶段提供了参数
                provided_params = plan_context.get("provided_params", {})
                computer_model = provided_params.get("computer_model")
                
                if not computer_model:
                    # 智能生成电脑型号参数
                    computer_model_param = await self.param_generator.generate_parameter_definition(
                        "computer_model",
                        {
                            "data_source": {
                                "type": "a2a_query",
                                "agent_id": "inventory_agent",
                                "method": "get_available_computers",
                                "params": {"category": "laptop", "status": "available"}
                            },
                            "label": "电脑型号",
                            "description": "请选择所需的电脑型号",
                            "required": True
                        }
                    )
                    
                    return {
                        "success": False,
                        "reason": "missing_params",
                        "required_params": {
                            "computer_model": computer_model_param
                        }
                    }
            
            # 使用参数执行业务逻辑
            employee_name = plan_context.get("values", {}).get("employee_name", "未知员工")
            result = await self._process_computer_application(computer_model, employee_name)
            
            return {
                "success": True,
                "result": result,
                "message": f"已为{employee_name}申请{computer_model}"
            }
            
        except Exception as e:
            logger.error(f"Error applying for computer: {e}")
            return {"success": False, "error": str(e)}

class HRAgent:
    """HR Agent示例"""
    
    def __init__(self, param_generator):
        self.param_generator = param_generator
    
    async def create_employee_profile(self, plan_context: Dict[str, Any]) -> Dict[str, Any]:
        """创建员工档案"""
        
        required_params = ["full_name", "department", "position", "start_date"]
        missing_params = {}
        
        for param in required_params:
            if not plan_context.get("values", {}).get(param) and not plan_context.get("provided_params", {}).get(param):
                # 智能生成参数定义
                param_config = await self._get_param_config(param)
                missing_params[param] = await self.param_generator.generate_parameter_definition(
                    param, param_config
                )
        
        if missing_params:
            return {
                "success": False,
                "reason": "missing_params",
                "required_params": missing_params
            }
        
        # 继续执行业务逻辑...
        return {"success": True, "message": "员工档案创建成功"}
    
    async def _get_param_config(self, param_name: str) -> Dict[str, Any]:
        """获取参数配置"""
        configs = {
            "full_name": {
                "type": "string",
                "label": "姓名",
                "description": "请输入员工的全名",
                "validation": {
                    "type": "string",
                    "min_length": 2,
                    "max_length": 20
                }
            },
            "department": {
                "data_source": {
                    "type": "a2a_query",
                    "agent_id": "hr_agent",
                    "method": "get_departments"
                },
                "label": "部门",
                "description": "请选择员工所属部门"
            },
            "position": {
                "type": "string",
                "label": "职位",
                "description": "请输入员工职位"
            },
            "start_date": {
                "type": "date",
                "label": "入职日期",
                "description": "请选择员工入职日期",
                "validation": {
                    "type": "date",
                    "min": "2024-01-01",
                    "max": "2025-12-31"
                }
            }
        }
        
        return configs.get(param_name, {})
```

---

## 🎨 前端集成

### 动态组件渲染
```javascript
class ComponentRenderer {
    constructor() {
        this.componentMap = {
            'input': this.renderInput,
            'textarea': this.renderTextarea,
            'select': this.renderSelect,
            'radio': this.renderRadio,
            'checkbox': this.renderCheckbox,
            'combobox': this.renderCombobox,
            'list': this.renderList,
            'date': this.renderDate,
            'number': this.renderNumber,
            'email': this.renderEmail,
            'url': this.renderUrl,
            'password': this.renderPassword,
            'file': this.renderFile,
            'range': this.renderRange
        };
    }
    
    async renderParameterField(paramName, config) {
        const componentType = config.type;
        const renderer = this.componentMap[componentType];
        
        if (!renderer) {
            console.warn(`Unknown component type: ${componentType}`);
            return this.renderInput(paramName, config);
        }
        
        // 如果是动态数据源，先获取选项
        if (config.options && config.data_source) {
            config.options = await this.fetchOptions(config.data_source);
        }
        
        return renderer.call(this, paramName, config);
    }
    
    async fetchOptions(dataSource) {
        const response = await fetch('/api/data-source/options', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(dataSource)
        });
        
        const result = await response.json();
        return result.options || [];
    }
    
    renderCombobox(paramName, config) {
        return `
            <div class="param-field" data-param="${paramName}">
                <label class="param-label">${config.label}</label>
                <div class="combobox-container">
                    <input type="text" 
                           class="combobox-input"
                           placeholder="${config.placeholder || '搜索并选择...'}"
                           data-param="${paramName}"
                           autocomplete="off">
                    <div class="combobox-dropdown" style="display: none;">
                        ${config.options.map(option => `
                            <div class="combobox-option" data-value="${option.value}">
                                ${option.label}
                                ${option.description ? `<small>${option.description}</small>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
    }
    
    renderList(paramName, config) {
        return `
            <div class="param-field" data-param="${paramName}">
                <label class="param-label">${config.label}</label>
                <div class="list-container">
                    ${config.options.map(option => `
                        <div class="list-item" data-value="${option.value}">
                            <div class="list-item-content">
                                <div class="list-item-title">${option.label}</div>
                                ${option.description ? `<div class="list-item-desc">${option.description}</div>` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
}
```

---

## 📊 API设计

### 数据源查询API
```python
@router.post("/data-source/options")
async def get_data_source_options(
    data_source: Dict[str, Any],
    data_source_manager = Depends(get_data_source_manager)
):
    """获取数据源选项"""
    options = await data_source_manager.get_options_for_param({
        'data_source': data_source
    })
    return {"options": options}

@router.get("/data-source/search")
async def search_options(
    query: str,
    data_source_id: str,
    data_source_manager = Depends(get_data_source_manager)
):
    """搜索选项（用于combobox）"""
    # 实现搜索逻辑
    results = await data_source_manager.search_options(query, data_source_id)
    return {"results": results}
```

---

## 📈 实施计划

### Phase 1: 核心功能（2周）
- [ ] 实现组件类型决策引擎
- [ ] 实现数据源管理器
- [ ] 实现智能参数生成器
- [ ] 实现基础API

### Phase 2: 数据源集成（1周）
- [ ] A2A查询集成
- [ ] 工具列表集成
- [ ] 数据库查询集成
- [ ] 缓存系统实现

### Phase 3: 前端集成（1周）
- [ ] 动态组件渲染
- [ ] 搜索功能实现
- [ ] 用户体验优化

---

## 🎯 验收标准

1. **功能完整性**:
   - ✅ 能够智能判断组件类型
   - ✅ 支持多种数据源查询
   - ✅ 动态组件渲染正常
   - ✅ 缓存机制有效

2. **性能要求**:
   - ✅ 组件生成响应时间 < 200ms
   - ✅ 数据源查询响应时间 < 1s
   - ✅ 缓存命中率 > 80%

3. **扩展性**:
   - ✅ 支持新增组件类型
   - ✅ 支持新增数据源类型
   - ✅ 支持自定义验证规则

---

**智能组件生成系统将让AI员工能够生成最适合的交互界面，提供最佳的用户体验！**
