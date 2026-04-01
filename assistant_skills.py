"""
功能性助手模块（可插拔技能注册）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AssistantSkill:
    name: str
    title: str
    description: str
    params: Dict[str, str]
    handler: Callable[[str, Dict[str, Any]], Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "params": self.params,
        }


class FunctionalAssistantHub:
    """模块化功能助手：统一技能注册、发现、执行。"""

    def __init__(
        self,
        character_manager,
        topic_initiator,
        daily_briefing_manager,
        intent_classifier,
        emotion_engine,
        anniversary_manager,
        memory_manager,
    ):
        self.character_manager = character_manager
        self.topic_initiator = topic_initiator
        self.daily_briefing_manager = daily_briefing_manager
        self.intent_classifier = intent_classifier
        self.emotion_engine = emotion_engine
        self.anniversary_manager = anniversary_manager
        self.memory_manager = memory_manager
        self._skills: Dict[str, AssistantSkill] = {}
        self._register_builtin_skills()

    def register(self, skill: AssistantSkill) -> None:
        self._skills[skill.name] = skill

    def list_skills(self) -> List[Dict[str, Any]]:
        return [v.to_dict() for v in self._skills.values()]

    def execute(self, skill_name: str, character_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        skill = self._skills.get(skill_name)
        if not skill:
            return {"status": "error", "detail": f"技能不存在: {skill_name}"}

        cid = character_id or self.character_manager.get_active_id()
        payload = params or {}
        result = skill.handler(cid, payload)
        return {
            "status": "success",
            "skill": skill_name,
            "character_id": cid,
            "result": result,
        }

    def suggest(self, message: str) -> Dict[str, Any]:
        intent = self.intent_classifier.detect(message)
        mapping = {
            "planning_task": ["daily_briefing", "anniversary_upcoming"],
            "advice_request": ["intent_detect", "memory_snapshot"],
            "emotional_support": ["emotion_snapshot", "topic_suggestion"],
            "relationship_talk": ["topic_suggestion", "memory_snapshot"],
            "knowledge_query": ["intent_detect"],
            "casual_chat": ["topic_suggestion"],
        }
        recommended = mapping.get(intent.intent, ["topic_suggestion"])
        return {
            "intent": intent.to_dict(),
            "recommended_skills": recommended,
        }

    def _register_builtin_skills(self) -> None:
        self.register(
            AssistantSkill(
                name="topic_suggestion",
                title="话题建议",
                description="根据当前时间与上下文给出开场话题",
                params={"use_llm": "bool，可选；true 时尝试 LLM 生成"},
                handler=self._skill_topic_suggestion,
            )
        )
        self.register(
            AssistantSkill(
                name="daily_briefing",
                title="每日通报",
                description="生成今日时间/待办/天气通报",
                params={"force": "bool，可选；是否强制生成"},
                handler=self._skill_daily_briefing,
            )
        )
        self.register(
            AssistantSkill(
                name="intent_detect",
                title="意图识别",
                description="识别用户输入意图并返回策略建议",
                params={"message": "string，必填；待识别文本"},
                handler=self._skill_intent_detect,
            )
        )
        self.register(
            AssistantSkill(
                name="emotion_snapshot",
                title="情绪快照",
                description="读取当前角色情绪状态",
                params={},
                handler=self._skill_emotion_snapshot,
            )
        )
        self.register(
            AssistantSkill(
                name="anniversary_upcoming",
                title="纪念日提醒",
                description="查询近期纪念日",
                params={"within_days": "int，可选；默认7"},
                handler=self._skill_anniversary_upcoming,
            )
        )
        self.register(
            AssistantSkill(
                name="memory_snapshot",
                title="记忆摘要",
                description="读取当前角色记忆上下文摘要",
                params={"topic": "string，可选；主题关键词"},
                handler=self._skill_memory_snapshot,
            )
        )

    def _skill_topic_suggestion(self, cid: str, params: Dict[str, Any]) -> Dict[str, Any]:
        use_llm = bool(params.get("use_llm", False))
        last_time = self.topic_initiator.get_last_chat_time(cid)
        recent_topics = self.topic_initiator.get_recent_topics_from_db(cid, n=20)
        topic = self.topic_initiator.get_topic_local(last_time, recent_topics)
        return {
            "topic": topic,
            "source": "local",
            "use_llm_requested": use_llm,
            "timestamp": datetime.now().isoformat(),
        }

    def _skill_daily_briefing(self, cid: str, params: Dict[str, Any]) -> Dict[str, Any]:
        force = bool(params.get("force", False))
        char = self.character_manager.get_character(cid)
        char_name = char.name if char else "助手"
        return self.daily_briefing_manager.get_daily_briefing(character_name=char_name, force=force)

    def _skill_intent_detect(self, cid: str, params: Dict[str, Any]) -> Dict[str, Any]:
        message = str(params.get("message", "")).strip()
        return self.intent_classifier.detect(message).to_dict()

    def _skill_emotion_snapshot(self, cid: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.emotion_engine.load(cid).badge_data()

    def _skill_anniversary_upcoming(self, cid: str, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            within_days = int(params.get("within_days", 7))
        except Exception:
            within_days = 7
        within_days = max(1, min(60, within_days))
        items = self.anniversary_manager.get_upcoming(within_days=within_days)
        return {
            "within_days": within_days,
            "count": len(items),
            "anniversaries": items,
        }

    def _skill_memory_snapshot(self, cid: str, params: Dict[str, Any]) -> Dict[str, Any]:
        topic = str(params.get("topic", "")).strip() or None
        context_text = self.memory_manager.get_memory_context(topic=topic)
        top_memories = self.memory_manager.get_ranked_memories(limit=6, emotion_priority=True)
        return {
            "topic": topic or "",
            "context": context_text,
            "top_memories": top_memories,
        }
