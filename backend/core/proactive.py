"""
Sistema proativo do Jarvis — roda em background e age sem precisar ser chamado.
"""
from datetime import datetime, timedelta
import httpx
from config import get_settings
from core import memory as mem
from core.brain import chat
from mac_agent.actions import send_notification

settings = get_settings()


def _speak(text: str) -> None:
    try:
        from voice.output import speak
        speak(text)
    except Exception as e:
        print(f"[Jarvis Proativo] Erro na voz: {e}")


def _should_speak() -> bool:
    """Só fala em voz alta entre 7h e 23h."""
    return 7 <= datetime.now().hour < 23


def _notify_and_speak(title: str, message: str, subtitle: str = "", speak_text: str = "") -> None:
    """Manda notificação no Mac e fala em voz alta se estiver em horário adequado."""
    send_notification(title=title, message=message[:200], subtitle=subtitle)
    if _should_speak() and speak_text:
        _speak(speak_text)


def _get_weather(city: str = "São Paulo") -> str:
    try:
        res = httpx.get(f"https://wttr.in/{city}?format=3", timeout=5)
        return res.text.strip()
    except Exception:
        return ""


def _get_day_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Bom dia"
    if hour < 18:
        return "Boa tarde"
    return "Boa noite"


def _is_training_day() -> bool:
    return datetime.now().weekday() in (0, 2, 4)


def morning_briefing(user_id: str) -> None:
    now = datetime.now()
    greeting = _get_day_greeting()
    time_str = now.strftime("%H:%M")
    day_name = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"][now.weekday()]
    training_today = _is_training_day()

    weather = _get_weather()
    weather_part = f" {weather}" if weather else ""
    day_context = f"Hoje é {day_name}.{weather_part}"
    if training_today:
        day_context += " Dia de treino — você vai às 7h."
    else:
        day_context += " Dia sem treino."

    session_id = f"proactive-morning-{now.strftime('%Y%m%d')}"
    prompt = (
        f"É {time_str} de {day_name}. Me dê um briefing matinal MUITO breve e objetivo: "
        f"cumprimente, fale o horário, {day_context} "
        f"Verifique minha agenda de hoje e GitHub. "
        f"Seja direto — máximo 4 frases. Sem listas longas."
    )

    try:
        reply = chat(user_id, session_id, prompt)
        _notify_and_speak(
            title=f"Jarvis — {greeting}, Edgar!",
            message=reply,
            subtitle=time_str,
            speak_text=reply,
        )
        mem.add_memory(
            user_id=user_id,
            category="routine",
            content=f"Briefing matinal enviado em {now.strftime('%d/%m/%Y %H:%M')}. Dia de treino: {training_today}.",
            importance=1,
        )
    except Exception as e:
        print(f"[Jarvis Proativo] Erro no briefing: {e}")


def calendar_reminder(user_id: str, minutes_before: int = 30) -> None:
    try:
        from integrations.google_calendar import get_upcoming_events, is_authenticated
        if not is_authenticated():
            return

        now = datetime.now()
        target = now + timedelta(minutes=minutes_before)

        events = get_upcoming_events(days=1)
        for event in events:
            start_str = event.get("start", "")
            if not start_str or "T" not in start_str:
                continue
            try:
                event_time = datetime.fromisoformat(start_str.replace("Z", "+00:00")).replace(tzinfo=None)
                diff = abs((event_time - target).total_seconds())
                if diff <= 300:
                    speak_text = f"Atenção: {event['title']} começa em {minutes_before} minutos."
                    _notify_and_speak(
                        title=f"Em {minutes_before} min: {event['title']}",
                        message=event.get("location", "") or "Sem local definido",
                        subtitle=event_time.strftime("%H:%M"),
                        speak_text=speak_text,
                    )
            except Exception:
                continue
    except Exception as e:
        print(f"[Jarvis Proativo] Erro no reminder de calendário: {e}")


def github_check(user_id: str) -> None:
    try:
        from integrations.github_client import get_notifications
        notifs = get_notifications(only_unread=True)
        reviews = [n for n in notifs if n.get("reason") in ("review_requested", "mention")]
        if reviews:
            titles = [n["title"] for n in reviews[:3]]
            count = len(reviews)
            speak_text = (
                f"Você tem {count} {'item' if count == 1 else 'itens'} aguardando no GitHub: "
                + ", ".join(titles[:2])
                + ("." if count <= 2 else " e mais.")
            )
            _notify_and_speak(
                title="GitHub — Atenção necessária",
                message="\n".join(titles),
                subtitle=f"{count} item(s) aguardando você",
                speak_text=speak_text,
            )
    except Exception as e:
        print(f"[Jarvis Proativo] Erro no check do GitHub: {e}")


def evening_summary(user_id: str) -> None:
    now = datetime.now()
    session_id = f"proactive-evening-{now.strftime('%Y%m%d')}"
    prompt = (
        "Faça um resumo noturno MUITO breve: o que aconteceu hoje que vale lembrar "
        "e o que tenho amanhã (agenda + se é dia de treino). Máximo 3 frases. Seja direto."
    )
    try:
        reply = chat(user_id, session_id, prompt)
        _notify_and_speak(
            title="Jarvis — Resumo do dia",
            message=reply,
            subtitle=now.strftime("%H:%M"),
            speak_text=reply,
        )
    except Exception as e:
        print(f"[Jarvis Proativo] Erro no resumo noturno: {e}")
