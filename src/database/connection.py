from typing import Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from database.models import Base


class DatabaseConnection:
    """Singleton para gerenciar conexão com o banco"""

    _instance: Optional["DatabaseConnection"] = None
    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None

    def __new__(cls) -> "DatabaseConnection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._engine is None:
            self._engine = create_engine(
                settings.DATABASE_URL,
                echo=False,  # True para debug SQL
                pool_pre_ping=True,
                pool_size=10,           # Connection pool size
                max_overflow=20,        # Additional connections beyond pool_size
                pool_recycle=3600,      # Recycle connections after 1 hour
                pool_timeout=30,        # Timeout for getting connection from pool
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
    def engine(self) -> Optional[Engine]:
        return self._engine

db = DatabaseConnection()
