import asyncio
import tempfile
import os
import edge_tts
from config import get_settings

settings = get_settings()

EDGE_VOICE = "pt-BR-AntonioNeural"


def synthesize(text: str) -> bytes:
    """Converte texto em áudio MP3. Usa ElevenLabs se configurado, senão edge-tts."""
    if settings.elevenlabs_api_key and settings.elevenlabs_api_key not in ("", "your_elevenlabs_api_key_here"):
        return _synthesize_elevenlabs(text)
    return asyncio.run(_synthesize_edge_tts(text))


def _synthesize_elevenlabs(text: str) -> bytes:
    from elevenlabs import ElevenLabs, VoiceSettings
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    audio = client.text_to_speech.convert(
        voice_id=settings.elevenlabs_voice_id,
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.8),
        output_format="mp3_44100_128",
    )
    return b"".join(audio)


async def _synthesize_edge_tts(text: str) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        tmp_path = f.name

    try:
        communicate = edge_tts.Communicate(text, EDGE_VOICE)
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)
