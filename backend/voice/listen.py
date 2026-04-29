import io
import tempfile
import sounddevice as sd
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel
from config import get_settings

settings = get_settings()

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        # Roda 100% local, sem enviar áudio pra nenhuma API
        _model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    return _model


def transcribe_file(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    model = _get_model()
    segments, _ = model.transcribe(tmp_path, language="pt")
    return " ".join(s.text.strip() for s in segments).strip()


def record_from_mic(duration_seconds: int = 5, sample_rate: int = 16000) -> str:
    """Grava do microfone e transcreve. Usado pelo Mac agent."""
    print(f"[Jarvis] Ouvindo por {duration_seconds}s...")
    audio = sd.rec(
        int(duration_seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio, sample_rate)
        tmp_path = f.name

    model = _get_model()
    segments, _ = model.transcribe(tmp_path, language="pt")
    text = " ".join(s.text.strip() for s in segments).strip()
    print(f"[Jarvis] Você disse: {text}")
    return text
