"""
情绪曲线追踪系统

在每轮对话中分析用户情绪的「效价(valence)」和「唤醒度(arousal)」，
持久化存储并提供趋势分析与上下文注入能力。

效价  : -1 (消极) ~ +1 (积极)
唤醒度:  0 (平静) ~  1 (激动)
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── 情绪词典（效价, 唤醒度）──────────────────
_LEXICON: Dict[str, tuple] = {
    # 积极 - 高唤醒
    "开心": (0.8, 0.7), "高兴": (0.8, 0.6), "兴奋": (0.7, 0.9),
    "哈哈": (0.7, 0.7), "太好了": (0.9, 0.8), "好棒": (0.8, 0.7),
    "期待": (0.6, 0.7), "爱你": (0.9, 0.8), "喜欢你": (0.85, 0.7),
    "嘻嘻": (0.6, 0.6), "好耶": (0.8, 0.8), "感动": (0.7, 0.5),
    "幸福": (0.9, 0.5), "太棒了": (0.9, 0.8), "好开心": (0.85, 0.75),
    "哇": (0.6, 0.8), "真棒": (0.7, 0.6), "谢谢": (0.5, 0.4),
    "宝贝": (0.7, 0.5), "亲爱的": (0.7, 0.5), "想你": (0.6, 0.6),
    "么么": (0.7, 0.5), "mua": (0.7, 0.5), "嗯嗯": (0.3, 0.2),
    "好的呢": (0.4, 0.3), "好哒": (0.5, 0.4), "乖": (0.5, 0.4),
    # 积极 - 低唤醒
    "安心": (0.6, 0.2), "放松": (0.5, 0.2), "满足": (0.7, 0.3),
    "温暖": (0.6, 0.3), "舒服": (0.5, 0.2), "知足": (0.6, 0.2),
    "不错": (0.4, 0.3), "还行": (0.2, 0.2), "可以": (0.2, 0.2),
    # 消极 - 高唤醒
    "生气": (-0.7, 0.8), "愤怒": (-0.8, 0.9), "烦死了": (-0.7, 0.8),
    "气死": (-0.8, 0.9), "炸了": (-0.6, 0.9), "焦虑": (-0.5, 0.7),
    "崩溃": (-0.8, 0.8), "疯了": (-0.6, 0.9), "受不了": (-0.6, 0.8),
    "滚": (-0.9, 0.9), "烦人": (-0.5, 0.6),
    # 消极 - 低唤醒
    "难过": (-0.7, 0.4), "伤心": (-0.8, 0.4), "失落": (-0.6, 0.3),
    "郁闷": (-0.5, 0.3), "无聊": (-0.3, 0.2), "累": (-0.4, 0.3),
    "困": (-0.2, 0.2), "烦": (-0.4, 0.4), "委屈": (-0.7, 0.5),
    "想哭": (-0.8, 0.5), "难受": (-0.6, 0.4), "压力大": (-0.5, 0.6),
    "失眠": (-0.4, 0.5), "孤独": (-0.6, 0.3), "寂寞": (-0.5, 0.3),
    "不开心": (-0.6, 0.3), "沮丧": (-0.7, 0.3), "害怕": (-0.6, 0.7),
    "担心": (-0.4, 0.5), "紧张": (-0.3, 0.6), "抑郁": (-0.8, 0.3),
    "心痛": (-0.8, 0.5), "绝望": (-0.9, 0.4),
}


@dataclass
class EmotionPoint:
    timestamp: str
    valence: float
    arousal: float
    dominant_emotion: str
    trigger_text: str


class EmotionTracker:
    """追踪用户情绪变化曲线，持久化到 JSON 文件。"""

    _MAX_HISTORY = 500

    def __init__(self, data_dir: str = "data"):
        self.data_file = Path(data_dir) / "emotion_curve.json"
        self.history: List[Dict] = self._load()

    # ─── 持久化 ─────────────────────────────────
    def _load(self) -> List[Dict]:
        if self.data_file.exists():
            try:
                return json.loads(self.data_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(
            json.dumps(self.history[-self._MAX_HISTORY :], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ─── 分析单条文本 ───────────────────────────
    def analyze(self, text: str) -> EmotionPoint:
        """分析文本的情绪效价和唤醒度。"""
        if not text:
            return EmotionPoint(datetime.now().isoformat(), 0.0, 0.0, "平和", "")

        val_sum, aro_sum, matches = 0.0, 0.0, 0
        dom = "平和"
        max_intensity = 0.0

        for word, (v, a) in _LEXICON.items():
            cnt = text.count(word)
            if cnt > 0:
                w = min(cnt, 3)  # 同一词最多计 3 次
                val_sum += v * w
                aro_sum += a * w
                matches += w
                intens = abs(v) * a
                if intens > max_intensity:
                    max_intensity = intens
                    dom = self._label(v, a)

        # 标点信号
        excl = text.count("!") + text.count("！")
        aro_boost = min(0.2, excl * 0.05)

        if matches > 0:
            val = max(-1.0, min(1.0, val_sum / matches))
            aro = max(0.0, min(1.0, aro_sum / matches + aro_boost))
        else:
            ellipsis = text.count("...") + text.count("…")
            quest = text.count("?") + text.count("？")
            val = -0.1 if ellipsis >= 2 else 0.1
            aro = 0.5 if quest >= 2 else 0.3
            aro = min(1.0, aro + aro_boost)
            dom = "迟疑" if ellipsis >= 2 else ("好奇" if quest >= 2 else "平和")

        return EmotionPoint(
            datetime.now().isoformat(),
            round(val, 3),
            round(aro, 3),
            dom,
            text[:60],
        )

    @staticmethod
    def _label(v: float, a: float) -> str:
        if v > 0.3:
            return "兴奋开心" if a > 0.5 else "平静愉悦"
        if v < -0.3:
            return "烦躁焦虑" if a > 0.5 else "低落消沉"
        return "平和"

    # ─── 记录一个数据点 ────────────────────────
    def record(self, text: str, character_id: str = "default") -> EmotionPoint:
        pt = self.analyze(text)
        self.history.append(
            {
                "ts": pt.timestamp,
                "v": pt.valence,
                "a": pt.arousal,
                "e": pt.dominant_emotion,
                "cid": character_id,
                "t": pt.trigger_text,
            }
        )
        self._save()
        return pt

    # ─── 趋势分析 ──────────────────────────────
    def get_trend(self, window: int = 10, character_id: str = None) -> Dict:
        """获取最近 window 条记录的情绪趋势。"""
        pool = self.history
        if character_id:
            pool = [p for p in pool if p.get("cid") == character_id]
        if not pool:
            return {
                "trend": "unknown",
                "trend_label": "暂无数据",
                "mood": "🤔 暂无数据",
                "avg_valence": 0,
                "avg_arousal": 0,
                "points": [],
                "total_records": 0,
            }

        recent = pool[-window:]
        avg_v = sum(p["v"] for p in recent) / len(recent)
        avg_a = sum(p["a"] for p in recent) / len(recent)

        # 趋势：前后半段效价对比
        if len(recent) >= 4:
            mid = len(recent) // 2
            fst = sum(p["v"] for p in recent[:mid]) / mid
            snd = sum(p["v"] for p in recent[mid:]) / (len(recent) - mid)
            delta = snd - fst
            if delta > 0.15:
                trend, label = "improving", "情绪好转中 📈"
            elif delta < -0.15:
                trend, label = "declining", "情绪走低中 📉"
            else:
                trend, label = "stable", "情绪平稳 ➡️"
        else:
            trend, label = "insufficient", "数据不足"

        if avg_v > 0.3:
            mood = "😊 心情不错"
        elif avg_v > 0:
            mood = "🙂 还行"
        elif avg_v > -0.3:
            mood = "😐 一般般"
        else:
            mood = "😢 心情低落"

        return {
            "trend": trend,
            "trend_label": label,
            "mood": mood,
            "avg_valence": round(avg_v, 3),
            "avg_arousal": round(avg_a, 3),
            "points": recent,
            "total_records": len(pool),
        }

    # ─── 为 AI 生成情绪上下文 ──────────────────
    def build_emotion_context(self, current_text: str, character_id: str = None) -> str:
        """构建情绪上下文信息，注入到系统提示词中。"""
        cur = self.analyze(current_text)
        trend = self.get_trend(window=8, character_id=character_id)

        lines = ["## 用户情绪感知 ##"]
        lines.append(
            f"- 当前情绪: {cur.dominant_emotion}（效价{cur.valence:+.1f}，唤醒{cur.arousal:.1f}）"
        )
        if trend["trend"] not in ("unknown", "insufficient"):
            lines.append(f"- 近期趋势: {trend['trend_label']}")
            lines.append(f"- 整体心情: {trend['mood']}")

        # 回复策略建议
        if cur.valence < -0.3:
            lines.append("- ⚠️ 用户情绪低落，请优先共情安慰，语气温柔，不急着给建议")
        elif cur.valence > 0.5 and cur.arousal > 0.5:
            lines.append("- 用户很开心，可以一起嗨，语气活泼")
        elif cur.arousal < 0.3:
            lines.append("- 用户比较平静，适合轻松自然的对话节奏")
        if trend.get("trend") == "declining":
            lines.append("- ⚠️ 情绪持续走低，请额外关心")

        return "\n".join(lines)

    # ─── 获取曲线数据（供前端绘图）──────────────
    def get_curve_data(self, days: int = 7, character_id: str = None) -> List[Dict]:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return [
            p
            for p in self.history
            if p["ts"] >= cutoff
            and (character_id is None or p.get("cid") == character_id)
        ]


# ── 全局实例 ─────────────────────────────────
emotion_tracker = EmotionTracker()
