"""Unit tests for shutdown service"""

import pytest
import signal
import time
import asyncio
from unittest.mock import Mock, patch, AsyncMock

from services.async_shutdown_service import ShutdownService


class TestShutdownService:
    """Test shutdown service functionality"""
    
    def test_shutdown_service_initialization(self, test_shutdown_service):
        """Test shutdown service initializes correctly"""
        assert test_shutdown_service.shutdown_handlers == []
        assert test_shutdown_service.is_shutting_down is False
        assert test_shutdown_service.shutdown_timeout == 30
        assert test_shutdown_service.emergency_backup_on_shutdown is False  # Disabled for tests
    
    def test_register_sync_shutdown_handler(self, test_shutdown_service):
        """Test registering synchronous shutdown handlers"""
        def test_handler():
            pass
        
        test_shutdown_service.register_shutdown_handler(test_handler, "Test handler")
        
        assert len(test_shutdown_service.shutdown_handlers) == 1
        assert test_shutdown_service.shutdown_handlers[0] == test_handler
    
    def test_register_async_shutdown_handler(self, test_shutdown_service):
        """Test registering asynchronous shutdown handlers"""
        async def async_test_handler():
            pass
        
        test_shutdown_service.register_shutdown_handler(async_test_handler, "Async test handler")
        
        assert len(test_shutdown_service.shutdown_handlers) == 1
        # Should be wrapped in a sync function
        assert test_shutdown_service.shutdown_handlers[0] != async_test_handler
        assert callable(test_shutdown_service.shutdown_handlers[0])
    
    def test_setup_signal_handlers(self, test_shutdown_service):
        """Test signal handler setup"""
        # Store original handlers
        original_sigint = signal.signal(signal.SIGINT, signal.default_int_handler)
        original_sigterm = signal.signal(signal.SIGTERM, signal.default_int_handler)
        
        try:
            test_shutdown_service.setup_signal_handlers()
            
            # Check that handlers were registered
            current_sigint = signal.signal(signal.SIGINT, signal.default_int_handler)
            current_sigterm = signal.signal(signal.SIGTERM, signal.default_int_handler)
            
            # Should be different from default
            assert current_sigint != signal.default_int_handler
            assert current_sigterm != signal.default_int_handler
            
        finally:
            # Restore original handlers
            signal.signal(signal.SIGINT, original_sigint)
            signal.signal(signal.SIGTERM, original_sigterm)
    
    def test_run_shutdown_handlers_success(self, test_shutdown_service):
        """Test successful execution of shutdown handlers"""
        execution_order = []
        
        def handler1():
            execution_order.append("handler1")
        
        def handler2():
            execution_order.append("handler2")
            time.sleep(0.1)  # Simulate some work
        
        test_shutdown_service.register_shutdown_handler(handler1, "Handler 1")
        test_shutdown_service.register_shutdown_handler(handler2, "Handler 2")
        
        test_shutdown_service._run_shutdown_handlers()
        
        assert execution_order == ["handler1", "handler2"]
    
    def test_run_shutdown_handlers_with_error(self, test_shutdown_service):
        """Test shutdown handlers execution with errors"""
        execution_order = []
        
        def good_handler():
            execution_order.append("good")
        
        def error_handler():
            execution_order.append("error")
            raise Exception("Test error")
        
        def final_handler():
            execution_order.append("final")
        
        test_shutdown_service.register_shutdown_handler(good_handler, "Good handler")
        test_shutdown_service.register_shutdown_handler(error_handler, "Error handler")
        test_shutdown_service.register_shutdown_handler(final_handler, "Final handler")
        
        # Should not raise exception, but continue execution
        test_shutdown_service._run_shutdown_handlers()
        
        # All handlers should have been called despite error
        assert execution_order == ["good", "error", "final"]
    
    def test_run_async_shutdown_handler(self, test_shutdown_service):
        """Test execution of async shutdown handlers"""
        execution_log = []
        
        async def async_handler():
            await asyncio.sleep(0.01)
            execution_log.append("async_executed")
        
        test_shutdown_service.register_shutdown_handler(async_handler, "Async handler")
        test_shutdown_service._run_shutdown_handlers()
        
        assert execution_log == ["async_executed"]
    
    @pytest.mark.asyncio
    async def test_create_emergency_backup_disabled(self, test_shutdown_service):
        """Test emergency backup when disabled"""
        # Emergency backup is disabled in test fixture
        assert test_shutdown_service.emergency_backup_on_shutdown is False
        
        # Should not create backup
        with patch('services.async_shutdown_service.backup_service') as mock_backup:
            await test_shutdown_service._create_emergency_backup()
            mock_backup.create_backup.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_create_emergency_backup_enabled(self, test_shutdown_service):
        """Test emergency backup when enabled"""
        test_shutdown_service.emergency_backup_on_shutdown = True
        
        with patch('services.async_shutdown_service.backup_service') as mock_backup:
            mock_backup.create_backup.return_value = "test_backup.db"
            
            await test_shutdown_service._create_emergency_backup()
            
            mock_backup.create_backup.assert_called_once()
            # Check that backup name contains "emergency_shutdown"
            call_args = mock_backup.create_backup.call_args[0]
            assert "emergency_shutdown_backup_" in call_args[0]
    
    def test_stop_background_services(self, test_shutdown_service):
        """Test stopping background services"""
        with patch('services.async_shutdown_service.backup_service') as mock_backup:
            mock_backup.is_running = True
            
            test_shutdown_service._stop_background_services()
            
            mock_backup.stop_automated_backups.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initiate_shutdown_complete_process(self, test_shutdown_service):
        """Test complete shutdown process"""
        execution_log = []
        test_shutdown_service.emergency_backup_on_shutdown = False  # Disable for test
        
        def test_handler():
            execution_log.append("handler_executed")
        
        test_shutdown_service.register_shutdown_handler(test_handler, "Test handler")
        
        with patch.object(test_shutdown_service, '_stop_background_services') as mock_stop:
            await test_shutdown_service.initiate_shutdown()
            
            assert test_shutdown_service.is_shutting_down is True
            assert execution_log == ["handler_executed"]
            mock_stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initiate_shutdown_duplicate_call(self, test_shutdown_service):
        """Test that duplicate shutdown calls are ignored"""
        test_shutdown_service.is_shutting_down = True
        
        execution_log = []
        
        def test_handler():
            execution_log.append("should_not_execute")
        
        test_shutdown_service.register_shutdown_handler(test_handler, "Test handler")
        
        # Should be ignored
        await test_shutdown_service.initiate_shutdown()
        
        assert execution_log == []
    
    def test_shutdown_with_timeout(self, test_shutdown_service):
        """Test shutdown with timeout"""
        # This is a more complex test that would require threading
        # For now, just test that the method exists and can be called
        with patch.object(test_shutdown_service, 'initiate_shutdown') as mock_shutdown:
            test_shutdown_service.shutdown_with_timeout(5)
            mock_shutdown.assert_called_once()
    
    def test_force_shutdown(self, test_shutdown_service):
        """Test force shutdown"""
        with patch('os._exit') as mock_exit:
            test_shutdown_service.force_shutdown(42)
            mock_exit.assert_called_once_with(42)


class TestShutdownServiceHelperFunctions:
    """Test the helper functions provided with shutdown service"""
    
    @pytest.mark.asyncio
    async def test_close_database_connections(self):
        """Test database connection closing"""
        from services.async_shutdown_service import close_database_connections
        
        # Should not raise exception
        await close_database_connections()
    
    def test_flush_logs(self):
        """Test log buffer flushing"""
        from services.async_shutdown_service import flush_logs
        
        # Should not raise exception
        flush_logs()
    
    def test_save_pending_operations(self):
        """Test saving pending operations"""
        from services.async_shutdown_service import save_pending_operations
        
        # This is an async function
        asyncio.run(save_pending_operations())
    
    def test_cleanup_temp_files(self):
        """Test temporary file cleanup"""
        from services.async_shutdown_service import cleanup_temp_files
        
        # Should not raise exception
        cleanup_temp_files()


class TestShutdownServiceEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_handler_timeout_simulation(self, test_shutdown_service):
        """Test handler that takes too long (simulated)"""
        def slow_handler():
            time.sleep(0.1)  # Short sleep for test
        
        test_shutdown_service.register_shutdown_handler(slow_handler, "Slow handler")
        
        # Should complete without hanging
        start_time = time.time()
        test_shutdown_service._run_shutdown_handlers()
        duration = time.time() - start_time
        
        # Should take at least the sleep time
        assert duration >= 0.1
    
    def test_async_handler_error(self, test_shutdown_service):
        """Test async handler that raises an error"""
        async def error_async_handler():
            raise ValueError("Async test error")
        
        test_shutdown_service.register_shutdown_handler(error_async_handler, "Error async handler")
        
        # Should not raise exception
        test_shutdown_service._run_shutdown_handlers()
    
    @pytest.mark.asyncio
    async def test_emergency_backup_error(self, test_shutdown_service):
        """Test emergency backup with error"""
        test_shutdown_service.emergency_backup_on_shutdown = True
        
        with patch('services.async_shutdown_service.backup_service') as mock_backup:
            mock_backup.create_backup.side_effect = Exception("Backup error")
            
            # Should not raise exception
            await test_shutdown_service._create_emergency_backup()
    
    def test_background_services_stop_error(self, test_shutdown_service):
        """Test background services stop with error"""
        with patch('services.async_shutdown_service.backup_service') as mock_backup:
            mock_backup.stop_automated_backups.side_effect = Exception("Stop error")
            
            # Should not raise exception
            test_shutdown_service._stop_background_services()
    
    @pytest.mark.asyncio
    async def test_shutdown_with_all_errors(self, test_shutdown_service):
        """Test shutdown process when everything fails"""
        def error_handler():
            raise RuntimeError("Handler error")
        
        test_shutdown_service.register_shutdown_handler(error_handler, "Error handler")
        test_shutdown_service.emergency_backup_on_shutdown = True
        
        with patch('services.async_shutdown_service.backup_service') as mock_backup:
            mock_backup.create_backup.side_effect = Exception("Backup error")
            mock_backup.stop_automated_backups.side_effect = Exception("Stop error")
            
            # Should complete without raising exception
            await test_shutdown_service.initiate_shutdown()
            
            assert test_shutdown_service.is_shutting_down is True