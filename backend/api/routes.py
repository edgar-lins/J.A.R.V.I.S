import uuid
import base64
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, Response
from api.schemas import ChatRequest, ChatResponse, ProfileUpdate, HealthMetric
from core import brain, memory as mem
from voice import listen, speak
from health.exams import process_document
from config import get_settings

settings = get_settings()
router = APIRouter()


def _user_id(req_user_id: str | None) -> str:
    return req_user_id or settings.default_user_id


# ── Chat ──────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    user_id = _user_id(req.user_id)
    reply = brain.chat(user_id, req.session_id, req.message)
    return ChatResponse(reply=reply, session_id=req.session_id)


# ── Voice ─────────────────────────────────────────────────────

@router.post("/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Recebe arquivo de áudio do browser e retorna o texto transcrito."""
    audio_bytes = await audio.read()
    text = listen.transcribe_file(audio_bytes, audio.content_type or "audio/webm")
    return {"text": text}


@router.post("/voice/speak")
def text_to_speech(req: ChatRequest):
    user_id = _user_id(req.user_id)
    reply = brain.chat(user_id, req.session_id, req.message)
    audio = speak.synthesize(reply)
    return {
        "reply": reply,
        "session_id": req.session_id,
        "audio_b64": base64.b64encode(audio).decode(),
    }


@router.post("/voice/full")
async def voice_full_cycle(audio: UploadFile = File(...), session_id: str = "", user_id: str = ""):
    if not session_id:
        session_id = str(uuid.uuid4())
    uid = user_id or settings.default_user_id

    audio_bytes = await audio.read()
    text = listen.transcribe_file(audio_bytes, audio.content_type or "audio/webm")
    if not text:
        raise HTTPException(status_code=422, detail="Não consegui entender o áudio.")

    reply = brain.chat(uid, session_id, text)
    reply_audio = speak.synthesize(reply)

    return {
        "user_text": text,
        "reply": reply,
        "session_id": session_id,
        "audio_b64": base64.b64encode(reply_audio).decode(),
    }


# ── Profile ───────────────────────────────────────────────────

@router.get("/profile")
def get_profile(user_id: str | None = None):
    uid = _user_id(user_id)
    profile = mem.get_profile(uid)
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return profile


@router.patch("/profile")
def update_profile(data: ProfileUpdate, user_id: str | None = None):
    uid = _user_id(user_id)
    payload = data.model_dump(exclude_none=True)
    return mem.upsert_profile(uid, payload)


# ── Health ────────────────────────────────────────────────────

@router.post("/health/metric")
def log_metric(metric: HealthMetric, user_id: str | None = None):
    uid = _user_id(user_id)
    return mem.log_health_metric(uid, metric.metric, metric.value, metric.unit, metric.notes)


@router.get("/health/history/{metric}")
def health_history(metric: str, user_id: str | None = None):
    uid = _user_id(user_id)
    return mem.get_health_history(uid, metric)


@router.post("/health/document")
async def upload_document(file: UploadFile = File(...), user_id: str | None = None):
    uid = _user_id(user_id)
    file_bytes = await file.read()
    doc = await process_document(uid, file.filename or "document", file_bytes)
    return doc


# ── Calendar events ───────────────────────────────────────────

@router.get("/calendar/next")
def calendar_next():
    try:
        from integrations.google_calendar import get_upcoming_events, is_authenticated
        if not is_authenticated():
            raise HTTPException(status_code=401, detail="Not authenticated")
        events = get_upcoming_events(days=1, max_results=1)
        return events[0] if events else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar/upcoming")
def calendar_upcoming(days: int = 3, max_results: int = 5):
    try:
        from integrations.google_calendar import get_upcoming_events, is_authenticated
        if not is_authenticated():
            return []
        return get_upcoming_events(days=days, max_results=max_results)
    except Exception:
        return []


# ── Status dos serviços ───────────────────────────────────────

@router.get("/status")
def services_status():
    import time
    results = {}

    # Backend — se chegou aqui, está online
    results["backend"] = {"status": "online", "level": "ok"}

    # Claude API
    try:
        if settings.anthropic_api_key:
            results["claude"] = {"status": "online", "level": "ok"}
        else:
            results["claude"] = {"status": "no key", "level": "err"}
    except Exception:
        results["claude"] = {"status": "error", "level": "err"}

    # ElevenLabs
    try:
        if settings.elevenlabs_api_key and settings.elevenlabs_api_key not in ("", "your_elevenlabs_api_key_here"):
            import httpx
            t0 = time.time()
            r = httpx.get(
                "https://api.elevenlabs.io/v1/user",
                headers={"xi-api-key": settings.elevenlabs_api_key},
                timeout=4,
            )
            ms = int((time.time() - t0) * 1000)
            if r.status_code == 200:
                results["elevenlabs"] = {"status": f"online · {ms}ms", "level": "ok"}
            else:
                results["elevenlabs"] = {"status": "auth error", "level": "err"}
        else:
            results["elevenlabs"] = {"status": "no key", "level": "warn"}
    except Exception:
        results["elevenlabs"] = {"status": "offline", "level": "err"}

    # Spotify
    try:
        from integrations.spotify import is_authenticated
        if is_authenticated():
            results["spotify"] = {"status": "connected", "level": "ok"}
        else:
            results["spotify"] = {"status": "not auth", "level": "warn"}
    except Exception:
        results["spotify"] = {"status": "offline", "level": "err"}

    # GitHub
    try:
        if settings.github_token:
            import httpx
            r = httpx.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {settings.github_token}"},
                timeout=4,
            )
            if r.status_code == 200:
                results["github"] = {"status": "authenticated", "level": "ok"}
            else:
                results["github"] = {"status": "auth error", "level": "err"}
        else:
            results["github"] = {"status": "no token", "level": "warn"}
    except Exception:
        results["github"] = {"status": "offline", "level": "err"}

    # Google Calendar
    try:
        from integrations.google_calendar import is_authenticated as gcal_auth
        if gcal_auth():
            results["calendar"] = {"status": "connected", "level": "ok"}
        else:
            results["calendar"] = {"status": "not auth", "level": "warn"}
    except Exception:
        results["calendar"] = {"status": "offline", "level": "err"}

    return results


# ── Memories ──────────────────────────────────────────────────

@router.get("/memories")
def list_memories(category: str | None = None, user_id: str | None = None):
    uid = _user_id(user_id)
    return mem.get_memories(uid, category=category)
