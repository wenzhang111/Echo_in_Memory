"""
对话意图识别模块（规则版）
用于给回复策略提供额外上下文，而不是替代模型生成。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class IntentResult:
    intent: str
    confidence: float
    strategy: str
    evidence: List[str]

    def to_dict(self) -> Dict:
        return {
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "strategy": self.strategy,
            "evidence": self.evidence,
        }


INTENT_STRATEGY = {
    "emotional_support": "先共情和安抚，再给轻量建议，避免说教。",
    "advice_request": "先澄清目标和约束，再给结构化建议和可执行步骤。",
    "planning_task": "输出清晰计划：目标、步骤、优先级、下一步。",
    "relationship_talk": "回应情感需求，语言更温柔，主动确认关系感受。",
    "knowledge_query": "给简洁准确答案，必要时给1-2个例子。",
    "casual_chat": "自然闲聊，延续上下文并抛出一个轻追问。",
}

INTENT_KEYWORDS = {
    "emotional_support": ["难受", "焦虑", "崩溃", "压力", "烦", "委屈", "失眠", "不开心", "想哭"],
    "advice_request": ["怎么办", "怎么做", "建议", "给我个方案", "帮我分析", "如何"],
    "planning_task": ["计划", "安排", "待办", "复盘", "拆解", "步骤", "路线图"],
    "relationship_talk": ["爱", "喜欢", "想你", "陪我", "抱抱", "亲爱的", "我们", "关系"],
    "knowledge_query": ["是什么", "为什么", "原理", "区别", "定义", "怎么理解"],
}


class IntentClassifier:
    """轻量规则分类器，强调稳定和可解释性。"""

    def detect(self, text: str) -> IntentResult:
        text = (text or "").strip()
        if not text:
            return IntentResult(
                intent="casual_chat",
                confidence=0.4,
                strategy=INTENT_STRATEGY["casual_chat"],
                evidence=["empty_input"],
            )

        scores: Dict[str, float] = {k: 0.0 for k in INTENT_STRATEGY}
        evidence: Dict[str, List[str]] = {k: [] for k in INTENT_STRATEGY}

        for intent, words in INTENT_KEYWORDS.items():
            for w in words:
                if w in text:
                    scores[intent] += 1.0
                    evidence[intent].append(w)

        # 语气增强特征
        if re.search(r"[?？]", text):
            scores["advice_request"] += 0.2
            scores["knowledge_query"] += 0.2
        if len(text) > 40:
            scores["planning_task"] += 0.2
        if re.search(r"(救命|撑不住|好难)", text):
            scores["emotional_support"] += 0.8
            evidence["emotional_support"].append("strong_emotion")

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        if best_score <= 0:
            best_intent = "casual_chat"
            best_score = 0.6
            evidence[best_intent].append("fallback")

        confidence = min(0.98, 0.55 + best_score * 0.12)

        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            strategy=INTENT_STRATEGY[best_intent],
            evidence=evidence[best_intent][:5],
        )


intent_classifier = IntentClassifier()
