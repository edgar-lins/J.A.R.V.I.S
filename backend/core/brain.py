import anthropic
import json
from datetime import datetime
from config import get_settings
from core import memory as mem

settings = get_settings()
client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are Jarvis, a highly intelligent and personal AI assistant for {name}.

## Current date and time
{current_datetime} (timezone: America/Sao_Paulo)
Always use this date as reference for scheduling events, reminders, and any date calculations. Never assume a different year.

You have access to {name}'s personal profile, memories, health data, and routines. You know them deeply and adapt your responses to their needs, goals, and context.

## Your personality and response style — non-negotiable rules
- NEVER use emojis. Zero. Not one.
- NEVER start with filler words: "Claro!", "Ótimo!", "Com certeza!", "Pronto!", "Feito!".
- Be as short as possible. One sentence when one sentence is enough.
- Actions confirmed in one line: "LinkedIn fechado." — nothing else unless asked.
- Observations or suggestions: one sentence max, only if truly relevant.
- Always respond in Brazilian Portuguese (pt-BR)

## What you know about {name}
{profile_summary}

## Long-term memories
{memories}

## Active routines
{routines}

## Your capabilities
- Answer questions and have natural conversations
- Track and analyze health data (weight, sleep, exams, blood tests)
- Build and adapt workout and diet plans
- Help with work tasks, code review, architecture decisions
- Manage Google Calendar, Gmail, GitHub (via tools)
- Read and edit Google Sheets (financial spreadsheet with one tab per month)
- Control the Mac (via local agent)
- Read and interpret uploaded medical exams (PDFs/images)

## Onboarding rule
If {profile_is_new} is true, this is the first interaction. Greet {name} warmly and ask for their basic info in a natural, conversational way — ONE question at a time. Start with: name, age, height, weight, main goals (health + career). Use the update_profile tool as they answer each question. Do NOT dump all questions at once.

## Memory rules (critical)
- Use save_memory proactively whenever you learn ANYTHING new: preferences, decisions made, routines created, health data, work context, goals updated, problems solved.
- Importance 5: health issues, major life decisions, critical work deadlines.
- Importance 4: routines created, goals set, preferences discovered.
- Importance 3: general facts, work context, daily patterns.
- NEVER ask the user something you already know — check memories and profile first.
- If you created a routine, saved data, or made a decision in a previous conversation, remember it — it's in your memories above.

Always respond as Jarvis. Be helpful, precise, and personal."""


def build_system_prompt(user_id: str) -> str:
    profile = mem.get_profile(user_id) or {}
    memories = mem.get_memories(user_id, limit=30)
    routines = mem.get_active_routines(user_id)

    name = profile.get("name", user_id.capitalize())
    is_new_profile = not profile.get("age") and not profile.get("weight_kg")

    parts = []
    if profile.get("age"):
        parts.append(f"Age: {profile['age']}")
    if profile.get("height_cm"):
        parts.append(f"Height: {profile['height_cm']}cm")
    if profile.get("weight_kg"):
        parts.append(f"Weight: {profile['weight_kg']}kg")
    if profile.get("occupation"):
        parts.append(f"Occupation: {profile['occupation']}")
    if profile.get("goals"):
        parts.append(f"Goals: {', '.join(profile['goals'])}")
    profile_summary = " | ".join(parts) if parts else "No profile data collected yet."

    memories_text = mem.format_memories_for_context(memories) or "No memories yet."

    routines_text = (
        "\n".join([f"- {r['name']} ({r['type']})" for r in routines])
        if routines else "No active routines yet."
    )

    return SYSTEM_PROMPT.format(
        name=name,
        profile_summary=profile_summary,
        memories=memories_text,
        routines=routines_text,
        profile_is_new=str(is_new_profile).lower(),
        current_datetime=datetime.now().strftime("%A, %d de %B de %Y %H:%M"),
    )


# Tools available to Jarvis
TOOLS = [
    {
        "name": "save_memory",
        "description": "Save an important fact or observation about the user to long-term memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["health", "work", "personal", "preference", "routine"],
                    "description": "Category of the memory",
                },
                "content": {
                    "type": "string",
                    "description": "The fact to remember, written in third person (e.g. 'User prefers morning workouts')",
                },
                "importance": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "Importance level: 1=low, 5=critical",
                },
            },
            "required": ["category", "content", "importance"],
        },
    },
    {
        "name": "update_profile",
        "description": "Update the user's personal profile with new information (height, weight, age, goals, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "height_cm": {"type": "number"},
                "weight_kg": {"type": "number"},
                "occupation": {"type": "string"},
                "goals": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "log_health_metric",
        "description": "Record a health measurement (weight, blood pressure, sleep hours, steps, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "e.g. 'weight_kg', 'blood_pressure', 'sleep_hours'"},
                "value": {"type": "number"},
                "unit": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["metric", "value"],
        },
    },
    {
        "name": "save_routine",
        "description": "Save a new workout, diet plan, or habit routine for the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "type": {"type": "string", "enum": ["workout", "diet", "habit", "schedule"]},
                "content": {"type": "object", "description": "Full structured content of the routine"},
            },
            "required": ["name", "type", "content"],
        },
    },
    {
        "name": "get_calendar_events",
        "description": "Get the user's upcoming Google Calendar events for the next N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "How many days ahead to look (default 7)", "default": 7},
            },
        },
    },
    {
        "name": "create_calendar_event",
        "description": "Create an event in the user's Google Calendar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_iso": {"type": "string", "description": "Start datetime in ISO 8601 format, e.g. 2025-05-01T07:00:00"},
                "end_iso": {"type": "string", "description": "End datetime in ISO 8601 format"},
                "description": {"type": "string"},
                "location": {"type": "string"},
                "recurrence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "RRULE strings for recurring events, e.g. ['RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR']",
                },
            },
            "required": ["title", "start_iso", "end_iso"],
        },
    },
    {
        "name": "update_calendar_event",
        "description": "Edit an existing Google Calendar event.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID from get_calendar_events"},
                "title": {"type": "string"},
                "start_iso": {"type": "string"},
                "end_iso": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "delete_calendar_event",
        "description": "Delete a Google Calendar event by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID from get_calendar_events"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "build_weekly_routine",
        "description": "Build and schedule a full weekly routine in Google Calendar based on the user's goals (workouts, meals, study, sleep). Creates multiple recurring events at once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "description": "List of recurring events to create",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "start_iso": {"type": "string"},
                            "end_iso": {"type": "string"},
                            "description": {"type": "string"},
                            "recurrence": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "start_iso", "end_iso"],
                    },
                },
            },
            "required": ["events"],
        },
    },
    # ── Clima ─────────────────────────────────────────────────
    {
        "name": "get_weather",
        "description": "Retorna o clima atual e previsão do dia para uma cidade.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Nome da cidade (padrão: São Paulo)", "default": "São Paulo"},
            },
        },
    },
    # ── Lembretes ─────────────────────────────────────────────
    {
        "name": "set_reminder",
        "description": "Cria um lembrete que dispara após X minutos ou em um horário específico. Jarvis fala o lembrete em voz alta e manda notificação no Mac.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "O que lembrar"},
                "minutes": {"type": "integer", "description": "Daqui quantos minutos disparar (use isto OU at_time)"},
                "at_time": {"type": "string", "description": "Horário específico no formato HH:MM (use isto OU minutes)"},
            },
            "required": ["message"],
        },
    },
    # ── Spotify ──────────────────────────────────────────────
    {
        "name": "spotify_play",
        "description": "Toca uma música, artista, playlist ou álbum no Spotify.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Nome da música, artista, playlist ou álbum"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "spotify_control",
        "description": "Controla a reprodução do Spotify: pausar, retomar, próxima, anterior.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["pause", "resume", "next", "previous"]},
            },
            "required": ["action"],
        },
    },
    {
        "name": "spotify_volume",
        "description": "Ajusta o volume do Spotify (0–100).",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["level"],
        },
    },
    {
        "name": "spotify_now_playing",
        "description": "Retorna a música que está tocando agora no Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    # ── Web Search ───────────────────────────────────────────
    {
        "name": "web_search",
        "description": "Busca informações atuais na web. Use para notícias, placar de jogos, clima, preços, eventos recentes — qualquer coisa que exija dados em tempo real.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca"},
                "count": {"type": "integer", "description": "Número de resultados (padrão 5)", "default": 5},
            },
            "required": ["query"],
        },
    },
    # ── GitHub ────────────────────────────────────────────────
    {
        "name": "get_my_prs",
        "description": "Get the user's GitHub pull requests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["open", "closed", "merged"], "default": "open"},
            },
        },
    },
    {
        "name": "get_my_issues",
        "description": "Get GitHub issues assigned to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "enum": ["open", "closed"], "default": "open"},
            },
        },
    },
    {
        "name": "get_github_notifications",
        "description": "Get the user's GitHub notifications (PRs, issues, mentions, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "only_unread": {"type": "boolean", "default": True},
            },
        },
    },
    {
        "name": "get_pr_details",
        "description": "Get detailed information about a specific GitHub PR including changed files and reviews.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_full_name": {"type": "string", "description": "e.g. 'org/repo-name'"},
                "pr_number": {"type": "integer"},
            },
            "required": ["repo_full_name", "pr_number"],
        },
    },
    # ── Gmail ─────────────────────────────────────────────────
    {
        "name": "get_unread_emails",
        "description": "Get unread emails from the user's Gmail inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "mark_email_as_read",
        "description": "Mark a Gmail message as read by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "mark_email_as_unread",
        "description": "Mark a specific Gmail message as unread by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "mark_all_emails_as_read",
        "description": (
            "Mark emails as read using a Gmail search query. Use this for bulk operations. "
            "Examples: mark all unread ('is:unread in:inbox'), from a sender ('from:github.com is:unread'), "
            "by category ('category:promotions is:unread'), older than N days ('is:unread older_than:30d'), "
            "with subject keyword ('subject:newsletter is:unread'). Always confirm with user before running."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query to select which emails to mark as read"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "send_email",
        "description": "Send or reply to an email via Gmail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "reply_to_thread_id": {"type": "string", "description": "Thread ID to reply in the same thread"},
            },
            "required": ["to", "subject", "body"],
        },
    },
    # ── Google Sheets ─────────────────────────────────────────
    {
        "name": "sheets_list_sheets",
        "description": "Lista todas as abas (páginas) da planilha financeira do usuário.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "sheets_read",
        "description": "Lê os dados de uma aba da planilha financeira. Use para consultar gastos, receitas ou saldo de um mês.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "description": "Nome da aba, ex: 'Abril 2025'"},
                "range": {"type": "string", "description": "Range opcional no formato A1:Z100. Se omitido, lê a aba inteira."},
            },
            "required": ["sheet_name"],
        },
    },
    {
        "name": "sheets_append_row",
        "description": "Adiciona uma nova linha no final de uma aba da planilha. Use para registrar um novo gasto ou receita.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "description": "Nome da aba, ex: 'Abril 2025'"},
                "values": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Valores das colunas na ordem da planilha, ex: ['30/04/2025', 'Mercado', '150', 'Alimentação']",
                },
            },
            "required": ["sheet_name", "values"],
        },
    },
    {
        "name": "sheets_update_cell",
        "description": "Atualiza o valor de uma célula específica na planilha.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string", "description": "Nome da aba"},
                "cell": {"type": "string", "description": "Referência da célula, ex: 'B5'"},
                "value": {"type": "string", "description": "Novo valor"},
            },
            "required": ["sheet_name", "cell", "value"],
        },
    },
    # ── Mac Agent ─────────────────────────────────────────────
    {
        "name": "open_app",
        "description": "Open a macOS application by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Exact app name as it appears in /Applications, e.g. 'Visual Studio Code', 'Slack', 'Safari'"},
            },
            "required": ["app_name"],
        },
    },
    {
        "name": "run_terminal_command",
        "description": "Run a shell command on the user's Mac and return the output. Use for file operations, scripts, git commands, etc. Dangerous commands are blocked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "timeout": {"type": "integer", "description": "Max seconds to wait (default 30)", "default": 30},
            },
            "required": ["command"],
        },
    },
    {
        "name": "take_screenshot_and_describe",
        "description": "Take a screenshot of the user's screen and describe what is visible. Use when user asks 'what's on my screen', 'can you see this error', or needs visual context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "What to look for or describe in the screenshot"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "send_mac_notification",
        "description": "Send a macOS system notification to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "message": {"type": "string"},
                "subtitle": {"type": "string"},
            },
            "required": ["title", "message"],
        },
    },
    {
        "name": "get_clipboard",
        "description": "Read the current content of the Mac clipboard.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_clipboard",
        "description": "Write text to the Mac clipboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "open_url",
        "description": "Open a URL in the default browser.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "get_running_apps",
        "description": "List all currently running applications on the Mac.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_volume",
        "description": "Set the Mac system volume (0-100).",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["level"],
        },
    },
    {
        "name": "browser_control",
        "description": "Control Chrome or Safari: close tab, close window, close all windows, list open tabs, open new tab, reload.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["close_tab", "close_window", "close_all_windows", "list_tabs", "new_tab", "reload"],
                },
                "browser": {
                    "type": "string",
                    "enum": ["Google Chrome", "Safari", "Firefox"],
                    "default": "Google Chrome",
                },
                "tab_index": {
                    "type": "integer",
                    "description": "Tab number to target (1-based). Omit to use the active tab.",
                },
            },
            "required": ["action"],
        },
    },
]


def handle_tool_call(user_id: str, tool_name: str, tool_input: dict) -> str:
    if tool_name == "save_memory":
        mem.add_memory(
            user_id,
            tool_input["category"],
            tool_input["content"],
            tool_input.get("importance", 1),
        )
        return f"Memory saved: {tool_input['content']}"

    elif tool_name == "update_profile":
        mem.upsert_profile(user_id, tool_input)
        return f"Profile updated with: {tool_input}"

    elif tool_name == "log_health_metric":
        mem.log_health_metric(
            user_id,
            tool_input["metric"],
            tool_input["value"],
            tool_input.get("unit", ""),
            tool_input.get("notes", ""),
        )
        return f"Health metric '{tool_input['metric']}' logged: {tool_input['value']}"

    elif tool_name == "save_routine":
        mem.save_routine(
            user_id,
            tool_input["name"],
            tool_input["type"],
            tool_input["content"],
        )
        return f"Routine '{tool_input['name']}' saved."

    elif tool_name == "get_calendar_events":
        try:
            from integrations.google_calendar import get_upcoming_events, format_events_for_jarvis, is_authenticated
            if not is_authenticated():
                return "Google Calendar não conectado. Peça ao usuário para acessar http://localhost:8000/auth/google"
            events = get_upcoming_events(days=tool_input.get("days", 7))
            return format_events_for_jarvis(events)
        except Exception as e:
            return f"Erro ao buscar eventos: {e}"

    elif tool_name == "create_calendar_event":
        try:
            from integrations.google_calendar import create_event, is_authenticated
            if not is_authenticated():
                return "Google Calendar não conectado. Peça ao usuário para acessar http://localhost:8000/auth/google"
            result = create_event(
                title=tool_input["title"],
                start_iso=tool_input["start_iso"],
                end_iso=tool_input["end_iso"],
                description=tool_input.get("description", ""),
                location=tool_input.get("location", ""),
                recurrence=tool_input.get("recurrence"),
            )
            return f"Evento criado: '{result['title']}' em {result['start']}"
        except Exception as e:
            return f"Erro ao criar evento: {e}"

    elif tool_name == "update_calendar_event":
        try:
            from integrations.google_calendar import update_event, is_authenticated
            if not is_authenticated():
                return "Google Calendar não conectado."
            result = update_event(
                event_id=tool_input["event_id"],
                title=tool_input.get("title"),
                start_iso=tool_input.get("start_iso"),
                end_iso=tool_input.get("end_iso"),
                description=tool_input.get("description"),
            )
            return f"Evento atualizado: '{result['title']}'"
        except Exception as e:
            return f"Erro ao editar evento: {e}"

    elif tool_name == "delete_calendar_event":
        try:
            from integrations.google_calendar import delete_event, is_authenticated
            if not is_authenticated():
                return "Google Calendar não conectado."
            delete_event(tool_input["event_id"])
            return f"Evento deletado com sucesso."
        except Exception as e:
            return f"Erro ao deletar evento: {e}"

    elif tool_name == "build_weekly_routine":
        try:
            from integrations.google_calendar import create_event, is_authenticated
            if not is_authenticated():
                return "Google Calendar não conectado. Peça ao usuário para acessar http://localhost:8000/auth/google"
            created = []
            for ev in tool_input.get("events", []):
                result = create_event(
                    title=ev["title"],
                    start_iso=ev["start_iso"],
                    end_iso=ev["end_iso"],
                    description=ev.get("description", ""),
                    recurrence=ev.get("recurrence"),
                )
                created.append(result["title"])
            return f"{len(created)} eventos criados: {', '.join(created)}"
        except Exception as e:
            return f"Erro ao criar rotina: {e}"

    # ── Clima ─────────────────────────────────────────────────

    elif tool_name == "get_weather":
        try:
            import httpx
            city = tool_input.get("city", "São Paulo").replace(" ", "+")
            res = httpx.get(f"https://wttr.in/{city}?format=j1", timeout=8)
            res.raise_for_status()
            data = res.json()
            current = data["current_condition"][0]
            today   = data["weather"][0]

            temp_c    = current["temp_C"]
            feels     = current["FeelsLikeC"]
            humidity  = current["humidity"]
            desc      = current["weatherDesc"][0]["value"]
            max_c     = today["maxtempC"]
            min_c     = today["mintempC"]
            rain_mm   = today.get("hourly", [{}])[4].get("precipMM", "0")

            return (
                f"{city.replace('+', ' ')}: {desc}, {temp_c}°C (sensação {feels}°C)\n"
                f"Hoje: máx {max_c}°C / mín {min_c}°C | Umidade: {humidity}% | Chuva: {rain_mm}mm"
            )
        except Exception as e:
            return f"Erro ao buscar clima: {e}"

    # ── Lembretes ─────────────────────────────────────────────

    elif tool_name == "set_reminder":
        try:
            from datetime import datetime, timedelta
            from core.scheduler import get_scheduler
            from mac_agent.actions import send_notification
            from voice.output import speak as _speak

            msg = tool_input["message"]
            scheduler = get_scheduler()

            if tool_input.get("minutes"):
                run_at = datetime.now() + timedelta(minutes=tool_input["minutes"])
                label = f"em {tool_input['minutes']} minutos"
            elif tool_input.get("at_time"):
                h, m = map(int, tool_input["at_time"].split(":"))
                run_at = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
                if run_at <= datetime.now():
                    run_at += timedelta(days=1)
                label = f"às {tool_input['at_time']}"
            else:
                return "Informe 'minutes' ou 'at_time' para o lembrete."

            def _fire(message=msg):
                _speak(f"Lembrete: {message}")
                send_notification(title="Jarvis — Lembrete", message=message)

            job_id = f"reminder_{run_at.strftime('%Y%m%d%H%M%S')}"
            scheduler.add_job(_fire, "date", run_date=run_at, id=job_id, replace_existing=True)
            return f"Lembrete definido para {label}: '{msg}'"
        except Exception as e:
            return f"Erro ao criar lembrete: {e}"

    # ── Spotify ──────────────────────────────────────────────

    elif tool_name == "spotify_play":
        try:
            from integrations.spotify import play, is_authenticated
            if not is_authenticated():
                return "Spotify não conectado. Acesse http://localhost:8000/auth/spotify"
            return play(tool_input["query"])
        except Exception as e:
            return f"Erro no Spotify: {e}"

    elif tool_name == "spotify_control":
        try:
            from integrations.spotify import pause, resume, next_track, previous_track, is_authenticated
            if not is_authenticated():
                return "Spotify não conectado. Acesse http://localhost:8000/auth/spotify"
            action = tool_input["action"]
            if action == "pause":    return pause()
            if action == "resume":   return resume()
            if action == "next":     return next_track()
            if action == "previous": return previous_track()
        except Exception as e:
            return f"Erro no Spotify: {e}"

    elif tool_name == "spotify_volume":
        try:
            from integrations.spotify import set_volume, is_authenticated
            if not is_authenticated():
                return "Spotify não conectado. Acesse http://localhost:8000/auth/spotify"
            return set_volume(tool_input["level"])
        except Exception as e:
            return f"Erro no Spotify: {e}"

    elif tool_name == "spotify_now_playing":
        try:
            from integrations.spotify import now_playing, is_authenticated
            if not is_authenticated():
                return "Spotify não conectado. Acesse http://localhost:8000/auth/spotify"
            return now_playing()
        except Exception as e:
            return f"Erro no Spotify: {e}"

    # ── Web Search ───────────────────────────────────────────

    elif tool_name == "web_search":
        try:
            from integrations.web_search import search
            return search(tool_input["query"], tool_input.get("count", 5))
        except Exception as e:
            return f"Erro na busca: {e}"

    # ── GitHub ────────────────────────────────────────────────

    elif tool_name == "get_my_prs":
        try:
            from integrations.github_client import get_my_prs, format_prs_for_jarvis
            prs = get_my_prs(state=tool_input.get("state", "open"))
            return format_prs_for_jarvis(prs)
        except Exception as e:
            return f"Erro ao buscar PRs: {e}"

    elif tool_name == "get_my_issues":
        try:
            from integrations.github_client import get_my_issues
            issues = get_my_issues(state=tool_input.get("state", "open"))
            if not issues:
                return "Nenhuma issue atribuída."
            return "\n".join([f"- #{i['number']} [{i['repo']}] {i['title']}" for i in issues])
        except Exception as e:
            return f"Erro ao buscar issues: {e}"

    elif tool_name == "get_github_notifications":
        try:
            from integrations.github_client import get_notifications, format_notifications_for_jarvis
            notifs = get_notifications(only_unread=tool_input.get("only_unread", True))
            return format_notifications_for_jarvis(notifs)
        except Exception as e:
            return f"Erro ao buscar notificações: {e}"

    elif tool_name == "get_pr_details":
        try:
            from integrations.github_client import get_pr_details
            import json
            details = get_pr_details(tool_input["repo_full_name"], tool_input["pr_number"])
            return json.dumps(details, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Erro ao buscar PR: {e}"

    # ── Gmail ─────────────────────────────────────────────────

    elif tool_name == "get_unread_emails":
        try:
            from integrations.gmail import get_unread_emails, format_emails_for_jarvis
            emails = get_unread_emails(max_results=tool_input.get("max_results", 10))
            return format_emails_for_jarvis(emails)
        except Exception as e:
            return f"Erro ao buscar e-mails: {e}"

    elif tool_name == "mark_email_as_read":
        try:
            from integrations.gmail import mark_as_read
            mark_as_read(tool_input["message_id"])
            return "E-mail marcado como lido."
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "mark_email_as_unread":
        try:
            from integrations.gmail import mark_as_unread
            mark_as_unread(tool_input["message_id"])
            return "E-mail marcado como não lido."
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "mark_all_emails_as_read":
        try:
            from integrations.gmail import mark_all_as_read
            query = tool_input.get("query", "is:unread in:inbox")
            count = mark_all_as_read(query)
            return f"{count} e-mail(s) marcados como lidos."
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "send_email":
        try:
            from integrations.gmail import send_email
            result = send_email(
                to=tool_input["to"],
                subject=tool_input["subject"],
                body=tool_input["body"],
                reply_to_thread_id=tool_input.get("reply_to_thread_id", ""),
            )
            return f"E-mail enviado. ID: {result['id']}"
        except Exception as e:
            return f"Erro ao enviar e-mail: {e}"

    # ── Google Sheets ─────────────────────────────────────────

    elif tool_name == "sheets_list_sheets":
        try:
            from integrations.google_sheets import list_sheets, is_authenticated
            if not is_authenticated():
                return "Google não autenticado. Acesse http://localhost:8000/auth/google"
            sheets = list_sheets()
            return "Abas da planilha: " + ", ".join(sheets)
        except Exception as e:
            return f"Erro ao listar abas: {e}"

    elif tool_name == "sheets_read":
        try:
            from integrations.google_sheets import read_sheet, format_sheet_for_jarvis, is_authenticated
            if not is_authenticated():
                return "Google não autenticado. Acesse http://localhost:8000/auth/google"
            rows = read_sheet(tool_input["sheet_name"], tool_input.get("range", ""))
            return format_sheet_for_jarvis(rows, tool_input["sheet_name"])
        except Exception as e:
            return f"Erro ao ler planilha: {e}"

    elif tool_name == "sheets_append_row":
        try:
            from integrations.google_sheets import append_row, is_authenticated
            if not is_authenticated():
                return "Google não autenticado. Acesse http://localhost:8000/auth/google"
            return append_row(tool_input["sheet_name"], tool_input["values"])
        except Exception as e:
            return f"Erro ao adicionar linha: {e}"

    elif tool_name == "sheets_update_cell":
        try:
            from integrations.google_sheets import update_cell, is_authenticated
            if not is_authenticated():
                return "Google não autenticado. Acesse http://localhost:8000/auth/google"
            return update_cell(tool_input["sheet_name"], tool_input["cell"], tool_input["value"])
        except Exception as e:
            return f"Erro ao atualizar célula: {e}"

    # ── Mac Agent ─────────────────────────────────────────────

    elif tool_name == "open_app":
        try:
            from mac_agent.actions import open_app
            return open_app(tool_input["app_name"])
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "run_terminal_command":
        try:
            from mac_agent.actions import run_command
            return run_command(tool_input["command"], tool_input.get("timeout", 30))
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "take_screenshot_and_describe":
        try:
            from mac_agent.actions import screenshot_as_base64
            b64 = screenshot_as_base64()
            question = tool_input.get("question", "Descreva o que está na tela.")
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {"type": "text", "text": f"{question}\n\nResponda em português."},
                    ],
                }],
            )
            return response.content[0].text
        except Exception as e:
            return f"Erro ao capturar tela: {e}"

    elif tool_name == "send_mac_notification":
        try:
            from mac_agent.actions import send_notification
            return send_notification(
                tool_input["title"],
                tool_input["message"],
                tool_input.get("subtitle", ""),
            )
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "get_clipboard":
        try:
            from mac_agent.actions import get_clipboard
            content = get_clipboard()
            return f"Clipboard: {content[:500]}" if content else "Clipboard está vazio."
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "set_clipboard":
        try:
            from mac_agent.actions import set_clipboard
            return set_clipboard(tool_input["text"])
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "open_url":
        try:
            from mac_agent.actions import open_url
            return open_url(tool_input["url"])
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "get_running_apps":
        try:
            from mac_agent.actions import get_running_apps
            apps = get_running_apps()
            return "Apps abertos: " + ", ".join(apps)
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "set_volume":
        try:
            from mac_agent.actions import set_volume
            return set_volume(tool_input["level"])
        except Exception as e:
            return f"Erro: {e}"

    elif tool_name == "browser_control":
        try:
            from mac_agent.actions import browser_action
            return browser_action(
                action=tool_input["action"],
                app=tool_input.get("browser", "Google Chrome"),
                tab_index=tool_input.get("tab_index", -1),
            )
        except Exception as e:
            return f"Erro: {e}"

    return "Tool not found."


def _ensure_profile(user_id: str) -> None:
    if not mem.get_profile(user_id):
        mem.upsert_profile(user_id, {"name": user_id.capitalize()})


def chat(user_id: str, session_id: str, user_message: str, screen_b64: str | None = None) -> str:
    _ensure_profile(user_id)
    mem.save_message(user_id, session_id, "user", user_message)

    history = mem.get_recent_messages(session_id, limit=20)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    # injeta screenshot como contexto visual na última mensagem do usuário
    if screen_b64:
        messages[-1] = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": screen_b64},
                },
                {"type": "text", "text": user_message},
            ],
        }

    system = build_system_prompt(user_id)

    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        system=system,
        messages=messages,
        tools=TOOLS,
    )

    # Agentic loop: processa tool calls até obter resposta final
    while response.stop_reason == "tool_use":
        tool_results = []
        assistant_content = response.content

        for block in response.content:
            if block.type == "tool_use":
                result = handle_tool_call(user_id, block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=TOOLS,
        )

    reply = ""
    for block in response.content:
        if hasattr(block, "text"):
            reply += block.text

    mem.save_message(user_id, session_id, "assistant", reply)
    return reply
