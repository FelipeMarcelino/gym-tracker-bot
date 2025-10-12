import os
from typing import Optional

from dotenv import load_dotenv


class Settings:
    """Singleton para configurações da aplicação"""

    _instance: Optional["Settings"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        load_dotenv()
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        #self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_tracker.db")
        #self.LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
        #self.OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        #self.WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
        #self._initialized = True

settings = Settings()
