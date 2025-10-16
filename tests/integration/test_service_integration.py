"""Integration tests for service interactions"""

import pytest
import asyncio
import time
import os
from unittest.mock import Mock, patch

from services.backup_service import BackupService
from services.health_service import HealthService
from services.shutdown_service import ShutdownService


class TestServiceIntegration:
    """Test integration between different services"""
    
    def test_health_and_backup_integration(self, test_backup_service, populated_test_database):
        """Test health service monitoring backup service"""
        test_backup_service.database_path = populated_test_database
        health_service = HealthService()
        
        # Start automated backups
        test_backup_service.start_automated_backups()
        
        try:
            # Create some backups
            backup1 = test_backup_service.create_backup("integration_test_1.db")
            backup2 = test_backup_service.create_backup("integration_test_2.db")
            
            assert os.path.exists(backup1)
            assert os.path.exists(backup2)
            
            # Get backup stats through health monitoring
            stats = test_backup_service.get_backup_stats()
            assert stats["total_backups"] >= 2
            assert stats["verified_backups"] >= 2
            
            # Verify backups are healthy
            backups = test_backup_service.list_backups()
            for backup in backups:
                assert backup["verified"] is True
                
        finally:
            test_backup_service.stop_automated_backups()
    
    def test_shutdown_and_backup_integration(self, test_backup_service, populated_test_database):
        """Test shutdown service creating emergency backup"""
        test_backup_service.database_path = populated_test_database
        shutdown_service = ShutdownService()
        shutdown_service.emergency_backup_on_shutdown = True
        
        # Start automated backups
        test_backup_service.start_automated_backups()
        
        try:
            # Simulate shutdown process
            initial_backups = len(test_backup_service.list_backups())
            
            # Mock the backup service in shutdown service
            with patch('services.shutdown_service.backup_service', test_backup_service):
                shutdown_service._create_emergency_backup()
            
            # Should have created an emergency backup
            final_backups = len(test_backup_service.list_backups())
            assert final_backups == initial_backups + 1
            
            # Find the emergency backup
            backups = test_backup_service.list_backups()
            emergency_backup = next(
                (b for b in backups if "emergency_shutdown_backup_" in b["name"]), 
                None
            )
            assert emergency_backup is not None
            assert emergency_backup["verified"] is True
            
        finally:
            test_backup_service.stop_automated_backups()
    
    @pytest.mark.asyncio
    async def test_health_service_comprehensive_check(self, test_backup_service, populated_test_database):
        """Test health service comprehensive check with real services"""
        test_backup_service.database_path = populated_test_database
        health_service = HealthService()
        
        # Record some metrics
        health_service.record_command(100, False)
        health_service.record_command(200, False)
        health_service.record_audio_processing(1500, False)
        
        # Get comprehensive health status
        health_status = await health_service.get_health_status()
        
        # Verify comprehensive results
        assert health_status.status in ["healthy", "degraded"]
        assert health_status.uptime_seconds >= 0
        assert "database" in health_status.checks
        assert "system_resources" in health_status.checks
        assert "configuration" in health_status.checks
        assert "dependencies" in health_status.checks
        
        # Verify metrics were collected
        assert "system" in health_status.metrics
        assert "bot" in health_status.metrics
        assert health_status.metrics["bot"]["total_commands_processed"] == 2
        assert health_status.metrics["bot"]["total_audio_processed"] == 1


class TestEndToEndWorkflow:
    """Test complete workflows involving multiple services"""
    
    @pytest.mark.asyncio
    async def test_startup_monitoring_shutdown_workflow(self, test_backup_service, populated_test_database):
        """Test complete startup -> monitoring -> shutdown workflow"""
        test_backup_service.database_path = populated_test_database
        health_service = HealthService()
        shutdown_service = ShutdownService()
        shutdown_service.emergency_backup_on_shutdown = True
        
        workflow_log = []
        
        # 1. Startup phase
        workflow_log.append("startup")
        test_backup_service.start_automated_backups()
        assert test_backup_service.is_running
        
        # 2. Operational phase with monitoring
        workflow_log.append("operational")
        
        # Simulate some bot activity
        health_service.record_command(150, False)
        health_service.record_audio_processing(2000, False)
        health_service.record_command(300, True)  # Error
        
        # Create manual backup
        backup_path = test_backup_service.create_backup("workflow_test.db")
        assert os.path.exists(backup_path)
        
        # Monitor health
        health_status = await health_service.get_health_status()
        assert health_status.status in ["healthy", "degraded"]
        
        # Check metrics
        bot_metrics = health_service._get_bot_metrics()
        assert bot_metrics.total_commands_processed == 2
        assert bot_metrics.total_audio_processed == 1
        assert bot_metrics.error_rate_percent > 0  # Had one error
        
        # 3. Shutdown phase
        workflow_log.append("shutdown")
        
        def track_shutdown():
            workflow_log.append("shutdown_handler_executed")
        
        shutdown_service.register_shutdown_handler(track_shutdown, "Track shutdown")
        
        # Mock the backup service in shutdown
        with patch('services.shutdown_service.backup_service', test_backup_service):
            shutdown_service.initiate_shutdown()
        
        # Verify shutdown completed
        assert shutdown_service.is_shutting_down is True
        assert "shutdown_handler_executed" in workflow_log
        assert not test_backup_service.is_running
        
        # Verify emergency backup was created
        backups = test_backup_service.list_backups()
        emergency_backup = next(
            (b for b in backups if "emergency_shutdown_backup_" in b["name"]), 
            None
        )
        assert emergency_backup is not None
        
        # Verify complete workflow
        expected_workflow = ["startup", "operational", "shutdown", "shutdown_handler_executed"]
        assert workflow_log == expected_workflow
    
    def test_error_recovery_workflow(self, test_backup_service, populated_test_database):
        """Test error recovery and resilience"""
        test_backup_service.database_path = populated_test_database
        health_service = HealthService()
        
        # Simulate various error conditions
        error_log = []
        
        # 1. Backup service errors
        try:
            test_backup_service.database_path = "/nonexistent/database.db"
            test_backup_service.create_backup("error_test.db")
        except Exception as e:
            error_log.append("backup_error_handled")
        
        # Restore working database
        test_backup_service.database_path = populated_test_database
        
        # 2. Health service with errors
        health_service.record_command(100, True)  # Error command
        health_service.record_audio_processing(500, True)  # Error audio
        
        metrics = health_service._get_bot_metrics()
        assert metrics.error_rate_percent == 100.0  # All operations failed
        
        # 3. Recovery - successful operations
        health_service.record_command(200, False)  # Success
        health_service.record_audio_processing(1000, False)  # Success
        
        metrics = health_service._get_bot_metrics()
        assert metrics.error_rate_percent == 50.0  # 2 errors out of 4 total
        
        # 4. Verify system can still create backups after errors
        backup_path = test_backup_service.create_backup("recovery_test.db")
        assert os.path.exists(backup_path)
        
        assert "backup_error_handled" in error_log
    
    def test_concurrent_operations(self, test_backup_service, populated_test_database):
        """Test concurrent operations across services"""
        test_backup_service.database_path = populated_test_database
        health_service = HealthService()
        
        # Start automated backups
        test_backup_service.start_automated_backups()
        
        try:
            # Simulate concurrent operations
            import threading
            
            results = {"backups": [], "metrics": []}
            
            def create_backups():
                for i in range(3):
                    try:
                        backup = test_backup_service.create_backup(f"concurrent_{i}.db")
                        results["backups"].append(backup)
                        time.sleep(0.1)
                    except Exception as e:
                        results["backups"].append(f"error: {e}")
            
            def record_metrics():
                for i in range(5):
                    health_service.record_command(100 + i * 10, i % 3 == 0)  # Some errors
                    time.sleep(0.05)
                results["metrics"].append("completed")
            
            # Run concurrently
            backup_thread = threading.Thread(target=create_backups)
            metrics_thread = threading.Thread(target=record_metrics)
            
            backup_thread.start()
            metrics_thread.start()
            
            backup_thread.join()
            metrics_thread.join()
            
            # Verify results
            successful_backups = [b for b in results["backups"] if not str(b).startswith("error")]
            assert len(successful_backups) >= 2  # At least most should succeed
            assert "completed" in results["metrics"]
            
            # Verify metrics were recorded
            bot_metrics = health_service._get_bot_metrics()
            assert bot_metrics.total_commands_processed == 5
            
        finally:
            test_backup_service.stop_automated_backups()


class TestServiceErrorPropagation:
    """Test how errors propagate between services"""
    
    def test_backup_service_error_in_health_check(self, test_backup_service):
        """Test backup service errors don't break health checks"""
        health_service = HealthService()
        
        # Break backup service
        test_backup_service.database_path = "/nonexistent/database.db"
        
        # Health service should still work
        simple_health = health_service.get_simple_health()
        assert "status" in simple_health
        
        # System metrics should still work
        system_metrics = health_service._get_system_metrics()
        assert system_metrics.cpu_percent >= 0
    
    def test_health_service_error_during_shutdown(self, test_shutdown_service):
        """Test health service errors don't break shutdown"""
        def failing_handler():
            raise RuntimeError("Handler failure")
        
        def working_handler():
            # This should still execute
            pass
        
        test_shutdown_service.register_shutdown_handler(failing_handler, "Failing handler")
        test_shutdown_service.register_shutdown_handler(working_handler, "Working handler")
        
        # Shutdown should complete despite handler failure
        test_shutdown_service.initiate_shutdown()
        assert test_shutdown_service.is_shutting_down is True
    
    @pytest.mark.asyncio
    async def test_database_error_isolation(self, test_backup_service):
        """Test database errors are properly isolated"""
        health_service = HealthService()
        
        # Break database connection
        with patch('services.health_service.db') as mock_db:
            mock_db.get_session.side_effect = Exception("Database connection failed")
            
            # Health service should handle the error gracefully
            health_status = await health_service.get_health_status()
            
            # Should report unhealthy but not crash
            assert health_status.status == "unhealthy"
            assert health_status.checks["database"]["status"] == "unhealthy"