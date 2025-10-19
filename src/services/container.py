"""Dependency injection container for services"""

from typing import Dict, Any, Optional, Type, TypeVar, Generic
import threading

from services.audio_service import AudioTranscriptionService


T = TypeVar('T')


class ServiceContainer:
    """Simple dependency injection container"""
    
    def __init__(self) -> None:
        self._services: Dict[Type[T], T] = {}
        self._lock = threading.RLock()
        self._initialized = False
    
    def register_service(self, service_type: Type[T], instance: T) -> None:
        """Register a service instance"""
        with self._lock:
            self._services[service_type] = instance
    
    def get_service(self, service_type: Type[T]) -> T:
        """Get a service instance"""
        with self._lock:
            if service_type not in self._services:
                # Auto-instantiate if not registered
                if service_type == AudioTranscriptionService:
                    instance = AudioTranscriptionService()
                else:
                    raise ValueError(f"Unknown service type: {service_type} - Note: Most services have been migrated to async versions. Check async_container.py")
                
                self._services[service_type] = instance
            
            return self._services[service_type]
    
    def clear(self) -> None:
        """Clear all registered services (useful for testing)"""
        with self._lock:
            self._services.clear()
    
    def initialize_services(self) -> None:
        """Initialize all services eagerly"""
        if self._initialized:
            return
            
        with self._lock:
            # Pre-initialize remaining sync services to catch configuration errors early
            self.get_service(AudioTranscriptionService)
            self._initialized = True


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """Get the global service container"""
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


# Convenience functions to maintain backward compatibility
def get_audio_service() -> AudioTranscriptionService:
    """Get audio transcription service"""
    return get_container().get_service(AudioTranscriptionService)


# Note: Most services have been migrated to async versions
# Use functions from async_container.py instead:
# - get_async_llm_service()
# - get_async_backup_service()
# - get_async_health_service()
# - get_async_shutdown_service()
# - get_async_export_service()
# - get_async_analytics_service()


def initialize_all_services() -> None:
    """Initialize all services - call this at startup"""
    get_container().initialize_services()


def clear_all_services() -> None:
    """Clear all services - useful for testing"""
    global _container
    if _container:
        _container.clear()
    _container = None