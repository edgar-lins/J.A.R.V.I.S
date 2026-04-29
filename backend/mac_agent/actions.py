import subprocess
import tempfile
import os
import base64
from pathlib import Path

# Comandos bloqueados por segurança
_BLOCKED = ["rm -rf /", "rm -rf ~", ":(){ :|:& };:", "mkfs", "dd if=", "chmod -R 777 /"]


def _run_applescript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip() or result.stderr.strip()


def open_app(app_name: str) -> str:
    result = subprocess.run(
        ["open", "-a", app_name],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode == 0:
        return f"'{app_name}' aberto com sucesso."
    return f"Não consegui abrir '{app_name}': {result.stderr.strip()}"


def focus_app(app_name: str) -> str:
    script = f'tell application "{app_name}" to activate'
    return _run_applescript(script)


def get_running_apps() -> list[str]:
    script = 'tell application "System Events" to get name of every application process whose background only is false'
    output = _run_applescript(script)
    return [a.strip() for a in output.split(",") if a.strip()]


def run_command(command: str, timeout: int = 30) -> str:
    for blocked in _BLOCKED:
        if blocked in command:
            return f"Comando bloqueado por segurança: '{blocked}'"

    result = subprocess.run(
        command, shell=True, capture_output=True, text=True, timeout=timeout,
        cwd=str(Path.home()),
    )
    output = result.stdout.strip()
    error = result.stderr.strip()

    if result.returncode != 0 and error:
        return f"Erro (código {result.returncode}):\n{error[:1000]}"
    return output[:2000] or "Comando executado sem saída."


def take_screenshot() -> bytes:
    """Tira screenshot da tela inteira e retorna como bytes PNG."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    subprocess.run(["screencapture", "-x", tmp_path], check=True, timeout=10)
    data = Path(tmp_path).read_bytes()
    os.unlink(tmp_path)
    return data


def screenshot_as_base64() -> str:
    return base64.standard_b64encode(take_screenshot()).decode()


def send_notification(title: str, message: str, subtitle: str = "") -> str:
    subtitle_part = f'subtitle "{subtitle}"' if subtitle else ""
    script = f'display notification "{message}" with title "{title}" {subtitle_part}'
    _run_applescript(script)
    return f"Notificação enviada: {title}"


def get_clipboard() -> str:
    result = subprocess.run(["pbpaste"], capture_output=True, text=True)
    return result.stdout


def set_clipboard(text: str) -> str:
    subprocess.run(["pbcopy"], input=text.encode(), check=True)
    return "Texto copiado para o clipboard."


def get_active_window() -> str:
    script = '''
    tell application "System Events"
        set frontApp to name of first application process whose frontmost is true
    end tell
    return frontApp
    '''
    return _run_applescript(script)


def set_volume(level: int) -> str:
    level = max(0, min(100, level))
    script = f"set volume output volume {level}"
    _run_applescript(script)
    return f"Volume ajustado para {level}%."


def lock_screen() -> str:
    script = 'tell application "System Events" to keystroke "q" using {control down, command down}'
    _run_applescript(script)
    return "Tela bloqueada."


def open_url(url: str) -> str:
    result = subprocess.run(["open", url], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return f"URL aberta no browser: {url}"
    return f"Erro ao abrir URL: {result.stderr.strip()}"


def browser_action(action: str, app: str = "Google Chrome", tab_index: int = -1) -> str:
    """
    Controla o browser via AppleScript.
    action: 'close_tab' | 'close_window' | 'close_all_windows' | 'list_tabs' | 'new_tab' | 'reload'
    """
    if action == "close_tab":
        if tab_index > 0:
            script = f'tell application "{app}" to close tab {tab_index} of front window'
        else:
            script = f'tell application "{app}" to close active tab of front window'

    elif action == "close_window":
        script = f'tell application "{app}" to close front window'

    elif action == "close_all_windows":
        script = f'tell application "{app}" to close every window'

    elif action == "list_tabs":
        script = f'''
        tell application "{app}"
            set tabList to {{}}
            repeat with t in tabs of front window
                set end of tabList to (title of t & " — " & URL of t)
            end repeat
            return tabList
        end tell
        '''

    elif action == "new_tab":
        script = f'tell application "{app}" to make new tab at end of tabs of front window'

    elif action == "reload":
        script = f'tell application "{app}" to reload active tab of front window'

    else:
        return f"Ação desconhecida: {action}"

    result = _run_applescript(script)
    return result or f"Ação '{action}' executada no {app}."


def type_text(text: str) -> str:
    script = f'tell application "System Events" to keystroke "{text}"'
    _run_applescript(script)
    return f"Texto digitado: {text}"
