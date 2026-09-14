from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nahallm_api_keys: str = ""
    nahallm_request_timeout_seconds: float = 45.0
    nahallm_max_retries_per_provider: int = 0

    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model_fast: str = "llama-3.1-8b-instant"
    groq_model_balanced: str = "llama-3.3-70b-versatile"

    cerebras_api_key: str = ""
    cerebras_base_url: str = "https://api.cerebras.ai/v1"
    cerebras_model_fast: str = "llama-3.1-8b"
    cerebras_model_balanced: str = "llama-3.3-70b"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model_balanced: str = "gemini-2.5-flash"
    gemini_model_premium: str = "gemini-2.5-pro"

    mistral_api_key: str = ""
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_model_balanced: str = "mistral-small-latest"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model_premium: str = ""

    @property
    def api_keys(self) -> set[str]:
        return {key.strip() for key in self.nahallm_api_keys.split(",") if key.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
