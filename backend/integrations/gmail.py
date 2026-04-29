import base64
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from integrations.google_calendar import _load_credentials


def _service():
    creds = _load_credentials()
    if not creds:
        raise RuntimeError("Google não autenticado. Acesse /auth/google para conectar.")
    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: dict) -> str:
    """Extrai texto do corpo do e-mail."""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload["parts"]:
            text = _decode_body(part)
            if text:
                return text
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def get_unread_emails(max_results: int = 10) -> list[dict]:
    """Retorna e-mails não lidos da caixa de entrada."""
    svc = _service()
    result = svc.users().messages().list(
        userId="me",
        q="is:unread in:inbox",
        maxResults=max_results,
    ).execute()

    messages = result.get("messages", [])
    emails = []
    for msg in messages:
        full = svc.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()

        headers = {h["name"]: h["value"] for h in full["payload"].get("headers", [])}
        body = _decode_body(full["payload"])

        emails.append({
            "id": full["id"],
            "thread_id": full["threadId"],
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", "(sem assunto)"),
            "date": headers.get("Date", ""),
            "snippet": full.get("snippet", ""),
            "body_preview": body[:500],
        })
    return emails


def mark_as_read(message_id: str) -> None:
    _service().users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def mark_as_unread(message_id: str) -> None:
    _service().users().messages().modify(
        userId="me",
        id=message_id,
        body={"addLabelIds": ["UNREAD"]},
    ).execute()


def mark_all_as_read(query: str = "is:unread in:inbox") -> int:
    """Marca todos os e-mails que correspondem à query como lidos. Retorna quantos foram marcados."""
    svc = _service()
    ids = []
    page_token = None

    while True:
        params = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        result = svc.users().messages().list(**params).execute()
        messages = result.get("messages", [])
        ids.extend([m["id"] for m in messages])
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    if not ids:
        return 0

    # Gmail batchModify aceita até 1000 IDs por chamada
    for i in range(0, len(ids), 1000):
        svc.users().messages().batchModify(
            userId="me",
            body={"ids": ids[i:i+1000], "removeLabelIds": ["UNREAD"]},
        ).execute()

    return len(ids)


def send_email(to: str, subject: str, body: str, reply_to_thread_id: str = "") -> dict:
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    msg_body: dict = {"raw": raw}
    if reply_to_thread_id:
        msg_body["threadId"] = reply_to_thread_id
    result = _service().users().messages().send(userId="me", body=msg_body).execute()
    return {"id": result["id"], "thread_id": result.get("threadId", "")}


def format_emails_for_jarvis(emails: list[dict]) -> str:
    if not emails:
        return "Nenhum e-mail não lido."
    lines = []
    for i, e in enumerate(emails, 1):
        lines.append(f"{i}. De: {e['from']}")
        lines.append(f"   Assunto: {e['subject']}")
        lines.append(f"   Prévia: {e['snippet'][:150]}")
        lines.append(f"   ID: {e['id']}")
        lines.append("")
    return "\n".join(lines)
