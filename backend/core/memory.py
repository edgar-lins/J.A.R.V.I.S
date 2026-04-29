from supabase import create_client, Client
from config import get_settings
from typing import Optional
import uuid

settings = get_settings()

_client: Optional[Client] = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


# ── Profile ──────────────────────────────────────────────────

def get_profile(user_id: str) -> Optional[dict]:
    res = get_db().table("profiles").select("*").eq("user_id", user_id).maybe_single().execute()
    return res.data if res else None


def upsert_profile(user_id: str, data: dict) -> dict:
    payload = {"user_id": user_id, **data}
    res = get_db().table("profiles").upsert(payload, on_conflict="user_id").execute()
    return res.data[0]


# ── Memories ─────────────────────────────────────────────────

def add_memory(user_id: str, category: str, content: str, importance: int = 1) -> dict:
    res = get_db().table("memories").insert({
        "user_id": user_id,
        "category": category,
        "content": content,
        "importance": importance,
    }).execute()
    return res.data[0]


def get_memories(user_id: str, category: Optional[str] = None, limit: int = 20) -> list[dict]:
    q = get_db().table("memories").select("*").eq("user_id", user_id).order("importance", desc=True)
    if category:
        q = q.eq("category", category)
    return q.limit(limit).execute().data


def format_memories_for_context(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = [f"[{m['category'].upper()}] {m['content']}" for m in memories]
    return "\n".join(lines)


# ── Conversations ─────────────────────────────────────────────

def save_message(user_id: str, session_id: str, role: str, content: str) -> None:
    get_db().table("conversations").insert({
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()


def get_recent_messages(session_id: str, limit: int = 60) -> list[dict]:
    res = (
        get_db().table("conversations")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=True)   # mais recentes primeiro
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data))  # volta para ordem cronológica


# ── Health ────────────────────────────────────────────────────

def log_health_metric(user_id: str, metric: str, value: float, unit: str = "", notes: str = "") -> dict:
    res = get_db().table("health_data").insert({
        "user_id": user_id,
        "metric": metric,
        "value": value,
        "unit": unit,
        "notes": notes,
    }).execute()
    return res.data[0]


def get_health_history(user_id: str, metric: str, limit: int = 30) -> list[dict]:
    return (
        get_db().table("health_data")
        .select("value, unit, notes, recorded_at")
        .eq("user_id", user_id)
        .eq("metric", metric)
        .order("recorded_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


def save_health_document(user_id: str, filename: str, file_path: str,
                          document_type: str, summary: str, raw_text: str) -> dict:
    res = get_db().table("health_documents").insert({
        "user_id": user_id,
        "filename": filename,
        "file_path": file_path,
        "document_type": document_type,
        "summary": summary,
        "raw_text": raw_text,
    }).execute()
    return res.data[0]


# ── Routines ─────────────────────────────────────────────────

def save_routine(user_id: str, name: str, routine_type: str, content: dict) -> dict:
    res = get_db().table("routines").insert({
        "user_id": user_id,
        "name": name,
        "type": routine_type,
        "content": content,
    }).execute()
    return res.data[0]


def get_active_routines(user_id: str) -> list[dict]:
    return (
        get_db().table("routines")
        .select("*")
        .eq("user_id", user_id)
        .eq("active", True)
        .execute()
        .data
    )
