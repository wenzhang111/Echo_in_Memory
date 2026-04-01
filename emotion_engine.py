"""
情感状态引擎 - 角色动态情绪系统

每个角色维护一个情绪向量，随对话内容动态变化，影响回复风格。
情绪维度: happy(开心), anxious(焦虑), missing(想你), tired(疲惫), excited(兴奋)
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data" / "emotions"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# 情绪维度定义
# ──────────────────────────────────────────────
EMOTION_DIMS = ["happy", "anxious", "missing", "tired", "excited"]

EMOTION_LABELS: Dict[str, str] = {
    "happy": "开心",
    "anxious": "焦虑",
    "missing": "想念",
    "tired": "疲惫",
    "excited": "兴奋",
}

# 情绪 → emoji 映射（取主导情绪用）
EMOTION_EMOJI: Dict[str, str] = {
    "happy": "😊",
    "anxious": "😟",
    "missing": "🥺",
    "tired": "😴",
    "excited": "🤩",
}

# ──────────────────────────────────────────────
# 关键词触发规则  (关键词列表, 影响的情绪维度, 变化量)
# 正数 = 提升该维度, 负数 = 降低该维度
# ──────────────────────────────────────────────
TRIGGER_RULES: List[tuple] = [
    # happy ↑
    (["哈哈", "开心", "快乐", "好棒", "太好了", "喜欢", "爱你", "爱我", "谢谢", "感谢",
      "真棒", "厉害", "好玩", "幸福", "高兴", "😊", "😄", "❤️", "💕", "🎉"], "happy", +0.15),
    # happy ↓
    (["难受", "不开心", "伤心", "失望", "烦死了", "讨厌", "憎恨", "崩溃", "哭了", "😭"], "happy", -0.10),
    # anxious ↑
    (["担心", "焦虑", "害怕", "紧张", "慌", "忧虑", "怎么办", "不知道", "迷茫", "压力",
      "焦虑症", "睡不着", "失眠", "担忧"], "anxious", +0.15),
    # anxious ↓
    (["放心", "没事", "好多了", "解决了", "顺利", "轻松", "终于", "搞定"], "anxious", -0.12),
    # missing ↑
    (["想你", "想念", "好久没", "多久没", "想见你", "不见了", "一直想", "念念不忘",
      "好想", "怎么不来", "你在哪", "想你了", "🥺", "💭"], "missing", +0.20),
    # missing ↓
    (["在这里", "我来了", "见到你", "回来了", "不走了"], "missing", -0.15),
    # tired ↑
    (["累了", "好累", "疲惫", "太累", "累死了", "撑不住", "精疲力竭", "体力透支",
      "熬夜", "没睡", "困死了", "累", "烦透了", "腰疼", "头疼", "😪", "😫"], "tired", +0.15),
    # tired ↓
    (["睡好了", "休息了", "恢复了", "精力充沛", "精神好", "睡够了", "放松"], "tired", -0.12),
    # excited ↑
    (["好激动", "期待", "太兴奋了", "哇", "wow", "amazing", "震惊", "不敢相信",
      "惊喜", "意外", "太好了吧", "真的吗", "厉害了", "🤩", "🔥", "💥", "好期待"], "excited", +0.18),
    # excited ↓
    (["无聊", "没意思", "淡淡的", "一般般", "无所谓", "随便", "算了"], "excited", -0.10),
]

# 自然衰减参数：每次对话后各维度向中性值 0.5 靠近
DECAY_RATE = 0.05
NEUTRAL = 0.5

# 情绪对回复风格的描述模板（注入到 system prompt）
EMOTION_PROMPT_TEMPLATES: Dict[str, str] = {
    "happy": "你现在心情很好，充满活力，说话时可以更加俏皮可爱，分享你的好心情。",
    "anxious": "你最近有些不安，说话时会更体贴地关心对方，语气中带着温柔的担忧。",
    "missing": "你非常想念对方，说话时会流露出一点撒娇和黏人，偶尔说说\"好想你\"之类的话。",
    "tired": "你感觉有点累，说话会更轻柔，也会关心对方是否注意休息。",
    "excited": "你现在很兴奋期待，语气活泼跳跃，经常感叹词和惊喜表达。",
}


class EmotionState:
    """单个角色的情绪状态"""

    def __init__(
        self,
        char_id: str,
        happy: float = 0.6,
        anxious: float = 0.2,
        missing: float = 0.3,
        tired: float = 0.2,
        excited: float = 0.4,
        last_updated: str = "",
        update_count: int = 0,
    ):
        self.char_id = char_id
        self.happy = max(0.0, min(1.0, happy))
        self.anxious = max(0.0, min(1.0, anxious))
        self.missing = max(0.0, min(1.0, missing))
        self.tired = max(0.0, min(1.0, tired))
        self.excited = max(0.0, min(1.0, excited))
        self.last_updated = last_updated or datetime.now().isoformat()
        self.update_count = update_count

    # ── Serialisation ──────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "char_id": self.char_id,
            "happy": round(self.happy, 3),
            "anxious": round(self.anxious, 3),
            "missing": round(self.missing, 3),
            "tired": round(self.tired, 3),
            "excited": round(self.excited, 3),
            "last_updated": self.last_updated,
            "update_count": self.update_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EmotionState":
        return cls(
            char_id=data.get("char_id", "default"),
            happy=data.get("happy", 0.6),
            anxious=data.get("anxious", 0.2),
            missing=data.get("missing", 0.3),
            tired=data.get("tired", 0.2),
            excited=data.get("excited", 0.4),
            last_updated=data.get("last_updated", ""),
            update_count=data.get("update_count", 0),
        )

    # ── Derived properties ─────────────────────────────────────────────────
    def dominant_emotion(self) -> str:
        """返回当前强度最高的情绪维度名"""
        return max(EMOTION_DIMS, key=lambda d: getattr(self, d))

    def mood_summary(self) -> str:
        """返回人类可读的情绪摘要（中文）"""
        dom = self.dominant_emotion()
        value = getattr(self, dom)
        label = EMOTION_LABELS[dom]
        emoji = EMOTION_EMOJI[dom]
        intensity = "非常" if value > 0.75 else ("有点" if value > 0.5 else "轻微")
        direction = intensity if value > NEUTRAL else "不太"
        return f"{emoji} {direction}{label}"

    def to_prompt_hint(self) -> str:
        """生成注入 system prompt 的情绪提示词"""
        dom = self.dominant_emotion()
        value = getattr(self, dom)
        # 只在情绪偏离中性较大时才注入
        if abs(value - NEUTRAL) < 0.15:
            return ""
        hint = EMOTION_PROMPT_TEMPLATES.get(dom, "")
        if not hint:
            return ""
        return f"\n## 当前情绪状态\n{hint}\n"

    def badge_data(self) -> dict:
        """供前端展示的简洁数据"""
        dom = self.dominant_emotion()
        return {
            "dominant": dom,
            "label": EMOTION_LABELS[dom],
            "emoji": EMOTION_EMOJI[dom],
            "summary": self.mood_summary(),
            "values": {dim: round(getattr(self, dim), 2) for dim in EMOTION_DIMS},
        }


import re as _re

# Maximum allowed length for a char_id used in file paths
_CHAR_ID_MAX_LEN = 64
_CHAR_ID_SAFE_RE = _re.compile(r"[^a-zA-Z0-9_\-]")


def _sanitize_char_id(char_id: str) -> str:
    """Sanitize char_id to prevent path traversal: allow only alphanumerics, underscores, hyphens."""
    safe = _CHAR_ID_SAFE_RE.sub("_", str(char_id))
    return safe[:_CHAR_ID_MAX_LEN] if safe else "default"


class EmotionEngine:
    """情感引擎 - 加载/保存/更新每个角色的情绪状态"""

    @staticmethod
    def _path(char_id: str) -> Path:
        safe_id = _sanitize_char_id(char_id)
        return DATA_DIR / f"{safe_id}.json"

    def load(self, char_id: str) -> EmotionState:
        path = self._path(char_id)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return EmotionState.from_dict(data)
            except Exception as exc:
                logger.warning(f"加载情绪状态失败 {char_id}: {exc}")
        return EmotionState(char_id=char_id)

    def save(self, state: EmotionState) -> None:
        path = self._path(state.char_id)
        try:
            path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"保存情绪状态失败 {state.char_id}: {exc}")

    def update_from_text(self, char_id: str, user_text: str, ai_text: str = "") -> EmotionState:
        """根据用户消息和 AI 回复更新情绪状态，返回更新后的状态"""
        state = self.load(char_id)
        combined = (user_text or "") + " " + (ai_text or "")

        # 1. 应用关键词触发规则
        for keywords, dim, delta in TRIGGER_RULES:
            if any(kw in combined for kw in keywords):
                old_val = getattr(state, dim)
                new_val = max(0.0, min(1.0, old_val + delta))
                setattr(state, dim, new_val)

        # 2. 自然衰减：各维度向 NEUTRAL(0.5) 靠近
        for dim in EMOTION_DIMS:
            current = getattr(state, dim)
            decayed = current + (NEUTRAL - current) * DECAY_RATE
            setattr(state, dim, round(decayed, 4))

        state.last_updated = datetime.now().isoformat()
        state.update_count += 1
        self.save(state)
        return state

    def set_state(self, char_id: str, updates: dict) -> EmotionState:
        """手动设置情绪维度值（前端或 API 调用）"""
        state = self.load(char_id)
        for dim in EMOTION_DIMS:
            if dim in updates:
                val = float(updates[dim])
                setattr(state, dim, max(0.0, min(1.0, val)))
        state.last_updated = datetime.now().isoformat()
        self.save(state)
        return state

    def reset(self, char_id: str) -> EmotionState:
        """重置为默认情绪"""
        state = EmotionState(char_id=char_id)
        self.save(state)
        return state


# 全局单例
emotion_engine = EmotionEngine()
