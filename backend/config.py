from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    anthropic_api_key: str
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel — trocar pela voz do Jarvis
    porcupine_access_key: str = ""

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change_me"

    default_user_id: str = "edgar"

    claude_model: str = "claude-opus-4-7"
    whisper_model: str = "base"  # tiny | base | small | medium | large

    github_token: str = ""
    github_username: str = ""
    brave_api_key: str = ""
    spotify_client_id: str = ""
    spotify_client_secret: str = ""


    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
