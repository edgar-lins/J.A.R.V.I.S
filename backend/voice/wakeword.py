"""
Wake word detection local via faster-whisper.
Fluxo: energia → tiny model detecta 'Jarvis' → entra em sessão → escuta comandos direto por _SESSION_TIMEOUT segundos.
Cada comando renova o timer. Sem fala → sessão expira → volta a aguardar wake word.
"""
import re
import threading
import subprocess
import tempfile
import os
import time
import numpy as np
import sounddevice as sd
import soundfile as sf
from config import get_settings

settings = get_settings()

_SAMPLE_RATE    = 16000
_CHUNK          = 480
_ENERGY_THRESH  = 350
_SILENCE_CHUNKS = 20
_MIN_SPEECH     = 6
_MAX_SPEECH     = 200

_CMD_SILENCE    = 1.4
_CMD_MAX        = 12
_CMD_ENERGY     = 0.012

_SESSION_TIMEOUT = 60   # segundos de sessão ativa após wake word

_WAKE_WORDS = {"jarvis", "jarvis,", "jarvis.", "hey jarvis", "oi jarvis", "jar"}

# Palavras que indicam que o usuário está falando sobre algo na tela
_SCREEN_TRIGGERS = {
    "tela", "aqui", "isso", "esse", "essa", "este", "esta",
    "erro", "error", "bug", "código", "code", "terminal",
    "veja", "olha", "olhe", "vê", "tá vendo", "o que tá",
    "o que está", "que tá escrito", "o que é isso",
}

_running = False
_thread: threading.Thread | None = None
_whisper_tiny = None
_whisper_main = None


def _get_tiny():
    global _whisper_tiny
    if _whisper_tiny is None:
        from faster_whisper import WhisperModel
        print("[WakeWord] Carregando modelo tiny...")
        _whisper_tiny = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _whisper_tiny


def _get_main():
    global _whisper_main
    if _whisper_main is None:
        from voice.listen import _get_model
        _whisper_main = _get_model()
    return _whisper_main


def _chime() -> None:
    subprocess.Popen(["afplay", "/System/Library/Sounds/Tink.aiff"])


def _speak(text: str) -> None:
    from voice.output import speak
    speak(text)


def _transcribe_wake(audio_int16: np.ndarray) -> str:
    model = _get_tiny()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        audio_float = audio_int16.astype(np.float32) / 32768.0
        sf.write(tmp, audio_float, _SAMPLE_RATE)
        segs, _ = model.transcribe(
            tmp,
            language=None,
            initial_prompt="Jarvis",
            condition_on_previous_text=False,
            vad_filter=True,
        )
        return " ".join(s.text.strip() for s in segs).strip().lower()
    finally:
        os.unlink(tmp)


def _transcribe_command(audio_int16: np.ndarray) -> str:
    model = _get_main()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp = f.name
    try:
        audio_float = audio_int16.astype(np.float32) / 32768.0
        sf.write(tmp, audio_float, _SAMPLE_RATE)
        segs, _ = model.transcribe(tmp, language="pt",
                                   condition_on_previous_text=False,
                                   vad_filter=True)
        return " ".join(s.text.strip() for s in segs).strip()
    finally:
        os.unlink(tmp)


def _record_command() -> np.ndarray | None:
    chunks = []
    silent = 0
    silent_limit = int(_CMD_SILENCE * _SAMPLE_RATE / _CHUNK)
    max_chunks   = int(_CMD_MAX     * _SAMPLE_RATE / _CHUNK)

    with sd.InputStream(samplerate=_SAMPLE_RATE, channels=1,
                        dtype="float32", blocksize=_CHUNK) as stream:
        for _ in range(max_chunks):
            data, _ = stream.read(_CHUNK)
            chunks.append(data.copy())
            rms = float(np.sqrt(np.mean(data ** 2)))
            silent = (silent + 1) if rms < _CMD_ENERGY else 0
            if silent >= silent_limit and len(chunks) > 10:
                break

    return np.concatenate(chunks, axis=0) if chunks else None


def _extract_inline_command(text: str) -> str:
    cleaned = re.sub(r"^(oi\s+)?jarvi?s[,.\s]*", "", text, flags=re.IGNORECASE).strip()
    return cleaned if len(cleaned) > 2 else ""


def _is_wake_word(text: str) -> bool:
    if not text:
        return False
    words = text.split()
    for i in range(len(words)):
        token = " ".join(words[i:i+2])
        if token in _WAKE_WORDS or words[i] in _WAKE_WORDS:
            return True
        if words[i].startswith("jar"):
            return True
    return False


def _needs_screen(command: str) -> bool:
    words = command.lower().split()
    return any(trigger in command.lower() for trigger in _SCREEN_TRIGGERS)


def _run_command(user_id: str, command: str, chat_fn) -> None:
    try:
        screen_b64 = None
        if _needs_screen(command):
            try:
                from mac_agent.actions import screenshot_as_base64
                screen_b64 = screenshot_as_base64()
                print("[WakeWord] Screenshot capturado para contexto.")
            except Exception as e:
                print(f"[WakeWord] Screenshot falhou: {e}")

        reply = chat_fn(user_id, f"voice-agent-{user_id}", command, screen_b64=screen_b64)
        print(f"[WakeWord] Resposta: {reply[:80]}")
        _speak(reply)
    except Exception as e:
        print(f"[WakeWord] Erro no chat: {e}")
        _speak("Tive um problema. Tente novamente.")


def _loop(user_id: str) -> None:
    try:
        _loop_inner(user_id)
    except Exception as e:
        import traceback
        print(f"[WakeWord] ERRO FATAL na thread: {e}")
        traceback.print_exc()


def _loop_inner(user_id: str) -> None:
    from core.brain import chat, _ensure_profile
    _ensure_profile(user_id)

    print("[WakeWord] Carregando modelos...")
    _get_tiny()
    _get_main()
    print("[WakeWord] Modelos prontos. Testando microfone...")

    try:
        with sd.InputStream(samplerate=_SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=_CHUNK) as test:
            test.read(_CHUNK)
        print("[WakeWord] Microfone OK.")
    except Exception as e:
        print(f"[WakeWord] ERRO no microfone: {e}")
        print("[WakeWord] Verifique permissões: Ajustes > Privacidade > Microfone")
        return

    session_until = 0.0  # timestamp de expiração da sessão ativa

    while _running:
        now = time.time()

        # ── MODO SESSÃO ───────────────────────────────────────────
        if now < session_until:
            remaining = int(session_until - now)
            print(f"[WakeWord] Sessão ativa ({remaining}s). Ouvindo...")
            cmd_audio = _record_command()
            if cmd_audio is not None:
                cmd_int16 = (cmd_audio * 32768).astype(np.int16)
                command = _transcribe_command(cmd_int16)
                print(f"[WakeWord] Comando (sessão): '{command}'")
                if command and len(command) > 2:
                    _run_command(user_id, command, chat)
                    session_until = time.time() + _SESSION_TIMEOUT  # renova após TTS terminar
                # sem fala detectada: deixa o timer correr normalmente
            continue

        # ── MODO WAKE WORD ────────────────────────────────────────
        print("[WakeWord] Aguardando wake word...")
        speech_buf: list[np.ndarray] = []
        silent_count = 0
        collecting = False

        with sd.InputStream(samplerate=_SAMPLE_RATE, channels=1,
                            dtype="int16", blocksize=_CHUNK) as stream:
            while _running and time.time() >= session_until:
                chunk, _ = stream.read(_CHUNK)
                chunk = chunk.copy()
                rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2)))

                if rms > _ENERGY_THRESH:
                    if not collecting:
                        collecting = True
                        speech_buf = []
                    speech_buf.append(chunk)
                    silent_count = 0
                elif collecting:
                    speech_buf.append(chunk)
                    silent_count += 1

                    if silent_count >= _SILENCE_CHUNKS or len(speech_buf) >= _MAX_SPEECH:
                        if len(speech_buf) >= _MIN_SPEECH:
                            audio = np.concatenate(speech_buf).flatten()
                            text  = _transcribe_wake(audio)
                            print(f"[WakeWord] Detectado: '{text}'")

                            if _is_wake_word(text):
                                print("[WakeWord] Wake word! Entrando em sessão.")
                                _chime()
                                inline = _extract_inline_command(text)
                                session_until = time.time() + _SESSION_TIMEOUT

                                if inline:
                                    print(f"[WakeWord] Comando inline: '{inline}'")
                                    _run_command(user_id, inline, chat)
                                else:
                                    _speak("Estou aqui.")

                                break  # sai do loop de wake word → entra em sessão

                        collecting = False
                        speech_buf = []
                        silent_count = 0


def start(user_id: str) -> None:
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_loop, args=(user_id,), daemon=True)
    _thread.start()


def stop() -> None:
    global _running
    _running = False
