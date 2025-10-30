"""Integration tests for dependency injection container with real services"""

import asyncio
import threading
import time
from unittest.mock import patch
import pytest

from services.container import (
    ServiceContainer,
    get_container,
    get_audio_service,
    initialize_all_services,
    clear_all_services,
)
from services.audio_service import AudioTranscriptionService


class TestContainerIntegration:
    """Integration tests with real AudioTranscriptionService"""

    def teardown_method(self):
        """Clean up after each test"""
        clear_all_services()

    def test_real_audio_service_integration(self):
        """Test integration with real AudioTranscriptionService"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_api_key_integration"
            
            # Arrange
            container = ServiceContainer()
            
            # Act
            audio_service = container.get_service(AudioTranscriptionService)
            
            # Assert
            assert audio_service is not None
            assert isinstance(audio_service, AudioTranscriptionService)
            assert hasattr(audio_service, 'client')
            assert hasattr(audio_service, 'gym_vocabulary')
            
            # Verify service is cached
            audio_service2 = container.get_service(AudioTranscriptionService)
            assert audio_service is audio_service2

    def test_global_container_with_real_service(self):
        """Test global container functions with real service integration"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_global_integration"
            
            # Act
            audio_service1 = get_audio_service()
            audio_service2 = get_audio_service()
            
            # Assert
            assert audio_service1 is audio_service2
            assert isinstance(audio_service1, AudioTranscriptionService)
            
            # Verify global container state
            container = get_container()
            assert AudioTranscriptionService in container._services

    def test_service_initialization_with_real_dependencies(self):
        """Test service initialization with real dependencies"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_init_integration"
            
            # Act
            initialize_all_services()
            
            # Assert
            container = get_container()
            assert container._initialized is True
            assert AudioTranscriptionService in container._services
            
            # Verify service is properly initialized
            audio_service = container.get_service(AudioTranscriptionService)
            assert hasattr(audio_service, 'client')

    def test_service_clearing_integration(self):
        """Test service clearing with real services"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_clear_integration"
            
            # Arrange - Initialize services
            audio_service = get_audio_service()
            container = get_container()
            assert len(container._services) > 0
            
            # Act
            clear_all_services()
            
            # Assert
            new_container = get_container()
            assert new_container is not container
            assert len(new_container._services) == 0

    def test_error_propagation_integration(self):
        """Test error propagation from real service initialization"""
        # Arrange - No API key should cause ServiceUnavailableError
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = None
            
            container = ServiceContainer()
            
            # Act & Assert
            with pytest.raises(Exception):  # ServiceUnavailableError from audio service
                container.get_service(AudioTranscriptionService)

    def test_concurrent_access_integration(self):
        """Test concurrent access to real services"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_concurrent_integration"
            
            services = []
            errors = []
            
            def get_service():
                try:
                    service = get_audio_service()
                    services.append(service)
                except Exception as e:
                    errors.append(e)
            
            # Act - Create multiple threads accessing service
            threads = []
            for i in range(10):
                thread = threading.Thread(target=get_service)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # Assert
            assert len(errors) == 0
            assert len(services) == 10
            
            # All services should be the same instance (singleton behavior)
            first_service = services[0]
            for service in services:
                assert service is first_service

    def test_service_lifecycle_integration(self):
        """Test complete service lifecycle with real services"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_lifecycle_integration"
            
            # Step 1: Initialize
            initialize_all_services()
            container = get_container()
            assert container._initialized is True
            
            # Step 2: Use service
            audio_service = get_audio_service()
            assert isinstance(audio_service, AudioTranscriptionService)
            
            # Step 3: Verify persistence
            audio_service2 = get_audio_service()
            assert audio_service is audio_service2
            
            # Step 4: Clear and restart
            clear_all_services()
            new_container = get_container()
            assert new_container is not container
            assert not new_container._initialized
            
            # Step 5: Re-initialize
            audio_service3 = get_audio_service()
            assert isinstance(audio_service3, AudioTranscriptionService)
            assert audio_service3 is not audio_service  # New instance after clear

    def test_service_replacement_integration(self):
        """Test service replacement with real service types"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_replacement_integration"
            
            # Arrange
            container = ServiceContainer()
            
            # Get original service
            original_service = container.get_service(AudioTranscriptionService)
            
            # Create replacement service
            replacement_service = AudioTranscriptionService()
            
            # Act - Replace service
            container.register_service(AudioTranscriptionService, replacement_service)
            
            # Assert
            retrieved_service = container.get_service(AudioTranscriptionService)
            assert retrieved_service is replacement_service
            assert retrieved_service is not original_service

    def test_memory_cleanup_integration(self):
        """Test memory cleanup and garbage collection integration"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_memory_integration"
            
            # Arrange
            container = ServiceContainer()
            
            # Create and register multiple services
            services = []
            for i in range(5):
                service = AudioTranscriptionService()
                container.register_service(type(f"AudioService{i}", (), {}), service)
                services.append(service)
            
            # Verify services are registered
            assert len(container._services) == 5
            
            # Act - Clear container
            container.clear()
            
            # Assert
            assert len(container._services) == 0
            
            # Services should still exist in local scope but not in container
            for service in services:
                assert isinstance(service, AudioTranscriptionService)

    def test_configuration_dependency_integration(self):
        """Test container behavior with different configuration scenarios"""
        # Test 1: Valid configuration
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "valid_test_key"
            
            container = ServiceContainer()
            service = container.get_service(AudioTranscriptionService)
            assert isinstance(service, AudioTranscriptionService)
        
        # Test 2: Invalid configuration
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = None
            
            container2 = ServiceContainer()
            with pytest.raises(Exception):
                container2.get_service(AudioTranscriptionService)

    def test_thread_safety_under_load_integration(self):
        """Test thread safety under high load with real services"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_load_integration"
            
            results = []
            errors = []
            
            def stress_test():
                try:
                    # Mix of operations
                    container = get_container()
                    service = get_audio_service()
                    
                    # Simulate some work
                    time.sleep(0.001)
                    
                    # Verify service is correct type
                    if isinstance(service, AudioTranscriptionService):
                        results.append("success")
                    else:
                        results.append("failure")
                        
                except Exception as e:
                    errors.append(e)
            
            # Act - Create high load
            threads = []
            for i in range(50):
                thread = threading.Thread(target=stress_test)
                threads.append(thread)
                thread.start()
            
            # Wait for all threads
            for thread in threads:
                thread.join()
            
            # Assert
            assert len(errors) == 0
            assert len(results) == 50
            assert all(result == "success" for result in results)


class TestContainerRealWorldScenarios:
    """Test real-world usage scenarios"""

    def teardown_method(self):
        """Clean up after each test"""
        clear_all_services()

    def test_application_startup_scenario(self):
        """Test typical application startup scenario"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "startup_test_key"
            
            # Step 1: Application initialization
            initialize_all_services()
            
            # Step 2: Verify all services are available
            container = get_container()
            assert container._initialized is True
            
            # Step 3: Get services as needed
            audio_service = get_audio_service()
            assert isinstance(audio_service, AudioTranscriptionService)
            
            # Step 4: Verify services are ready for use
            assert hasattr(audio_service, 'client')
            assert hasattr(audio_service, 'gym_vocabulary')

    def test_service_access_patterns(self):
        """Test different service access patterns"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "access_pattern_test"
            
            # Pattern 1: Global convenience function (uses global container)
            service1 = get_audio_service()
            
            # Pattern 2: Multiple global accesses (should reuse same instance)
            service2 = get_audio_service()
            
            # Pattern 3: Access via global container (should be same as convenience function)
            global_container = get_container()
            service3 = global_container.get_service(AudioTranscriptionService)
            
            # Global services should be the same instance
            assert service1 is service2 is service3
            
            # Pattern 4: Separate container instance (different from global)
            separate_container = ServiceContainer()
            service4 = separate_container.get_service(AudioTranscriptionService)
            
            # Separate container creates different instance
            assert service4 is not service1

    def test_error_recovery_scenario(self):
        """Test error recovery and service re-initialization"""
        # Step 1: Service fails to initialize
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = None
            
            container = ServiceContainer()
            with pytest.raises(Exception):
                container.get_service(AudioTranscriptionService)
        
        # Step 2: Fix configuration and retry
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "recovery_test_key"
            
            # Should work after clearing and retrying
            clear_all_services()
            service = get_audio_service()
            assert isinstance(service, AudioTranscriptionService)

    def test_service_isolation_scenario(self):
        """Test service isolation between different container instances"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "isolation_test"
            
            # Create two separate containers
            container1 = ServiceContainer()
            container2 = ServiceContainer()
            
            # Register different instances in each
            service1 = AudioTranscriptionService()
            service2 = AudioTranscriptionService()
            
            container1.register_service(AudioTranscriptionService, service1)
            container2.register_service(AudioTranscriptionService, service2)
            
            # Verify isolation
            assert container1.get_service(AudioTranscriptionService) is service1
            assert container2.get_service(AudioTranscriptionService) is service2
            assert service1 is not service2

    def test_performance_characteristics(self):
        """Test performance characteristics of container operations"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "performance_test"
            
            container = ServiceContainer()
            
            # Test service retrieval performance
            start_time = time.time()
            
            # First access (includes instantiation)
            service1 = container.get_service(AudioTranscriptionService)
            first_access_time = time.time() - start_time
            
            # Subsequent accesses (cached)
            start_time = time.time()
            for _ in range(100):
                service = container.get_service(AudioTranscriptionService)
                assert service is service1
            
            cached_access_time = time.time() - start_time
            
            # Cached access should be much faster
            assert cached_access_time < first_access_time
            assert cached_access_time < 0.1  # Should be very fast for 100 cached accesses

    def test_container_state_consistency(self):
        """Test container state consistency across operations"""
        # Mock the settings to avoid actual API calls
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "consistency_test"
            
            # Test state transitions
            container = ServiceContainer()
            
            # Initial state
            assert not container._initialized
            assert len(container._services) == 0
            
            # After service access
            service = container.get_service(AudioTranscriptionService)
            assert len(container._services) == 1
            assert AudioTranscriptionService in container._services
            
            # After initialization
            container.initialize_services()
            assert container._initialized is True
            assert len(container._services) == 1  # Should not duplicate
            
            # After clear
            container.clear()
            assert len(container._services) == 0
            # Note: _initialized flag is not reset by clear() by design