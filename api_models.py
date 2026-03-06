"""
多模型API支持模块 (v2)
支持 OpenAI, DeepSeek, Claude, 以及本地 Ollama

提供统一的接口进行 API 调用，包含：
- 真正的 SSE 流式响应
- 多轮对话历史注入
- 意图动态调参
- 回复增强管线
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, AsyncIterator
import asyncio
import httpx
import json
from datetime import datetime

logger = logging.getLogger(__name__)

def get_dynamic_system_prompt() -> str:
    """从当前激活角色构建系统提示词"""
    try:
        from character_manager import character_manager
        char = character_manager.get_active_character()
        return char.build_system_prompt()
    except Exception as e:
        logger.warning(f"获取角色提示词失败，使用默认: {e}")
        return "你是一个温柔体贴的女友，风格温暖亲切，适当调皮。"


def _get_conversation_history(limit: int = 5) -> List[dict]:
    """获取近期对话历史，格式化为 messages 数组。"""
    try:
        from database import db
        from character_manager import character_manager
        cid = character_manager.get_active_id()
        pairs = db.get_recent_conversations(num_pairs=limit, character_id=cid)
        messages = []
        for user_msg, ai_msg in reversed(pairs):
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            if ai_msg:
                messages.append({"role": "assistant", "content": ai_msg})
        return messages
    except Exception:
        return []

class BaseAPIModel(ABC):
    """所有模型的基类"""
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name
        self.created_at = datetime.now()
    
    @abstractmethod
    async def generate(
        self, 
        message: str, 
        context: str = "", 
        temperature: float = 0.7, 
        max_tokens: int = 512
    ) -> str:
        """生成回复"""
        pass

    async def generate_stream(
        self,
        message: str,
        context: str = "",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """流式生成回复（默认 fallback 到非流式）"""
        result = await self.generate(message, context, temperature, max_tokens)
        yield result
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查模型是否可用"""
        pass
    
    @abstractmethod
    def get_info(self) -> dict:
        """获取模型信息"""
        pass


class OpenAIModel(BaseAPIModel):
    """OpenAI 模型支持 (GPT-3.5-turbo, GPT-4 等)"""
    
    def __init__(self, api_key: str = None, model_name: str = "gpt-3.5-turbo"):
        super().__init__(model_name)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.api_base = "https://api.openai.com/v1/chat/completions"
        self.timeout = 30  # 秒
    
    def is_available(self) -> bool:
        """检查API密钥是否配置"""
        return bool(self.api_key)
    
    def get_info(self) -> dict:
        return {
            "name": "OpenAI",
            "model": self.model_name,
            "provider": "openai",
            "available": self.is_available(),
            "speed": "快速 (2-5秒)"
        }
    
    async def generate(
        self, 
        message: str, 
        context: str = "", 
        temperature: float = 0.7, 
        max_tokens: int = 512
    ) -> str:
        """通过 OpenAI API 生成回复"""
        if not self.is_available():
            raise ValueError("OpenAI API 密钥未配置")
        
        # 构建系统提示词
        system_prompt = get_dynamic_system_prompt()
        if context:
            system_prompt += f"\n参考背景信息:\n{context}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建多轮消息（含历史）
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(_get_conversation_history(limit=5))
        messages.append({"role": "user", "content": message})
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"📤 发送请求到 OpenAI: {self.api_base}")
                response = await client.post(self.api_base, json=payload, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                # 检查响应格式
                if "choices" not in data or not data["choices"]:
                    logger.error(f"❌ OpenAI 响应格式错误: {data}")
                    raise KeyError("Invalid response structure: no choices")
                
                reply = data["choices"][0].get("message", {}).get("content", "").strip()
                
                if not reply:
                    logger.error(f"❌ OpenAI 返回空内容")
                    raise ValueError("API 返回空回复")
                
                logger.info(f"✓ OpenAI 生成成功 ({len(reply)} 字符)")
                return reply
                
        except httpx.TimeoutException:
            logger.error("❌ OpenAI 超时（30秒内无响应）")
            raise ValueError("API 请求超时，请稍后重试")
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ OpenAI HTTP 错误 {e.response.status_code}: {e.response.text}")
            raise ValueError(f"API 错误 ({e.response.status_code}): {e.response.text[:200]}")
        except httpx.HTTPError as e:
            logger.error(f"❌ OpenAI 网络错误: {str(e)}")
            raise ValueError(f"网络错误: {str(e)}")
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"❌ OpenAI 响应解析失败: {type(e).__name__}: {str(e)}")
            raise ValueError(f"服务器响应格式错误: {str(e)}")

    async def generate_stream(
        self,
        message: str,
        context: str = "",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """OpenAI 真正的 SSE 流式生成"""
        if not self.is_available():
            raise ValueError("OpenAI API 密钥未配置")

        system_prompt = get_dynamic_system_prompt()
        if context:
            system_prompt += f"\n参考背景信息:\n{context}"

        msgs = [{"role": "system", "content": system_prompt}]
        msgs.extend(_get_conversation_history(limit=5))
        msgs.append({"role": "user", "content": message})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream("POST", self.api_base, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            obj = json.loads(data_str)
                            delta = obj["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except Exception as e:
            logger.error(f"❌ OpenAI stream 错误: {e}")
            raise ValueError(f"OpenAI 流式生成失败: {e}")


class DeepSeekModel(BaseAPIModel):
    """DeepSeek 模型支持"""
    
    def __init__(self, api_key: str = None, model_name: str = "deepseek-chat"):
        super().__init__(model_name)
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.api_base = "https://api.deepseek.com/chat/completions"
        self.timeout = 60
    
    def is_available(self) -> bool:
        """检查API密钥是否配置"""
        return bool(self.api_key)
    
    def get_info(self) -> dict:
        return {
            "name": "DeepSeek",
            "model": self.model_name,
            "provider": "deepseek",
            "available": self.is_available(),
            "speed": "极快 (1-3秒)",
            "cost_effective": True
        }
    
    async def generate(
        self, 
        message: str, 
        context: str = "", 
        temperature: float = 0.7, 
        max_tokens: int = 512
    ) -> str:
        """通过 DeepSeek API 生成回复"""
        if not self.is_available():
            raise ValueError("DeepSeek API 密钥未配置")

        system_prompt = get_dynamic_system_prompt()
        if context:
            system_prompt += f"\n参考背景信息:\n{context}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # 构建多轮消息（含历史）
        msgs = [{"role": "system", "content": system_prompt}]
        msgs.extend(_get_conversation_history(limit=5))
        msgs.append({"role": "user", "content": message})

        payload = {
            "model": self.model_name,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"📤 发送请求到 DeepSeek: {self.api_base}")
                response = await client.post(self.api_base, json=payload, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                if "choices" not in data or not data["choices"]:
                    logger.error(f"❌ DeepSeek 响应格式错误: {data}")
                    raise KeyError("Invalid response structure: no choices")
                
                reply = data["choices"][0].get("message", {}).get("content", "").strip()
                
                if not reply:
                    raise ValueError("API 返回空回复")
                
                logger.info(f"✓ DeepSeek 生成成功 ({len(reply)} 字符)")
                return reply
                
        except httpx.TimeoutException:
            logger.error("❌ DeepSeek 超时")
            raise ValueError("API 请求超时，请稍后重试")
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ DeepSeek HTTP 错误 {e.response.status_code}: {e.response.text}")
            raise ValueError(f"API 错误 ({e.response.status_code}): {e.response.text[:200]}")
        except httpx.HTTPError as e:
            logger.error(f"❌ DeepSeek 网络错误: {str(e)}")
            raise ValueError(f"网络错误: {str(e)}")
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"❌ DeepSeek 响应解析失败: {type(e).__name__}: {str(e)}")
            raise ValueError(f"服务器响应格式错误: {str(e)}")

    async def generate_stream(
        self,
        message: str,
        context: str = "",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """DeepSeek 真正的 SSE 流式生成（OpenAI 兼容格式）"""
        if not self.is_available():
            raise ValueError("DeepSeek API 密钥未配置")

        system_prompt = get_dynamic_system_prompt()
        if context:
            system_prompt += f"\n参考背景信息:\n{context}"

        msgs = [{"role": "system", "content": system_prompt}]
        msgs.extend(_get_conversation_history(limit=5))
        msgs.append({"role": "user", "content": message})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                async with client.stream("POST", self.api_base, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            obj = json.loads(data_str)
                            delta = obj["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
        except Exception as e:
            logger.error(f"❌ DeepSeek stream 错误: {e}")
            raise ValueError(f"DeepSeek 流式生成失败: {e}")


class ClaudeModel(BaseAPIModel):
    """Claude 模型支持 (如果有 API 密钥)"""
    
    def __init__(self, api_key: str = None, model_name: str = "claude-3-sonnet-20240229"):
        super().__init__(model_name)
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY", "")
        self.api_base = "https://api.anthropic.com/v1/messages"
        self.timeout = 30
    
    def is_available(self) -> bool:
        return bool(self.api_key)
    
    def get_info(self) -> dict:
        return {
            "name": "Claude",
            "model": self.model_name,
            "provider": "anthropic",
            "available": self.is_available(),
            "speed": "快速 (3-7秒)"
        }
    
    async def generate(
        self, 
        message: str, 
        context: str = "", 
        temperature: float = 0.7, 
        max_tokens: int = 512
    ) -> str:
        """通过 Claude API 生成回复"""
        if not self.is_available():
            raise ValueError("Claude API 密钥未配置")
        
        full_message = message
        if context:
            full_message = f"背景信息:\n{context}\n\n用户消息:\n{message}"
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        # 构建多轮消息（含历史）
        history = _get_conversation_history(limit=5)
        claude_msgs = []
        for m in history:
            claude_msgs.append({"role": m["role"], "content": m["content"]})
        claude_msgs.append({"role": "user", "content": full_message})

        payload = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "system": get_dynamic_system_prompt() + "请用中文回复。",
            "messages": claude_msgs
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.debug(f"📤 发送请求到 Claude: {self.api_base}")
                response = await client.post(self.api_base, json=payload, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                
                # 检查响应格式
                if "content" not in data or not data["content"]:
                    logger.error(f"❌ Claude 响应格式错误: {data}")
                    raise KeyError("Invalid response structure: no content")
                
                reply = data["content"][0].get("text", "").strip()
                
                if not reply:
                    logger.error(f"❌ Claude 返回空内容")
                    raise ValueError("API 返回空回复")
                
                logger.info(f"✓ Claude 生成成功 ({len(reply)} 字符)")
                return reply
                
        except httpx.TimeoutException:
            logger.error("❌ Claude 超时（30秒内无响应）")
            raise ValueError("API 请求超时，请稍后重试")
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Claude HTTP 错误 {e.response.status_code}: {e.response.text}")
            raise ValueError(f"API 错误 ({e.response.status_code}): {e.response.text[:200]}")
        except httpx.HTTPError as e:
            logger.error(f"❌ Claude 网络错误: {str(e)}")
            raise ValueError(f"网络错误: {str(e)}")
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"❌ Claude 响应解析失败: {type(e).__name__}: {str(e)}")
            raise ValueError(f"服务器响应格式错误: {str(e)}")


class OllamaModel(BaseAPIModel):
    """本地 Ollama 模型支持"""
    
    def __init__(self, model_name: str = "qwen3:4b", api_url: str = None):
        super().__init__(model_name)
        self.api_url = api_url or os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
        self.timeout = 180  # 本地可能更慢
    
    def is_available(self) -> bool:
        """检查 Ollama 服务是否运行"""
        try:
            import httpx
            response = httpx.get(
                self.api_url.replace("/api/generate", "/api/tags"),
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def get_info(self) -> dict:
        return {
            "name": "Ollama (本地)",
            "model": self.model_name,
            "provider": "local",
            "available": self.is_available(),
            "speed": "取决于硬件 (10-60秒)"
        }
    
    async def generate(
        self, 
        message: str, 
        context: str = "", 
        temperature: float = 0.7, 
        max_tokens: int = 512
    ) -> str:
        """通过 Ollama 生成回复"""
        if not self.is_available():
            raise ValueError("Ollama 服务未运行或不可达")

        system_prompt = get_dynamic_system_prompt()
        if context:
            system_prompt += f"\n背景信息:\n{context}"
        
        full_prompt = f"{system_prompt}\n\n用户: {message}\n\n回复:"
        
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "temperature": temperature,
            "num_predict": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                
                data = response.json()
                reply = data.get("response", "").strip()
                
                if not reply:
                    raise ValueError("Ollama 返回空回复")
                
                logger.info(f"✓ Ollama 生成成功 ({len(reply)} 字符)")
                return reply
                
        except httpx.TimeoutException:
            logger.error("❌ Ollama 超时")
            raise ValueError("本地模型生成超时，请稍后重试")
        except httpx.HTTPError as e:
            logger.error(f"❌ Ollama 错误: {str(e)}")
            raise ValueError(f"Ollama 错误: {str(e)}")
        except (json.JSONDecodeError, KeyError):
            logger.error("❌ Ollama 返回数据格式错误")
            raise ValueError("本地模型响应格式错误")


class ModelManager:
    """模型管理器 - 统一管理所有可用模型"""
    
    def __init__(self):
        self.models = {}
        self._initialize_models()
    
    def _initialize_models(self):
        """初始化所有可用模型"""
        # OpenAI 模型
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            self.models["gpt-3.5-turbo"] = OpenAIModel(openai_key, "gpt-3.5-turbo")
            self.models["gpt-4-turbo"] = OpenAIModel(openai_key, "gpt-4-turbo")
            logger.info("✓ OpenAI 模型已加载")
        
        # DeepSeek 模型
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
        if deepseek_key:
            self.models["deepseek-chat"] = DeepSeekModel(deepseek_key)
            logger.info("✓ DeepSeek 模型已加载")
        
        # Claude 模型
        claude_key = os.getenv("CLAUDE_API_KEY", "")
        if claude_key:
            self.models["claude-3-sonnet"] = ClaudeModel(claude_key)
            logger.info("✓ Claude 模型已加载")
        
        # Ollama 模型 (始终可用)
        ollama_model = os.getenv("OLLAMA_MODEL", "qwen:4b")
        self.models["ollama"] = OllamaModel(ollama_model)
        logger.info(f"✓ Ollama 模型已加载 ({ollama_model})")
    
    def get_available_models(self) -> List[dict]:
        """获取所有可用模型列表"""
        available = []
        for name, model in self.models.items():
            if model.is_available():
                available.append({
                    "id": name,
                    "info": model.get_info()
                })
        return available
    
    def get_model(self, model_name: str = None) -> BaseAPIModel:
        """获取指定模型，如果不存在则返回默认模型"""
        if model_name and model_name in self.models:
            return self.models[model_name]
        
        # 返回第一个可用的模型
        for model in self.models.values():
            if model.is_available():
                return model
        
        raise ValueError("没有可用的模型")
    
    def get_model_info(self, model_name: str = None) -> dict:
        """获取模型信息"""
        model = self.get_model(model_name)
        return model.get_info()
    
    async def generate(
        self,
        message: str,
        model_name: str = None,
        context: str = "",
        temperature: float = 0.7,
        max_tokens: int = 512
    ) -> str:
        """使用指定模型生成回复"""
        model = self.get_model(model_name)
        return await model.generate(message, context, temperature, max_tokens)

    async def generate_stream(
        self,
        message: str,
        model_name: str = None,
        context: str = "",
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> AsyncIterator[str]:
        """使用指定模型流式生成回复"""
        model = self.get_model(model_name)
        async for chunk in model.generate_stream(message, context, temperature, max_tokens):
            yield chunk


# 创建全局模型管理器实例
model_manager = ModelManager()
