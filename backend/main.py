import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from apscheduler.triggers.cron import CronTrigger
from api.routes import router
from config import get_settings
from core.scheduler import get_scheduler

settings = get_settings()
USER_ID = settings.default_user_id


def _setup_scheduler():
    from core.proactive import morning_briefing, calendar_reminder, github_check, evening_summary

    scheduler = get_scheduler()

    # Briefing matinal — Seg/Qua/Sex às 6:30 (dias de treino)
    scheduler.add_job(
        morning_briefing, CronTrigger(day_of_week="mon,wed,fri", hour=6, minute=30),
        args=[USER_ID], id="morning_training",
    )
    # Briefing matinal — Ter/Qui/Sáb/Dom às 7:30 (dias sem treino)
    scheduler.add_job(
        morning_briefing, CronTrigger(day_of_week="tue,thu,sat,sun", hour=7, minute=30),
        args=[USER_ID], id="morning_rest",
    )
    # Resumo noturno — todo dia às 22:00
    scheduler.add_job(
        evening_summary, CronTrigger(hour=22, minute=0),
        args=[USER_ID], id="evening_summary",
    )
    # Alerta de calendário — verifica a cada 5 min se tem evento em 30 min
    scheduler.add_job(
        calendar_reminder, "interval", minutes=5,
        args=[USER_ID, 30], id="calendar_reminder",
    )
    # Check do GitHub — a cada 30 min durante horário de trabalho
    scheduler.add_job(
        github_check, CronTrigger(day_of_week="mon-fri", hour="9-18", minute="0,30"),
        args=[USER_ID], id="github_check",
    )

    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_scheduler()
    get_scheduler().start()
    print("[Jarvis] Scheduler proativo iniciado.")

    from voice.wakeword import start as wakeword_start
    wakeword_start(USER_ID)
    print("[Jarvis] Wake word ativa. Diga 'Jarvis' para ativar.")

    yield

    from voice.wakeword import stop as wakeword_stop
    wakeword_stop()
    get_scheduler().shutdown()


app = FastAPI(title="Jarvis", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/health")
def healthcheck():
    return {"status": "online", "version": "0.1.0"}


# ── Google OAuth ──────────────────────────────────────────────

@app.get("/auth/google")
def google_auth():
    from pathlib import Path
    if not Path("google_credentials.json").exists():
        return HTMLResponse("""
        <h2>google_credentials.json não encontrado</h2>
        <p>Baixe as credenciais OAuth no Google Cloud Console e coloque na raiz do projeto como <b>google_credentials.json</b></p>
        """)
    from integrations.google_calendar import get_auth_url
    return RedirectResponse(get_auth_url())


@app.get("/auth/google/callback")
def google_callback(code: str):
    from integrations.google_calendar import exchange_code
    exchange_code(code)
    return HTMLResponse("""
    <html><body style="background:#0a0a0f;color:#4ade80;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column">
    <h2>✅ Google Calendar conectado!</h2>
    <p>Pode fechar esta aba e voltar ao Jarvis.</p>
    </body></html>
    """)


# ── Spotify OAuth ─────────────────────────────────────────────

@app.get("/auth/spotify")
def spotify_auth():
    from integrations.spotify import get_auth_url
    return RedirectResponse(get_auth_url())


@app.get("/auth/spotify/callback")
def spotify_callback(code: str):
    from integrations.spotify import exchange_code
    exchange_code(code)
    return HTMLResponse("""
    <html><body style="background:#0a0a0f;color:#1db954;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;flex-direction:column">
    <h2>Spotify conectado!</h2>
    <p>Pode fechar esta aba e voltar ao Jarvis.</p>
    </body></html>
    """)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )
