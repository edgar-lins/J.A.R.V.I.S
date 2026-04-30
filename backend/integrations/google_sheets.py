from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from config import get_settings

settings = get_settings()

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
]
TOKEN_PATH = Path(".google_token.json")


def _load_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds if creds and creds.valid else None


def is_authenticated() -> bool:
    return _load_credentials() is not None


def _service():
    creds = _load_credentials()
    if not creds:
        raise RuntimeError("Google não autenticado. Acesse /auth/google para conectar.")
    return build("sheets", "v4", credentials=creds)


def _spreadsheet_id() -> str:
    sid = settings.google_sheets_id
    if not sid:
        raise RuntimeError("GOOGLE_SHEETS_ID não configurado no .env")
    return sid


# ── Leitura ───────────────────────────────────────────────────

def list_sheets() -> list[str]:
    svc = _service()
    meta = svc.spreadsheets().get(spreadsheetId=_spreadsheet_id()).execute()
    return [s["properties"]["title"] for s in meta["sheets"]]


def read_sheet(sheet_name: str, range_: str = "") -> list[list]:
    svc = _service()
    full_range = f"'{sheet_name}'!{range_}" if range_ else f"'{sheet_name}'"
    result = svc.spreadsheets().values().get(
        spreadsheetId=_spreadsheet_id(),
        range=full_range,
    ).execute()
    return result.get("values", [])


def format_sheet_for_jarvis(rows: list[list], sheet_name: str) -> str:
    if not rows:
        return f"Planilha '{sheet_name}' está vazia."
    lines = [f"Aba: {sheet_name}"]
    for row in rows:
        lines.append(" | ".join(str(c) for c in row))
    return "\n".join(lines)


# ── Escrita ───────────────────────────────────────────────────

def append_row(sheet_name: str, values: list) -> str:
    svc = _service()
    body = {"values": [values]}
    svc.spreadsheets().values().append(
        spreadsheetId=_spreadsheet_id(),
        range=f"'{sheet_name}'",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body,
    ).execute()
    return f"Linha adicionada em '{sheet_name}': {values}"


def update_cell(sheet_name: str, cell: str, value: str) -> str:
    svc = _service()
    range_ = f"'{sheet_name}'!{cell}"
    body = {"values": [[value]]}
    svc.spreadsheets().values().update(
        spreadsheetId=_spreadsheet_id(),
        range=range_,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()
    return f"Célula {cell} de '{sheet_name}' atualizada para: {value}"


def update_range(sheet_name: str, range_: str, values: list[list]) -> str:
    svc = _service()
    full_range = f"'{sheet_name}'!{range_}"
    body = {"values": values}
    svc.spreadsheets().values().update(
        spreadsheetId=_spreadsheet_id(),
        range=full_range,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()
    return f"Range {range_} de '{sheet_name}' atualizado."
