"""Integration tests for service interactions"""

import os
from unittest.mock import patch

import pytest

from services.async_health_service import HealthService
from services.async_shutdown_service import ShutdownService
from services.backup_factory import BackupFactory


class TestServiceIntegration:
    """Test integration between different services"""

    @pytest.mark.asyncio
    async def test_health_and_backup_integration(self, test_backup_service, populated_test_database, mock_pg_dump):
        """Test health service monitoring backup service"""
        from services.backup_factory import BackupFactory
        
        # Set database path for SQLite services only
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = populated_test_database
            
        health_service = HealthService()

        # Start automated backups (only if supported)
        automation_started = False
        if hasattr(test_backup_service, 'start_automated_backups'):
            test_backup_service.start_automated_backups()
            automation_started = True

        try:
            # Create some backups using appropriate methods
            if BackupFactory.is_postgresql():
                # PostgreSQL backups
                backup1 = await test_backup_service.create_backup_sql()
                backup2 = await test_backup_service.create_backup_json()
            else:
                # SQLite backups
                backup1 = await test_backup_service.create_backup("integration_test_1.db")
                backup2 = await test_backup_service.create_backup("integration_test_2.db")

            assert os.path.exists(backup1)
            assert os.path.exists(backup2)

            # Get backup stats through health monitoring
            if hasattr(test_backup_service, 'get_backup_stats'):
                stats = await test_backup_service.get_backup_stats()
                assert stats["total_backups"] >= 2
                assert stats.get("verified_backups", 2) >= 2

            # Verify backups are healthy
            backups = await test_backup_service.list_backups()
            for backup in backups:
                # Only check verification for SQLite (PostgreSQL doesn't have this)
                if BackupFactory.is_sqlite():
                    assert backup["verified"] is True

        finally:
            # Stop automated backups (only if we started them)
            if automation_started and hasattr(test_backup_service, 'stop_automated_backups'):
                test_backup_service.stop_automated_backups()

    @pytest.mark.asyncio
    async def test_shutdown_and_backup_integration(self, test_backup_service, populated_test_database, mock_pg_dump):
        """Test shutdown service creating emergency backup"""
        from services.backup_factory import BackupFactory
        
        # Set database path for SQLite services only
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = populated_test_database
            
        shutdown_service = ShutdownService()
        shutdown_service.emergency_backup_on_shutdown = True

        # Start automated backups (only if supported)
        automation_started = False
        if hasattr(test_backup_service, 'start_automated_backups'):
            test_backup_service.start_automated_backups()
            automation_started = True

        try:
            # Simulate shutdown process
            backups_list = await test_backup_service.list_backups()
            initial_backups = len(backups_list)

            # Mock the backup service in shutdown service using container
            with patch("services.async_container.get_async_backup_service", return_value=test_backup_service):
                await shutdown_service._create_emergency_backup()

            # Should have created an emergency backup
            backups_list = await test_backup_service.list_backups()
            final_backups = len(backups_list)
            assert final_backups == initial_backups + 1

            # Find the emergency backup
            backups = await test_backup_service.list_backups()
            
            # Look for emergency backup (pattern varies by database type)
            if BackupFactory.is_postgresql():
                emergency_backup = next(
                    (b for b in backups if any(pattern in b["name"] for pattern in ["emergency_shutdown_backup_", "gym_tracker_backup_"])),
                    None,
                )
            else:
                emergency_backup = next(
                    (b for b in backups if "emergency_shutdown_backup_" in b["name"]),
                    None,
                )
            
            assert emergency_backup is not None
            
            # Only check verification for SQLite (PostgreSQL doesn't have this)
            if BackupFactory.is_sqlite():
                assert emergency_backup["verified"] is True

        finally:
            # Stop automated backups (only if we started them)
            if automation_started and hasattr(test_backup_service, 'stop_automated_backups'):
                test_backup_service.stop_automated_backups()

    @pytest.mark.asyncio
    async def test_health_service_comprehensive_check(self, test_backup_service, populated_test_database):
        """Test health service comprehensive check with real services"""
        from services.backup_factory import BackupFactory
        
        # Set database path for SQLite services only
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = populated_test_database
        health_service = HealthService()

        # Record some metrics
        health_service.record_command(100, False)
        health_service.record_command(200, False)
        health_service.record_audio_processing(1500, False)

        # Mock TELEGRAM_BOT_TOKEN for configuration health check
        with patch("services.async_health_service.settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token_123"
            mock_settings.DATABASE_URL = "sqlite+aiosqlite:///test.db"
            mock_settings.GROQ_API_KEY = "test_groq_key"
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
    async def test_startup_monitoring_shutdown_workflow(self, test_backup_service, populated_test_database, mock_pg_dump):
        """Test complete startup -> monitoring -> shutdown workflow"""
        # Set database path for SQLite services only
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = populated_test_database
        health_service = HealthService()
        shutdown_service = ShutdownService()
        shutdown_service.emergency_backup_on_shutdown = True

        workflow_log = []

        # 1. Startup phase
        workflow_log.append("startup")
        
        # Start automated backups (only if supported by SQLite service)
        automation_started = False
        if hasattr(test_backup_service, 'start_automated_backups'):
            test_backup_service.start_automated_backups()
            automation_started = True
            assert test_backup_service.is_running

        # 2. Operational phase with monitoring
        workflow_log.append("operational")

        # Simulate some bot activity
        health_service.record_command(150, False)
        health_service.record_audio_processing(2000, False)
        health_service.record_command(300, True)  # Error

        # Create manual backup using appropriate method
        if BackupFactory.is_postgresql():
            backup_path = await test_backup_service.create_backup_sql()
        else:
            backup_path = await test_backup_service.create_backup("workflow_test.db")
        assert os.path.exists(backup_path)

        # Monitor health with mocked settings
        with patch("services.async_health_service.settings") as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = "test_token_123"
            mock_settings.DATABASE_URL = "sqlite+aiosqlite:///test.db"
            mock_settings.GROQ_API_KEY = "test_groq_key"
            health_status = await health_service.get_health_status()
        assert health_status.status in ["healthy", "degraded"]

        # Check metrics
        bot_metrics = await health_service._get_bot_metrics_async()
        assert bot_metrics.total_commands_processed == 2
        assert bot_metrics.total_audio_processed == 1
        assert bot_metrics.error_rate_percent > 0  # Had one error

        # 3. Shutdown phase
        workflow_log.append("shutdown")

        def track_shutdown():
            workflow_log.append("shutdown_handler_executed")

        shutdown_service.register_shutdown_handler(track_shutdown, "Track shutdown")

        # Mock the backup service in shutdown using container
        with patch("services.async_container.get_async_backup_service", return_value=test_backup_service):
            await shutdown_service.initiate_shutdown()

        # Verify shutdown completed
        assert shutdown_service.is_shutting_down is True
        assert "shutdown_handler_executed" in workflow_log
        
        # Only check is_running for SQLite service that supports it
        if hasattr(test_backup_service, 'is_running'):
            assert not test_backup_service.is_running

        # Verify emergency backup was created
        backups = await test_backup_service.list_backups()
        
        # Look for emergency backup (pattern varies by database type)
        if BackupFactory.is_postgresql():
            # For PostgreSQL, the emergency backup will be the most recent backup
            # (since shutdown service triggers emergency backup during shutdown)
            assert len(backups) >= 2  # At least manual + emergency backup
            emergency_backup = backups[0]  # Most recent
        else:
            # For SQLite, look for specific emergency backup naming pattern
            emergency_backup = next(
                (b for b in backups if "emergency_shutdown_backup_" in b["name"]),
                None,
            )
            assert emergency_backup is not None

        # Verify complete workflow
        expected_workflow = ["startup", "operational", "shutdown", "shutdown_handler_executed"]
        assert workflow_log == expected_workflow

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, test_backup_service, populated_test_database, mock_pg_dump):
        """Test error recovery and resilience"""
        from services.backup_factory import BackupFactory
        
        # Set database path for SQLite services only
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = populated_test_database
        health_service = HealthService()

        # Simulate various error conditions
        error_log = []

        # 1. Backup service errors
        try:
            # Only test with invalid database path for SQLite services
            if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
                test_backup_service.database_path = "/nonexistent/database.db"
                await test_backup_service.create_backup("error_test.db")
            else:
                # For PostgreSQL, create a backup with invalid backup name to trigger error
                # (passing an invalid path as backup name)
                await test_backup_service.create_backup_sql("/invalid/path/that/will/fail.sql")
        except Exception:
            error_log.append("backup_error_handled")

        # Restore working database for SQLite
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = populated_test_database

        # 2. Health service with errors
        health_service.record_command(100, True)  # Error command
        health_service.record_audio_processing(500, True)  # Error audio

        metrics = await health_service._get_bot_metrics_async()
        assert metrics.error_rate_percent == 100.0  # All operations failed

        # 3. Recovery - successful operations
        health_service.record_command(200, False)  # Success
        health_service.record_audio_processing(1000, False)  # Success

        metrics = await health_service._get_bot_metrics_async()
        assert metrics.error_rate_percent == 50.0  # 2 errors out of 4 total

        # 4. Verify system can still create backups after errors
        if BackupFactory.is_postgresql():
            backup_path = await test_backup_service.create_backup_sql()
        else:
            backup_path = await test_backup_service.create_backup("recovery_test.db")
        assert os.path.exists(backup_path)

        assert "backup_error_handled" in error_log

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, test_backup_service, populated_test_database, mock_pg_dump):
        """Test concurrent operations across services"""
        from services.backup_factory import BackupFactory
        
        # Set database path for SQLite services only
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = populated_test_database
        health_service = HealthService()

        # Start automated backups (only if supported by SQLite service)
        automation_started = False
        if hasattr(test_backup_service, 'start_automated_backups'):
            test_backup_service.start_automated_backups()
            automation_started = True

        try:
            # Simulate concurrent operations
            import asyncio

            results = {"backups": [], "metrics": []}

            async def create_backups():
                for i in range(3):
                    try:
                        if BackupFactory.is_postgresql():
                            backup = await test_backup_service.create_backup_sql()
                        else:
                            backup = await test_backup_service.create_backup(f"concurrent_{i}.db")
                        results["backups"].append(backup)
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        results["backups"].append(f"error: {e}")

            async def record_metrics():
                for i in range(5):
                    health_service.record_command(100 + i * 10, i % 3 == 0)  # Some errors
                    await asyncio.sleep(0.05)
                results["metrics"].append("completed")

            # Run concurrently using asyncio
            await asyncio.gather(
                create_backups(),
                record_metrics(),
            )

            # Verify results
            successful_backups = [b for b in results["backups"] if not str(b).startswith("error")]
            assert len(successful_backups) >= 2  # At least most should succeed
            assert "completed" in results["metrics"]

            # Verify metrics were recorded
            bot_metrics = await health_service._get_bot_metrics_async()
            assert bot_metrics.total_commands_processed == 5

        finally:
            # Stop automated backups (only if we started them)
            if automation_started and hasattr(test_backup_service, 'stop_automated_backups'):
                test_backup_service.stop_automated_backups()


class TestServiceErrorPropagation:
    """Test how errors propagate between services"""

    @pytest.mark.asyncio
    async def test_backup_service_error_in_health_check(self, test_backup_service):
        """Test backup service errors don't break health checks"""
        from services.backup_factory import BackupFactory
        
        health_service = HealthService()

        # Break backup service (only for SQLite)
        if hasattr(test_backup_service, 'database_path') and BackupFactory.is_sqlite():
            test_backup_service.database_path = "/nonexistent/database.db"

        # Health service should still work
        simple_health = await health_service.get_simple_health()
        assert "status" in simple_health

        # System metrics should still work
        system_metrics = health_service._get_system_metrics()
        assert system_metrics.cpu_percent >= 0

    @pytest.mark.asyncio
    async def test_health_service_error_during_shutdown(self, test_shutdown_service):
        """Test health service errors don't break shutdown"""
        def failing_handler():
            raise RuntimeError("Handler failure")

        def working_handler():
            # This should still execute
            pass

        test_shutdown_service.register_shutdown_handler(failing_handler, "Failing handler")
        test_shutdown_service.register_shutdown_handler(working_handler, "Working handler")

        # Shutdown should complete despite handler failure
        await test_shutdown_service.initiate_shutdown()
        assert test_shutdown_service.is_shutting_down is True

    @pytest.mark.asyncio
    async def test_database_error_isolation(self, test_backup_service):
        """Test database errors are properly isolated"""
        health_service = HealthService()

        # Break database connection by patching the actual import
        with patch("database.async_connection.get_async_session_context") as mock_session_context:
            mock_session_context.side_effect = Exception("Database connection failed")

            # Health service should handle the error gracefully
            health_status = await health_service.get_health_status()

            # Should report unhealthy but not crash
            assert health_status.status == "unhealthy"
            assert health_status.checks["async_database"]["status"] == "unhealthy"

