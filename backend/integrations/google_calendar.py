import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
]
TOKEN_PATH = Path(".google_token.json")
CREDENTIALS_PATH = Path("google_credentials.json")
REDIRECT_URI = "http://localhost:8000/auth/google/callback"

# Guarda o flow entre a geração da URL e o callback
_active_flow: Flow | None = None


def _load_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds if creds and creds.valid else None


def _save_credentials(creds: Credentials) -> None:
    TOKEN_PATH.write_text(creds.to_json())


def get_auth_url() -> str:
    global _active_flow
    _active_flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_PATH),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, _ = _active_flow.authorization_url(prompt="consent", access_type="offline")
    return auth_url


def exchange_code(code: str) -> None:
    global _active_flow
    if _active_flow is None:
        raise RuntimeError("Flow expirado. Acesse /auth/google novamente.")
    _active_flow.fetch_token(code=code)
    _save_credentials(_active_flow.credentials)
    _active_flow = None


def is_authenticated() -> bool:
    return _load_credentials() is not None


def _service():
    creds = _load_credentials()
    if not creds:
        raise RuntimeError("Google Calendar não autenticado. Acesse /auth/google para conectar.")
    return build("calendar", "v3", credentials=creds)


# ── Leitura ───────────────────────────────────────────────────

def get_upcoming_events(days: int = 7, max_results: int = 20) -> list[dict]:
    svc = _service()
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)

    result = svc.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = []
    for e in result.get("items", []):
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        end_t = e["end"].get("dateTime", e["end"].get("date", ""))
        events.append({
            "id": e["id"],
            "title": e.get("summary", "(sem título)"),
            "start": start,
            "end": end_t,
            "description": e.get("description", ""),
            "location": e.get("location", ""),
        })
    return events


def format_events_for_jarvis(events: list[dict]) -> str:
    if not events:
        return "Nenhum evento nos próximos dias."
    lines = []
    for e in events:
        lines.append(f"- [{e['id']}] {e['title']} | {e['start']} → {e['end']}")
        if e.get("location"):
            lines.append(f"  Local: {e['location']}")
    return "\n".join(lines)


# ── Criação ───────────────────────────────────────────────────

def create_event(
    title: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    location: str = "",
    recurrence: list[str] | None = None,
) -> dict:
    svc = _service()
    body: dict = {
        "summary": title,
        "start": {"dateTime": start_iso, "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": end_iso, "timeZone": "America/Sao_Paulo"},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if recurrence:
        body["recurrence"] = recurrence

    created = svc.events().insert(calendarId="primary", body=body).execute()
    return {"id": created["id"], "title": title, "start": start_iso, "link": created.get("htmlLink", "")}


def update_event(event_id: str, title: str | None = None, start_iso: str | None = None,
                  end_iso: str | None = None, description: str | None = None) -> dict:
    svc = _service()
    event = svc.events().get(calendarId="primary", eventId=event_id).execute()
    if title:
        event["summary"] = title
    if start_iso:
        event["start"] = {"dateTime": start_iso, "timeZone": "America/Sao_Paulo"}
    if end_iso:
        event["end"] = {"dateTime": end_iso, "timeZone": "America/Sao_Paulo"}
    if description is not None:
        event["description"] = description
    updated = svc.events().update(calendarId="primary", eventId=event_id, body=event).execute()
    return {"id": updated["id"], "title": updated.get("summary", ""), "start": updated["start"].get("dateTime", "")}


def delete_event(event_id: str) -> None:
    _service().events().delete(calendarId="primary", eventId=event_id).execute()
