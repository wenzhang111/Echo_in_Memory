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
    
    def check_connection(self) -> bool:
        """检查Ollama服务连接"""
        try:
            response = requests.get(
                f"{self.api_url.replace('/api/generate', '')}/api/tags",
                timeout=5
            )
            if response.status_code == 200:
                logger.info("✓ Ollama服务已连接")
                return True
            else:
                logger.warning(f"✗ Ollama 返回状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"✗ 无法连接到Ollama: {e}")
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
                logger.error(f"   请运行: ollama pull {self.model}")
                logger.error(f"   或使用其他模型: ollama pull qwen2:1b")
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

    # ──────────────────────────────────────────
    # /api/chat 结构化多轮对话接口
    # ──────────────────────────────────────────
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = OLLAMA_TEMPERATURE,
        top_p: float = OLLAMA_TOP_P,
        top_k: int = GENERATION_TOP_K,
        num_predict: int = GENERATION_NUM_PREDICT,
    ) -> Optional[str]:
        """
        使用 /api/chat 进行结构化多轮对话（非流式）。
        messages: [{"role": "system"/"user"/"assistant", "content": "..."}]
        """
        chat_url = self.api_url.replace('/api/generate', '/api/chat')
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "num_predict": num_predict,
                "repeat_penalty": GENERATION_REPEAT_PENALTY,
            },
        }
        if OLLAMA_FORCE_GPU:
            payload["options"]["num_gpu"] = OLLAMA_NUM_GPU

        try:
            response = requests.post(chat_url, json=payload, timeout=self.timeout)
            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', '').strip()
            else:
                logger.error(f"Ollama /api/chat 错误: {response.status_code} - {response.text[:200]}")
                return None
        except requests.Timeout:
            logger.error(f"Chat 请求超时 ({self.timeout}秒)")
            return None
        except Exception as e:
            logger.error(f"Chat 生成失败: {e}")
            return None

    def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = OLLAMA_TEMPERATURE,
        top_p: float = OLLAMA_TOP_P,
        top_k: int = GENERATION_TOP_K,
        num_predict: int = GENERATION_NUM_PREDICT,
    ) -> Iterator[str]:
        """
        使用 /api/chat 进行流式多轮对话。
        """
        chat_url = self.api_url.replace('/api/generate', '/api/chat')
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "num_predict": num_predict,
                "repeat_penalty": GENERATION_REPEAT_PENALTY,
            },
        }
        if OLLAMA_FORCE_GPU:
            payload["options"]["num_gpu"] = OLLAMA_NUM_GPU

        try:
            response = requests.post(
                chat_url, json=payload, timeout=self.timeout, stream=True
            )
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            chunk = data.get('message', {}).get('content', '')
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            continue
            elif response.status_code == 404:
                logger.error(f"❌ 模型不存在或不支持 /api/chat: {self.model}")
            else:
                logger.error(f"Ollama chat stream 错误: {response.status_code}")
        except requests.Timeout:
            logger.error(f"Chat 流式请求超时 ({self.timeout}秒)")
        except Exception as e:
            logger.error(f"Chat 流式生成失败: {e}")


class ChatManager:
    """
    聊天管理器 (v2)
    使用 /api/chat 结构化多轮对话，集成：
    - context_engine: Token预算管理 + 结构化messages
    - emotion_tracker: 情绪曲线追踪
    - response_enhancer: 回复质量增强 + 意图动态调参
    """

    def __init__(self):
        self.ollama = OllamaClient()
        self.conversation_history = []

        try:
            if not self.ollama.check_connection():
                logger.warning("⚠️ Ollama连接失败，请确保Ollama服务正在运行")
        except Exception as e:
            logger.warning(f"⚠️ 无法检查Ollama连接: {str(e)}")

    # ──────────────────────────────────────────
    #  核心对话方法
    # ──────────────────────────────────────────
    def chat(
        self,
        user_input: str,
        use_memory: bool = True,
        stream: bool = False,
        **kwargs
    ) -> Optional[str]:
        """
        进行一次聊天交互（非流式）。
        自动使用意图动态调参 + 结构化messages + 回复增强。
        """
        if stream:
            return self.chat_stream(user_input, use_memory, **kwargs)

        # 1) 意图检测 → 动态生成参数
        intent_result = intent_classifier.detect(user_input)
        dynamic = response_enhancer.get_dynamic_params(intent_result.intent)
        # 合并：动态参数为基础，显式传入的 kwargs 覆盖
        gen_params = {
            'temperature': dynamic.get('temperature', OLLAMA_TEMPERATURE),
            'num_predict': dynamic.get('max_tokens', GENERATION_NUM_PREDICT),
            'top_p': dynamic.get('top_p', OLLAMA_TOP_P),
        }
        for k in ('temperature', 'num_predict', 'top_p', 'top_k'):
            if k in kwargs:
                gen_params[k] = kwargs[k]

        # 2) 构建结构化 messages → /api/chat
        if use_memory:
            messages = self._build_messages(user_input)
            raw_response = self.ollama.chat_completion(messages, **gen_params)
        else:
            raw_response = self.ollama.generate(user_input, **gen_params)

        if not raw_response:
            return None

        # 3) 回复增强管线
        enhanced = response_enhancer.enhance(raw_response)
        response = enhanced.text or raw_response
        if enhanced.was_cleaned:
            logger.info(f"🔧 回复已增强: {enhanced.cleaning_notes}")

        # 4) 记录情绪
        try:
            cid = self._get_active_id()
            emotion_tracker.record(user_input, character_id=cid)
        except Exception as e:
            logger.debug(f"情绪记录失败: {e}")

        # 5) 保存
        self._save_conversation_pair(user_input, response)
        return response

    def chat_stream(
        self,
        user_input: str,
        use_memory: bool = True,
        **kwargs
    ) -> Iterator[str]:
        """
        流式聊天交互。
        实时过滤 <think> 标签，完成后增强并保存。
        """
        # 意图动态调参
        intent_result = intent_classifier.detect(user_input)
        dynamic = response_enhancer.get_dynamic_params(intent_result.intent)
        gen_params = {
            'temperature': dynamic.get('temperature', OLLAMA_TEMPERATURE),
            'num_predict': dynamic.get('max_tokens', GENERATION_NUM_PREDICT),
            'top_p': dynamic.get('top_p', OLLAMA_TOP_P),
        }
        for k in ('temperature', 'num_predict', 'top_p', 'top_k'):
            if k in kwargs:
                gen_params[k] = kwargs[k]

        # 构建 messages
        if use_memory:
            messages = self._build_messages(user_input)
            raw_stream = self.ollama.chat_completion_stream(messages, **gen_params)
        else:
            raw_stream = self.ollama.generate_stream(user_input, **gen_params)

        # 流式过滤 <think> 标签
        stream_filter = response_enhancer.create_stream_filter()
        response_parts = []
        raw_parts = []
        for chunk in raw_stream:
            raw_parts.append(chunk)
            filtered = stream_filter(chunk)
            if filtered:
                response_parts.append(filtered)
                yield filtered

        # 流式结束后：增强完整文本用于存储
        if raw_parts:
            raw_full = ''.join(raw_parts)
            enhanced = response_enhancer.enhance(raw_full)
            # 记录情绪
            try:
                cid = self._get_active_id()
                emotion_tracker.record(user_input, character_id=cid)
            except Exception:
                pass
            self._save_conversation_pair(user_input, enhanced.text or raw_full)

    # ──────────────────────────────────────────
    #  构建结构化 messages
    # ──────────────────────────────────────────
    def _build_messages(self, user_input: str) -> List[Dict[str, str]]:
        """使用 context_engine 构建 Token 预算内的结构化 messages。"""
        # 系统提示词（角色设定 + 性格 + 记忆）
        system_prompt = memory_prompt_builder.build_system_prompt_with_memory()
        # 意图上下文
        intent_context = memory_manager.get_intent_context(user_input)
        # 情绪上下文
        cid = self._get_active_id()
        emotion_context = emotion_tracker.build_emotion_context(user_input, character_id=cid)

        # 近期对话历史 → 结构化 user/assistant 消息
        recent_pairs = db.get_recent_conversations(
            num_pairs=CONTEXT_WINDOW, character_id=cid
        )
        history: List[Dict[str, str]] = []
        for user_msg, ai_msg in reversed(recent_pairs):  # oldest first
            if user_msg:
                history.append({"role": "user", "content": user_msg})
            if ai_msg:
                history.append({"role": "assistant", "content": ai_msg})

        # RAG 语义检索
        rag_results = []
        try:
            rag_results = rag_system.search_relevant_conversations(user_input, top_k=3)
        except Exception:
            pass

        return context_engine.build_messages(
            system_prompt=system_prompt,
            intent_context=intent_context,
            emotion_context=emotion_context,
            conversation_history=history,
            rag_results=rag_results,
            user_input=user_input,
        )

    @staticmethod
    def _get_active_id() -> str:
        try:
            from character_manager import character_manager
            return character_manager.get_active_id()
        except Exception:
            return "default"
    
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
