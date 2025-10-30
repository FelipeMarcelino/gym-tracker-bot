"""Unit tests for dependency injection container"""

import threading
import time
from typing import Protocol
from unittest.mock import MagicMock, patch, Mock
import pytest

from services.container import (
    ServiceContainer,
    get_container,
    get_audio_service,
    initialize_all_services,
    clear_all_services,
)
from services.audio_service import AudioTranscriptionService


# Test service interfaces for mocking
class MockService:
    """Mock service for testing"""
    
    def __init__(self, name: str = "test"):
        self.name = name
        self.initialized = True
    
    def do_something(self):
        return f"Mock service {self.name} doing something"


class MockServiceInterface(Protocol):
    """Protocol for mock service interface"""
    
    def do_something(self) -> str:
        ...


class TestServiceContainer:
    """Test cases for ServiceContainer class"""

    def test_container_initialization(self):
        """Test container initialization with proper state"""
        # Act
        container = ServiceContainer()
        
        # Assert
        assert container._services == {}
        assert container._initialized is False
        assert hasattr(container, '_lock')
        assert isinstance(container._lock, type(threading.RLock()))

    def test_register_service(self):
        """Test service registration"""
        # Arrange
        container = ServiceContainer()
        mock_service = MockService("test1")
        
        # Act
        container.register_service(MockService, mock_service)
        
        # Assert
        assert MockService in container._services
        assert container._services[MockService] is mock_service

    def test_register_multiple_services(self):
        """Test registering multiple different service types"""
        # Arrange
        container = ServiceContainer()
        mock_service1 = MockService("service1")
        
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            mock_service2 = AudioTranscriptionService()
        
        # Act
        container.register_service(MockService, mock_service1)
        container.register_service(AudioTranscriptionService, mock_service2)
        
        # Assert
        assert len(container._services) == 2
        assert container._services[MockService] is mock_service1
        assert container._services[AudioTranscriptionService] is mock_service2

    def test_get_registered_service(self):
        """Test retrieving a pre-registered service"""
        # Arrange
        container = ServiceContainer()
        mock_service = MockService("registered")
        container.register_service(MockService, mock_service)
        
        # Act
        retrieved_service = container.get_service(MockService)
        
        # Assert
        assert retrieved_service is mock_service
        assert retrieved_service.name == "registered"

    def test_get_service_returns_same_instance(self):
        """Test that getting service multiple times returns same instance"""
        # Arrange
        container = ServiceContainer()
        mock_service = MockService("singleton")
        container.register_service(MockService, mock_service)
        
        # Act
        service1 = container.get_service(MockService)
        service2 = container.get_service(MockService)
        
        # Assert
        assert service1 is service2
        assert service1 is mock_service

    def test_auto_instantiate_audio_service(self):
        """Test auto-instantiation of AudioTranscriptionService"""
        # Arrange
        container = ServiceContainer()
        
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            # Act
            service = container.get_service(AudioTranscriptionService)
            
            # Assert
            assert service is not None
            assert isinstance(service, AudioTranscriptionService)
            assert AudioTranscriptionService in container._services

    def test_get_unknown_service_type_raises_error(self):
        """Test that unknown service types raise ValueError"""
        # Arrange
        container = ServiceContainer()
        
        class UnknownService:
            pass
        
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown service type"):
            container.get_service(UnknownService)

    def test_error_message_mentions_async_container(self):
        """Test that error message mentions async_container.py"""
        # Arrange
        container = ServiceContainer()
        
        class UnknownService:
            pass
        
        # Act & Assert
        with pytest.raises(ValueError, match="async_container.py"):
            container.get_service(UnknownService)

    def test_clear_services(self):
        """Test clearing all services from container"""
        # Arrange
        container = ServiceContainer()
        mock_service = MockService("to_clear")
        container.register_service(MockService, mock_service)
        
        # Verify service is registered
        assert len(container._services) == 1
        
        # Act
        container.clear()
        
        # Assert
        assert len(container._services) == 0
        assert MockService not in container._services

    def test_initialize_services(self):
        """Test eager initialization of all services"""
        # Arrange
        container = ServiceContainer()
        
        # Verify not initialized initially
        assert container._initialized is False
        
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            # Act
            container.initialize_services()
            
            # Assert
            assert container._initialized is True
            assert AudioTranscriptionService in container._services

    def test_initialize_services_idempotent(self):
        """Test that initialize_services can be called multiple times safely"""
        # Arrange
        container = ServiceContainer()
        
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            # Act - Initialize multiple times
            container.initialize_services()
            container.initialize_services()
            container.initialize_services()
            
            # Assert - Should only initialize once
            assert container._initialized is True
            # Service should be in container only once
            assert len([s for s in container._services.keys() if s == AudioTranscriptionService]) == 1

    def test_thread_safety_concurrent_registration(self):
        """Test thread safety during concurrent service registration"""
        # Arrange
        container = ServiceContainer()
        results = []
        errors = []
        
        def register_service(service_id):
            try:
                mock_service = MockService(f"service_{service_id}")
                # Use service_id as the type key to avoid conflicts
                service_type = type(f"MockService{service_id}", (), {})
                container.register_service(service_type, mock_service)
                results.append(service_id)
            except Exception as e:
                errors.append(e)
        
        # Act - Create multiple threads registering services
        threads = []
        for i in range(10):
            thread = threading.Thread(target=register_service, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Assert
        assert len(errors) == 0
        assert len(results) == 10
        assert len(container._services) == 10

    def test_thread_safety_concurrent_access(self):
        """Test thread safety during concurrent service access"""
        # Arrange
        container = ServiceContainer()
        mock_service = MockService("shared")
        container.register_service(MockService, mock_service)
        
        results = []
        errors = []
        
        def get_service():
            try:
                service = container.get_service(MockService)
                results.append(service.name)
            except Exception as e:
                errors.append(e)
        
        # Act - Create multiple threads accessing same service
        threads = []
        for i in range(20):
            thread = threading.Thread(target=get_service)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Assert
        assert len(errors) == 0
        assert len(results) == 20
        assert all(name == "shared" for name in results)

    def test_thread_safety_concurrent_initialization(self):
        """Test thread safety during concurrent service initialization"""
        # Arrange
        container = ServiceContainer()
        
        initialization_count = []
        errors = []
        
        def initialize_services():
            try:
                with patch('services.audio_service.settings') as mock_settings:
                    mock_settings.GROQ_API_KEY = "test_key"
                    container.initialize_services()
                    if container._initialized:
                        initialization_count.append(1)
            except Exception as e:
                errors.append(e)
        
        # Act - Create multiple threads initializing services
        threads = []
        for i in range(10):
            thread = threading.Thread(target=initialize_services)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Assert
        assert len(errors) == 0
        assert container._initialized is True
        # Service should be in container only once despite multiple threads
        assert len([s for s in container._services.keys() if s == AudioTranscriptionService]) == 1

    def test_service_replacement(self):
        """Test replacing a registered service with a new instance"""
        # Arrange
        container = ServiceContainer()
        original_service = MockService("original")
        replacement_service = MockService("replacement")
        
        # Act
        container.register_service(MockService, original_service)
        retrieved_original = container.get_service(MockService)
        
        container.register_service(MockService, replacement_service)
        retrieved_replacement = container.get_service(MockService)
        
        # Assert
        assert retrieved_original.name == "original"
        assert retrieved_replacement.name == "replacement"
        assert retrieved_replacement is not retrieved_original


class TestGlobalContainerManagement:
    """Test cases for global container functions"""

    def teardown_method(self):
        """Clean up after each test"""
        clear_all_services()

    def test_get_container_singleton(self):
        """Test that get_container returns the same instance"""
        # Act
        container1 = get_container()
        container2 = get_container()
        
        # Assert
        assert container1 is container2
        assert isinstance(container1, ServiceContainer)

    def test_get_container_creates_new_after_clear(self):
        """Test that get_container creates new instance after clearing"""
        # Arrange
        original_container = get_container()
        mock_service = MockService("test")
        original_container.register_service(MockService, mock_service)
        
        # Act
        clear_all_services()
        new_container = get_container()
        
        # Assert
        assert new_container is not original_container
        assert len(new_container._services) == 0

    def test_get_audio_service_convenience_function(self):
        """Test get_audio_service convenience function"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            # Act
            audio_service = get_audio_service()
            
            # Assert
            assert audio_service is not None
            assert isinstance(audio_service, AudioTranscriptionService)

    def test_get_audio_service_returns_same_instance(self):
        """Test that get_audio_service returns same instance on multiple calls"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            # Act
            service1 = get_audio_service()
            service2 = get_audio_service()
            
            # Assert
            assert service1 is service2
            assert isinstance(service1, AudioTranscriptionService)

    def test_initialize_all_services_function(self):
        """Test initialize_all_services function"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            # Act
            initialize_all_services()
            
            # Assert
            container = get_container()
            assert container._initialized is True

    def test_clear_all_services_function(self):
        """Test clear_all_services function"""
        # Arrange
        container = get_container()
        mock_service = MockService("to_clear")
        container.register_service(MockService, mock_service)
        
        # Verify service is registered
        assert len(container._services) == 1
        
        # Act
        clear_all_services()
        
        # Assert
        # Should create a new container since old one was cleared
        new_container = get_container()
        assert len(new_container._services) == 0

    def test_clear_all_services_before_any_container_created(self):
        """Test clearing services before any container is created"""
        # Arrange - Start with no global container
        import services.container
        services.container._container = None
        
        # Act - Should not raise any error
        clear_all_services()
        
        # Assert - Should still work
        container = get_container()
        assert isinstance(container, ServiceContainer)


class TestErrorHandling:
    """Test cases for error handling scenarios"""

    def teardown_method(self):
        """Clean up after each test"""
        clear_all_services()

    def test_service_instantiation_error_propagation(self):
        """Test that service instantiation errors are properly propagated"""
        # Arrange
        container = ServiceContainer()
        
        # Mock settings to fail during AudioTranscriptionService creation
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = None  # This should cause ServiceUnavailableError
            
            # Act & Assert
            with pytest.raises(Exception):  # Should raise ServiceUnavailableError
                container.get_service(AudioTranscriptionService)

    def test_register_service_with_none_instance(self):
        """Test registering a service with None instance"""
        # Arrange
        container = ServiceContainer()
        
        # Act
        container.register_service(MockService, None)
        
        # Assert
        assert container.get_service(MockService) is None

    def test_container_state_after_partial_initialization_failure(self):
        """Test container state when initialization partially fails"""
        # Arrange
        container = ServiceContainer()
        
        # Mock AudioTranscriptionService to fail at the container level
        with patch('services.container.AudioTranscriptionService') as mock_audio_class:
            mock_audio_class.side_effect = Exception("Audio service failed")
            
            # Act & Assert
            with pytest.raises(Exception, match="Audio service failed"):
                container.initialize_services()
            
            # Container should not be marked as initialized after failure
            assert container._initialized is False


class TestServiceLifecycle:
    """Test cases for service lifecycle management"""

    def teardown_method(self):
        """Clean up after each test"""
        clear_all_services()

    def test_service_registration_order_independence(self):
        """Test that service registration order doesn't matter"""
        # Arrange
        container = ServiceContainer()
        
        # Create services in different orders
        service_a = MockService("A")
        service_b = MockService("B")
        
        class ServiceA:
            pass
        
        class ServiceB:
            pass
        
        # Act - Register in one order
        container.register_service(ServiceB, service_b)
        container.register_service(ServiceA, service_a)
        
        # Assert - Should be able to retrieve in any order
        retrieved_a = container.get_service(ServiceA)
        retrieved_b = container.get_service(ServiceB)
        
        assert retrieved_a is service_a
        assert retrieved_b is service_b

    def test_lazy_vs_eager_initialization(self):
        """Test difference between lazy and eager initialization"""
        # Arrange
        container = ServiceContainer()
        
        # Act 1 - Lazy initialization (service not created yet)
        assert AudioTranscriptionService not in container._services
        
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            # Act 2 - First access triggers creation
            service = container.get_service(AudioTranscriptionService)
            assert service is not None
            assert isinstance(service, AudioTranscriptionService)
            
            # Test eager initialization with second container
            container2 = ServiceContainer()
            
            # Act 3 - Eager initialization
            container2.initialize_services()
            assert AudioTranscriptionService in container2._services

    def test_container_isolation(self):
        """Test that different container instances are isolated"""
        # Arrange
        container1 = ServiceContainer()
        container2 = ServiceContainer()
        
        service1 = MockService("container1")
        service2 = MockService("container2")
        
        # Act
        container1.register_service(MockService, service1)
        container2.register_service(MockService, service2)
        
        # Assert
        assert container1.get_service(MockService).name == "container1"
        assert container2.get_service(MockService).name == "container2"
        assert container1.get_service(MockService) is not container2.get_service(MockService)