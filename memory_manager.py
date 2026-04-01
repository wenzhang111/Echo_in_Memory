"""
长期记忆管理 - 实现真正的"记住"能力
"""
import logging
import re
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import db
from rag_system import memory_extractor, rag_system
from intent_classifier import intent_classifier
from config import (
    MEMORY_EXTRACTION_FREQUENCY, 
    MAX_LONG_TERM_MEMORIES,
    PERSONALITY_UPDATE_FREQUENCY
)

logger = logging.getLogger(__name__)


class LongTermMemoryManager:
    """
    长期记忆管理器
    负责从对话中提取、存储和利用关键信息
    """
    
    def __init__(self):
        self.memory_categories = {
            'personality': '性格与习惯',
            'relationship': '关系与感情',
            'experience': '共同经历',
            'preference': '喜好与兴趣',
            'important_info': '重要信息'
        }
        self.time_markers = [
            '今天', '昨天', '昨晚', '前天', '最近', '刚刚', '早上', '中午', '晚上',
            '上周', '这周', '下周', '上个月', '这个月', '明天', '后天'
        ]
        self.relationship_aliases = [
            '宝宝', '宝子', '宝贝', '亲爱的', '老公', '老婆', '乖乖', '小可爱'
        ]
        self.emotion_need_words = [
            '难受', '不开心', '烦', '崩溃', '焦虑', '累', '委屈', '想哭', '失眠', '压力'
        ]
        self.commitment_words = [
            '喜欢你', '爱你', '只想跟你', '只跟你', '只要你', '不想失去你'
        ]

    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ''
        text = str(text).replace('\u3000', ' ').strip()
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('。。。', '...')
        return text

    @staticmethod
    def _normalize_key(text: str, max_len: int = 24) -> str:
        text = re.sub(r'[^\w\u4e00-\u9fff]+', '_', text)
        text = re.sub(r'_+', '_', text).strip('_')
        return text[:max_len] if text else 'unknown'

    @staticmethod
    def _is_substantial_text(text: str) -> bool:
        if not text:
            return False
        stripped = text.strip()
        if len(stripped) < 3:
            return False
        if stripped.startswith('[') and stripped.endswith(']') and len(stripped) < 16:
            return False
        return True

    @staticmethod
    def _should_skip_topic(topic: str) -> bool:
        if not topic or len(topic) < 2 or len(topic) > 12:
            return True
        if re.fullmatch(r'[0-9]+', topic):
            return True
        stop = {
            '这个', '那个', '真的', '感觉', '然后', '就是', '你们', '我们', '自己', '时候',
            '因为', '可以', '喜欢', '特别', '还有', '已经', '现在', '今天', '昨天', '明天',
            '没有', '不是', '还是', '如果', '但是', '而且', '那种', '什么', '就是说',
            '晚安', '漂亮', '恭喜', 'qaq', 'QAQ'
        }
        if topic in stop:
            return True
        if topic.endswith(('了', '的', '吗', '吧', '呢', '啊')):
            return True
        if len(set(topic)) == 1 and len(topic) >= 2:
            return True
        return False

    @staticmethod
    def _should_skip_preference_value(value: str) -> bool:
        if not value or len(value) < 2:
            return True
        stop_values = {'要爱', '那个', '这个', '这样', '那样', '一下', '一下子', '一些', '一点'}
        if value in stop_values:
            return True
        bad_prefix = ('你', '我', '他', '她', '这', '那', '一个', '一种', '一下')
        if value.startswith(bad_prefix):
            return True
        if re.search(r'[\?？!！。,.，\n]', value):
            return True
        return False

    def _deduplicate_pairs(self, pairs: List[Dict]) -> List[Dict]:
        deduped: List[Dict] = []
        seen: Set[Tuple[str, str]] = set()

        for pair in pairs:
            user_msg = self._clean_text(pair.get('user_message', ''))
            ai_msg = self._clean_text(pair.get('ai_response', ''))
            if not self._is_substantial_text(user_msg) or not self._is_substantial_text(ai_msg):
                continue

            key = (user_msg, ai_msg)
            if key in seen:
                continue

            seen.add(key)
            normalized = dict(pair)
            normalized['user_message'] = user_msg
            normalized['ai_response'] = ai_msg
            deduped.append(normalized)

        return deduped
    
    def extract_and_store_memories(self, force: bool = False, character_id: Optional[str] = None, limit: Optional[int] = None):
        """
        定期从对话中提取记忆
        - force=True: 忽略频率阈值，适合导入后全量提取
        - character_id: 可选角色过滤
        """
        total_conversations = db.get_conversation_count(character_id=character_id)
        if total_conversations <= 0:
            return False

        if not force and total_conversations % MEMORY_EXTRACTION_FREQUENCY != 0:
            return False

        if force:
            db.clear_long_term_memories('relationship')
            db.clear_long_term_memories('preference')
            db.clear_long_term_memories('experience')
            db.clear_long_term_memories('important_info')

        extraction_limit = limit or (min(2000, max(200, MEMORY_EXTRACTION_FREQUENCY * 4)) if force else MEMORY_EXTRACTION_FREQUENCY)
        recent_pairs = db.get_conversation_pairs(
            limit=min(total_conversations, extraction_limit),
            character_id=character_id
        )
        recent_pairs = list(reversed(recent_pairs))
        recent_pairs = self._deduplicate_pairs(recent_pairs)

        if not recent_pairs:
            return False

        logger.info(
            f"开始提取长期记忆 (总对话: {total_conversations}, 使用样本: {len(recent_pairs)}, "
            f"force={force}, character_id={character_id or 'all'})"
        )

        self._extract_and_store_topics(recent_pairs)
        self._extract_relationship_info(recent_pairs)
        self._extract_shared_experiences(recent_pairs)
        self._extract_preferences(recent_pairs)

        if force or total_conversations % PERSONALITY_UPDATE_FREQUENCY == 0:
            self._update_personality_profile(recent_pairs)

        logger.info("长期记忆提取完成")
        return True
    
    def _extract_and_store_topics(self, pairs: List[Dict]):
        """提取并存储话题（仅作为辅助信息，不直接作为用户偏好）"""
        conversations = [(p['user_message'], '') for p in pairs]
        topics = memory_extractor.extract_key_topics(conversations)

        max_frequency = max(topics.values()) if topics else 1
        saved = 0
        for topic, frequency in topics.items():
            if self._should_skip_topic(topic):
                continue
            if frequency < 2:
                continue

            normalized_topic = self._normalize_key(topic, 20)
            importance = min(0.9, 0.45 + (frequency / max_frequency) * 0.35)
            db.add_long_term_memory(
                category='important_info',
                key=f'topic_{normalized_topic}',
                content=f'近期高频话题：{topic}',
                importance_score=min(0.72, importance)
            )
            saved += 1
            if saved >= 8:
                break
    
    def _extract_relationship_info(self, pairs: List[Dict]):
        """
        从对话中提取关系信息
        例如: 用户对AI的称呼、亲密度、需求等
        """
        all_user_text = '\n'.join([p['user_message'] for p in pairs])
        all_text = '\n'.join([p['user_message'] + '\n' + p['ai_response'] for p in pairs])

        alias_hits = {alias: all_text.count(alias) for alias in self.relationship_aliases if all_text.count(alias) > 0}
        if alias_hits:
            top_alias = sorted(alias_hits.items(), key=lambda x: -x[1])[:3]
            alias_desc = '、'.join([a for a, _ in top_alias])
            db.add_long_term_memory(
                category='relationship',
                key='relationship_closeness',
                content=f'你们经常使用亲密称呼（如：{alias_desc}）',
                importance_score=0.88
            )

        emotional_need_count = sum(all_user_text.count(word) for word in self.emotion_need_words)
        if emotional_need_count >= 2:
            db.add_long_term_memory(
                category='relationship',
                key='relationship_emotional_support',
                content='你在压力或情绪低落时，常会希望得到安慰和陪伴',
                importance_score=0.92
            )

        commitment_count = sum(all_text.count(word) for word in self.commitment_words)
        if commitment_count >= 1:
            db.add_long_term_memory(
                category='relationship',
                key='relationship_commitment',
                content='你对关系有较强的专一和确认需求（在意“只跟彼此”）',
                importance_score=0.9
            )
    
    def _extract_shared_experiences(self, pairs: List[Dict]):
        """
        提取共同经历
        """
        timeline_events: List[Tuple[str, str]] = []
        seen_event_keys: Set[str] = set()

        for pair in pairs[-300:]:
            user_msg = self._clean_text(pair['user_message'])
            if not self._is_substantial_text(user_msg):
                continue

            marker = next((m for m in self.time_markers if m in user_msg), None)
            if not marker:
                continue

            question_hints = ['什么', '怎么', '吗', '嘛', '呢', '为啥', '为什么', '哪', '几']
            if '?' in user_msg or '？' in user_msg:
                continue
            if any(q in user_msg for q in question_hints) and len(user_msg) <= 22:
                continue

            event_text = re.sub(r'[\!！\?？]+$', '', user_msg).strip()
            event_key = f"{marker}_{self._normalize_key(event_text, 28)}"
            if event_key in seen_event_keys:
                continue

            seen_event_keys.add(event_key)
            timeline_events.append((marker, event_text[:80]))

        for marker, event_text in timeline_events[-12:]:
            db.add_long_term_memory(
                category='experience',
                key=f"timeline_{marker}_{self._normalize_key(event_text, 24)}",
                content=f"{marker}你提到：{event_text}",
                importance_score=0.74
            )
    
    def _extract_preferences(self, pairs: List[Dict]):
        """
        提取用户偏好和兴趣
        """
        user_messages = [p['user_message'] for p in pairs] + [p['ai_response'] for p in pairs]
        extracted: Dict[str, Tuple[str, float]] = {}

        patterns = [
            (re.compile(r'我(?:比较|更)?喜欢(?P<v>[^，。！？\n]{1,18})'), 'like', 0.86),
            (re.compile(r'我最喜欢(?P<v>[^，。！？\n]{1,18})'), 'like', 0.9),
            (re.compile(r'我想(?P<v>[^，。！？\n]{2,18})'), 'want', 0.74),
            (re.compile(r'我不喜欢(?P<v>[^，。！？\n]{1,18})'), 'dislike', 0.86),
            (re.compile(r'我不想(?P<v>[^，。！？\n]{1,18})'), 'avoid', 0.8),
            (re.compile(r'我讨厌(?P<v>[^，。！？\n]{1,18})'), 'dislike', 0.9),
        ]

        for msg in user_messages:
            msg = self._clean_text(msg)
            for pattern, pref_type, score in patterns:
                for match in pattern.finditer(msg):
                    value = self._clean_text(match.group('v'))
                    if pref_type in {'want', 'avoid'} and value.startswith('要') and len(value) > 2:
                        value = value[1:]
                    if self._should_skip_preference_value(value):
                        continue

                    normalized = self._normalize_key(value, 20)
                    pref_key = f"{pref_type}_{normalized}"

                    if pref_type == 'like':
                        content = f"你明确说过喜欢「{value}」"
                    elif pref_type == 'want':
                        content = f"你提到想要/想做「{value}」"
                    elif pref_type == 'avoid':
                        content = f"你提到不太想「{value}」"
                    else:
                        content = f"你明确表达过不喜欢「{value}」"

                    extracted[pref_key] = (content, score)

        saved = 0
        for pref_key, (content, score) in extracted.items():
            db.add_long_term_memory(
                category='preference',
                key=f'pref_{pref_key}',
                content=content,
                importance_score=score
            )
            saved += 1
            if saved >= 16:
                break
    
    def _update_personality_profile(self, pairs: List[Dict]):
        """
        更新AI的性格特征档案
        """
        conversations = [(p['user_message'], p['ai_response']) for p in pairs]
        patterns = memory_extractor.extract_personality_patterns(conversations)
        
        # 存储性格特征
        for trait_name, trait_value in patterns.items():
            db.update_personality_trait(
                trait_name=trait_name,
                trait_value=trait_value,
                frequency=0.7,
                confidence=0.8
            )
        
        logger.info(f"已更新性格特征: {list(patterns.keys())}")
    
    def get_memory_context(self, topic: str = None) -> str:
        """
        获取记忆上下文，用于注入到对话中
        """
        context = "## 我对你的了解 ##\n"
        
        important_memories = db.get_memories_by_category('relationship')[:4]
        
        if important_memories:
            context += "### 关于我们的关系 ###\n"
            for mem in important_memories:
                context += f"- {mem['content']}\n"
        
        preference_memories = db.get_memories_by_category('preference')[:6]
        if preference_memories:
            context += "\n### 你的喜好 ###\n"
            for mem in preference_memories:
                context += f"- {mem['content']}\n"
        
        experience_memories = db.get_memories_by_category('experience')[:6]
        if experience_memories:
            context += "\n### 时间线里的你 ###\n"
            for mem in experience_memories:
                context += f"- {mem['content']}\n"

        if not important_memories and not preference_memories and not experience_memories:
            context += "- 还在继续了解你，会优先记住你明确表达过的喜好和经历。\n"
        
        return context
    
    def search_relevant_memories(self, keyword: str) -> List[Dict]:
        """
        搜索相关的记忆
        """
        return db.search_memories(keyword)
    
    def get_personality_summary(self) -> str:
        """
        获取性格特征总结
        """
        traits = db.get_all_personality_traits()
        
        summary = "## 我的性格档案 ##\n"
        
        if '常用词' in traits:
            words = traits['常用词']['trait_value']
            summary += f"**常用词**: {', '.join(words[:10])}\n"
        
        if '撒娇频率' in traits:
            summary += f"**撒娇频率**: {traits['撒娇频率']['trait_value']}\n"
        
        if '平均回复长度' in traits:
            length = traits['平均回复长度']['trait_value']
            summary += f"**回复长度**: {length} 字符左右\n"
        
        summary += "\n*性格特征根据对话自动学习和更新*\n"
        
        return summary

    def get_intent_context(self, user_input: str) -> str:
        """生成当前用户输入的意图上下文提示。"""
        result = intent_classifier.detect(user_input)
        evidence = "、".join(result.evidence) if result.evidence else "无"
        return (
            "## 当前用户意图 ##\n"
            f"- 意图类型: {result.intent}\n"
            f"- 识别置信度: {result.confidence:.2f}\n"
            f"- 回复策略: {result.strategy}\n"
            f"- 触发依据: {evidence}\n"
        )

    # ──────────────────────────────────────────────────────────────────────
    # 主动记忆管理（Active Memory Management）
    # ──────────────────────────────────────────────────────────────────────

    def decay_trivial_memories(self, age_days: int = 30, min_ref_count: int = 0, decay_amount: float = 0.08) -> int:
        """
        对"冷门"记忆降低重要性分值，模拟遗忘曲线。
        - age_days: 记忆创建超过此天数才考虑衰减
        - min_ref_count: 引用次数 <= 此值才考虑衰减
        - decay_amount: 每次调用降低的分值

        返回衰减条数。
        """
        conn = db.get_connection()
        cursor = conn.cursor()
        cutoff_ts = (datetime.now() - timedelta(days=age_days)).isoformat()
        cursor.execute(
            """
            SELECT id, importance_score FROM long_term_memories
            WHERE created_at < ? AND reference_count <= ? AND importance_score > 0.1
            """,
            (cutoff_ts, min_ref_count),
        )
        rows = cursor.fetchall()
        decayed = 0
        for row in rows:
            mem_id = row["id"]
            new_score = max(0.1, round(float(row["importance_score"]) - decay_amount, 4))
            cursor.execute(
                "UPDATE long_term_memories SET importance_score = ? WHERE id = ?",
                (new_score, mem_id),
            )
            decayed += 1
        conn.commit()
        conn.close()
        logger.info(f"[记忆衰减] 已对 {decayed} 条冷门记忆降低重要性分值")
        return decayed

    def boost_emotional_memories(self, user_text: str, ai_text: str, boost_amount: float = 0.05) -> None:
        """
        当对话中检测到强情绪信号时，对最近关系类/经历类记忆提升重要性分值。
        """
        EMOTION_SIGNALS = [
            "爱你", "喜欢你", "想念", "想你", "好开心", "太感动", "哭了",
            "委屈", "幸福", "难受", "崩溃", "感谢", "谢谢你", "永远"
        ]
        combined = (user_text or "") + (ai_text or "")
        if not any(sig in combined for sig in EMOTION_SIGNALS):
            return
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE long_term_memories
            SET importance_score = MIN(1.0, importance_score + ?)
            WHERE category IN ('relationship', 'experience') AND importance_score < 1.0
            ORDER BY last_updated DESC
            LIMIT 5
            """,
            (boost_amount,),
        )
        conn.commit()
        conn.close()

    def compress_old_memories(self, category: str = None, max_per_key_prefix: int = 2) -> int:
        """
        合并同一 key 前缀下的冗余记忆，保留重要性最高的若干条，删除其余。
        这是对 Mem0 "主动记忆管理" 理念的轻量实现。

        返回删除条数。
        """
        categories = [category] if category else ["personality", "relationship", "experience", "preference", "important_info"]
        total_removed = 0

        conn = db.get_connection()
        cursor = conn.cursor()

        for cat in categories:
            cursor.execute(
                "SELECT id, key, importance_score FROM long_term_memories WHERE category = ? ORDER BY key, importance_score DESC",
                (cat,),
            )
            rows = cursor.fetchall()
            # Group by 4-char key prefix to catch near-duplicates like "pref_like_" variants
            from collections import defaultdict
            groups: dict = defaultdict(list)
            for row in rows:
                prefix = str(row["key"])[:20]
                groups[prefix].append(row)

            for prefix, group in groups.items():
                if len(group) <= max_per_key_prefix:
                    continue
                # Keep top max_per_key_prefix by importance_score (already sorted DESC)
                to_delete = group[max_per_key_prefix:]
                ids_to_delete = [r["id"] for r in to_delete]
                cursor.executemany("DELETE FROM long_term_memories WHERE id = ?", [(i,) for i in ids_to_delete])
                total_removed += len(ids_to_delete)

        conn.commit()
        conn.close()
        logger.info(f"[记忆压缩] 已删除 {total_removed} 条冗余记忆")
        return total_removed


class MemoryAugmentedPrompt:
    """
    记忆增强的提示词构建器
    负责将记忆信息融入到模型的输入中
    """
    
    def __init__(self, memory_manager: LongTermMemoryManager):
        self.memory_manager = memory_manager
    
    def build_system_prompt_with_memory(self) -> str:
        """
        构建包含长期记忆的系统提示词
        使用当前激活角色的设定
        """
        from character_manager import character_manager
        
        char = character_manager.get_active_character()
        
        # 使用角色自带的 build_system_prompt() 方法
        system_prompt = char.build_system_prompt()

        # 添加性格特征
        system_prompt += self.memory_manager.get_personality_summary()
        
        # 添加记忆上下文
        system_prompt += "\n"
        system_prompt += self.memory_manager.get_memory_context()
        
        return system_prompt
    
    def build_full_context(self, user_input: str) -> str:
        """
        为单条用户输入构建完整的上下文
        包括系统提示词、长期记忆和最近的对话历史
        """
        context = self.build_system_prompt_with_memory()

        # 追加意图识别结果，帮助模型选对回复策略
        context += "\n" + self.memory_manager.get_intent_context(user_input)
        
        # 添加最近的对话历史
        recent_history = rag_system.get_chunked_conversation_history(chunk_size=5)
        if recent_history:
            context += "\n" + recent_history
        
        # 搜索相关的历史对话
        search_results = rag_system.search_relevant_conversations(user_input, top_k=3)
        if search_results:
            context += "\n## 相似的对话参考 ##\n"
            for i, result in enumerate(search_results, 1):
                context += f"{i}. 用户: {result['user_message'][:50]}\n"
                context += f"   我的回复: {result['ai_response'][:50]}\n"
        
        # 最后是当前的用户输入
        context += f"\n用户: {user_input}\n我: "
        
        return context


# 全局实例
memory_manager = LongTermMemoryManager()
memory_prompt_builder = MemoryAugmentedPrompt(memory_manager)
