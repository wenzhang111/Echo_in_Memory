"""
语言风格学习模块 - 从导入聊天记录中提取更贴近真人的表达风格
分析维度：口头表达、句尾习惯、语气词、情绪倾向、代表性原句
"""
import re
import json
import logging
from collections import Counter
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

STYLE_DIR = Path(__file__).parent / "data" / "styles"
STYLE_DIR.mkdir(parents=True, exist_ok=True)


class StyleProfile:
    """语言风格档案"""

    def __init__(self):
        self.frequent_words: List[str] = []
        self.catchphrases: List[str] = []
        self.emoji_habits: List[str] = []
        self.tone_particles: Dict[str, int] = {}

        self.avg_length: float = 0
        self.short_ratio: float = 0
        self.long_ratio: float = 0
        self.question_ratio: float = 0
        self.exclamation_ratio: float = 0

        self.positive_ratio: float = 0
        self.negative_ratio: float = 0
        self.flirt_level: float = 0
        self.humor_level: float = 0

        self.ending_styles: Dict[str, int] = {}
        self.signature_sentences: List[str] = []
        self.style_tags: List[str] = []

        self.sample_count: int = 0
        self.analyzed_at: str = ""

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: dict) -> 'StyleProfile':
        p = cls()
        for k, v in data.items():
            if hasattr(p, k):
                setattr(p, k, v)
        return p

    def to_prompt(self) -> str:
        """将风格档案转成可直接注入 system prompt 的文本"""
        if self.sample_count <= 0:
            return ""

        lines = ["## 从聊天记录中学习到的语言风格（高优先级）"]

        if self.style_tags:
            lines.append(f"- 风格标签: {'、'.join(self.style_tags[:6])}")

        if self.avg_length > 0:
            lines.append(
                f"- 回复长度: 平均{self.avg_length:.0f}字，短句占比{self.short_ratio * 100:.0f}%"
            )

        if self.catchphrases:
            lines.append(f"- 高频表达: {'，'.join(self.catchphrases[:8])}")

        top_endings = sorted(self.ending_styles.items(), key=lambda x: -x[1])[:6]
        if top_endings:
            lines.append(f"- 常见句尾: {'、'.join([k for k, _ in top_endings])}")

        top_particles = sorted(self.tone_particles.items(), key=lambda x: -x[1])[:6]
        if top_particles:
            lines.append(f"- 常用语气词: {'、'.join([k for k, _ in top_particles])}")

        if self.emoji_habits:
            lines.append(f"- 表情习惯: {' '.join(self.emoji_habits[:8])}")

        if self.signature_sentences:
            lines.append("- 代表性原句（模仿节奏，不要逐字复读）:")
            for i, sent in enumerate(self.signature_sentences[:8], 1):
                lines.append(f"  {i}) {sent}")

        lines.append("- 模仿要求: 保持口语化、生活化，优先短句，避免书面腔和模板化回答")
        return "\n".join(lines)


class StyleLearner:
    """从聊天记录中学习语言风格"""

    TONE_PARTICLES = [
        '呢', '吧', '呀', '哦', '嘛', '啦', '哈', '嘿', '喽', '噢',
        '嗯', '哎', '唉', '诶', '嘞', '呐', '咯', '哟', '耶', '啊',
        '呗', '哒', '喔', '嘛', '鸭'
    ]

    FLIRT_WORDS = [
        '宝宝', '宝子', '宝贝', '亲爱的', '老公', '老婆', '想你', '喜欢你',
        '抱抱', '亲亲', '爱你', '只想跟你', '只跟你', '小可怜'
    ]

    HUMOR_MARKERS = [
        '哈哈', '哈哈哈', '笑死', '离谱', '绝了', '服了', '无语', '好家伙',
        '哦豁', '蚌埠住了', '破防了', '🤣', '😂', '😹', 'hhh', '233'
    ]

    DIALECT_HINTS = ['要得', '晓得', '屋头', '呗', '哒', '喔', '哈', '哟']

    EMOJI_PATTERNS = re.compile(
        r'[\U0001F300-\U0001FAFF]'
        r'|\[[^\[\]]{1,10}\]'
    )

    def analyze(self, ai_responses: List[str]) -> StyleProfile:
        profile = StyleProfile()
        cleaned = [self._clean_response(x) for x in ai_responses if self._clean_response(x)]
        if not cleaned:
            return profile

        profile.sample_count = len(cleaned)
        profile.analyzed_at = datetime.now().isoformat()

        balanced = self._build_balanced_corpus(cleaned)
        if not balanced:
            return profile

        lengths = [len(r) for r in balanced]
        profile.avg_length = sum(lengths) / len(lengths)
        profile.short_ratio = sum(1 for l in lengths if l < 12) / len(lengths)
        profile.long_ratio = sum(1 for l in lengths if l > 45) / len(lengths)

        profile.question_ratio = sum(1 for r in balanced if '?' in r or '？' in r) / len(balanced)
        profile.exclamation_ratio = sum(1 for r in balanced if '!' in r or '！' in r) / len(balanced)

        full_text = '\n'.join(balanced)
        for p in self.TONE_PARTICLES:
            c = full_text.count(p)
            if c > 0:
                profile.tone_particles[p] = c

        flirt_sent = sum(1 for r in balanced if any(w in r for w in self.FLIRT_WORDS))
        humor_sent = sum(1 for r in balanced if any(w in r for w in self.HUMOR_MARKERS))
        profile.flirt_level = flirt_sent / len(balanced)
        profile.humor_level = humor_sent / len(balanced)

        emoji_counter = Counter()
        for r in balanced:
            for token in self.EMOJI_PATTERNS.findall(r):
                token = token.strip()
                if token in {'️', '/', '(', ')', '~', '^', '_', '>', '<'}:
                    continue
                if len(token) == 1 and re.fullmatch(r'[A-Za-z0-9]', token):
                    continue
                emoji_counter[token] += 1
        profile.emoji_habits = [e for e, _ in emoji_counter.most_common(15)]

        profile.frequent_words, profile.catchphrases = self._extract_words_and_catchphrases(balanced)
        profile.ending_styles = self._extract_ending_styles(balanced)
        profile.signature_sentences = self._extract_signature_sentences(cleaned)

        pos_words = {'喜欢', '开心', '高兴', '爱', '幸福', '可以', '好呀', '没事', '放心'}
        neg_words = {'难过', '伤心', '生气', '讨厌', '害怕', '烦', '累', '不想', '崩溃'}
        pos_c = sum(full_text.count(w) for w in pos_words)
        neg_c = sum(full_text.count(w) for w in neg_words)
        total_emo = pos_c + neg_c
        if total_emo > 0:
            profile.positive_ratio = pos_c / total_emo
            profile.negative_ratio = neg_c / total_emo

        profile.style_tags = self._build_style_tags(profile)
        return profile

    @staticmethod
    def _clean_response(text: str) -> str:
        if not text:
            return ''
        text = str(text).replace('\u3000', ' ').strip()
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('。。。', '...')
        return text

    @staticmethod
    def _build_balanced_corpus(responses: List[str]) -> List[str]:
        counter = Counter(responses)
        corpus: List[str] = []
        for msg, cnt in counter.items():
            repeat = min(cnt, 3)
            corpus.extend([msg] * repeat)
        return corpus

    @staticmethod
    def _is_noise_sentence(text: str) -> bool:
        t = text.strip()
        if not t:
            return True
        if re.fullmatch(r'[哈啊嘿呵hH]+[!！?？]*', t):
            return True
        if re.fullmatch(r'\[.{1,10}\]', t):
            return True
        if len(set(t)) <= 2 and len(t) >= 6:
            return True
        return False

    def _extract_words_and_catchphrases(self, responses: List[str]) -> Tuple[List[str], List[str]]:
        try:
            import jieba
        except ImportError:
            jieba = None

        stopwords = {
            '的', '了', '在', '是', '我', '你', '他', '她', '和', '也', '都', '就', '不',
            '有', '到', '说', '要', '去', '会', '这', '那', '什么', '吗', '啊', '呢', '吧',
            '呀', '哦', '嘛', '啦', '一', '很', '上', '下', '着', '过', '对', '把', '让'
        }

        word_counter = Counter()
        for resp in responses:
            if jieba:
                words = [w.strip() for w in jieba.cut(resp, cut_all=False)]
            else:
                words = list(resp)

            filtered = [w for w in words if len(w) >= 2 and w not in stopwords]
            word_counter.update(filtered)

        frequent = [w for w, _ in word_counter.most_common(30)]

        exact_counter = Counter(
            r for r in responses
            if 4 <= len(r) <= 24 and not self._is_noise_sentence(r)
        )
        catchphrases: List[str] = [
            s for s, c in exact_counter.most_common(20)
            if c >= 3
        ][:8]

        phrase_counter = Counter()
        phrase_pattern = re.compile(r'([\u4e00-\u9fffA-Za-z0-9]{2,10}(?:哟|哈|呀|嘛|吧|呗|哒|喔|哦))')
        for r in responses:
            for m in phrase_pattern.findall(r):
                phrase_counter[m] += 1

        for phrase, cnt in phrase_counter.most_common(20):
            if cnt >= 2 and phrase not in catchphrases and not self._is_noise_sentence(phrase):
                catchphrases.append(phrase)
            if len(catchphrases) >= 12:
                break

        return frequent, catchphrases

    @staticmethod
    def _extract_ending_styles(responses: List[str]) -> Dict[str, int]:
        endings = ['哈', '哟', '吧', '呢', '啊', '呀', '嘛', '啦', '呗', '哒', '喔', '哦', '？', '！', '...']
        counter = Counter()

        for r in responses:
            text = r.strip()
            if not text:
                continue

            matched = False
            for end in endings:
                if text.endswith(end):
                    counter[end] += 1
                    matched = True
                    break

            if not matched and len(text) >= 2:
                if not text.endswith(']'):
                    counter[text[-1]] += 1

        return dict(counter.most_common(12))

    def _extract_signature_sentences(self, responses: List[str]) -> List[str]:
        counter = Counter(responses)
        candidates = [
            s for s in counter.keys()
            if 6 <= len(s) <= 30 and not self._is_noise_sentence(s)
        ]

        def score(sentence: str) -> float:
            val = 0.0
            if any(d in sentence for d in self.DIALECT_HINTS):
                val += 2.0
            if any(w in sentence for w in self.FLIRT_WORDS):
                val += 1.4
            if any(w in sentence for w in self.HUMOR_MARKERS):
                val += 1.2
            if '？' in sentence or '?' in sentence:
                val += 0.8
            if '！' in sentence or '!' in sentence:
                val += 0.6
            if 8 <= len(sentence) <= 20:
                val += 0.9
            val += min(2.0, counter[sentence] / 2.0)
            return val

        ranked = sorted(candidates, key=score, reverse=True)
        return ranked[:12]

    @staticmethod
    def _build_style_tags(profile: StyleProfile) -> List[str]:
        tags: List[str] = []
        if profile.short_ratio >= 0.55:
            tags.append('短句直给')
        if profile.question_ratio >= 0.12:
            tags.append('会反问推进')
        if profile.flirt_level >= 0.15:
            tags.append('亲密表达明显')
        if profile.humor_level >= 0.12:
            tags.append('带一点玩笑感')
        if profile.negative_ratio >= 0.45:
            tags.append('情绪表达直接')
        if not tags:
            tags.append('自然口语化')
        return tags

    def analyze_and_save(self, ai_responses: List[str], character_id: str = "default") -> StyleProfile:
        profile = self.analyze(ai_responses)
        path = STYLE_DIR / f"{character_id}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"语言风格档案已保存: {path}  (样本数 {profile.sample_count})")
        return profile

    @staticmethod
    def load_profile(character_id: str = "default") -> Optional[StyleProfile]:
        path = STYLE_DIR / f"{character_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return StyleProfile.from_dict(json.load(f))
        except Exception:
            return None

    def learn_from_database(self, character_id: str = "default") -> StyleProfile:
        from database import db

        pairs = db.get_conversation_pairs(limit=50000, character_id=character_id)
        ai_responses = [p['ai_response'] for p in pairs if p.get('ai_response')]
        if not ai_responses:
            logger.warning(f"角色 {character_id} 没有可学习的聊天记录")
            return StyleProfile()

        logger.info(f"开始学习角色 {character_id} 的语言风格 ({len(ai_responses)} 条记录)...")
        return self.analyze_and_save(ai_responses, character_id)


style_learner = StyleLearner()
