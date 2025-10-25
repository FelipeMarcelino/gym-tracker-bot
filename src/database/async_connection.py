"""Async database connection for improved performance"""

from typing import Optional, AsyncGenerator
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from config.logging_config import get_logger
from config.settings import settings
from database.models import Base

logger = get_logger(__name__)


class AsyncDatabaseConnection:
    """Async database connection manager with connection pooling"""

    _instance: Optional["AsyncDatabaseConnection"] = None
    _engine: Optional[AsyncEngine] = None
    _session_factory: Optional[async_sessionmaker[AsyncSession]] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> "AsyncDatabaseConnection":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        """Initialize async database connection"""
        async with self._lock:
            if self._engine is None:
                # Read DATABASE_URL from environment directly to support test overrides
                import os

                database_url = os.getenv("DATABASE_URL", "sqlite:///gym_tracker.db")

                # Convert SQLite URL to async version
                if database_url.startswith("sqlite:///"):
                    async_url = database_url.replace(
                        "sqlite:///", "sqlite+aiosqlite:///"
                    )
                else:
                    # For other databases, you might need different async drivers
                    # PostgreSQL: postgresql+asyncpg://
                    # MySQL: mysql+aiomysql://
                    async_url = database_url

                # Configure engine based on database type
                if "sqlite" in async_url:
                    # SQLite-specific configuration (no connection pooling)
                    self._engine = create_async_engine(
                        async_url,
                        echo=False,  # True for debug SQL
                        poolclass=NullPool,
                    )
                else:
                    # Other databases (PostgreSQL, MySQL, etc.)
                    self._engine = create_async_engine(
                        async_url,
                        echo=False,  # True for debug SQL
                        pool_pre_ping=True,
                        pool_size=10,  # Connection pool size
                        max_overflow=20,  # Additional connections beyond pool_size
                        pool_recycle=3600,  # Recycle connections after 1 hour
                        pool_timeout=30,  # Timeout for getting connection from pool
                    )

                self._session_factory = async_sessionmaker(
                    bind=self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )

                # Create tables if they don't exist
                async with self._engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)

                logger.info(f"Async database initialized: {async_url}")

    async def get_session(self) -> AsyncSession:
        """Get an async database session"""
        if self._session_factory is None:
            await self.initialize()
        return self._session_factory()

    @asynccontextmanager
    async def get_session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async session as a context manager"""
        session = await self.get_session()
        try:
            yield session
        finally:
            await session.close()

    @property
    def engine(self) -> Optional[AsyncEngine]:
        """Get the async engine"""
        return self._engine

    async def close(self) -> None:
        """Close the async database connection"""
        if self._engine:
            await self._engine.dispose()
            logger.info("Async database connection closed")


# Global async database instance
async_db = AsyncDatabaseConnection()


# Utility functions for easier usage
async def get_async_session() -> AsyncSession:
    """Get an async database session"""
    return await async_db.get_session()


@asynccontextmanager
async def get_async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Get an async session as a context manager"""
    async with async_db.get_session_context() as session:
        yield session
