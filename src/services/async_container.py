"""Async dependency injection container for services"""

from typing import Dict, Any, Optional, Type, TypeVar
import asyncio
from contextlib import asynccontextmanager

from services.async_user_service import AsyncUserService
from services.async_workout_service import AsyncWorkoutService
from services.async_session_manager import AsyncSessionManager
from services.async_analytics_service import AsyncAnalyticsService
from services.async_export_service import AsyncExportService
from database.async_connection import async_db

T = TypeVar('T')


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
            
        async with self._lock:
            # Initialize async database connection first
            await async_db.initialize()
            
            # Pre-initialize all services to catch configuration errors early
            await self.get_service(AsyncUserService)
            await self.get_service(AsyncWorkoutService)
            await self.get_service(AsyncSessionManager)
            await self.get_service(AsyncAnalyticsService)
            await self.get_service(AsyncExportService)
            
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


async def get_async_container() -> AsyncServiceContainer:
    """Get the global async service container"""
    global _async_container
    if _async_container is None:
        _async_container = AsyncServiceContainer()
        await _async_container.initialize_services()
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
    global _async_container
    if _async_container:
        await _async_container.shutdown()
    _async_container = None


@asynccontextmanager
async def async_service_context():
    """Context manager for async services lifecycle"""
    try:
        await initialize_async_services()
        yield
    finally:
        await shutdown_async_services()