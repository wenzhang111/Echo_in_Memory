"""
主程序 - FastAPI 服务 + 聊天管理
"""
import os
import sys
import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import db
from rag_system import rag_system
from memory_manager import memory_manager
from ollama_client import chat_manager
from api_models import model_manager
from optimized_rag import optimized_rag
from character_manager import character_manager, Character, WRITING_STYLE_PRESETS
from style_learner import StyleLearner
from topic_initiator import topic_initiator, get_time_context
from intent_classifier import intent_classifier
from daily_briefing import daily_briefing_manager
from emotion_engine import emotion_engine
from anniversary_manager import anniversary_manager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="言忆",
    description="基于本地与外部模型的虚拟伴侣系统，具备记忆与风格学习能力",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).parent
WEB_UI_PATH = PROJECT_ROOT / "web_ui.html"
static_dir = PROJECT_ROOT / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class ChatRequest(BaseModel):
    message: str
    use_memory: bool = True
    temperature: float = 0.7
    max_tokens: int = 512


class ChatAPIRequest(BaseModel):
    message: str
    model: str = "ollama"
    use_memory: bool = True
    temperature: float = 0.7
    max_tokens: int = 512


class IntentDetectRequest(BaseModel):
    message: str


class MemoryUpdateRequest(BaseModel):
    category: Optional[str] = None
    key: Optional[str] = None
    content: Optional[str] = None
    importance_score: Optional[float] = None


class MemoryCorrectionRequest(BaseModel):
    memory_id: int
    corrected_content: str
    correction_reason: str = ""


class StyleControlRequest(BaseModel):
    style_strength: Optional[str] = None
    negative_constraints: Optional[List[str]] = None


class DailyTodoItem(BaseModel):
    title: str
    time_hint: str = ""
    enabled: bool = True
    weekdays: List[int] = Field(default_factory=list)


class DailyTodosUpdateRequest(BaseModel):
    todos: List[DailyTodoItem]


class EmotionUpdateRequest(BaseModel):
    happy: Optional[float] = None
    anxious: Optional[float] = None
    missing: Optional[float] = None
    tired: Optional[float] = None
    excited: Optional[float] = None


class AnniversaryCreateRequest(BaseModel):
    title: str
    month: int
    day: int
    recurring: bool = True
    year: Optional[int] = None
    description: str = ""


class AnniversaryUpdateRequest(BaseModel):
    title: Optional[str] = None
    month: Optional[int] = None
    day: Optional[int] = None
    recurring: Optional[bool] = None
    year: Optional[int] = None
    description: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("🚀 言忆系统启动")
    logger.info("=" * 60)

    try:
        if chat_manager.ollama.check_connection():
            models = chat_manager.ollama.get_available_models()
            logger.info(f"✓ Ollama 可用模型: {', '.join(models)}")
        else:
            logger.warning("⚠️ Ollama 未连接，可先使用 /chat-api 外部模型")
    except Exception as exc:
        logger.warning(f"⚠️ Ollama 检查失败: {exc}")

    logger.info(f"📊 当前对话记录: {db.get_conversation_count()} 条")

    def _preload_rag():
        try:
            rag_system.vector_store.preload()
            logger.info("✓ RAG 向量模型预加载完成")
        except Exception as exc:
            logger.warning(f"⚠️ RAG 预加载失败（不影响运行）: {exc}")

    threading.Thread(target=_preload_rag, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
async def serve_web_ui():
    if WEB_UI_PATH.exists():
        return WEB_UI_PATH.read_text(encoding="utf-8")
    return "<h1>Web UI 文件不存在</h1><p>请检查 web_ui.html</p>"


@app.get("/api/info")
async def api_info():
    return {
        "name": "言忆",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    try:
        ollama_online = chat_manager.ollama.check_connection()
    except Exception:
        ollama_online = False

    return {
        "status": "ok" if ollama_online else "degraded",
        "ollama_connected": ollama_online,
        "conversations": db.get_conversation_count(),
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        if not chat_manager.ollama.check_connection():
            raise HTTPException(status_code=503, detail="Ollama 未运行，请先执行 ollama serve")

        response = chat_manager.chat(
            request.message,
            use_memory=request.use_memory,
            temperature=request.temperature,
            num_predict=request.max_tokens,
        )
        if not response:
            raise HTTPException(status_code=503, detail="本地模型未返回内容")

        return {
            "status": "success",
            "user_message": request.message,
            "ai_response": response,
            "timestamp": datetime.now().isoformat(),
            "message_count": db.get_conversation_count(),
            "emotion": emotion_engine.update_from_text(
                character_manager.get_active_id(), request.message, response
            ).badge_data(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("/chat 调用失败")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/chat/stream")
async def chat_stream(message: str, use_memory: bool = True, temperature: float = 0.7, max_tokens: int = 512):
    def generate():
        parts = []
        try:
            for chunk in chat_manager.chat_stream(
                message,
                use_memory=use_memory,
                temperature=temperature,
                num_predict=max_tokens,
            ):
                parts.append(chunk)
                payload = json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

            full_text = "".join(parts)
            done_payload = json.dumps(
                {"type": "done", "full_response": full_text, "message_count": db.get_conversation_count()},
                ensure_ascii=False,
            )
            yield f"data: {done_payload}\n\n"
        except Exception as exc:
            err = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/list-models")
async def list_models():
    try:
        available = model_manager.get_available_models()
        return {"status": "success", "available_models": available, "count": len(available)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"列举模型失败: {exc}")


@app.post("/chat-api")
async def chat_with_api(request: ChatAPIRequest):
    try:
        intent_result = intent_classifier.detect(request.message)
        context_parts = [memory_manager.get_intent_context(request.message)]
        if request.use_memory:
            context_parts.insert(0, memory_manager.get_memory_context())
        context = "\n".join([c for c in context_parts if c])

        response = await model_manager.generate(
            message=request.message,
            model_name=request.model,
            context=context,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        if not response:
            raise HTTPException(status_code=500, detail="外部模型返回空响应")

        active_id = character_manager.get_active_id()
        db.add_conversation_pair(
            user_message=request.message,
            ai_response=response,
            context_tags=[
                f"intent:{intent_result.intent}",
                f"intent_conf:{intent_result.confidence:.2f}",
            ],
            quality_score=0.8,
            character_id=active_id,
        )
        character_manager.add_chat_message(active_id, request.message, response)
        emotion_state = emotion_engine.update_from_text(active_id, request.message, response)
        memory_manager.boost_emotional_memories(request.message, response)

        return {
            "status": "success",
            "user_message": request.message,
            "ai_response": response,
            "model_used": request.model,
            "timestamp": datetime.now().isoformat(),
            "message_count": db.get_conversation_count(),
            "emotion": emotion_state.badge_data(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("/chat-api 调用失败")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/chat-api/stream")
async def chat_api_stream(request: ChatAPIRequest):
    async def generate():
        try:
            intent_result = intent_classifier.detect(request.message)
            context_parts = [memory_manager.get_intent_context(request.message)]
            if request.use_memory:
                context_parts.insert(0, memory_manager.get_memory_context())
            context = "\n".join([c for c in context_parts if c])

            response = await model_manager.generate(
                message=request.message,
                model_name=request.model,
                context=context,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            if not response:
                payload = json.dumps({"type": "error", "message": "模型返回空响应"}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                return

            active_id = character_manager.get_active_id()
            db.add_conversation_pair(
                user_message=request.message,
                ai_response=response,
                context_tags=[
                    f"intent:{intent_result.intent}",
                    f"intent_conf:{intent_result.confidence:.2f}",
                ],
                quality_score=0.8,
                character_id=active_id,
            )
            character_manager.add_chat_message(active_id, request.message, response)
            emotion_state = emotion_engine.update_from_text(active_id, request.message, response)
            memory_manager.boost_emotional_memories(request.message, response)

            for char in response:
                payload = json.dumps({"type": "chunk", "content": char}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

            done = json.dumps(
                {
                    "type": "done",
                    "full_response": response,
                    "message_count": db.get_conversation_count(),
                    "emotion": emotion_state.badge_data(),
                },
                ensure_ascii=False,
            )
            yield f"data: {done}\n\n"
        except Exception as exc:
            err = json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False)
            yield f"data: {err}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/characters")
async def list_characters():
    chars = character_manager.list_characters()
    active_id = character_manager.get_active_id()
    return {"status": "success", "characters": chars, "active_id": active_id, "count": len(chars)}


@app.post("/characters")
async def create_character(data: dict):
    try:
        char = Character(
            name=data.get("name", "新角色"),
            age=data.get("age", "20"),
            occupation=data.get("occupation", ""),
            city=data.get("city", ""),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", "你是一个虚拟助手。"),
            writing_style=data.get("writing_style", "温柔撒娇"),
            writing_style_custom=data.get("writing_style_custom", ""),
            avatar_emoji=data.get("avatar_emoji", "💕"),
        )
        character_manager.save_character(char)
        return {"status": "success", "character": char.to_dict()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/characters/{char_id}")
async def get_character(char_id: str):
    char = character_manager.get_character(char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    result = char.to_dict()
    result["chat_stats"] = character_manager.get_chat_stats(char_id)
    return result


@app.put("/characters/{char_id}")
async def update_character(char_id: str, data: dict):
    char = character_manager.update_character(char_id, data)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"status": "success", "character": char.to_dict()}


@app.delete("/characters/{char_id}")
async def delete_character(char_id: str):
    if not character_manager.delete_character(char_id):
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"status": "success", "message": f"角色 {char_id} 已删除"}


@app.post("/characters/{char_id}/activate")
async def activate_character(char_id: str):
    char = character_manager.get_character(char_id)
    if not char:
        raise HTTPException(status_code=404, detail="角色不存在")
    character_manager.set_active(char_id)
    return {"status": "success", "active_id": char_id, "active_name": char.name}


@app.get("/characters/{char_id}/history")
async def get_character_history(char_id: str, limit: int = 100):
    history = character_manager.get_chat_history(char_id, limit=limit)
    return {"status": "success", "history": history, "count": len(history)}


@app.delete("/characters/{char_id}/history")
async def clear_character_history(char_id: str):
    character_manager.clear_chat_history(char_id)
    return {"status": "success", "message": "聊天记录已清空"}


@app.get("/writing-styles")
async def get_writing_styles():
    return {"status": "success", "styles": WRITING_STYLE_PRESETS}


@app.get("/memory/search")
async def search_memory(keyword: str, category: str = None):
    memories = db.get_memories_by_category(category) if category else db.search_memories(keyword)
    return {"keyword": keyword, "results": memories, "count": len(memories)}


@app.get("/memory/context")
async def get_memory_context():
    return {
        "personality_summary": memory_manager.get_personality_summary(),
        "memory_context": memory_manager.get_memory_context(),
    }


@app.get("/memory/all")
async def get_all_memories(category: str = None, limit: int = 50, emotion_priority: bool = False):
    memories = memory_manager.get_ranked_memories(
        category=category,
        limit=limit,
        emotion_priority=emotion_priority,
    )
    return {"total": len(memories), "memories": memories}


@app.get("/memory/{memory_id}")
async def get_memory_item(memory_id: int):
    memory = db.get_memory_by_id(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"status": "success", "memory": memory}


@app.put("/memory/{memory_id}")
async def update_memory_item(memory_id: int, data: MemoryUpdateRequest):
    if data.importance_score is not None and not (0.0 <= data.importance_score <= 1.0):
        raise HTTPException(status_code=400, detail="importance_score 必须在 0~1")

    updated = db.update_long_term_memory(
        memory_id=memory_id,
        category=data.category,
        key=data.key,
        content=data.content,
        importance_score=data.importance_score,
    )
    if not updated:
        existing = db.get_memory_by_id(memory_id)
        if not existing:
            raise HTTPException(status_code=404, detail="记忆不存在")
        raise HTTPException(status_code=400, detail="未提供可更新字段")

    return {"status": "success", "memory": db.get_memory_by_id(memory_id)}


@app.delete("/memory/{memory_id}")
async def delete_memory_item(memory_id: int):
    if not db.delete_long_term_memory(memory_id):
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"status": "success", "deleted_id": memory_id}


@app.post("/memory/correct")
async def correct_memory_item(data: MemoryCorrectionRequest):
    memory = db.get_memory_by_id(data.memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")

    corrected = (data.corrected_content or "").strip()
    if not corrected:
        raise HTTPException(status_code=400, detail="corrected_content 不能为空")

    db.update_long_term_memory(
        memory_id=data.memory_id,
        content=corrected,
        importance_score=max(float(memory.get("importance_score", 0.5)), 0.9),
    )

    if data.correction_reason.strip():
        db.add_long_term_memory(
            category="important_info",
            key=f"memory_fix_{data.memory_id}",
            content=f"用户对记忆#{data.memory_id}进行了纠错：{data.correction_reason.strip()}",
            importance_score=0.95,
        )

    return {
        "status": "success",
        "message": "记忆已纠错",
        "before": memory,
        "after": db.get_memory_by_id(data.memory_id),
    }


@app.post("/memory/correct-priority")
async def correct_memory_item_priority(data: MemoryCorrectionRequest):
    memory = db.get_memory_by_id(data.memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")

    corrected = (data.corrected_content or "").strip()
    if not corrected:
        raise HTTPException(status_code=400, detail="corrected_content 不能为空")

    db.update_long_term_memory(
        memory_id=data.memory_id,
        content=corrected,
        importance_score=0.99,
    )
    db.increment_memory_reference(data.memory_id)
    db.increment_memory_reference(data.memory_id)

    reason = (data.correction_reason or "").strip() or "未提供原因"
    db.add_long_term_memory(
        category="important_info",
        key=f"priority_fix_{data.memory_id}",
        content=f"用户通过高优先通道纠错记忆#{data.memory_id}：{reason}",
        importance_score=0.99,
    )

    return {
        "status": "success",
        "priority": "high",
        "message": "高优先纠错已生效",
        "before": memory,
        "after": db.get_memory_by_id(data.memory_id),
    }


@app.post("/intent/detect")
async def detect_intent(data: IntentDetectRequest):
    result = intent_classifier.detect(data.message)
    return {"status": "success", "result": result.to_dict()}


@app.get("/daily/todos")
async def get_daily_todos():
    todos = daily_briefing_manager.get_todos()
    return {"status": "success", "count": len(todos), "todos": todos}


@app.put("/daily/todos")
async def update_daily_todos(data: DailyTodosUpdateRequest):
    items = []
    for item in data.todos:
        if hasattr(item, "model_dump"):
            items.append(item.model_dump())
        else:
            items.append(item.dict())

    todos = daily_briefing_manager.update_todos(items)
    return {"status": "success", "count": len(todos), "todos": todos}


@app.get("/daily/briefing")
async def get_daily_briefing(character_id: str = None, force: bool = False, persist: bool = True):
    active_id = character_id or character_manager.get_active_id()
    char = character_manager.get_character(active_id)
    char_name = char.name if char else "助手"

    briefing = daily_briefing_manager.get_daily_briefing(character_name=char_name, force=force)

    if briefing.get("sent") and briefing.get("message") and persist:
        db.add_conversation_pair(
            user_message="",
            ai_response=briefing["message"],
            context_tags=["system:daily_briefing", f"date:{briefing.get('date', '')}"],
            quality_score=0.9,
            character_id=active_id,
        )
        character_manager.add_chat_message(active_id, "", briefing["message"])

    return {
        "status": "success",
        "character_id": active_id,
        **briefing,
    }


@app.get("/history")
async def get_conversation_history(limit: int = 50, offset: int = 0, character_id: str = None):
    pairs = db.get_conversation_pairs(limit=limit, offset=offset, character_id=character_id)
    return {
        "total": db.get_conversation_count(character_id),
        "limit": limit,
        "offset": offset,
        "character_id": character_id,
        "conversations": pairs,
    }


@app.get("/history/related")
async def get_related_conversations(query: str, top_k: int = 10):
    results = rag_system.search_relevant_conversations(query, top_k=top_k)
    return {"query": query, "results": results, "count": len(results)}


@app.post("/import/wechat")
async def import_wechat_data(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith(".json"):
            raise HTTPException(status_code=400, detail="仅支持 JSON 文件")

        payload = json.loads((await file.read()).decode("utf-8"))
        if not isinstance(payload, list) or not payload:
            raise HTTPException(status_code=400, detail="JSON 必须是非空数组")

        imported = 0
        active_id = character_manager.get_active_id()
        for i in range(0, len(payload) - 1, 2):
            user_msg = str(payload[i].get("content", "")).strip()
            ai_msg = str(payload[i + 1].get("content", "")).strip()
            if not user_msg or not ai_msg:
                continue
            db.add_conversation_pair(user_message=user_msg, ai_response=ai_msg, quality_score=0.6, character_id=active_id)
            imported += 1

        if imported > 0:
            memory_manager.extract_and_store_memories(force=True, character_id=active_id)

        return {"status": "success", "imported_count": imported, "total_conversations": db.get_conversation_count()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导入失败: {exc}")


@app.post("/import-chat/{chat_type}")
async def import_chat_records(chat_type: str, file: UploadFile = File(...)):
    try:
        if chat_type not in ["weixin", "qq"]:
            raise HTTPException(status_code=400, detail="仅支持 weixin 或 qq")

        data = json.loads((await file.read()).decode("utf-8"))
        messages = data if isinstance(data, list) else data.get("messages", data.get("data", []))
        if not messages:
            raise HTTPException(status_code=400, detail="消息为空")

        imported = 0
        active_id = character_manager.get_active_id()

        if chat_type == "weixin" and isinstance(messages[0], dict) and "isSelf" in messages[0]:
            for i, msg in enumerate(messages):
                if msg.get("isSelf") and msg.get("type") != 10000:
                    content_text = str(msg.get("content", "")).strip()
                    if len(content_text) < 2:
                        continue
                    for j in range(i + 1, min(i + 6, len(messages))):
                        reply = messages[j]
                        if reply.get("type") != 10000 and not reply.get("isSelf"):
                            reply_text = str(reply.get("content", "")).strip()
                            if len(reply_text) >= 2:
                                db.add_conversation_pair(
                                    user_message=content_text,
                                    ai_response=reply_text,
                                    quality_score=0.7,
                                    character_id=active_id,
                                )
                                imported += 1
                                break
        else:
            for i in range(0, len(messages) - 1, 2):
                m1 = messages[i]
                m2 = messages[i + 1]
                c1 = (m1.get("content") or m1.get("text") or "") if isinstance(m1, dict) else str(m1)
                c2 = (m2.get("content") or m2.get("text") or "") if isinstance(m2, dict) else str(m2)
                c1, c2 = str(c1).strip(), str(c2).strip()
                if c1 and c2:
                    db.add_conversation_pair(user_message=c1, ai_response=c2, quality_score=0.6, character_id=active_id)
                    imported += 1

        if imported > 0:
            memory_manager.extract_and_store_memories(force=True, character_id=active_id)

        return {"status": "success", "imported_count": imported, "total_conversations": db.get_conversation_count()}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"导入失败: {exc}")


@app.get("/export/history")
async def export_history():
    pairs = db.get_conversation_pairs(limit=10000)
    return JSONResponse(
        content={
            "export_time": datetime.now().isoformat(),
            "total_conversations": len(pairs),
            "conversations": pairs,
        },
        headers={"Content-Disposition": f"attachment; filename=conversation_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"},
    )


@app.get("/export/memories")
async def export_memories():
    memories = {}
    for cat in ["personality", "relationship", "experience", "preference", "important_info"]:
        memories[cat] = db.get_memories_by_category(cat)
    return JSONResponse(
        content={
            "export_time": datetime.now().isoformat(),
            "memories": memories,
            "personality_traits": db.get_all_personality_traits(),
        },
        headers={"Content-Disposition": f"attachment; filename=memories_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"},
    )


@app.get("/stats")
async def get_statistics():
    pairs = db.get_conversation_pairs(limit=10000)
    avg_length = (sum(len(p.get("ai_response", "")) for p in pairs) / len(pairs)) if pairs else 0
    return {
        "status": "success",
        "total_conversations": db.get_conversation_count(),
        "user_messages": len(pairs),
        "ai_messages": len(pairs),
        "avg_response_length": avg_length,
        "total_memories": len(db.search_memories("")) if pairs else 0,
        "personality_traits": len(db.get_all_personality_traits()),
        "models_available": chat_manager.ollama.get_available_models(),
        "database_path": str(db.db_path),
        "database_size_mb": os.path.getsize(db.db_path) / 1024 / 1024 if os.path.exists(db.db_path) else 0,
    }


@app.get("/stats/optimized")
async def get_statistics_optimized():
    stats = optimized_rag.get_stats()
    return {
        "status": "success",
        "total_conversations": stats["total_conversations"],
        "average_quality": stats["average_quality"],
        "high_quality_count": stats["high_quality_count"],
        "cache_entries": stats["cache_entries"],
        "database_size_mb": os.path.getsize(db.db_path) / 1024 / 1024 if os.path.exists(db.db_path) else 0,
    }


@app.get("/memories/context")
async def get_smart_context(query: str = "", max_results: int = 10):
    context = optimized_rag.get_context_by_semantics(query, max_results) if query else optimized_rag.get_recent_conversations(max_results)
    return {"status": "success", "context": context, "query": query, "max_results": max_results}


@app.get("/memories/recent")
async def get_recent_memories(limit: int = 20):
    return {"status": "success", "context": optimized_rag.get_recent_conversations(limit), "limit": limit}


@app.get("/memories/quality")
async def get_quality_memories(limit: int = 50, threshold: float = 0.7):
    return {
        "status": "success",
        "context": optimized_rag.get_high_quality_memories(limit, threshold),
        "limit": limit,
        "quality_threshold": threshold,
    }


@app.get("/memories")
async def get_memories_by_category():
    return {
        "personality": db.get_memories_by_category("personality")[:50],
        "relationship": db.get_memories_by_category("relationship")[:50],
        "experience": db.get_memories_by_category("experience")[:50],
        "preference": db.get_memories_by_category("preference")[:50],
    }


@app.get("/personality")
async def get_personality_profile():
    char = character_manager.get_active_character()
    profile = char.to_dict()
    profile["summary"] = memory_manager.get_personality_summary()
    profile["traits"] = db.get_all_personality_traits()
    profile["memory_context"] = memory_manager.get_memory_context()
    return profile


@app.post("/personality")
async def save_personality_profile(data: dict):
    active_id = character_manager.get_active_id()
    character_manager.update_character(active_id, data)
    return {"status": "success", "message": "性格档案已保存"}


@app.post("/admin/clear")
async def clear_all_data(confirm: bool = False):
    if not confirm:
        return {"status": "cancelled", "message": "请使用 ?confirm=true 确认清空所有数据"}
    db.clear_all_data()
    return {"status": "success", "message": "所有数据已清空"}


@app.post("/admin/extract-memories")
async def manually_extract_memories():
    active_id = character_manager.get_active_id()
    memory_manager.extract_and_store_memories(force=True, character_id=active_id)
    return {"status": "success", "message": "记忆提取已完成"}


@app.delete("/admin/clear-conversations")
async def clear_conversations(character_id: str = None, confirm: bool = False):
    if not confirm:
        summary = db.get_conversation_pairs_summary(character_id)
        return {
            "status": "preview",
            "message": "请添加 ?confirm=true 确认删除",
            "will_delete": summary.get("total", 0),
            "character_id": character_id or "全部",
            "earliest": summary.get("earliest"),
            "latest": summary.get("latest"),
        }

    deleted = db.clear_conversation_pairs(character_id)
    try:
        optimized_rag.clear_cache()
    except Exception:
        pass

    return {
        "status": "success",
        "deleted_count": deleted,
        "character_id": character_id or "全部",
        "remaining": db.get_conversation_count(character_id),
    }


@app.get("/admin/conversation-summary")
async def conversation_summary(character_id: str = None):
    summary = db.get_conversation_pairs_summary(character_id)
    return {"status": "success", "character_id": character_id or "全部", **summary}


@app.post("/style/learn")
async def learn_style(character_id: str = None):
    cid = character_id or character_manager.get_active_id()
    from llm_style_extractor import LLMStyleExtractor

    extractor = LLMStyleExtractor()
    profile = await extractor.extract_from_database(cid, limit=3000)
    return {
        "status": "success",
        "character_id": cid,
        "sample_count": profile.sample_count,
        "profile": profile.to_dict(),
    }


@app.get("/style/profile")
async def get_style_profile(character_id: str = None):
    cid = character_id or character_manager.get_active_id()
    profile = StyleLearner.load_profile(cid)
    if not profile:
        return {"status": "empty", "character_id": cid, "profile": None}
    return {
        "status": "success",
        "character_id": cid,
        "profile": profile.to_dict(),
        "prompt_preview": profile.to_prompt(),
    }


@app.put("/style/control")
async def update_style_control(data: StyleControlRequest, character_id: str = None):
    cid = character_id or character_manager.get_active_id()
    profile = StyleLearner.load_profile(cid)
    if not profile:
        raise HTTPException(status_code=404, detail="风格档案不存在，请先学习风格")

    allowed = {"natural", "balanced", "strong"}
    if data.style_strength is not None:
        if data.style_strength not in allowed:
            raise HTTPException(status_code=400, detail=f"style_strength 必须是 {sorted(list(allowed))}")
        profile.style_strength = data.style_strength
    if data.negative_constraints is not None:
        profile.negative_constraints = [x.strip() for x in data.negative_constraints if str(x).strip()][:12]

    from style_learner import STYLE_DIR
    style_path = STYLE_DIR / f"{cid}.json"
    with open(style_path, "w", encoding="utf-8") as f:
        json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

    return {"status": "success", "character_id": cid, "profile": profile.to_dict()}


@app.get("/metrics/summary")
async def get_metrics_summary(character_id: str = None, window_days: int = 7):
    cid = character_id or character_manager.get_active_id()
    all_memories = memory_manager.get_ranked_memories(limit=10000)
    if all_memories:
        used = sum(1 for m in all_memories if int(m.get("reference_count", 0) or 0) > 0)
        correction = sum(1 for m in all_memories if str(m.get("key", "")).startswith(("memory_fix_", "priority_fix_")))
        memory_hit_rate = round(used / len(all_memories), 4)
        correction_rate = round(correction / len(all_memories), 4)
        memory_misrecall_rate = correction_rate
    else:
        memory_hit_rate = 0.0
        correction_rate = 0.0
        memory_misrecall_rate = 0.0

    pairs = db.get_conversation_pairs(limit=300, character_id=cid)
    profile = StyleLearner.load_profile(cid)
    style_similarity = 0.0
    style_consistency = 0.0
    user_satisfaction_proxy = 0.5
    if profile:
        learner = StyleLearner()
        recent_ai = [p["ai_response"] for p in pairs[:60] if p.get("ai_response")]
        if recent_ai:
            style_similarity = round(max(0.0, 1.0 - learner.detect_style_drift(profile, recent_ai)), 4)
            style_consistency = round(max(0.0, 1.0 - learner.detect_style_drift(profile, recent_ai[:20])), 4)
            user_satisfaction_proxy = round(max(0.0, min(1.0, 1.0 - memory_misrecall_rate * 0.6)), 4)

    return {
        "status": "success",
        "character_id": cid,
        "window_days": window_days,
        "memory_metrics": {
            "memory_hit_rate": memory_hit_rate,
            "memory_misrecall_rate": memory_misrecall_rate,
            "user_correction_rate": correction_rate,
        },
        "style_metrics": {
            "style_similarity": style_similarity,
            "style_consistency": style_consistency,
            "user_satisfaction_proxy": user_satisfaction_proxy,
        },
        "weekly_regression_recommendation": "建议每周固定时间调用本接口并记录趋势用于回归对比",
    }


@app.post("/topic/proactive/trigger")
async def trigger_proactive_chat(character_id: str = None, force: bool = False):
    active_id = character_id or character_manager.get_active_id()
    last_time = topic_initiator.get_last_chat_time(active_id)
    now = datetime.now()
    if not force and last_time:
        gap = now - last_time
        if gap.total_seconds() < 4 * 3600:
            return {"status": "skipped", "message": "距离上次聊天太近，暂不触发"}

    recent_topics = topic_initiator.get_recent_topics_from_db(active_id, n=20)
    char = character_manager.get_character(active_id)
    char_name = char.name if char else "助手"

    style_hint = ""
    profile = StyleLearner.load_profile(active_id)
    if profile:
        style_hint = profile.to_prompt()

    prompt = topic_initiator.build_proactive_prompt(
        last_chat_time=last_time,
        recent_topics=recent_topics,
        character_name=char_name,
        style_hint=style_hint,
    )

    from ollama_client import OllamaClient

    try:
        text = OllamaClient().generate(prompt, temperature=0.8, num_predict=128)
    except Exception as exc:
        logger.warning(f"主动消息生成失败: {exc}")
        text = ""

    if not text:
        text = topic_initiator.get_topic_local(last_time, recent_topics)

    db.add_conversation_pair(
        user_message="",
        ai_response=text.strip(),
        quality_score=0.9,
        character_id=active_id,
    )
    character_manager.add_chat_message(active_id, "", text.strip())
    return {"status": "success", "message": text.strip()}


@app.get("/topic/suggest")
async def suggest_topic(character_id: str = None, use_llm: bool = False):
    cid = character_id or character_manager.get_active_id()
    last_time = topic_initiator.get_last_chat_time(cid)
    recent_topics = topic_initiator.get_recent_topics_from_db(cid, n=20)
    time_ctx = get_time_context()

    if not use_llm:
        topic = topic_initiator.get_topic_local(last_time, recent_topics)
        return {"status": "success", "topic": topic, "time_context": time_ctx, "source": "local"}

    char = character_manager.get_character(cid)
    char_name = char.name if char else "助手"
    style_hint = ""
    profile = StyleLearner.load_profile(cid)
    if profile:
        style_hint = profile.to_prompt()

    prompt = topic_initiator.build_proactive_prompt(
        last_chat_time=last_time,
        recent_topics=recent_topics,
        character_name=char_name,
        style_hint=style_hint,
    )

    from ollama_client import OllamaClient

    try:
        result = OllamaClient().generate(prompt, temperature=0.9, num_predict=128)
        if result:
            return {
                "status": "success",
                "topic": result.strip(),
                "time_context": time_ctx,
                "source": "llm",
            }
    except Exception as exc:
        logger.warning(f"LLM 话题生成失败: {exc}")

    topic = topic_initiator.get_topic_local(last_time, recent_topics)
    return {"status": "success", "topic": topic, "time_context": time_ctx, "source": "local_fallback"}


@app.get("/topic/time-context")
async def get_current_time_context():
    return get_time_context()


# ──────────────────────────────────────────────────────────────────────────
# 情感状态 API
# ──────────────────────────────────────────────────────────────────────────

@app.get("/emotion/state")
async def get_emotion_state(character_id: str = None):
    """获取当前角色的情绪状态"""
    cid = character_id or character_manager.get_active_id()
    state = emotion_engine.load(cid)
    return {"status": "success", "character_id": cid, "emotion": state.badge_data(), "raw": state.to_dict()}


@app.post("/emotion/update")
async def update_emotion_state(data: EmotionUpdateRequest, character_id: str = None):
    """手动调整情绪值（各维度 0-1）"""
    cid = character_id or character_manager.get_active_id()
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="至少提供一个情绪维度值")
    state = emotion_engine.set_state(cid, updates)
    return {"status": "success", "character_id": cid, "emotion": state.badge_data()}


@app.post("/emotion/reset")
async def reset_emotion_state(character_id: str = None):
    """重置情绪为默认值"""
    cid = character_id or character_manager.get_active_id()
    state = emotion_engine.reset(cid)
    return {"status": "success", "character_id": cid, "emotion": state.badge_data()}


# ──────────────────────────────────────────────────────────────────────────
# 主动记忆管理 API
# ──────────────────────────────────────────────────────────────────────────

@app.post("/memory/compact")
async def compact_memories(category: str = None):
    """压缩冗余记忆（合并相同前缀的重复条目）"""
    removed = memory_manager.compress_old_memories(category=category)
    return {"status": "success", "removed_count": removed, "category": category or "全部"}


@app.post("/memory/decay")
async def decay_memories(age_days: int = 30):
    """对冷门旧记忆执行重要性衰减"""
    decayed = memory_manager.decay_trivial_memories(age_days=age_days)
    return {"status": "success", "decayed_count": decayed, "age_days": age_days}


# ──────────────────────────────────────────────────────────────────────────
# 纪念日 API
# ──────────────────────────────────────────────────────────────────────────

@app.get("/anniversaries")
async def list_anniversaries(include_builtin: bool = True):
    """列出所有纪念日（含内置节日）"""
    items = anniversary_manager.list_anniversaries(include_builtin=include_builtin)
    return {"status": "success", "count": len(items), "anniversaries": items}


@app.get("/anniversaries/upcoming")
async def get_upcoming_anniversaries(within_days: int = 7):
    """获取未来 N 天内的纪念日"""
    items = anniversary_manager.get_upcoming(within_days=within_days)
    return {"status": "success", "within_days": within_days, "count": len(items), "anniversaries": items}


@app.post("/anniversaries")
async def create_anniversary(data: AnniversaryCreateRequest):
    """创建新纪念日"""
    try:
        ann = anniversary_manager.create_anniversary(data.model_dump())
        return {"status": "success", "anniversary": ann.to_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/anniversaries/{ann_id}")
async def update_anniversary_item(ann_id: str, data: AnniversaryUpdateRequest):
    """更新纪念日"""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    try:
        ann = anniversary_manager.update_anniversary(ann_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not ann:
        raise HTTPException(status_code=404, detail="纪念日不存在")
    return {"status": "success", "anniversary": ann.to_dict()}


@app.delete("/anniversaries/{ann_id}")
async def delete_anniversary_item(ann_id: str):
    """删除纪念日"""
    if not anniversary_manager.delete_anniversary(ann_id):
        raise HTTPException(status_code=404, detail="纪念日不存在")
    return {"status": "success", "deleted_id": ann_id}


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


if __name__ == "__main__":
    logger.info("启动 FastAPI 服务...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
