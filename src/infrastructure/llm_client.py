"""
LLM Client 抽象与具体实现

支持多 Provider 的可插拔接口。目前实现 Google Gemini 适配器。
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
import json
import httpx

from config import config_loader

logger = logging.getLogger(__name__)


class LLMClient:
    """统一的 LLM 客户端接口。"""

    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """给定文本 prompt（和可选 tools 声明）生成文本响应。"""
        raise NotImplementedError

    async def propose_tool_call(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """返回模型建议的函数调用（若有）。

        统一返回：{"name": str, "arguments": dict}
        无建议时返回 None。
        """
        raise NotImplementedError


class GoogleGeminiClient(LLMClient):
    """Google Gemini 适配器。"""

    def __init__(self, model_name: Optional[str] = None):
        try:
            import google.generativeai as genai  # type: ignore
            from google.generativeai.types import HarmCategory, HarmBlockThreshold  # type: ignore
        except Exception as e:
            # 延迟导入失败时记录，但不在初始化阶段直接抛错，避免影响加载
            logger.warning("google.generativeai 导入失败: %s", e)
            genai = None  # type: ignore
            HarmCategory = None  # type: ignore
            HarmBlockThreshold = None  # type: ignore

        self._genai = genai
        self._HarmCategory = HarmCategory
        self._HarmBlockThreshold = HarmBlockThreshold

        # 读取 API Key：优先配置，再环境变量
        api_key = (
            config_loader.get("google_adk.api_key")
            or config_loader.get("llm.google.api_key")
            or os.getenv("GOOGLE_API_KEY")
            or os.getenv("ADK_API_KEY")
        )

        if self._genai and api_key:
            self._genai.configure(api_key=api_key)
        elif not api_key:
            logger.warning("Google API Key 未配置，后续调用可能失败。")

        # 默认模型
        self.model_name = (
            model_name
            or config_loader.get("llm.model")
            or "gemini-pro"
        )

        # 推理与安全配置
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        if self._HarmCategory and self._HarmBlockThreshold:
            self.safety_settings = {
                self._HarmCategory.HARM_CATEGORY_HARASSMENT: self._HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                self._HarmCategory.HARM_CATEGORY_HATE_SPEECH: self._HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                self._HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: self._HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                self._HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: self._HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        else:
            self.safety_settings = None

        # 构造底层模型
        self._model = None
        if self._genai:
            kw: Dict[str, Any] = {"model_name": self.model_name, "generation_config": self.generation_config}
            if self.safety_settings:
                kw["safety_settings"] = self.safety_settings
            try:
                self._model = self._genai.GenerativeModel(**kw)
                logger.info("GoogleGeminiClient 初始化完成: %s", self.model_name)
            except Exception as e:
                logger.error("创建 GenerativeModel 失败: %s", e)

    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        if not self._model:
            raise RuntimeError("GoogleGeminiClient 未正确初始化（缺少 SDK 或 API Key）。")
        try:
            kwargs: Dict[str, Any] = {}
            if tools:
                kwargs["tools"] = tools
            resp = await self._model.generate_content_async(prompt, **kwargs)
            return getattr(resp, "text", str(resp))
        except TypeError:
            # SDK 不支持 tools 参数
            resp = await self._model.generate_content_async(prompt)
            return getattr(resp, "text", str(resp))
        except Exception as e:
            logger.error("Gemini generate 失败: %s", e)
            raise


class BaseOpenAICompatibleClient(LLMClient):
    """基于 OpenAI Chat Completions API 兼容层的通用客户端。

    子类通过提供 base_url 与认证头实现 OpenAI 与 DeepSeek 等。
    """

    def __init__(self, model_name: Optional[str], base_url: str, api_key: str, organization: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.organization = organization
        self.model_name = model_name or "gpt-4o"

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        return headers

    def _map_tools(self, tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        # 输入是 [{"function_declarations": [schema...]}] for Gemini 风格
        # 这里接受直接是 function schema 列表，或封装过的，进行宽松适配
        function_schemas: List[Dict[str, Any]] = []
        if isinstance(tools, list) and tools and "function_declarations" in (tools[0] or {}):
            function_schemas = tools[0]["function_declarations"]
        else:
            # 视为已经是 function 列表
            function_schemas = tools  # type: ignore
        mapped: List[Dict[str, Any]] = []
        for fs in function_schemas:
            mapped.append({
                "type": "function",
                "function": {
                    "name": fs.get("name"),
                    "description": fs.get("description", ""),
                    "parameters": fs.get("parameters", {"type": "object", "properties": {}}),
                },
            })
        return mapped

    async def generate(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
        mapped_tools = self._map_tools(tools)
        if mapped_tools:
            payload["tools"] = mapped_tools
            payload["tool_choice"] = "auto"
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = (
                ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            )
            return content or ""

    async def propose_tool_call(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
        mapped_tools = self._map_tools(tools)
        if mapped_tools:
            payload["tools"] = mapped_tools
            payload["tool_choice"] = "auto"
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()
            msg = ((data.get("choices") or [{}])[0].get("message") or {})
            # 新版字段 tool_calls
            tool_calls = msg.get("tool_calls") or []
            if tool_calls:
                tc = tool_calls[0]
                fn = tc.get("function") or {}
                name = fn.get("name")
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"_raw": args}
                return {"name": name, "arguments": args or {}}
            # 兼容旧版 function_call
            fnc = msg.get("function_call")
            if fnc:
                name = fnc.get("name")
                args = fnc.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"_raw": args}
                return {"name": name, "arguments": args or {}}
            return None


class OpenAIClient(BaseOpenAICompatibleClient):
    def __init__(self, model_name: Optional[str] = None):
        api_key = (
            config_loader.get("openai.api_key")
            or os.getenv("OPENAI_API_KEY")
            or ""
        )
        org = config_loader.get("openai.organization")
        base_url = config_loader.get("openai.base_url", "https://api.openai.com/v1")
        super().__init__(model_name=model_name or config_loader.get("llm.model"), base_url=base_url, api_key=api_key, organization=org)


class DeepSeekClient(BaseOpenAICompatibleClient):
    def __init__(self, model_name: Optional[str] = None):
        api_key = (
            config_loader.get("deepseek.api_key")
            or os.getenv("DEEPSEEK_API_KEY")
            or ""
        )
        base_url = config_loader.get("deepseek.base_url", "https://api.deepseek.com/v1")
        # DeepSeek 模型常见为 deepseek-chat / deepseek-coder 等
        model = model_name or config_loader.get("llm.model") or "deepseek-chat"
        super().__init__(model_name=model, base_url=base_url, api_key=api_key)

    async def propose_tool_call(self, prompt: str, tools: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """尝试解析 Gemini 返回的函数调用。"""
        if not self._model:
            return None
        try:
            kwargs: Dict[str, Any] = {}
            if tools:
                kwargs["tools"] = tools
            resp = await self._model.generate_content_async(prompt, **kwargs)
            # 尝试从候选中解析 function_call
            candidate = None
            try:
                candidate = getattr(resp, "candidates", [None])[0]
            except Exception:
                candidate = None
            if not candidate:
                return None
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", []) if content is not None else []
            for part in parts:
                fn = getattr(part, "function_call", None)
                if not fn:
                    continue
                name = getattr(fn, "name", None)
                args = getattr(fn, "args", None) or getattr(fn, "arguments", None)
                # 某些版本为 dict，某些为 json 字符串
                if isinstance(args, str):
                    import json as _json
                    try:
                        args = _json.loads(args)
                    except Exception:
                        args = {"_raw": args}
                if name:
                    return {"name": name, "arguments": args or {}}
            return None
        except TypeError:
            # 不支持 tools 参数，无法稳定解析函数调用
            return None
        except Exception as e:
            logger.debug("propose_tool_call 解析失败: %s", e)
            return None


def build_llm_client(provider: Optional[str] = None, model_name: Optional[str] = None) -> LLMClient:
    """根据 provider 创建对应的 LLMClient。默认 google。

    配置键：
    - llm.provider: google/openai/azure_openai/anthropic/...
    - llm.model: 具体模型名
    """
    prov = provider or (config_loader.get("llm.provider") or "google").lower()
    mdl = model_name or config_loader.get("llm.model")

    if prov == "google":
        return GoogleGeminiClient(model_name=mdl)
    if prov == "openai":
        return OpenAIClient(model_name=mdl)
    if prov == "deepseek":
        return DeepSeekClient(model_name=mdl)

    # 其他 Provider 可在此扩展
    raise NotImplementedError(f"Unsupported llm.provider: {prov}")


