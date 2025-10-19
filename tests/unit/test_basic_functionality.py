"""Basic functionality tests that should always pass"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Simple tests that verify core functionality without complex mocking


def test_imports():
    """Test that core modules can be imported"""
    try:
        from config.logging_config import get_logger
        from services.async_backup_service import BackupService
        from services.async_health_service import HealthService
        from services.async_shutdown_service import ShutdownService
        from services.exceptions import GymTrackerError, ValidationError
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import core modules: {e}")


def test_logger_initialization():
    """Test logger can be initialized"""
    from config.logging_config import get_logger
    
    logger = get_logger("test")
    assert logger is not None
    assert logger.name == "test"


def test_backup_service_creation():
    """Test backup service can be created"""
    from services.async_backup_service import BackupService
    
    with tempfile.TemporaryDirectory() as temp_dir:
        service = BackupService(
            backup_dir=temp_dir,
            max_backups=5,
            backup_frequency_hours=1
        )
        
        assert service.backup_dir == Path(temp_dir)
        assert service.max_backups == 5
        assert service.backup_frequency_hours == 1
        assert not service.is_running


def test_health_service_creation():
    """Test health service can be created"""
    from services.async_health_service import HealthService
    
    service = HealthService()
    assert service.command_count == 0
    assert service.audio_count == 0
    assert service.error_count == 0
    assert service.response_times == []


def test_shutdown_service_creation():
    """Test shutdown service can be created"""
    from services.async_shutdown_service import ShutdownService
    
    service = ShutdownService()
    assert service.shutdown_handlers == []
    assert service.is_shutting_down is False
    assert service.shutdown_timeout == 30


def test_exceptions_creation():
    """Test custom exceptions can be created"""
    from services.exceptions import GymTrackerError, ValidationError, BackupError
    
    # Test basic exception
    error = GymTrackerError("Test error")
    assert "Test error" in str(error)
    
    # Test validation error
    validation_error = ValidationError("Validation failed")
    assert "Validation failed" in str(validation_error)
    
    # Test backup error
    backup_error = BackupError("Backup failed")
    assert "Backup failed" in str(backup_error)


def test_health_service_metrics():
    """Test health service can record metrics"""
    from services.async_health_service import HealthService
    
    service = HealthService()
    
    # Record some metrics
    service.record_command(100.0, False)
    service.record_command(200.0, True)
    service.record_audio_processing(1500.0, False)
    
    assert service.command_count == 2
    assert service.audio_count == 1
    assert service.error_count == 1
    assert len(service.response_times) == 3


def test_shutdown_service_handlers():
    """Test shutdown service can register handlers"""
    from services.async_shutdown_service import ShutdownService
    
    service = ShutdownService()
    
    def test_handler():
        pass
    
    service.register_shutdown_handler(test_handler, "Test handler")
    assert len(service.shutdown_handlers) == 1


@pytest.mark.asyncio
async def test_async_health_service():
    """Test health service async functionality"""
    from services.async_health_service import HealthService
    from unittest.mock import patch
    
    service = HealthService()
    
    # Mock the complex parts to avoid real system calls
    with patch.object(service, '_run_health_checks') as mock_checks, \
         patch.object(service, '_collect_metrics') as mock_metrics:
        
        mock_checks.return_value = {"test": {"status": "healthy"}}
        mock_metrics.return_value = {"test": {"value": 100}}
        
        health_status = await service.get_health_status()
        
        assert health_status.status == "healthy"
        assert health_status.uptime_seconds >= 0
        assert "test" in health_status.checks


@pytest.mark.asyncio
async def test_backup_service_stats_no_backups():
    """Test backup service stats with no backups"""
    from services.async_backup_service import BackupService
    
    with tempfile.TemporaryDirectory() as temp_dir:
        service = BackupService(backup_dir=temp_dir)
        
        stats = await service.get_backup_stats()
        assert stats["total_backups"] == 0
        assert stats["total_size_mb"] == 0
        assert stats["newest_backup"] is None
        assert stats["oldest_backup"] is None


def test_backup_service_automation():
    """Test backup service automation controls"""
    from services.async_backup_service import BackupService
    
    with tempfile.TemporaryDirectory() as temp_dir:
        service = BackupService(backup_dir=temp_dir)
        
        # Initially not running
        assert not service.is_running
        
        # Start automation
        service.start_automated_backups()
        assert service.is_running
        
        # Stop automation  
        service.stop_automated_backups()
        assert not service.is_running


def test_configuration_loading():
    """Test configuration can be loaded"""
    try:
        from config.settings import settings
        assert hasattr(settings, 'TELEGRAM_BOT_TOKEN')
        assert hasattr(settings, 'DATABASE_URL')
    except Exception as e:
        pytest.fail(f"Failed to load configuration: {e}")


class TestBasicIntegration:
    """Basic integration tests between components"""
    
    @pytest.mark.asyncio
    async def test_health_service_with_backup_service(self):
        """Test health service can work with backup service"""
        from services.async_health_service import HealthService
        from services.async_backup_service import BackupService
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_service = BackupService(backup_dir=temp_dir)
            health_service = HealthService()
            
            # Should not error when services exist
            backup_stats = await backup_service.get_backup_stats()
            assert backup_stats["total_backups"] == 0
            
            simple_health = await health_service.get_simple_health()
            assert "status" in simple_health
    
    def test_shutdown_service_with_health_service(self):
        """Test shutdown service can work with health service"""
        from services.async_shutdown_service import ShutdownService
        from services.async_health_service import HealthService
        
        shutdown_service = ShutdownService()
        health_service = HealthService()
        
        # Register health-related shutdown handler
        def save_metrics():
            # Simulate saving health metrics
            pass
        
        shutdown_service.register_shutdown_handler(save_metrics, "Save metrics")
        assert len(shutdown_service.shutdown_handlers) == 1


def test_logging_integration():
    """Test logging works across services"""
    from config.logging_config import get_logger
    from services.async_health_service import HealthService
    
    # Get logger
    logger = get_logger("test_integration")
    
    # Create service that uses logging
    health_service = HealthService()
    
    # Should not error
    logger.info("Test log message")
    health_service.record_command(100, False)


@pytest.mark.asyncio
async def test_error_handling_integration():
    """Test error handling works across services"""
    from services.exceptions import BackupError, ValidationError
    from services.async_backup_service import BackupService
    
    with tempfile.TemporaryDirectory() as temp_dir:
        service = BackupService(backup_dir=temp_dir)
        service.database_path = "/nonexistent/database.db"
        
        # Should raise BackupError, not generic exception
        with pytest.raises(BackupError):
            await service.create_backup("test.db")


# Mark this as a comprehensive test
@pytest.mark.integration
def test_full_service_lifecycle():
    """Test complete service lifecycle"""
    from services.async_backup_service import BackupService
    from services.async_health_service import HealthService
    from services.async_shutdown_service import ShutdownService
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize services
        backup_service = BackupService(backup_dir=temp_dir)
        health_service = HealthService()
        shutdown_service = ShutdownService()
        
        # Start backup automation
        backup_service.start_automated_backups()
        
        # Record some health metrics
        health_service.record_command(150, False)
        health_service.record_audio_processing(2000, False)
        
        # Register shutdown handler
        def cleanup():
            pass
        
        shutdown_service.register_shutdown_handler(cleanup, "Cleanup")
        
        # Verify everything is working
        assert backup_service.is_running
        assert health_service.command_count == 1
        assert health_service.audio_count == 1
        assert len(shutdown_service.shutdown_handlers) == 1
        
        # Stop services
        backup_service.stop_automated_backups()
        assert not backup_service.is_running