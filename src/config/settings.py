from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with automatic environment variable validation"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
        extra="ignore",
    )

    # Core settings
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(None, description="Telegram bot token")
    AUTHORIZED_USER_IDS: str = Field(
        default="", description="Comma-separated string of authorized user IDs"
    )
    DATABASE_URL: str = Field(
        default="sqlite:///gym_tracker.db", description="Database connection URL"
    )

    # AI/ML settings
    WHISPER_MODEL: str = Field(
        default="whisper-large-v3", description="Whisper model to use for transcription"
    )
    LLM_MODEL: str = Field(
        default="llama3.1:8b", description="LLM model for text processing"
    )
    OLLAMA_HOST: str = Field(
        default="http://localhost:11434", description="Ollama host URL"
    )
    GROQ_API_KEY: Optional[str] = Field(None, description="Groq API key")

    # Session and timeout settings
    SESSION_TIMEOUT_HOURS: int = Field(
        default=3, gt=0, le=24, description="Session timeout in hours"
    )

    # Rate limiting settings
    RATE_LIMIT_GENERAL_REQUESTS: int = Field(
        default=20, gt=0, le=1000, description="General request rate limit"
    )
    RATE_LIMIT_VOICE_REQUESTS: int = Field(
        default=5, gt=0, le=100, description="Voice request rate limit"
    )
    RATE_LIMIT_COMMAND_REQUESTS: int = Field(
        default=30, gt=0, le=1000, description="Command request rate limit"
    )
    RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=60, gt=0, le=3600, description="Rate limit window in seconds"
    )
    RATE_LIMIT_CLEANUP_FREQUENCY_HOURS: int = Field(
        default=1, gt=0, le=24, description="Rate limit cleanup frequency in hours"
    )
    RATE_LIMIT_MAX_INACTIVE_SECONDS: int = Field(
        default=3600,
        gt=0,
        le=86400,
        description="Remove users inactive for this many seconds",
    )

    # File size limits (in MB)
    MAX_AUDIO_FILE_SIZE_MB: int = Field(
        default=100, gt=0, le=500, description="Max audio file size in MB"
    )
    MAX_VOICE_FILE_SIZE_MB: int = Field(
        default=100, gt=0, le=500, description="Max voice file size in MB"
    )

    # Duration limits (in seconds)
    MAX_AUDIO_DURATION_SECONDS: int = Field(
        default=300, gt=0, le=3600, description="Max audio duration in seconds"
    )

    # Text limits
    MAX_TEXT_LENGTH: int = Field(
        default=1000, gt=0, le=50000, description="Max text length"
    )
    MAX_NAME_LENGTH: int = Field(
        default=100, gt=0, le=500, description="Max name length"
    )
    MAX_TRANSCRIPTION_LENGTH: int = Field(
        default=10000, gt=0, le=100000, description="Max transcription length"
    )

    # LLM settings
    LLM_TEMPERATURE: float = Field(
        default=0.1, ge=0.0, le=2.0, description="LLM temperature"
    )
    LLM_MAX_TOKENS: int = Field(
        default=8000, gt=0, le=100000, description="LLM max tokens"
    )

    # Logging limits
    LOG_TEXT_PREVIEW_LENGTH: int = Field(
        default=100, gt=0, le=1000, description="Log text preview length"
    )
    LOG_MESSAGE_PREVIEW_LENGTH: int = Field(
        default=50, gt=0, le=500, description="Log message preview length"
    )

    @property
    def authorized_user_ids_list(self) -> List[int]:
        """Get AUTHORIZED_USER_IDS as a list of integers"""
        if not self.AUTHORIZED_USER_IDS.strip():
            print(
                "⚠️  AVISO: Nenhum usuário autorizado configurado! Configure AUTHORIZED_USER_IDS no arquivo .env"
            )
            return []

        try:
            # Remove spaces and convert to int
            ids = [
                int(user_id.strip())
                for user_id in self.AUTHORIZED_USER_IDS.split(",")
                if user_id.strip()
            ]
            return ids
        except ValueError as e:
            raise ValueError(
                f"❌ Erro ao converter AUTHORIZED_USER_IDS: {e}\n"
                f"   Certifique-se de usar apenas números separados por vírgula",
            )

    @validator("AUTHORIZED_USER_IDS")
    def validate_authorized_user_ids(cls, v):
        """Validate AUTHORIZED_USER_IDS format"""
        if not v.strip():
            return v  # Allow empty string

        try:
            # Test parsing to ensure valid format
            [int(user_id.strip()) for user_id in v.split(",") if user_id.strip()]
            return v
        except ValueError as e:
            raise ValueError(
                f"❌ Erro ao converter AUTHORIZED_USER_IDS: {e}\n"
                f"   Certifique-se de usar apenas números separados por vírgula",
            )

    @validator("TELEGRAM_BOT_TOKEN")
    def validate_bot_token(cls, v):
        """Validate Telegram bot token format"""
        if v and not v.startswith(("bot", "telegram")):
            # Basic validation for Telegram bot token format
            if ":" not in v or len(v) < 20:
                raise ValueError("Invalid Telegram bot token format")
        return v

    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Validate database URL format"""
        if not v.startswith(
            ("sqlite://", "postgresql://", "mysql://", "sqlite+aiosqlite://")
        ):
            raise ValueError("Unsupported database URL format")
        return v

    @validator("OLLAMA_HOST")
    def validate_ollama_host(cls, v):
        """Validate Ollama host URL format"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Ollama host must be a valid HTTP/HTTPS URL")
        return v


# Create singleton instance
settings = Settings()
