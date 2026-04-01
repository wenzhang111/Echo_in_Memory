"""
每日首启通报模块
在每天第一次启动时，生成更像真人的时间/天气/待办聊天通报。
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from topic_initiator import get_external_context, get_time_context
from anniversary_manager import anniversary_manager

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TODOS_FILE = DATA_DIR / "daily_todos.json"
STATE_FILE = DATA_DIR / "daily_briefing_state.json"

DEFAULT_TODOS = [
    {"title": "确认今天最重要的1件事", "time_hint": "上午", "enabled": True, "weekdays": []},
    {"title": "中午喝水并短暂休息 10 分钟", "time_hint": "中午", "enabled": True, "weekdays": []},
    {"title": "晚上做一次简短复盘", "time_hint": "晚上", "enabled": True, "weekdays": []},
]

GREETING_BY_SLOT = {
    "early_morning": ["早呀", "清晨好"],
    "morning": ["早安", "上午好"],
    "forenoon": ["上午好", "嘿，上午好"],
    "noon": ["中午好", "午安"],
    "afternoon": ["下午好", "下午辛苦啦"],
    "evening": ["傍晚好", "晚上好"],
    "night": ["晚上好", "今天辛苦啦"],
    "late_night": ["夜深啦", "这么晚还在呢"],
    "midnight": ["凌晨好", "还醒着呀"],
}

CLOSINGS = [
    "我会一直在，随时可以找我聊。",
    "如果你愿意，我也可以帮你把今天任务拆成更轻松的小步骤。",
    "今天我们就稳稳推进，不求完美，先完成最关键的一件事。",
]


class DailyBriefingManager:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        if not TODOS_FILE.exists():
            TODOS_FILE.write_text(json.dumps(DEFAULT_TODOS, ensure_ascii=False, indent=2), encoding="utf-8")
        if not STATE_FILE.exists():
            STATE_FILE.write_text(
                json.dumps({"last_sent_date": "", "last_sent_character": ""}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    @staticmethod
    def _safe_read_json(path: Path, default):
        try:
            if not path.exists():
                return default
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _today_str(now: datetime) -> str:
        return now.strftime("%Y-%m-%d")

    def _load_state(self) -> Dict:
        return self._safe_read_json(STATE_FILE, {"last_sent_date": "", "last_sent_character": ""})

    def _save_state(self, state: Dict):
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def _sanitize_todos(self, todos: List[Dict]) -> List[Dict]:
        cleaned: List[Dict] = []
        for item in todos:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue

            time_hint = str(item.get("time_hint", "")).strip()[:20]
            enabled = bool(item.get("enabled", True))

            weekdays_raw = item.get("weekdays", [])
            weekdays: List[int] = []
            if isinstance(weekdays_raw, list):
                for w in weekdays_raw:
                    try:
                        iv = int(w)
                    except Exception:
                        continue
                    if 0 <= iv <= 6:
                        weekdays.append(iv)

            cleaned.append(
                {
                    "title": title[:80],
                    "time_hint": time_hint,
                    "enabled": enabled,
                    "weekdays": sorted(set(weekdays)),
                }
            )
        return cleaned

    def get_todos(self) -> List[Dict]:
        todos = self._safe_read_json(TODOS_FILE, DEFAULT_TODOS)
        if not isinstance(todos, list):
            todos = DEFAULT_TODOS
        cleaned = self._sanitize_todos(todos)
        if not cleaned:
            cleaned = self._sanitize_todos(DEFAULT_TODOS)
        return cleaned

    def update_todos(self, todos: List[Dict]) -> List[Dict]:
        cleaned = self._sanitize_todos(todos)
        if not cleaned:
            cleaned = self._sanitize_todos(DEFAULT_TODOS)
        TODOS_FILE.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
        return cleaned

    def get_today_todos(self, now: datetime | None = None, limit: int = 4) -> List[Dict]:
        now = now or datetime.now()
        weekday = now.weekday()
        todos = self.get_todos()
        filtered = []
        for t in todos:
            if not t.get("enabled", True):
                continue
            weekdays = t.get("weekdays") or []
            if weekdays and weekday not in weekdays:
                continue
            filtered.append(t)
        return filtered[:limit]

    def should_send_today(self, force: bool = False, now: datetime | None = None) -> bool:
        if force:
            return True
        now = now or datetime.now()
        state = self._load_state()
        return state.get("last_sent_date", "") != self._today_str(now)

    def build_briefing_message(self, character_name: str = "助手", now: datetime | None = None) -> Dict:
        now = now or datetime.now()
        ctx = get_time_context(now)
        ext = get_external_context()
        todos = self.get_today_todos(now)

        greet_candidates = GREETING_BY_SLOT.get(ctx.get("time_slot", "morning"), ["你好"])
        greeting = random.choice(greet_candidates)

        time_line = f"{greeting}，{character_name}来给你做今日小通报啦。现在是 {ctx['hour']:02d}:{ctx['minute']:02d}，{ctx['weekday_name']}。"

        weather = ext.get("weather", "").strip()
        weather_line = f"天气这边我看了一眼：{weather}。" if weather else "天气信息我暂时没拿到，不过我们照样可以把今天安排好。"

        if todos:
            todo_parts = []
            for i, t in enumerate(todos, start=1):
                hint = f"（{t['time_hint']}）" if t.get("time_hint") else ""
                todo_parts.append(f"{i}. {t['title']}{hint}")
            todo_line = "今天我建议你先这样推进：\n" + "\n".join(todo_parts)
        else:
            todo_line = "今天暂时没有预设待办，我们可以一起临时安排。"

        # 纪念日提醒（3 天内）
        anniversary_line = anniversary_manager.build_upcoming_notice(within_days=3)

        quote = ext.get("hitokoto", "").strip()
        quote_line = f"顺便分享一句：\"{quote}\"。" if quote else ""

        closing = random.choice(CLOSINGS)
        message = "\n".join([x for x in [time_line, weather_line, todo_line, anniversary_line, quote_line, closing] if x])

        return {
            "date": self._today_str(now),
            "time_context": ctx,
            "weather": weather,
            "todos": todos,
            "message": message,
        }

    def get_daily_briefing(self, character_name: str = "助手", force: bool = False) -> Dict:
        now = datetime.now()
        if not self.should_send_today(force=force, now=now):
            return {
                "sent": False,
                "date": self._today_str(now),
                "message": "",
                "reason": "already_sent_today",
            }

        payload = self.build_briefing_message(character_name=character_name, now=now)
        state = self._load_state()
        state["last_sent_date"] = payload["date"]
        state["last_sent_character"] = character_name
        self._save_state(state)

        payload["sent"] = True
        payload["reason"] = "generated"
        return payload


daily_briefing_manager = DailyBriefingManager()
