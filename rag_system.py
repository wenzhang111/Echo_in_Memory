"""
向量检索系统 (RAG) - 聊天记忆搜索和上下文检索
"""
import os
import time
import numpy as np
from typing import List, Dict, Tuple, Optional
import logging
import sys
from pathlib import Path

# 添加父目录到路径以导入config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    EMBEDDING_MODEL, EMBEDDING_DIMENSION, 
    MAX_RETRIEVED_CONVERSATIONS, SIMILARITY_THRESHOLD,
    EMBEDDINGS_DIR, HF_ENDPOINT, EMBEDDING_LOAD_RETRY_SECONDS
)
from database import db

logger = logging.getLogger(__name__)


class VectorStore:
    """向量存储和相似度搜索"""
    
    def __init__(self):
        # 延迟加载中文embedding模型（轻量级）
        self.model = None
        self._loading = False
        self._loaded = False
        self._last_load_failed_at = 0.0
        # 不在这里调用 _load_model，避免模块初始化时的网络请求

        # 规范化并注入镜像端点，避免环境变量里包含空格/尾斜杠导致URL异常
        if HF_ENDPOINT:
            normalized = HF_ENDPOINT.strip().rstrip("/")
            os.environ["HF_ENDPOINT"] = normalized

    def _can_retry_load(self) -> bool:
        if self._last_load_failed_at <= 0:
            return True
        return (time.time() - self._last_load_failed_at) >= max(0, EMBEDDING_LOAD_RETRY_SECONDS)
    
    def _load_model(self):
        """延迟加载模型"""
        if self._loading:
            return
        if not self._can_retry_load():
            return

        self._loading = True
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            self._loaded = True
            self._last_load_failed_at = 0.0
            logger.info(f"✓ 嵌入模型加载完成: {EMBEDDING_MODEL}")
        except Exception as e:
            logger.warning(f"无法加载Sentence-Transformers模型，使用备用方案: {e}")
            self.model = None
            self._last_load_failed_at = time.time()
        finally:
            self._loading = False
    
    def preload(self):
        """在启动时主动预加载模型，避免首次聊天延迟"""
        if not self._loaded and self.model is None:
            logger.info(f"🔄 预加载嵌入模型: {EMBEDDING_MODEL} ...")
            self._load_model()
    
    def encode(self, text: str) -> np.ndarray:
        """将文本编码为向量"""
        if self.model is None:
            self._load_model()
        
        if self.model is None:
            # 备用：简单的哈希编码（不推荐，仅作为演示）
            return self._simple_hash_encoding(text)
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.astype(np.float32)
    
    def _simple_hash_encoding(self, text: str) -> np.ndarray:
        """简单的哈希编码作为备用"""
        np.random.seed(hash(text) % (2**32))
        return np.random.randn(EMBEDDING_DIMENSION).astype(np.float32)
    
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """批量编码文本"""
        if self.model is None:
            return np.array([self._simple_hash_encoding(text) for text in texts])
        
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.astype(np.float32)
    
    @staticmethod
    def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(vec1, vec2) / (norm1 * norm2))


class ConversationRAG:
    """对话检索增强生成系统"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.embedding_cache = {}  # 缓存已编码的文本
    
    def search_relevant_conversations(
        self,
        query: str,
        top_k: int = MAX_RETRIEVED_CONVERSATIONS,
        min_similarity: float = SIMILARITY_THRESHOLD
    ) -> List[Dict]:
        """
        根据查询找到最相关的历史对话
        优化版：先用 SQL LIKE 预筛选候选集，再向量精排
        避免对全量数据做 embedding 编码
        """
        # 1) 提取查询关键词，做 SQL 文本预筛选（毫秒级）
        candidates = []
        try:
            import jieba
            keywords = [w for w in jieba.cut(query) if len(w) > 1][:5]
        except Exception:
            keywords = [query]

        for kw in keywords:
            found = db.search_conversation_pairs_text(kw, limit=30)
            for item in found:
                if item['id'] not in {c['id'] for c in candidates}:
                    candidates.append(item)
            if len(candidates) >= 60:
                break

        # 补充最近的对话（保证时效性）
        recent = db.get_conversation_pairs(limit=10)
        for r in recent:
            if r['id'] not in {c['id'] for c in candidates}:
                candidates.append(r)

        if not candidates:
            logger.warning("数据库中没有对话记录")
            return []

        # 2) 只对候选集做向量编码 + 精排
        query_embedding = self.vector_store.encode(query)
        similarities = []

        for pair in candidates:
            user_msg = pair['user_message']
            ai_resp = pair['ai_response']

            user_embedding = self.vector_store.encode(user_msg)
            ai_embedding = self.vector_store.encode(ai_resp)

            user_sim = self.vector_store.cosine_similarity(query_embedding, user_embedding)
            ai_sim = self.vector_store.cosine_similarity(query_embedding, ai_embedding)
            max_sim = max(user_sim, ai_sim)

            if max_sim >= min_similarity:
                similarities.append({
                    'pair': pair,
                    'similarity': max_sim,
                })

        similarities.sort(key=lambda x: x['similarity'], reverse=True)

        results = []
        for item in similarities[:top_k]:
            results.append({
                'user_message': item['pair']['user_message'],
                'ai_response': item['pair']['ai_response'],
                'timestamp': item['pair']['timestamp'],
                'similarity_score': round(item['similarity'], 3),
                'quality_score': item['pair']['quality_score']
            })

        logger.info(f"检索到 {len(results)} 条相关对话 (候选 {len(candidates)}, 查询: {query[:30]}...)")
        return results
    
    def build_context_from_search(self, search_results: List[Dict]) -> str:
        """
        从搜索结果构建上下文提示词
        """
        if not search_results:
            return ""
        
        context = "## 相关的历史对话 ##\n"
        for i, result in enumerate(search_results, 1):
            context += f"\n{i}. 相似度: {result['similarity_score']}\n"
            context += f"   用户: {result['user_message'][:100]}\n"
            context += f"   我: {result['ai_response'][:100]}\n"
        
        return context
    
    def get_chunked_conversation_history(self, chunk_size: int = 5) -> str:
        """
        获取最近的对话历史并分块
        用于填充模型的上下文窗口
        """
        recent_pairs = db.get_recent_conversations(num_pairs=chunk_size * 2)
        
        if not recent_pairs:
            return ""
        
        history = "## 最近的对话 ##\n"
        for user_msg, ai_resp in recent_pairs:
            history += f"用户: {user_msg}\n"
            history += f"我: {ai_resp}\n\n"
        
        return history


class MemoryExtractor:
    """从对话中提取关键信息和长期记忆"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
    
    def extract_key_topics(self, conversations: List[Tuple[str, str]], top_n: int = 30) -> Dict[str, int]:
        """
        提取对话中的关键话题
        返回话题和出现频率
        """
        from collections import Counter

        # 兼容旧调用：允许传入 List[str]
        normalized_conversations: List[Tuple[str, str]] = []
        for item in conversations or []:
            if isinstance(item, tuple) and len(item) >= 2:
                normalized_conversations.append((str(item[0]), str(item[1])))
            elif isinstance(item, str):
                normalized_conversations.append((item, ""))
        
        # 中文分词
        try:
            import jieba
            jieba.initialize()
        except ImportError:
            logger.warning("jieba未安装，使用简单词分割")
            jieba = None
        
        all_words = []
        
        for user_msg, ai_resp in normalized_conversations:
            text = user_msg + ai_resp
            
            if jieba:
                words = jieba.cut(text, cut_all=False)
                # 过滤停用词（长度>1的词）
                words = [w for w in words if len(w) > 1 and not self._is_stopword(w)]
            else:
                # 简化的词分割
                words = [w for w in text.split() if len(w) > 1]
            
            all_words.extend(words)
        
        topic_freq = Counter(all_words)
        if top_n <= 0:
            top_n = 30
        return dict(topic_freq.most_common(top_n))
    
    @staticmethod
    def _is_stopword(word: str) -> bool:
        """判断是否是停用词"""
        stopwords = {'的', '了', '在', '是', '我', '你', '他', '她', '和', '与', '等', '哈', '呢', '啊'}
        return word in stopwords
    
    def extract_personality_patterns(self, conversations: List[Tuple[str, str]]) -> Dict:
        """
        从AI回复中提取性格特征
        """
        ai_responses = [ai_resp for _, ai_resp in conversations]
        full_text = ''.join(ai_responses)
        
        patterns = {
            '常用词': self._extract_frequent_words(full_text),
            '笑声': self._count_laughs(full_text),
            '情感词': self._extract_emotion_words(full_text),
            '平均回复长度': len(full_text) // len(ai_responses) if ai_responses else 0,
            '撒娇频率': self._count_pattern(full_text, r'呢~|不要|嘛|呀'),
        }
        
        return patterns
    
    @staticmethod
    def _extract_frequent_words(text: str, top_n: int = 20) -> List[str]:
        """提取高频词"""
        try:
            import jieba
            words = jieba.cut(text, cut_all=False)
            from collections import Counter
            word_freq = Counter(w for w in words if len(w) > 1)
            return [word for word, _ in word_freq.most_common(top_n)]
        except:
            return []
    
    @staticmethod
    def _count_laughs(text: str) -> int:
        """统计笑声出现次数"""
        laugh_patterns = ['哈哈', '哈', '嘻嘻', '呵呵', '嘿嘿', '😄', '😂']
        count = 0
        for pattern in laugh_patterns:
            count += text.count(pattern)
        return count
    
    @staticmethod
    def _extract_emotion_words(text: str) -> Dict[str, int]:
        """提取情感词"""
        positive = {'喜欢', '开心', '开心', '高兴', '爱', '棒', '好'}
        negative = {'难过', '伤心', '生气', '讨厌', '害怕'}
        
        pos_count = sum(text.count(word) for word in positive)
        neg_count = sum(text.count(word) for word in negative)
        
        return {'positive': pos_count, 'negative': neg_count}
    
    @staticmethod
    def _count_pattern(text: str, pattern: str) -> int:
        """计算匹配模式的次数"""
        import re
        return len(re.findall(pattern, text))


# 全局实例
rag_system = ConversationRAG()
memory_extractor = MemoryExtractor(rag_system.vector_store)
