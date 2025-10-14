"""Dependency injection container for services"""

from typing import Dict, Any, Optional, Type, TypeVar, Generic
import threading

from services.audio_service import AudioTranscriptionService
from services.llm_service import LLMParsingService
from services.session_manager import SessionManager
from services.workout_service import WorkoutService
from services.export_service import ExportService
from services.analytics_service import AnalyticsService


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
                elif service_type == LLMParsingService:
                    instance = LLMParsingService()
                elif service_type == SessionManager:
                    instance = SessionManager()
                elif service_type == WorkoutService:
                    instance = WorkoutService()
                elif service_type == ExportService:
                    instance = ExportService()
                elif service_type == AnalyticsService:
                    instance = AnalyticsService()
                else:
                    raise ValueError(f"Unknown service type: {service_type}")
                
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
            # Pre-initialize all services to catch configuration errors early
            self.get_service(AudioTranscriptionService)
            self.get_service(LLMParsingService) 
            self.get_service(SessionManager)
            self.get_service(WorkoutService)
            self.get_service(ExportService)
            self.get_service(AnalyticsService)
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


def get_llm_service() -> LLMParsingService:
    """Get LLM parsing service"""
    return get_container().get_service(LLMParsingService)


def get_session_manager() -> SessionManager:
    """Get session manager service"""
    return get_container().get_service(SessionManager)


def get_workout_service() -> WorkoutService:
    """Get workout service"""
    return get_container().get_service(WorkoutService)


def get_export_service() -> ExportService:
    """Get export service"""
    return get_container().get_service(ExportService)


def get_analytics_service() -> AnalyticsService:
    """Get analytics service"""
    return get_container().get_service(AnalyticsService)


def initialize_all_services() -> None:
    """Initialize all services - call this at startup"""
    get_container().initialize_services()


def clear_all_services() -> None:
    """Clear all services - useful for testing"""
    global _container
    if _container:
        _container.clear()
    _container = None