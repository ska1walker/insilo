"""Runtime configuration via env vars (Pydantic Settings)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "insilo"
    db_user: str = "insilo"
    db_password: str = "insilo_dev_only"

    # --- Redis / KVRocks ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_namespace: str = "insilo"

    # --- MinIO / S3 ---
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "insilo_dev"
    minio_secret_key: str = "insilo_dev_secret"
    minio_bucket: str = "insilo-audio"
    minio_use_ssl: bool = False

    # --- App ---
    app_lang: str = "de"
    app_timezone: str = "Europe/Berlin"
    audio_retention_days: int = 90
    max_upload_mb: int = 500

    # --- Internal AI services ---
    whisper_url: str = "http://localhost:8001"
    embeddings_url: str = "http://localhost:8002"

    # LLM is reached via an OpenAI-compatible endpoint. On Olares we point at
    # the LiteLLM gateway (shared across all kaivo apps so we don't burn an
    # extra GPU slot). Locally we run Ollama natively on Mac Metal; its
    # /v1/chat/completions endpoint is OpenAI-compatible too.
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "sk-local"     # Ollama doesn't enforce; LiteLLM does
    llm_model: str = "qwen2.5:7b-instruct"

    # The system template used when the user doesn't pick one explicitly.
    default_template_id: str = "00000000-0000-0000-0000-000000000001"

    # --- Olares context (dev defaults) ---
    olares_user: str = "devuser"
    olares_zone: str = "devuser.olares.local"

    # --- Dev ---
    log_level: str = "info"
    debug: bool = True

    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
