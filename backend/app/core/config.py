from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Meeting Intelligence & Accountability System"
    APP_ENV: str = "development"
    DEBUG: bool = True

    API_V1_PREFIX: str = "/api"

    DATABASE_URL: str = (
        "postgresql://postgres:postgres@localhost:5432/"
        "meeting_intelligence"
    )

    # AI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Local Ollama
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3:4b"

    # Embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Speech-to-text
    WHISPER_MODEL: str = "small"

    # Speaker diarization
    HUGGINGFACE_TOKEN: str = ""

    # Files
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 500

    ALLOWED_AUDIO_EXTENSIONS: str = (
        ".mp3,.wav,.m4a,.aac,.flac,.ogg,.webm"
    )

    ALLOWED_VIDEO_EXTENSIONS: str = (
        ".mp4,.mov,.avi,.mkv,.webm"
    )

    # Frontend
    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://localhost:3001"
    )

    # Authentication
    JWT_SECRET: str = "change-this-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # Processing
    MAX_TRANSCRIPT_SEGMENTS: int = 10000
    MAX_MEETING_TITLE_LENGTH: int = 255

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]

    @property
    def allowed_audio_extensions(self) -> list[str]:
        return [
            extension.strip().lower()
            for extension in self.ALLOWED_AUDIO_EXTENSIONS.split(",")
            if extension.strip()
        ]

    @property
    def allowed_video_extensions(self) -> list[str]:
        return [
            extension.strip().lower()
            for extension in self.ALLOWED_VIDEO_EXTENSIONS.split(",")
            if extension.strip()
        ]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()