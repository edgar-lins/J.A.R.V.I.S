"""Saída de voz do Jarvis — usada pelo wakeword, proativo e qualquer módulo."""
import subprocess
import tempfile
import os


def speak(text: str) -> None:
    """Fala o texto em voz alta. Usa ElevenLabs se configurado, senão say do macOS."""
    try:
        from voice.speak import synthesize
        audio = synthesize(text)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio)
            tmp = f.name
        try:
            subprocess.run(["afplay", tmp], check=False)
        finally:
            os.unlink(tmp)
    except Exception as e:
        print(f"[Voice] Fallback TTS: {e}")
        subprocess.Popen(["say", "-v", "Felipe", "-r", "175", text])
