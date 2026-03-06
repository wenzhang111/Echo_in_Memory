"""
回复增强管线 - 提升 LLM 输出质量

功能:
1. 清理思维链标签 <think>...</think>
2. 去除角色泄漏前缀（"AI:" "系统:" 等）
3. 去除过度重复的句子
4. 修剪不完整尾部
5. 质量评分（0~1）
6. 按意图动态调参（temperature / max_tokens / top_p）
"""
import re
import logging
from typing import Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── 意图 → 最优生成参数 ─────────────────────
INTENT_PARAMS: Dict[str, Dict] = {
    "emotional_support": dict(
        temperature=0.85, max_tokens=512, top_p=0.92,
        desc="情感支持：更有温度和创意",
    ),
    "advice_request": dict(
        temperature=0.50, max_tokens=600, top_p=0.85,
        desc="建议咨询：精确结构化",
    ),
    "planning_task": dict(
        temperature=0.40, max_tokens=700, top_p=0.80,
        desc="任务规划：条理清晰",
    ),
    "relationship_talk": dict(
        temperature=0.80, max_tokens=400, top_p=0.90,
        desc="亲密对话：温暖自然",
    ),
    "knowledge_query": dict(
        temperature=0.30, max_tokens=500, top_p=0.80,
        desc="知识回答：准确精炼",
    ),
    "casual_chat": dict(
        temperature=0.75, max_tokens=256, top_p=0.90,
        desc="闲聊模式：轻松活泼",
    ),
}


@dataclass
class EnhancedResponse:
    text: str
    quality_score: float
    was_cleaned: bool
    cleaning_notes: list = field(default_factory=list)


class ResponseEnhancer:
    """回复增强管线"""

    _THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
    _ROLE_RE = re.compile(
        r"^(?:系统|System|系统提示|AI|Assistant|我|回复|助手)[：:]\s*",
        re.MULTILINE,
    )

    # ─── 动态调参 ──────────────────────────────
    def get_dynamic_params(self, intent: str) -> Dict:
        """
        根据意图返回最佳生成参数。

        返回 dict 包含 temperature, max_tokens, top_p, desc
        """
        params = INTENT_PARAMS.get(intent, INTENT_PARAMS["casual_chat"]).copy()
        return params

    # ─── 增强管线 ──────────────────────────────
    def enhance(self, raw: str) -> EnhancedResponse:
        """
        对原始 LLM 输出执行增强管线：
        1) 清理 <think> 标签
        2) 去除角色前缀泄漏
        3) 去除重复句子
        4) 修剪不完整尾部
        5) 质量评分
        """
        if not raw:
            return EnhancedResponse("", 0.0, False, ["empty"])

        text = raw
        notes: list = []

        # 1. thinking tags
        cleaned = self._THINK_RE.sub("", text)
        if len(cleaned) < len(text):
            notes.append("removed_think_tags")
            text = cleaned.strip()

        # 2. role-prefix leak
        cleaned = self._ROLE_RE.sub("", text)
        if len(cleaned) < len(text):
            notes.append("removed_role_prefix")
            text = cleaned.strip()

        # 3. dedup sentences
        deduped = self._dedup_sentences(text)
        if len(deduped) < len(text):
            notes.append("removed_repetition")
            text = deduped

        # 4. trailing trim
        text = self._trim_tail(text)

        score = self._score(text)
        return EnhancedResponse(text, score, bool(notes), notes)

    # ─── 流式过滤：实时去除 <think> 块 ─────────
    def create_stream_filter(self):
        """
        返回一个有状态的过滤函数，供流式生成时逐 chunk 调用。

        用法:
            filt = enhancer.create_stream_filter()
            for chunk in stream:
                out = filt(chunk)
                if out:
                    yield out
        """
        state = {"in_think": False, "buf": ""}

        def _filter(chunk: str) -> str:
            if not chunk:
                return ""

            result_parts = []
            buf = state["buf"] + chunk

            while buf:
                if not state["in_think"]:
                    idx = buf.find("<think>")
                    if idx == -1:
                        # 安全区域，但末尾可能有 "<" 等不完整标签
                        safe_end = len(buf)
                        # 保留最后 7 个字符以防 <think> 被截断
                        if len(buf) > 7 and "<" in buf[-7:]:
                            safe_end = buf.rfind("<", max(0, len(buf) - 7))
                            if safe_end < 0:
                                safe_end = len(buf)
                        result_parts.append(buf[:safe_end])
                        buf = buf[safe_end:]
                        break
                    else:
                        result_parts.append(buf[:idx])
                        state["in_think"] = True
                        buf = buf[idx + 7:]  # skip "<think>"
                else:
                    idx = buf.find("</think>")
                    if idx == -1:
                        buf = ""  # 全部丢弃（仍在 think 块内）
                        break
                    else:
                        state["in_think"] = False
                        buf = buf[idx + 8:]  # skip "</think>"

            state["buf"] = buf
            return "".join(result_parts)

        return _filter

    # ──── 内部方法 ─────────────────────────────
    @staticmethod
    def _dedup_sentences(text: str) -> str:
        parts = re.split(r"([。！？\n])", text)
        seen: Dict[str, int] = {}
        out = []
        i = 0
        while i < len(parts):
            s = parts[i].strip()
            sep = parts[i + 1] if i + 1 < len(parts) else ""
            i += 2
            if not s:
                continue
            key = s[:20]
            seen[key] = seen.get(key, 0) + 1
            if seen[key] <= 3:
                out.append(s + sep)
        # 可能有落单尾部
        if len(parts) % 2 == 1 and parts[-1].strip():
            out.append(parts[-1])
        return "".join(out) if out else text

    @staticmethod
    def _trim_tail(text: str) -> str:
        if not text:
            return text
        ends = "。！？~♪♥…\n"
        for i in range(len(text) - 1, -1, -1):
            if text[i] in ends:
                # 只在尾部残余不超过 30% 时修剪
                if i > len(text) * 0.7:
                    return text[: i + 1]
                break
        return text

    @staticmethod
    def _score(text: str) -> float:
        if not text:
            return 0.0
        s = 0.5
        if len(text) < 5:
            s -= 0.3
        elif len(text) > 20:
            s += 0.1
        if len(text) > 10:
            s += (len(set(text)) / len(text)) * 0.2
        if any(c in text for c in "。！？~"):
            s += 0.1
        return max(0.0, min(1.0, round(s, 3)))


# ── 全局实例 ─────────────────────────────────
response_enhancer = ResponseEnhancer()
