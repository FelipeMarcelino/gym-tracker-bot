from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from database.models import Base


class DatabaseConnection:
    """Singleton para gerenciar conexão com o banco"""

    _instance: Optional["DatabaseConnection"] = None
    _engine = None
    _session_factory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._engine = create_engine(
                settings.DATABASE_URL,
                echo=False,  # True para debug SQL
                pool_pre_ping=True,
            )
            self._session_factory = sessionmaker(
                bind=self._engine,
                expire_on_commit=False,
            )
            # Criar tabelas se não existirem
            Base.metadata.create_all(self._engine)
            print(f"✅ Banco de dados inicializado: {settings.DATABASE_URL}")

    def get_session(self) -> Session:
        """Retorna uma nova sessão do banco"""
        return self._session_factory()

    @property
    def engine(self):
        return self._engine

db = DatabaseConnection()
