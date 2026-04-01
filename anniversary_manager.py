"""
纪念日与提醒管理器

支持添加/编辑/删除纪念日，每天检查即将到来的纪念日并融入每日通报。
"""
from __future__ import annotations

import json
import uuid
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ANNIVERSARIES_FILE = DATA_DIR / "anniversaries.json"

# 常用节日（固定日期，每年循环）
BUILT_IN_ANNIVERSARIES = [
    {"id": "__valentines__", "title": "情人节", "month": 2, "day": 14, "recurring": True, "builtin": True},
    {"id": "__qixi__", "title": "七夕情人节", "month": 7, "day": 7, "recurring": True, "builtin": True, "lunar_note": "农历七月初七（此处以公历近似）"},
    {"id": "__xmas__", "title": "圣诞节", "month": 12, "day": 25, "recurring": True, "builtin": True},
    {"id": "__newyear__", "title": "元旦", "month": 1, "day": 1, "recurring": True, "builtin": True},
]


class Anniversary:
    def __init__(
        self,
        title: str,
        month: int,
        day: int,
        recurring: bool = True,
        year: Optional[int] = None,
        description: str = "",
        id: str = "",
        created_at: str = "",
        builtin: bool = False,
    ):
        self.id = id or str(uuid.uuid4())[:8]
        self.title = title.strip()[:80]
        self.month = int(month)
        self.day = int(day)
        self.recurring = bool(recurring)
        self.year = int(year) if year else None       # 仅一次性纪念日需要年份
        self.description = description.strip()[:200]
        self.created_at = created_at or datetime.now().isoformat()
        self.builtin = builtin

    # ── Validation ─────────────────────────────────────────────────────────
    def is_valid(self) -> bool:
        try:
            date(2024, self.month, self.day)   # 用闰年检测 2 月 29
            return True
        except ValueError:
            return False

    # ── Serialisation ──────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "month": self.month,
            "day": self.day,
            "recurring": self.recurring,
            "year": self.year,
            "description": self.description,
            "created_at": self.created_at,
            "builtin": self.builtin,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Anniversary":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            month=data.get("month", 1),
            day=data.get("day", 1),
            recurring=data.get("recurring", True),
            year=data.get("year"),
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            builtin=data.get("builtin", False),
        )

    # ── Calendar logic ─────────────────────────────────────────────────────
    def next_occurrence(self, today: Optional[date] = None) -> Optional[date]:
        """返回从 today 起（含）的下一个触发日期。不循环且已过期则返回 None。"""
        today = today or date.today()
        if not self.recurring and self.year:
            target = date(self.year, self.month, self.day)
            return target if target >= today else None
        # 循环纪念日
        try:
            candidate = date(today.year, self.month, self.day)
        except ValueError:
            return None
        if candidate < today:
            try:
                candidate = date(today.year + 1, self.month, self.day)
            except ValueError:
                return None
        return candidate

    def days_until(self, today: Optional[date] = None) -> Optional[int]:
        """返回距下次出现的天数，已过期不循环的返回 None。"""
        nxt = self.next_occurrence(today)
        if nxt is None:
            return None
        return (nxt - (today or date.today())).days


class AnniversaryManager:
    """纪念日 CRUD + 查询"""

    def __init__(self):
        self._ensure_file()

    def _ensure_file(self):
        if not ANNIVERSARIES_FILE.exists():
            ANNIVERSARIES_FILE.write_text("[]", encoding="utf-8")

    def _load_all(self) -> List[Anniversary]:
        try:
            raw = json.loads(ANNIVERSARIES_FILE.read_text(encoding="utf-8"))
            return [Anniversary.from_dict(r) for r in raw if isinstance(r, dict)]
        except Exception:
            return []

    def _save_all(self, items: List[Anniversary]):
        ANNIVERSARIES_FILE.write_text(
            json.dumps([a.to_dict() for a in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── CRUD ───────────────────────────────────────────────────────────────
    def list_anniversaries(self, include_builtin: bool = True) -> List[dict]:
        items = self._load_all()
        result = []
        if include_builtin:
            # 内置节日
            for b in BUILT_IN_ANNIVERSARIES:
                a = Anniversary.from_dict(b)
                d = a.to_dict()
                d["days_until"] = a.days_until()
                d["next_occurrence"] = (a.next_occurrence() or "").isoformat() if a.next_occurrence() else None
                result.append(d)
        for a in items:
            d = a.to_dict()
            d["days_until"] = a.days_until()
            nxt = a.next_occurrence()
            d["next_occurrence"] = nxt.isoformat() if nxt else None
            result.append(d)
        # 按 days_until 升序
        result.sort(key=lambda x: (x["days_until"] if x["days_until"] is not None else 9999))
        return result

    def get_anniversary(self, ann_id: str) -> Optional[Anniversary]:
        for a in self._load_all():
            if a.id == ann_id:
                return a
        return None

    def create_anniversary(self, data: dict) -> Anniversary:
        a = Anniversary(
            title=data.get("title", "新纪念日"),
            month=data.get("month", 1),
            day=data.get("day", 1),
            recurring=data.get("recurring", True),
            year=data.get("year"),
            description=data.get("description", ""),
        )
        if not a.is_valid():
            raise ValueError(f"无效日期: {a.month}/{a.day}")
        items = self._load_all()
        items.append(a)
        self._save_all(items)
        return a

    def update_anniversary(self, ann_id: str, data: dict) -> Optional[Anniversary]:
        items = self._load_all()
        for i, a in enumerate(items):
            if a.id == ann_id:
                for field in ("title", "month", "day", "recurring", "year", "description"):
                    if field in data:
                        setattr(a, field, data[field])
                if not a.is_valid():
                    raise ValueError(f"无效日期: {a.month}/{a.day}")
                items[i] = a
                self._save_all(items)
                return a
        return None

    def delete_anniversary(self, ann_id: str) -> bool:
        items = self._load_all()
        new_items = [a for a in items if a.id != ann_id]
        if len(new_items) == len(items):
            return False
        self._save_all(new_items)
        return True

    # ── Upcoming ───────────────────────────────────────────────────────────
    def get_upcoming(self, within_days: int = 7, today: Optional[date] = None) -> List[dict]:
        """返回 within_days 天内到期的纪念日（含内置）"""
        today = today or date.today()
        result = []
        all_items = [Anniversary.from_dict(b) for b in BUILT_IN_ANNIVERSARIES] + self._load_all()
        for a in all_items:
            d = a.days_until(today)
            if d is not None and 0 <= d <= within_days:
                entry = a.to_dict()
                entry["days_until"] = d
                nxt = a.next_occurrence(today)
                entry["next_occurrence"] = nxt.isoformat() if nxt else None
                result.append(entry)
        result.sort(key=lambda x: x["days_until"])
        return result

    def build_upcoming_notice(self, within_days: int = 7) -> str:
        """生成纪念日提醒文本，供每日通报使用"""
        upcoming = self.get_upcoming(within_days)
        if not upcoming:
            return ""
        lines = []
        for a in upcoming:
            d = a["days_until"]
            if d == 0:
                lines.append(f"🎉 今天是【{a['title']}】！")
            elif d == 1:
                lines.append(f"⏰ 明天是【{a['title']}】，别忘了！")
            else:
                lines.append(f"📅 还有 {d} 天是【{a['title']}】")
        return "\n".join(lines)


# 全局单例
anniversary_manager = AnniversaryManager()
