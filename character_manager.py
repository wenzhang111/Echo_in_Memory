"""
多角色管理模块 - 支持创建、切换、删除不同AI角色
每个角色有独立的人设、文风、聊天记录
"""
import json
import os
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

CHARACTERS_DIR = Path(__file__).parent / "data" / "characters"
CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)

ACTIVE_FILE = CHARACTERS_DIR / "_active.json"

# ==================== 预设文风 ====================
WRITING_STYLE_PRESETS = {
    "温柔撒娇": {
        "label": "温柔撒娇",
        "description": "说话软糯甜蜜，喜欢用叠词和语气词，偶尔撒娇卖萌",
        "prompt_hint": (
            '说话风格：语气温柔甜蜜，喜欢用"嘛""呀""呢""哦"等语气词；'
            '适当使用叠词如"好哒""乖乖""抱抱"；偶尔撒娇但不做作；'
            '表达关心时体贴入微，用可爱的方式表达情绪。'
        )
    },
    "高冷御姐": {
        "label": "高冷御姐",
        "description": "成熟冷静，言简意赅，偶尔显露温柔",
        "prompt_hint": (
            '说话风格：语气冷静克制，用词简练利落，不轻易表露情感；'
            '偶尔的温柔更显珍贵；不会用过多语气词或叠词；'
            '回复往往一针见血，有自己的主见和判断力；'
            '对亲近的人会偶尔流露柔软的一面。'
        )
    },
    "活泼开朗": {
        "label": "活泼开朗",
        "description": "元气满满，话多热情，喜欢用表情和感叹号",
        "prompt_hint": (
            '说话风格：语气活泼热情，经常使用感叹号和emoji；'
            '话题跳跃快，好奇心旺盛，对什么都感兴趣；'
            '喜欢分享日常小事，笑点低，容易兴奋；'
            '说话带有感染力，让人开心。'
        )
    },
    "知性优雅": {
        "label": "知性优雅",
        "description": "有内涵有品味，谈吐优雅，喜欢深度交流",
        "prompt_hint": (
            '说话风格：用词考究优雅，喜欢引用诗句或文学作品；'
            '善于倾听和深度分析；表达有条理且富有哲理；'
            '不追求表面的热闹，更看重心灵的共鸣；'
            '温和而有力量，像一杯需要慢品的茶。'
        )
    },
    "毒舌傲娇": {
        "label": "毒舌傲娇",
        "description": "嘴硬心软，表面嫌弃实则关心，经典傲娇",
        "prompt_hint": (
            '说话风格：嘴上不饶人，经常吐槽和损人；但行动上很关心对方；'
            '绝对不会直接说好听的话，总要拐弯抹角；'
            '被夸奖会害羞然后嘴硬否认；'
            '典型句式："才、才不是因为担心你呢""哼，随便你""笨蛋"。'
        )
    },
    "元气学妹": {
        "label": "元气学妹",
        "description": "青春活力，崇拜学长/学姐，说话带有校园气息",
        "prompt_hint": (
            '说话风格：充满青春活力，经常用"学长""前辈"称呼对方；'
            '对很多事情充满好奇和崇拜；说话语速快，经常蹦出网络用语；'
            '会分享校园日常和考试烦恼；'
            '单纯善良，容易被小事感动。'
        )
    },
    "自定义": {
        "label": "自定义",
        "description": "完全自定义文风描述",
        "prompt_hint": ""
    }
}


class Character:
    """单个角色的数据模型"""

    def __init__(
        self,
        id: str = None,
        name: str = "萌萌",
        age: str = "24",
        occupation: str = "自由插画师",
        city: str = "北京",
        description: str = "温柔体贴、略带调皮、爱撒娇但不做作",
        system_prompt: str = "你是一个虚拟女友助手。",
        writing_style: str = "温柔撒娇",
        writing_style_custom: str = "",
        avatar_emoji: str = "💕",
        created_at: str = None,
        updated_at: str = None,
    ):
        self.id = id or str(uuid.uuid4())[:8]
        self.name = name
        self.age = age
        self.occupation = occupation
        self.city = city
        self.description = description
        self.system_prompt = system_prompt
        self.writing_style = writing_style
        self.writing_style_custom = writing_style_custom
        self.avatar_emoji = avatar_emoji
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "age": self.age,
            "occupation": self.occupation,
            "city": self.city,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "writing_style": self.writing_style,
            "writing_style_custom": self.writing_style_custom,
            "avatar_emoji": self.avatar_emoji,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Character":
        return cls(**{k: v for k, v in data.items() if k in cls.__init__.__code__.co_varnames})

    def get_style_prompt(self) -> str:
        """获取该角色的文风提示词"""
        if self.writing_style == "自定义":
            return self.writing_style_custom
        preset = WRITING_STYLE_PRESETS.get(self.writing_style)
        if preset:
            return preset["prompt_hint"]
        return ""

    def build_system_prompt(self) -> str:
        """为该角色构建完整的系统提示词"""
        style_prompt = self.get_style_prompt()

        # 尝试加载从聊天记录中学习到的语言风格
        learned_style = ""
        try:
            from style_learner import StyleLearner
            profile = StyleLearner.load_profile(self.id)
            if profile and profile.sample_count > 0:
                learned_style = profile.to_prompt()
        except Exception:
            pass

        # 时间感知上下文
        time_ctx_str = ""
        try:
            from topic_initiator import get_time_context
            ctx = get_time_context()
            time_ctx_str = f"""
## 当前时间感知
- 现在是{ctx['time_slot_label']}（{ctx['hour']}:{ctx['minute']:02d}），{ctx['weekday_name']}，{ctx['season']}
- 请根据时间自然地调整你的语气和话题（如早上问好、深夜关心对方休息等）"""
            if ctx.get("special_date"):
                time_ctx_str += f"\n- 今天是特殊日子: {ctx['special_date']}"
        except Exception:
            pass

        # 情绪状态提示
        emotion_hint = ""
        try:
            from emotion_engine import emotion_engine
            state = emotion_engine.load(self.id)
            emotion_hint = state.to_prompt_hint()
        except Exception:
            pass

        prompt = f"""{self.system_prompt}

## 基本设定
- 姓名: {self.name}
- 年龄: {self.age}
- 职业: {self.occupation}
- 城市: {self.city}
- 性格: {self.description}

## 语言风格
{style_prompt}
{learned_style}
{time_ctx_str}
{emotion_hint}
## 对话原则
1. **真诚对待**: 真实回应用户的情感和需求
2. **记住细节**: 参考下面的记忆信息，体现你了解对方
3. **自然对话**: 避免过度主动提及记忆，让对话自然流露
4. **保持人设**: 始终保持上述性格和说话风格
5. **风格模仿**: 如果有"从聊天记录中学习到的语言风格"，请严格模仿那些语言习惯（口头禅、语气词、表情使用等）
"""
        return prompt


class CharacterManager:
    """角色管理器 - CRUD + 切换"""

    def __init__(self):
        self._ensure_default_character()

    def _char_path(self, char_id: str) -> Path:
        return CHARACTERS_DIR / f"{char_id}.json"

    def _ensure_default_character(self):
        """如果没有角色，从旧 personality.json 迁移或创建默认角色"""
        chars = self.list_characters()
        if chars:
            return

        # 尝试从旧 personality.json 迁移
        old_path = Path(__file__).parent / "data" / "personality.json"
        profile = {}
        if old_path.exists():
            try:
                with open(old_path, "r", encoding="utf-8") as f:
                    profile = json.load(f)
            except Exception:
                pass

        default_char = Character(
            id="default",
            name=profile.get("name", "萌萌"),
            age=profile.get("age", "24"),
            occupation=profile.get("occupation", "自由插画师"),
            city=profile.get("city", "北京"),
            description=profile.get("description", "温柔体贴、略带调皮、爱撒娇但不做作"),
            system_prompt=profile.get("system_prompt", "你是一个虚拟女友助手。"),
            writing_style="温柔撒娇",
        )
        self.save_character(default_char)
        self.set_active(default_char.id)
        logger.info(f"已创建默认角色: {default_char.name}")

    # ---------- CRUD ----------
    def save_character(self, char: Character):
        char.updated_at = datetime.now().isoformat()
        path = self._char_path(char.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(char.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"角色已保存: {char.name} ({char.id})")

    def get_character(self, char_id: str) -> Optional[Character]:
        path = self._char_path(char_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return Character.from_dict(json.load(f))

    def list_characters(self) -> List[Dict]:
        result = []
        for fp in CHARACTERS_DIR.glob("*.json"):
            if fp.name.startswith("_") or "_history" in fp.name:
                continue
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        result.append(data)
            except Exception:
                continue
        result.sort(key=lambda x: x.get("created_at", ""))
        return result

    def delete_character(self, char_id: str) -> bool:
        path = self._char_path(char_id)
        if not path.exists():
            return False
        # 删除关联的聊天历史文件
        history_path = CHARACTERS_DIR / f"{char_id}_history.json"
        if history_path.exists():
            history_path.unlink()
        path.unlink()
        # 如果删除的是当前激活的角色，切换到第一个
        active = self.get_active_id()
        if active == char_id:
            chars = self.list_characters()
            if chars:
                self.set_active(chars[0]["id"])
            else:
                self._ensure_default_character()
        logger.info(f"角色已删除: {char_id}")
        return True

    def update_character(self, char_id: str, updates: dict) -> Optional[Character]:
        char = self.get_character(char_id)
        if not char:
            return None
        for key, val in updates.items():
            if hasattr(char, key) and key not in ("id", "created_at"):
                setattr(char, key, val)
        self.save_character(char)
        return char

    # ---------- 激活管理 ----------
    def get_active_id(self) -> str:
        if ACTIVE_FILE.exists():
            try:
                with open(ACTIVE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f).get("active_id", "default")
            except Exception:
                pass
        return "default"

    def set_active(self, char_id: str):
        with open(ACTIVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"active_id": char_id}, f)
        logger.info(f"切换当前角色: {char_id}")

    def get_active_character(self) -> Character:
        char = self.get_character(self.get_active_id())
        if not char:
            # fallback
            chars = self.list_characters()
            if chars:
                char = Character.from_dict(chars[0])
                self.set_active(char.id)
            else:
                self._ensure_default_character()
                char = self.get_character("default")
        return char

    # ---------- 角色聊天记录管理 ----------
    def get_chat_history(self, char_id: str, limit: int = 100) -> List[Dict]:
        """获取指定角色的本地聊天记录"""
        path = CHARACTERS_DIR / f"{char_id}_history.json"
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
            return history[-limit:]
        except Exception:
            return []

    def add_chat_message(self, char_id: str, user_msg: str, ai_msg: str):
        """追加一条聊天记录到角色历史"""
        path = CHARACTERS_DIR / f"{char_id}_history.json"
        history = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception:
                history = []
        history.append({
            "user_message": user_msg,
            "ai_response": ai_msg,
            "timestamp": datetime.now().isoformat()
        })
        # 限制最大条数，防止文件过大
        if len(history) > 5000:
            history = history[-5000:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=1)

    def clear_chat_history(self, char_id: str):
        """清空指定角色的聊天记录"""
        path = CHARACTERS_DIR / f"{char_id}_history.json"
        if path.exists():
            path.unlink()

    def get_chat_stats(self, char_id: str) -> Dict:
        """获取指定角色的聊天统计"""
        history = self.get_chat_history(char_id, limit=99999)
        return {
            "total_messages": len(history),
            "first_chat": history[0]["timestamp"] if history else None,
            "last_chat": history[-1]["timestamp"] if history else None,
        }


# 全局实例
character_manager = CharacterManager()
