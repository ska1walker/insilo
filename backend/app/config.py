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

    # --- Storage ---
    # "minio" → S3-API (boto3). "local" → write to a hostPath-mounted folder.
    # On Olares we default to "local" because cross-namespace S3 is locked
    # down by NetworkPolicy and the audio never has to leave the box anyway.
    storage_backend: str = "minio"
    storage_local_path: str = "/app/data/audio"

    # --- MinIO / S3 (only used when storage_backend == "minio") ---
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
    # Kein Vorgabewert. Jede Adresse, die wir hier raten würden, ist bei
    # einem anderen Kunden falsch: die Olares-App-Kennung von LiteLLM wird
    # erst bei dessen Installation vergeben, ein eigener Alias ist frei
    # gewählt, und der clusterinterne Weg ist durch den Envoy-Sidecar
    # gesperrt (verlangt einen Authelia-Token, den ein Server-zu-Server-
    # Aufruf nicht hat). Leer heißt „noch nicht eingerichtet" — die
    # Oberfläche sagt das, statt in einen Verbindungsfehler zu laufen.
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # ---- Spracherkennung ---------------------------------------------
    # Leer = der mitgelieferte Whisper-Dienst transkribiert, und kein Audio
    # verlässt die Box. Eine Adresse hier (oder pro Org in org_settings)
    # schaltet auf einen OpenAI-kompatiblen STT-Server um — dann geht das
    # Audio dorthin, und der Datenschutz-Nachweis sagt das.
    stt_base_url: str = ""
    stt_api_key: str = ""
    stt_model: str = ""

    # The system template used when the user doesn't pick one explicitly.
    default_template_id: str = "00000000-0000-0000-0000-000000000001"

    # --- Olares context (dev defaults) ---
    olares_zone: str = "devuser.olares.local"

    # --- Webhooks ---
    webhook_default_timeout_sec: int = 10
    webhook_max_retries: int = 2
    webhook_retry_base_delay_sec: int = 30

    # --- Speaker catalog ---
    # Cosine-Similarity, ab der ein Cluster-Centroid automatisch einem
    # Org-Speaker zugeordnet wird. 0.5 ist konservativ; bei viel manueller
    # Korrektur kann der User später hochziehen.
    speaker_match_threshold: float = 0.5
    # Pro Sprecher behalten wir die N jüngsten Voiceprints (FIFO). Genug
    # für robuste Mittelwerte, bei Stimme-altert/Mikrofon-Wechsel passt
    # sich der Voiceprint langsam an.
    speaker_max_voiceprints_per_speaker: int = 20
    # Ab dieser Cosine-Similarity blenden wir die "X% Confidence"-Pill
    # in der Transkript-Anzeige aus (zu offensichtlich um anzuzeigen).
    speaker_high_confidence_threshold: float = 0.75

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
