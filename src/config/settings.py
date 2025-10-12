import os
from typing import List, Optional

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
        self.AUTHORIZED_USER_IDS = self.get_authorized_users()
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_tracker.db")
        self.WHISPER_MODEL =  os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large
        self.LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
        self.OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        #self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///gym_tracker.db")
        #self.LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
        #self.OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        #self.WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
        #self._initialized = True


    def get_authorized_users(self) -> List[int]:
        """Converte string de IDs em lista de inteiros
        Exemplo: "123,456,789" → [123, 456, 789]
        """
        if not os.getenv("AUTHORIZED_USER_IDS"):
            print("⚠️  AVISO: Nenhum usuário autorizado configurado!")
            print("   Configure AUTHORIZED_USER_IDS no arquivo .env")
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
