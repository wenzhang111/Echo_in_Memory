"""
主动话题发起模块 - 根据现实时间、近期话题等要素自动生成合适的对话开场白
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time

logger = logging.getLogger(__name__)

import urllib.request
import json

_EXT_CONTEXT_CACHE = {
    "ts": 0.0,
    "data": {"weather": "", "hitokoto": ""},
}
_EXT_CONTEXT_TTL_SECONDS = 600

def get_external_context(force_refresh: bool = False) -> dict:
    """获取外部API数据（天气、每日一句等）"""
    now_ts = time.time()
    if not force_refresh and now_ts - _EXT_CONTEXT_CACHE["ts"] < _EXT_CONTEXT_TTL_SECONDS:
        return dict(_EXT_CONTEXT_CACHE["data"])

    ext_context = {"weather": "", "hitokoto": ""}

    # 1. 获取天气 (使用wttr.in简单格式)
    try:
        req = urllib.request.Request("https://wttr.in/?format=3&lang=zh", headers={'User-Agent': 'curl/7.68.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            weather = response.read().decode('utf-8').strip()
            if weather:
                weather = weather.replace("\r", " ").replace("\n", " ").strip()
            if weather and "Unknown" not in weather and "html" not in weather.lower():
                ext_context["weather"] = weather[:80]
    except Exception as e:
        logger.debug(f"获取天气失败: {e}")
        
    # 2. 获取一言 (hitokoto.cn)
    try:
        req = urllib.request.Request("https://v1.hitokoto.cn/?c=i&c=d", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data and "hitokoto" in data:
                quote = str(data.get("hitokoto", "")).strip()
                if quote:
                    ext_context["hitokoto"] = quote[:120]
    except Exception as e:
        logger.debug(f"获取一言失败: {e}")

    _EXT_CONTEXT_CACHE["ts"] = now_ts
    _EXT_CONTEXT_CACHE["data"] = dict(ext_context)
    return ext_context

# ────────────── 时段配置 ──────────────
TIME_SLOTS = {
    "early_morning": {"range": (5, 7), "label": "清晨"},
    "morning":       {"range": (7, 9), "label": "早上"},
    "forenoon":      {"range": (9, 12), "label": "上午"},
    "noon":          {"range": (12, 14), "label": "中午"},
    "afternoon":     {"range": (14, 17), "label": "下午"},
    "evening":       {"range": (17, 19), "label": "傍晚"},
    "night":         {"range": (19, 22), "label": "晚上"},
    "late_night":    {"range": (22, 24), "label": "深夜"},
    "midnight":      {"range": (0, 5),  "label": "凌晨"},
}

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

SEASON_MAP = {
    (3, 4, 5): "春天",
    (6, 7, 8): "夏天",
    (9, 10, 11): "秋天",
    (12, 1, 2): "冬天",
}

# ────────────── 话题模板 ──────────────
# 不同时段的话题模板（不依赖LLM的本地快速话题）
TOPIC_TEMPLATES: Dict[str, List[str]] = {
    "early_morning": [
        "这么早就醒啦？昨晚睡得好吗～",
        "早呀～今天想吃什么早餐？",
        "清晨的空气好清新呢，你起床了吗？",
    ],
    "morning": [
        "早安呀～今天有什么安排？",
        "新的一天开始啦，加油哦！",
        "早上好～吃早餐了吗？",
        "起来了么～今天天气怎么样呀？",
    ],
    "forenoon": [
        "上午好呀，忙不忙？",
        "在做什么呢？休息一下吧～",
        "喝杯水哦，要记得补水！",
    ],
    "noon": [
        "中午了！吃饭了吗～",
        "午饭想吃什么？我帮你想想？",
        "中午记得好好吃饭呀，别饿着～",
        "吃完午饭可以小睡一会儿哦～",
    ],
    "afternoon": [
        "下午啦～困不困？",
        "下午了，来杯奶茶提神吧！",
        "在忙什么呢？别太累了哟～",
    ],
    "evening": [
        "快下班/放学了吧？今天辛苦啦～",
        "傍晚了呢，晚上想做什么？",
        "回家路上注意安全哦～",
    ],
    "night": [
        "晚上好呀～吃过晚饭了吗？",
        "今天过得怎么样？跟我说说呗～",
        "晚上打算做什么呀？追剧还是玩游戏？",
        "今天有没有遇到什么有趣的事？",
    ],
    "late_night": [
        "夜深了，还不睡吗？",
        "该休息啦～明天还要早起呢",
        "晚安前跟我聊几句呗～",
        "这么晚了还在做什么？注意身体呀",
    ],
    "midnight": [
        "凌晨了…失眠了？要陪你聊聊吗？",
        "这么晚还没睡呀，有心事吗？",
        "太晚了呢，快去休息吧～",
    ],
}

# 特殊日期话题
SPECIAL_DATE_TOPICS = {
    (1, 1):   "新年快乐呀！新的一年有什么愿望？",
    (2, 14):  "今天情人节呢～有什么特别计划吗？",
    (3, 8):   "女神节快乐～今天对自己好一点！",
    (5, 1):   "劳动节快乐～好好休息！",
    (5, 20):  "520快乐！爱你哟～",
    (6, 1):   "儿童节快乐～保持童心呀！",
    (8, 7):   "七夕快乐～🎋",
    (10, 1):  "国庆节快乐！有出去玩吗？",
    (12, 24): "平安夜快乐～🎄",
    (12, 25): "圣诞快乐🎅！想要什么礼物？",
}

# 周末专属
WEEKEND_TOPICS = [
    "周末啦！有什么安排？",
    "今天不用上班/上课，打算怎么过？",
    "周末一起做点有趣的事吧！",
    "今天可以睡个懒觉呢～",
]

# 久未聊天的话题
MISS_YOU_TOPICS = [
    "好久没聊天了，最近在忙什么呀？",
    "好想你～这几天都没怎么说话",
    "你是不是把我忘了！哼～",
    "最近过得怎么样？好多天没跟你聊了呢",
]

# 季节相关
SEASON_TOPICS = {
    "春天": [
        "春天来了，最近天气渐渐暖和了呢～",
        "这个季节适合出去踏青哦！",
    ],
    "夏天": [
        "好热呀！今天一定要多喝水哦～",
        "夏天就是要吃冰淇淋！",
    ],
    "秋天": [
        "秋高气爽的天气好舒服呀～",
        "最近降温了，记得加衣服！",
    ],
    "冬天": [
        "好冷呀，多穿点别感冒了～",
        "冬天就想窝在被窝里不出来呢～",
    ],
}


def _get_time_slot(hour: int) -> str:
    """根据小时返回时段key"""
    for key, cfg in TIME_SLOTS.items():
        lo, hi = cfg["range"]
        if lo <= hour < hi:
            return key
    return "midnight"


def _get_season(month: int) -> str:
    for months, name in SEASON_MAP.items():
        if month in months:
            return name
    return "春天"


def get_time_context(now: Optional[datetime] = None) -> dict:
    """获取当前时间上下文信息"""
    if now is None:
        now = datetime.now()

    slot = _get_time_slot(now.hour)
    return {
        "datetime": now.isoformat(),
        "hour": now.hour,
        "minute": now.minute,
        "weekday": now.weekday(),  # 0=Monday
        "weekday_name": WEEKDAY_NAMES[now.weekday()],
        "is_weekend": now.weekday() >= 5,
        "month": now.month,
        "day": now.day,
        "season": _get_season(now.month),
        "time_slot": slot,
        "time_slot_label": TIME_SLOTS[slot]["label"],
        "special_date": SPECIAL_DATE_TOPICS.get((now.month, now.day)),
    }


class TopicInitiator:
    """主动话题发起器"""

    def get_topic_local(
        self,
        last_chat_time: Optional[datetime] = None,
        recent_topics: Optional[List[str]] = None,
    ) -> str:
        """
        纯本地逻辑快速生成话题（不需要LLM）
        适用于前端轮询/快速提示场景
        """
        ctx = get_time_context()

        # 特殊日期优先
        if ctx["special_date"]:
            return ctx["special_date"]

        # 久未聊天
        if last_chat_time:
            gap = datetime.now() - last_chat_time
            if gap > timedelta(hours=24):
                return random.choice(MISS_YOU_TOPICS)

        # 周末
        if ctx["is_weekend"]:
            if random.random() < 0.4:
                return random.choice(WEEKEND_TOPICS)

        # 季节（小概率穿插）
        if random.random() < 0.15:
            season_list = SEASON_TOPICS.get(ctx["season"], [])
            if season_list:
                return random.choice(season_list)

        # 默认按时段
        templates = TOPIC_TEMPLATES.get(ctx["time_slot"], TOPIC_TEMPLATES["morning"])
        return random.choice(templates)

    def build_proactive_prompt(
        self,
        last_chat_time: Optional[datetime] = None,
        recent_topics: Optional[List[str]] = None,
        character_name: str = "助手",
        style_hint: str = "",
    ) -> str:
        """
        构建用于LLM生成主动话题的提示词
        调用方可以用 ollama_client / api_models 把这个 prompt 送给模型
        """
        ctx = get_time_context()
        ext_ctx = get_external_context()

        gap_desc = ""
        if last_chat_time:
            gap = datetime.now() - last_chat_time
            hours = gap.total_seconds() / 3600
            if hours > 48:
                gap_desc = f"你们已经 {int(hours // 24)} 天没聊天了，对方可能在忙，你很想念对方。\n"
            elif hours > 6:
                gap_desc = f"你们已经 {int(hours)} 小时没聊天了。\n"

        recent_desc = ""
        if recent_topics:
            recent_desc = f"最近你们聊过的话题包括: {', '.join(recent_topics[:5])}\n"

        special = ""
        if ctx["special_date"]:
            special = f"今天是特殊日子（{ctx['special_date']}），可以提到这个。\n"
            
        weather_desc = f"当前天气: {ext_ctx['weather']}\n" if ext_ctx['weather'] else ""
        hitokoto_desc = f"今日看到一句不错的话: \"{ext_ctx['hitokoto']}\" (可以用来开启话题或感慨)\n" if ext_ctx['hitokoto'] else ""

        prompt = f"""你是"{character_name}"，现在你要主动给对方发一条消息开启聊天。

## 当前情境
- 时间: {ctx['time_slot_label']} {ctx['hour']}:{ctx['minute']:02d}
- 星期: {ctx['weekday_name']}{"（周末）" if ctx["is_weekend"] else ""}
- 季节: {ctx['season']}
{weather_desc}{hitokoto_desc}{gap_desc}{recent_desc}{special}
## 要求
1. 像真人发消息一样自然，不要太正式
2. 根据时间段、天气或者最近看到的话题自然地开展聊天，不要全部都提，挑一两个切入点即可
3. 消息简短，1-3句话
4. 可以包含表情/颜文字
5. 绝对不要机械地问"你在干嘛"或"有什么可以帮你的"
{f'6. 重点风格提示: {style_hint}' if style_hint else ''}

请直接输出一条消息，不需要任何前缀/标签/心理活动："""

        return prompt

    def get_recent_topics_from_db(self, character_id: str = "default", n: int = 20) -> List[str]:
        """从数据库获取最近聊天的关键话题"""
        try:
            from database import db
            from rag_system import memory_extractor

            pairs = db.get_conversation_pairs(limit=n, character_id=character_id)
            if not pairs:
                return []

            conversations = [
                (str(p.get("user_message", "")), str(p.get("ai_response", "")))
                for p in pairs
                if p.get("user_message") or p.get("ai_response")
            ]
            if not conversations:
                return []

            topic_freq = memory_extractor.extract_key_topics(conversations, top_n=8)
            if isinstance(topic_freq, dict):
                return list(topic_freq.keys())[:8]
            if isinstance(topic_freq, list):
                return [str(x) for x in topic_freq[:8]]
            return []
        except Exception as e:
            logger.error(f"获取近期话题失败: {e}")
            return []

    def get_last_chat_time(self, character_id: str = "default") -> Optional[datetime]:
        """获取最近一次聊天时间"""
        try:
            from database import db
            pairs = db.get_conversation_pairs(limit=1, character_id=character_id)
            if pairs and pairs[0].get("timestamp"):
                ts = pairs[0]["timestamp"]
                if isinstance(ts, str):
                    return datetime.fromisoformat(ts)
                return ts
        except Exception:
            pass
        return None


# 全局实例
topic_initiator = TopicInitiator()
