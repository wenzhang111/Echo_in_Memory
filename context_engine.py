"""
智能上下文引擎 - Token感知的结构化上下文管理

核心能力:
1. Token预算管理 — 防止上下文溢出模型窗口
2. 结构化消息构建 — 输出 Ollama /api/chat 格式的 messages 数组
3. 优先级裁剪 — 预算不足时自动保留最重要的上下文
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """估算中英文混合文本的 token 数（UTF-8 字节 / 3 的近似值）。"""
    if not text:
        return 0
    return max(1, len(text.encode("utf-8")) // 3)


class ContextEngine:
    """
    Token感知的智能上下文构建器。

    将系统提示、记忆、对话历史、RAG检索结果、意图/情绪上下文
    整合为结构化的 messages 数组，并在 token 预算内自动裁剪。
    """

    def __init__(self, max_context_tokens: int = 6000):
        self.max_context_tokens = max_context_tokens

    # ──────────────────────────────────────────
    # 对外主入口
    # ──────────────────────────────────────────
    def build_messages(
        self,
        system_prompt: str,
        intent_context: str = "",
        emotion_context: str = "",
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rag_results: Optional[List[Dict]] = None,
        user_input: str = "",
    ) -> List[Dict[str, str]]:
        """
        构建结构化 messages 数组。

        参数
        ----
        system_prompt      : 角色设定 + 记忆 + 性格（已合并的完整系统提示词）
        intent_context     : 意图识别结果（可选）
        emotion_context    : 情绪追踪结果（可选）
        conversation_history : [{"role":"user"/"assistant","content":"..."}]
        rag_results        : 语义检索到的相似对话列表
        user_input         : 当前用户输入

        返回
        ----
        List[{"role": "system"/"user"/"assistant", "content": "..."}]
        """
        total_budget = self.max_context_tokens
        messages: List[Dict[str, str]] = []

        # ── 1. 构建 system 消息 ──────────────────────
        system_parts = [system_prompt]
        if emotion_context:
            system_parts.append(emotion_context)
        if intent_context:
            system_parts.append(intent_context)
        if rag_results:
            rag_text = self._format_rag(rag_results)
            if rag_text:
                system_parts.append(rag_text)

        full_system = "\n\n".join(p for p in system_parts if p)
        system_tokens = estimate_tokens(full_system)

        # system 消息最多占 50% 预算
        system_ceiling = int(total_budget * 0.50)
        if system_tokens > system_ceiling:
            full_system = self._truncate(full_system, system_ceiling)
            system_tokens = system_ceiling

        messages.append({"role": "system", "content": full_system})
        used_tokens = system_tokens

        # ── 2. 对话历史（多轮 user/assistant）─────────
        # 留出空间给当前用户输入 + 一点余量
        input_tokens = estimate_tokens(user_input)
        history_budget = total_budget - used_tokens - input_tokens - 50
        if conversation_history and history_budget > 0:
            history_msgs = self._fit_history(conversation_history, history_budget)
            messages.extend(history_msgs)
            used_tokens += sum(estimate_tokens(m["content"]) for m in history_msgs)

        # ── 3. 当前用户输入 ──────────────────────────
        messages.append({"role": "user", "content": user_input})
        used_tokens += input_tokens

        logger.debug(
            f"📊 Context: {used_tokens}/{total_budget} tokens, "
            f"{len(messages)} messages, "
            f"history_turns={len(messages) - 2}"
        )
        return messages

    # ──────────────────────────────────────────
    # Fallback: 拍平为纯文本（给 /api/generate）
    # ──────────────────────────────────────────
    def messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """将 messages 数组拍平为纯文本 prompt。"""
        parts = []
        for m in messages:
            if m["role"] == "system":
                parts.append(m["content"])
            elif m["role"] == "user":
                parts.append(f"用户: {m['content']}")
            elif m["role"] == "assistant":
                parts.append(f"我: {m['content']}")
        parts.append("我: ")
        return "\n".join(parts)

    # ──────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────
    @staticmethod
    def _format_rag(results: List[Dict]) -> str:
        if not results:
            return ""
        lines = ["## 相关对话参考 ##"]
        for i, r in enumerate(results[:3], 1):
            u = (r.get("user_message") or "")[:60]
            a = (r.get("ai_response") or "")[:60]
            lines.append(f"{i}. 用户: {u}")
            lines.append(f"   回复: {a}")
        return "\n".join(lines)

    @staticmethod
    def _truncate(text: str, max_tokens: int) -> str:
        current = estimate_tokens(text)
        if current <= max_tokens:
            return text
        ratio = len(text) / max(1, current)
        target = int(max_tokens * ratio * 0.95)
        return text[:target] + "…"

    @staticmethod
    def _fit_history(
        history: List[Dict[str, str]], max_tokens: int
    ) -> List[Dict[str, str]]:
        """从最新的历史向前纳入，直到超出预算。"""
        result: List[Dict[str, str]] = []
        used = 0
        for msg in reversed(history):
            t = estimate_tokens(msg["content"])
            if used + t > max_tokens:
                break
            result.insert(0, msg)
            used += t
        return result


# ── 全局实例 ────────────────────────────────
def _default_budget() -> int:
    try:
        from config import MODEL_CONTEXT_WINDOW
        return MODEL_CONTEXT_WINDOW
    except ImportError:
        return 6000


context_engine = ContextEngine(max_context_tokens=_default_budget())
