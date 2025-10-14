import os
from typing import List, Optional

from dotenv import load_dotenv


class Settings:
    """Singleton para configurações da aplicação"""

    _instance: Optional["Settings"] = None

    def __new__(cls) -> "Settings":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        load_dotenv()
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        self.AUTHORIZED_USER_IDS = self.get_authorized_users()
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_tracker.db")
        self.WHISPER_MODEL =  os.getenv("WHISPER_MODEL", "whisper-large-v3")  # tiny, base, small, medium, large
        self.LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
        self.OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.GROQ_API_KEY = os.getenv("GROQ_API_KEY")

        # Session and timeout settings
        self.SESSION_TIMEOUT_HOURS = int(os.getenv("SESSION_TIMEOUT_HOURS", "3"))

        # Rate limiting settings
        self.RATE_LIMIT_GENERAL_REQUESTS = int(os.getenv("RATE_LIMIT_GENERAL_REQUESTS", "20"))
        self.RATE_LIMIT_VOICE_REQUESTS = int(os.getenv("RATE_LIMIT_VOICE_REQUESTS", "5"))
        self.RATE_LIMIT_COMMAND_REQUESTS = int(os.getenv("RATE_LIMIT_COMMAND_REQUESTS", "30"))
        self.RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

        # File size limits (in MB)
        self.MAX_AUDIO_FILE_SIZE_MB = int(os.getenv("MAX_AUDIO_FILE_SIZE_MB", "100"))
        self.MAX_VOICE_FILE_SIZE_MB = int(os.getenv("MAX_VOICE_FILE_SIZE_MB", "100"))

        # Duration limits (in seconds)
        self.MAX_AUDIO_DURATION_SECONDS = int(os.getenv("MAX_AUDIO_DURATION_SECONDS", "300"))  # 5 minutes

        # Text limits
        self.MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "1000"))
        self.MAX_NAME_LENGTH = int(os.getenv("MAX_NAME_LENGTH", "100"))
        self.MAX_TRANSCRIPTION_LENGTH = int(os.getenv("MAX_TRANSCRIPTION_LENGTH", "10000"))

        # LLM settings
        self.LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        self.LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))

        # Logging limits
        self.LOG_TEXT_PREVIEW_LENGTH = int(os.getenv("LOG_TEXT_PREVIEW_LENGTH", "100"))
        self.LOG_MESSAGE_PREVIEW_LENGTH = int(os.getenv("LOG_MESSAGE_PREVIEW_LENGTH", "50"))

        self._initialized = True


    def get_authorized_users(self) -> List[int]:
        """Converte string de IDs em lista de inteiros
        Exemplo: "123,456,789" → [123, 456, 789]
        """
        if not os.getenv("AUTHORIZED_USER_IDS"):
            # Can't use logger here since settings are loaded before logging is configured
            print("⚠️  AVISO: Nenhum usuário autorizado configurado! Configure AUTHORIZED_USER_IDS no arquivo .env")
            return []

        try:
            # Remover espaços e converter para int
            ids = [
                int(user_id.strip())
                for user_id in os.getenv("AUTHORIZED_USER_IDS").split(",")
                if user_id.strip()
            ]
            return ids
        except ValueError as e:
            raise ValueError(
                f"❌ Erro ao converter AUTHORIZED_USER_IDS: {e}\n"
                f"   Certifique-se de usar apenas números separados por vírgula",
            )
settings = Settings()
