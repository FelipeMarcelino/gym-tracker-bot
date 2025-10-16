"""Async dependency injection container for services"""

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Optional, Type, TypeVar

from config.logging_config import get_logger
from database.async_connection import async_db
from services.async_analytics_service import AsyncAnalyticsService
from services.async_export_service import AsyncExportService
from services.async_session_manager import AsyncSessionManager
from services.async_user_service import AsyncUserService
from services.async_workout_service import AsyncWorkoutService

logger = get_logger(__name__)
T = TypeVar("T")


class AsyncServiceContainer:
    """Async dependency injection container for improved performance"""

    def __init__(self) -> None:
        self._services: Dict[Type[T], T] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def register_service(self, service_type: Type[T], instance: T) -> None:
        """Register a service instance (async)"""
        async with self._lock:
            self._services[service_type] = instance

    async def get_service(self, service_type: Type[T]) -> T:
        """Get a service instance (async)"""
        async with self._lock:
            if service_type not in self._services:
                # Auto-instantiate if not registered
                if service_type == AsyncUserService:
                    instance = AsyncUserService()
                elif service_type == AsyncWorkoutService:
                    instance = AsyncWorkoutService()
                elif service_type == AsyncSessionManager:
                    instance = AsyncSessionManager()
                elif service_type == AsyncAnalyticsService:
                    instance = AsyncAnalyticsService()
                elif service_type == AsyncExportService:
                    instance = AsyncExportService()
                else:
                    raise ValueError(f"Unknown async service type: {service_type}")

                self._services[service_type] = instance

            return self._services[service_type]

    async def clear(self) -> None:
        """Clear all registered services (useful for testing)"""
        async with self._lock:
            self._services.clear()

    async def initialize_services(self) -> None:
        """Initialize all async services eagerly"""
        if self._initialized:
            return

        # Create services outside the lock
        services_to_create = {
            AsyncUserService: AsyncUserService(),
            AsyncWorkoutService: AsyncWorkoutService(),
            AsyncSessionManager: AsyncSessionManager(),
            AsyncAnalyticsService: AsyncAnalyticsService(),
            AsyncExportService: AsyncExportService(),
        }

        async with self._lock:
            if self._initialized:
                return

            # Initialize async database connection first
            await async_db.initialize()

            # Register the pre-created services
            for service_type, instance in services_to_create.items():
                self._services[service_type] = instance

            # Perform startup cleanup of stale sessions
            session_manager = self._services[AsyncSessionManager]
            cleaned_count = await session_manager.cleanup_stale_sessions()
            if cleaned_count > 0:
                logger.info(f"🧹 Startup cleanup: {cleaned_count} stale sessions marked as finished")
            else:
                logger.info("🧹 Startup cleanup: No stale sessions found")

            self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown async services and cleanup resources"""
        async with self._lock:
            # Close database connections
            await async_db.close()

            # Clear services
            self._services.clear()
            self._initialized = False


# Global async container instance
_async_container: Optional[AsyncServiceContainer] = None
_container_lock = asyncio.Lock()


async def get_async_container() -> AsyncServiceContainer:
    """Get the global async service container, creating it if it doesn't exist."""
    global _async_container
    if _async_container is None:
        async with _container_lock:
            if _async_container is None:
                _async_container = AsyncServiceContainer()
    return _async_container



# Convenience functions for async services
async def get_async_user_service() -> AsyncUserService:
    """Get async user service"""
    container = await get_async_container()
    return await container.get_service(AsyncUserService)


async def get_async_workout_service() -> AsyncWorkoutService:
    """Get async workout service"""
    container = await get_async_container()
    return await container.get_service(AsyncWorkoutService)


async def get_async_session_manager() -> AsyncSessionManager:
    """Get async session manager service"""
    container = await get_async_container()
    return await container.get_service(AsyncSessionManager)


async def get_async_analytics_service() -> AsyncAnalyticsService:
    """Get async analytics service"""
    container = await get_async_container()
    return await container.get_service(AsyncAnalyticsService)


async def get_async_export_service() -> AsyncExportService:
    """Get async export service"""
    container = await get_async_container()
    return await container.get_service(AsyncExportService)


async def initialize_async_services() -> None:
    """Initialize all async services - call this at startup"""
    container = await get_async_container()
    await container.initialize_services()


async def shutdown_async_services() -> None:
    """Shutdown all async services - call this at shutdown"""
    container = await get_async_container()
    await container.shutdown()
    global _async_container
    _async_container = None



@asynccontextmanager
async def async_service_context():
    """Context manager for async services lifecycle"""
    try:
        await initialize_async_services()
        yield
    finally:
        await shutdown_async_services()

