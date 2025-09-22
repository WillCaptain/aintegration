"""
Email Agent实现

专门用于邮件发送的Agent
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailAgent:
    """邮件发送Agent"""
    
    def __init__(self, agent_id: str = "email_agent_v1"):
        self.agent_id = agent_id
        self.agent_name = "Email Agent"
        self.system_prompt = "你是一个邮件发送的专业代理，负责发送各种类型的邮件"
        self.allowed_tools = ["send_email", "validate_email", "format_email"]
        
    async def execute(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行邮件发送任务"""
        try:
            logger.info(f"Email Agent {self.agent_id} executing: {prompt[:100]}...")
            
            # 解析上下文中的邮件信息
            email_info = self._extract_email_info(context)
            
            if not email_info:
                return {
                    "success": False,
                    "error": "无法从上下文中提取邮件信息",
                    "context": context
                }
            
            # 验证邮件信息
            validation_result = await self._validate_email_info(email_info)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result["error"],
                    "context": context
                }
            
            # 格式化邮件内容
            formatted_email = self._format_email(email_info)
            
            # 发送邮件
            send_result = await self._send_email(formatted_email)
            
            if send_result["success"]:
                return {
                    "success": True,
                    "result": "邮件发送成功",
                    "message_id": send_result.get("message_id"),
                    "context": {
                        **context,
                        "email_sent": True,
                        "sent_at": datetime.now().isoformat(),
                        "message_id": send_result.get("message_id")
                    }
                }
            else:
                return {
                    "success": False,
                    "error": send_result["error"],
                    "context": {
                        **context,
                        "email_sent": False,
                        "error": send_result["error"]
                    }
                }
                
        except Exception as e:
            logger.error(f"Email Agent execution error: {e}")
            return {
                "success": False,
                "error": f"邮件发送过程中发生错误: {str(e)}",
                "context": context
            }
    
    def _extract_email_info(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """从上下文中提取邮件信息"""
        try:
            # 支持多种上下文格式
            email_info = {}
            
            # 方式1: 直接包含邮件字段
            if all(key in context for key in ["to", "subject", "body"]):
                email_info = {
                    "to": context["to"],
                    "subject": context["subject"],
                    "body": context["body"]
                }
            
            # 方式2: 从嵌套对象中提取
            elif "email" in context:
                email_data = context["email"]
                if isinstance(email_data, dict):
                    email_info = {
                        "to": email_data.get("to"),
                        "subject": email_data.get("subject"),
                        "body": email_data.get("body")
                    }
            
            # 方式3: 从任务上下文中提取
            elif "values" in context:
                values = context["values"]
                email_info = {
                    "to": values.get("to"),
                    "subject": values.get("subject"), 
                    "body": values.get("body")
                }
            
            # 检查是否成功提取
            if all(email_info.get(key) for key in ["to", "subject", "body"]):
                return email_info
            
            logger.warning(f"无法从上下文中提取完整的邮件信息: {context}")
            return None
            
        except Exception as e:
            logger.error(f"提取邮件信息时发生错误: {e}")
            return None
    
    async def _validate_email_info(self, email_info: Dict[str, Any]) -> Dict[str, Any]:
        """验证邮件信息"""
        try:
            # 验证收件人邮箱
            to_email = email_info.get("to", "").strip()
            if not to_email:
                return {"valid": False, "error": "收件人邮箱不能为空"}
            
            if not self._is_valid_email(to_email):
                return {"valid": False, "error": f"收件人邮箱格式不正确: {to_email}"}
            
            # 验证邮件主题
            subject = email_info.get("subject", "").strip()
            if not subject:
                return {"valid": False, "error": "邮件主题不能为空"}
            
            if len(subject) > 200:
                return {"valid": False, "error": "邮件主题长度不能超过200个字符"}
            
            # 验证邮件内容
            body = email_info.get("body", "").strip()
            if not body:
                return {"valid": False, "error": "邮件内容不能为空"}
            
            if len(body) > 10000:
                return {"valid": False, "error": "邮件内容长度不能超过10000个字符"}
            
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"验证邮件信息时发生错误: {e}")
            return {"valid": False, "error": f"验证过程发生错误: {str(e)}"}
    
    def _is_valid_email(self, email: str) -> bool:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _format_email(self, email_info: Dict[str, Any]) -> Dict[str, Any]:
        """格式化邮件内容"""
        try:
            # 添加邮件头信息
            formatted_email = {
                "to": email_info["to"],
                "subject": email_info["subject"],
                "body": email_info["body"],
                "from": "noreply@company.com",  # 可以从配置中获取
                "timestamp": datetime.now().isoformat(),
                "agent_id": self.agent_id
            }
            
            # 可以在这里添加更多格式化逻辑
            # 比如：添加签名、格式化正文等
            
            return formatted_email
            
        except Exception as e:
            logger.error(f"格式化邮件时发生错误: {e}")
            raise
    
    async def _send_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """发送邮件"""
        try:
            logger.info(f"发送邮件到: {email_data['to']}")
            
            # 模拟邮件发送过程
            # 在实际实现中，这里会调用真实的邮件服务API
            
            # 模拟网络延迟
            await asyncio.sleep(0.1)
            
            # 模拟发送成功
            message_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(email_data['to']) % 10000:04d}"
            
            # 记录发送日志
            logger.info(f"邮件发送成功: {message_id}")
            
            return {
                "success": True,
                "message_id": message_id,
                "status": "sent",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"发送邮件时发生错误: {e}")
            return {
                "success": False,
                "error": f"邮件发送失败: {str(e)}"
            }
    
    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent信息"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "system_prompt": self.system_prompt,
            "allowed_tools": self.allowed_tools,
            "capabilities": [
                "发送邮件",
                "验证邮箱格式",
                "格式化邮件内容",
                "错误处理和重试"
            ]
        }
