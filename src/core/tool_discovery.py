"""
工具发现机制

负责发现和获取工具选项，支持：
1. 本地工具查询
2. A2A工具查询
3. 智能工具匹配
"""

import logging
from typing import Dict, Any, List, Optional
from .id_generator import id_generator

logger = logging.getLogger(__name__)

class ToolDiscovery:
    """工具发现器"""
    
    def __init__(self, mcp_client=None, a2a_client=None):
        self.mcp_client = mcp_client
        self.a2a_client = a2a_client
        self._local_tools_cache = {}
        self._a2a_agents_cache = {}
    
    async def get_options_for_param(self, param_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取参数选项数据"""
        
        data_source = param_config.get('data_source', {})
        source_type = data_source.get('type')
        
        if source_type == 'static':
            return data_source.get('options', [])
        
        elif source_type == 'local_tool':
            return await self._get_from_local_tool(data_source)
        
        elif source_type == 'a2a_query':
            return await self._get_from_a2a(data_source)
        
        elif source_type == 'smart_discovery':
            return await self._smart_discovery(param_config)
        
        return []
    
    async def _get_from_local_tool(self, data_source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从本地工具获取选项"""
        tool_name = data_source.get('tool_name')
        tool_params = data_source.get('params', {})
        
        if not self.mcp_client:
            logger.warning("MCP client not available for local tool query")
            return []
        
        try:
            # 调用本地MCP工具
            result = await self.mcp_client.call_tool(tool_name, tool_params)
            
            if result.get('success'):
                return result.get('data', [])
            else:
                logger.error(f"Local tool {tool_name} failed: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Error calling local tool {tool_name}: {e}")
            return []
    
    async def _get_from_a2a(self, data_source: Dict[str, Any]) -> List[Dict[str, Any]]:
        """通过A2A查询获取选项"""
        target_agent = data_source.get('agent_id')
        query_method = data_source.get('method')
        query_params = data_source.get('params', {})
        
        if not self.a2a_client:
            logger.warning("A2A client not available for agent query")
            return []
        
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
    
    async def _smart_discovery(self, param_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """智能工具发现"""
        param_name = param_config.get('name', '')
        param_type = param_config.get('type', '')
        
        # 基于参数名称和类型智能匹配工具
        if 'region' in param_name.lower() or 'area' in param_name.lower():
            return await self._discover_region_tools()
        elif 'phone' in param_name.lower() or 'mobile' in param_name.lower():
            return await self._discover_phone_tools()
        elif 'email' in param_name.lower():
            return await self._discover_email_tools()
        elif 'id_card' in param_name.lower() or 'idcard' in param_name.lower():
            return await self._discover_id_card_tools()
        
        return []
    
    async def _discover_region_tools(self) -> List[Dict[str, Any]]:
        """发现地区相关工具"""
        options = []
        
        # 1. 尝试本地工具
        if self.mcp_client:
            try:
                result = await self.mcp_client.call_tool("get_china_regions", {"level": "province"})
                if result.get('success'):
                    options.extend(result.get('data', []))
            except Exception as e:
                logger.debug(f"Local region tool not available: {e}")
        
        # 2. 尝试A2A查询
        if self.a2a_client:
            try:
                response = await self.a2a_client.call_agent_method(
                    "common_tools_agent",
                    "get_china_regions",
                    {"level": "province"}
                )
                if response.get('success'):
                    options.extend(response.get('options', []))
            except Exception as e:
                logger.debug(f"A2A region query failed: {e}")
        
        # 3. 如果都没有，返回默认地区列表
        if not options:
            options = [
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
            ]
        
        return options
    
    async def _discover_phone_tools(self) -> List[Dict[str, Any]]:
        """发现手机号相关工具"""
        # 返回运营商选项
        return [
            {"value": "中国移动", "label": "中国移动", "pattern": "^1[3-9]\\d{9}$"},
            {"value": "中国联通", "label": "中国联通", "pattern": "^1[3-9]\\d{9}$"},
            {"value": "中国电信", "label": "中国电信", "pattern": "^1[3-9]\\d{9}$"}
        ]
    
    async def _discover_email_tools(self) -> List[Dict[str, Any]]:
        """发现邮箱相关工具"""
        # 返回常用邮箱域名
        return [
            {"value": "gmail.com", "label": "Gmail"},
            {"value": "qq.com", "label": "QQ邮箱"},
            {"value": "163.com", "label": "163邮箱"},
            {"value": "126.com", "label": "126邮箱"},
            {"value": "sina.com", "label": "新浪邮箱"},
            {"value": "hotmail.com", "label": "Hotmail"},
            {"value": "outlook.com", "label": "Outlook"}
        ]
    
    async def _discover_id_card_tools(self) -> List[Dict[str, Any]]:
        """发现身份证相关工具"""
        # 返回地区代码选项（用于身份证前6位）
        return [
            {"value": "110000", "label": "北京市", "code": "110000"},
            {"value": "310000", "label": "上海市", "code": "310000"},
            {"value": "440000", "label": "广东省", "code": "440000"},
            {"value": "320000", "label": "江苏省", "code": "320000"},
            {"value": "330000", "label": "浙江省", "code": "330000"}
        ]
    
    async def discover_agents_by_capability(self, capability: str) -> List[str]:
        """根据能力发现Agent"""
        if not self.a2a_client:
            return []
        
        try:
            agents = await self.a2a_client.discover_agents(capability)
            return [agent.id for agent in agents]
        except Exception as e:
            logger.error(f"Error discovering agents for capability {capability}: {e}")
            return []
    
    async def get_agent_tools(self, agent_id: str) -> List[Dict[str, Any]]:
        """获取Agent的工具列表"""
        if not self.a2a_client:
            return []
        
        try:
            response = await self.a2a_client.call_agent_method(
                agent_id,
                "get_available_tools",
                {}
            )
            
            if response.get('success'):
                return response.get('tools', [])
            return []
        except Exception as e:
            logger.error(f"Error getting tools from agent {agent_id}: {e}")
            return []
