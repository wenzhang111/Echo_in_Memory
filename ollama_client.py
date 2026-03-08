"""
Ollama客户端 - 与本地LLM集成
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import json
import logging
from typing import Optional, Iterator
from config import (
    OLLAMA_API_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_TEMPERATURE, OLLAMA_TOP_P,
    GENERATION_MAX_TOKENS, GENERATION_TOP_K, GENERATION_NUM_PREDICT, GENERATION_REPEAT_PENALTY,
    OLLAMA_FORCE_GPU, OLLAMA_NUM_GPU,
)

# 预加载必要的模块，避免函数内部动态导入问题
# (这些会在函数调用时被真正使用)
from memory_manager import memory_prompt_builder, memory_manager
from database import db
from rag_system import memory_extractor
from intent_classifier import intent_classifier

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama本地模型调用客户端"""
    
    def __init__(self, api_url: str = OLLAMA_API_URL, model: str = OLLAMA_MODEL):
        self.api_url = api_url
        self.model = model
        self.timeout = OLLAMA_TIMEOUT
        self._last_connection_ok: Optional[bool] = None
    
    def check_connection(self) -> bool:
        """检查Ollama服务连接"""
        try:
            response = requests.get(
                f"{self.api_url.replace('/api/generate', '')}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                if self._last_connection_ok is not True:
                    logger.info("✓ Ollama服务已连接")
                self._last_connection_ok = True
                return True
            else:
                if self._last_connection_ok is not False:
                    logger.warning(f"✗ Ollama 返回状态码: {response.status_code}")
                self._last_connection_ok = False
        except Exception as e:
            if self._last_connection_ok is not False:
                logger.error(f"✗ 无法连接到Ollama: {e}")
            self._last_connection_ok = False
            return False
        
        return False
    
    def get_available_models(self) -> list:
        """获取可用的模型列表"""
        try:
            response = requests.get(
                f"{self.api_url.replace('/api/generate', '')}/api/tags",
                timeout=10
            )
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [m['name'] for m in models]
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
        
        return []

    def _ensure_model_available(self) -> bool:
        """确保当前模型可用，不可用时自动切换到首个可用模型。"""
        models = self.get_available_models()
        if not models:
            logger.error("❌ 未检测到任何本地模型，请先运行: ollama pull <模型名>")
            return False

        if self.model in models:
            return True

        old_model = self.model
        self.model = models[0]
        logger.warning(f"⚠️ 配置模型不存在: {old_model}，已自动切换为: {self.model}")
        return True
    
    def generate(
        self,
        prompt: str,
        temperature: float = OLLAMA_TEMPERATURE,
        top_p: float = OLLAMA_TOP_P,
        top_k: int = GENERATION_TOP_K,
        num_predict: int = GENERATION_NUM_PREDICT,
        stream: bool = False
    ) -> Optional[str]:
        """
        生成回复（非流式）
        针对低端GPU优化：使用更少的生成token和更快的采样策略
        """
        # 快速检查 Ollama 连接（5秒超时）
        if not self.check_connection():
            logger.error("Ollama 服务未运行，无法生成回复")
            return None

        if not self._ensure_model_available():
            return None
            
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": stream,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "num_predict": num_predict,
                "repeat_penalty": GENERATION_REPEAT_PENALTY  # 降低重复
            }

            # 强制GPU模式：通过ollama options传递num_gpu，避免静默CPU回退
            if OLLAMA_FORCE_GPU:
                payload["options"] = {
                    "num_gpu": OLLAMA_NUM_GPU,
                }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            elif response.status_code == 404:
                logger.error(f"❌ 模型不存在: {self.model}")
                if self._ensure_model_available():
                    payload["model"] = self.model
                    retry_resp = requests.post(self.api_url, json=payload, timeout=self.timeout)
                    if retry_resp.status_code == 200:
                        return retry_resp.json().get('response', '').strip()
                logger.error("   请运行: ollama pull <模型名>")
                return None
            else:
                logger.error(f"Ollama API错误: {response.status_code}")
                return None
        
        except requests.Timeout:
            logger.error(f"请求超时 ({self.timeout}秒)")
            return None
        except Exception as e:
            logger.error(f"生成回复时出错: {e}")
            return None
    
    def generate_stream(
        self,
        prompt: str,
        temperature: float = OLLAMA_TEMPERATURE,
        top_p: float = OLLAMA_TOP_P,
        top_k: int = GENERATION_TOP_K,
        num_predict: int = GENERATION_NUM_PREDICT
    ) -> Iterator[str]:
        """
        流式生成回复
        实时返回生成的文本片段，低端GPU优化版本
        """
        try:
            if not self.check_connection():
                logger.error("Ollama 服务未运行，无法进行流式生成")
                return

            if not self._ensure_model_available():
                return

            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "num_predict": num_predict,
                "repeat_penalty": GENERATION_REPEAT_PENALTY
            }

            if OLLAMA_FORCE_GPU:
                payload["options"] = {
                    "num_gpu": OLLAMA_NUM_GPU,
                }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get('response', '')
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            continue
            elif response.status_code == 404:
                logger.error(f"❌ 模型不存在: {self.model}")
                if self._ensure_model_available():
                    payload["model"] = self.model
                    retry_resp = requests.post(self.api_url, json=payload, timeout=self.timeout, stream=True)
                    if retry_resp.status_code == 200:
                        for line in retry_resp.iter_lines():
                            if line:
                                try:
                                    data = json.loads(line)
                                    chunk = data.get('response', '')
                                    if chunk:
                                        yield chunk
                                except json.JSONDecodeError:
                                    continue
                        return
                logger.error("   请运行: ollama pull <模型名>")
            else:
                logger.error(f"Ollama API错误: {response.status_code} - {response.text[:200]}")
        
        except requests.Timeout:
            logger.error(f"流式生成请求超时 ({self.timeout}秒)")
        except Exception as e:
            logger.error(f"流式生成时出错: {e}")
    
    def generate_with_context(
        self,
        prompt: str,
        context: str = "",
        system_prefix: str = "",
        **kwargs
    ) -> Optional[str]:
        """
        带有上下文的生成
        """
        # 构建完整的输入
        full_prompt = ""
        
        if system_prefix:
            full_prompt += system_prefix + "\n"
        
        if context:
            full_prompt += context + "\n"
        
        full_prompt += prompt
        
        return self.generate(full_prompt, **kwargs)
    
    def generate_with_context_stream(
        self,
        prompt: str,
        context: str = "",
        system_prefix: str = "",
        **kwargs
    ) -> Iterator[str]:
        """
        带有上下文的流式生成
        """
        full_prompt = ""
        
        if system_prefix:
            full_prompt += system_prefix + "\n"
        
        if context:
            full_prompt += context + "\n"
        
        full_prompt += prompt
        
        yield from self.generate_stream(full_prompt, **kwargs)


class ChatManager:
    """
    聊天管理器
    整合Ollama、记忆系统和数据库
    """
    
    def __init__(self):
        self.ollama = OllamaClient()
        self.conversation_history = []
        
        # 检查Ollama连接（失败时仅警告，不影响模块初始化）
        try:
            if not self.ollama.check_connection():
                logger.warning("⚠️ Ollama连接失败，请确保Ollama服务正在运行")
        except Exception as e:
            logger.warning(f"⚠️ 无法检查Ollama连接: {str(e)}")
    
    def chat(
        self,
        user_input: str,
        use_memory: bool = True,
        stream: bool = False,
        **kwargs
    ) -> Optional[str]:
        """
        进行一次聊天交互
        
        Args:
            user_input: 用户输入
            use_memory: 是否使用记忆系统
            stream: 是否使用流式生成
        """
        if stream:
            return self.chat_stream(user_input, use_memory, **kwargs)
        
        # 构建带记忆的上下文
        if use_memory:
            full_prompt = memory_prompt_builder.build_full_context(user_input)
        else:
            full_prompt = user_input
        
        # 调用Ollama生成回复
        response = self.ollama.generate(full_prompt, **kwargs)
        
        if response:
            # 存储对话对到数据库
            self._save_conversation_pair(user_input, response)
        
        return response
    
    def chat_stream(
        self,
        user_input: str,
        use_memory: bool = True,
        **kwargs
    ) -> Iterator[str]:
        """
        流式聊天交互
        """
        # 构建带记忆的上下文
        if use_memory:
            full_prompt = memory_prompt_builder.build_full_context(user_input)
        else:
            full_prompt = user_input
        
        # 流式生成
        response_parts = []
        for chunk in self.ollama.generate_stream(full_prompt, **kwargs):
            response_parts.append(chunk)
            yield chunk
        
        # 保存完整的对话
        if response_parts:
            full_response = ''.join(response_parts)
            self._save_conversation_pair(user_input, full_response)
    
    def _save_conversation_pair(self, user_input: str, ai_response: str):
        """保存对话对到数据库（关联当前角色）"""
        try:
            from character_manager import character_manager
            active_id = character_manager.get_active_id()
            
            # 简单的情感分析
            sentiment = self._analyze_sentiment(user_input)
            intent_result = intent_classifier.detect(user_input)
            context_tags = [
                f"intent:{intent_result.intent}",
                f"intent_conf:{intent_result.confidence:.2f}",
            ]
            
            db.add_conversation_pair(
                user_message=user_input,
                ai_response=ai_response,
                user_sentiment=sentiment,
                context_tags=context_tags,
                quality_score=self._estimate_quality(user_input, ai_response),
                character_id=active_id
            )
            
            # 同时保存到角色聊天记录文件
            character_manager.add_chat_message(active_id, user_input, ai_response)
            
            # 检查是否需要提取长期记忆
            memory_manager.extract_and_store_memories()
        
        except Exception as e:
            logger.error(f"保存对话时出错: {e}")
    
    @staticmethod
    def _analyze_sentiment(text: str) -> str:
        """简单的情感分析"""
        positive_words = {'好', '开心', '高兴', '爱', '棒', '妙'}
        negative_words = {'难受', '伤心', '讨厌', '害怕', '烦'}
        
        pos_count = sum(text.count(word) for word in positive_words)
        neg_count = sum(text.count(word) for word in negative_words)
        
        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        return 'neutral'
    
    @staticmethod
    def _estimate_quality(user_input: str, ai_response: str) -> float:
        """估计对话质量"""
        # 简单的启发式评分
        quality = 0.5
        
        # 回复长度
        if len(ai_response) > 20:
            quality += 0.15
        if len(ai_response) > 50:
            quality += 0.1
        
        # 是否包含问题（互动性）
        if '?' in ai_response or '？' in ai_response:
            quality += 0.1
        
        # 是否有表情
        if any(emoji in ai_response for emoji in ['😄', '😂', '💕', '🥰', '😍']):
            quality += 0.1
        
        return min(1.0, quality)


# 全局实例
chat_manager = ChatManager()
