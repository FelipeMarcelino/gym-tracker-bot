"""Unit tests for health service"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock

from services.async_health_service import HealthService, SystemMetrics, DatabaseMetrics, BotMetrics


class TestHealthService:
    """Test health service functionality"""
    
    def test_health_service_initialization(self, test_health_service):
        """Test health service initializes correctly"""
        assert test_health_service.command_count == 0
        assert test_health_service.audio_count == 0
        assert test_health_service.error_count == 0
        assert test_health_service.response_times == []
        assert test_health_service.max_response_times == 1000
    
    def test_record_command_metrics(self, test_health_service):
        """Test recording command metrics"""
        # Record successful command
        test_health_service.record_command(150.5, False)
        assert test_health_service.command_count == 1
        assert test_health_service.error_count == 0
        assert test_health_service.response_times == [150.5]
        
        # Record command with error
        test_health_service.record_command(250.0, True)
        assert test_health_service.command_count == 2
        assert test_health_service.error_count == 1
        assert test_health_service.response_times == [150.5, 250.0]
    
    def test_record_audio_metrics(self, test_health_service):
        """Test recording audio processing metrics"""
        # Record successful audio processing
        test_health_service.record_audio_processing(1500.0, False)
        assert test_health_service.audio_count == 1
        assert test_health_service.error_count == 0
        assert test_health_service.response_times == [1500.0]
        
        # Record audio processing with error
        test_health_service.record_audio_processing(2000.0, True)
        assert test_health_service.audio_count == 2
        assert test_health_service.error_count == 1
        assert test_health_service.response_times == [1500.0, 2000.0]
    
    def test_response_time_limit(self, test_health_service):
        """Test response time list size limit"""
        # Add more response times than limit
        for i in range(1200):
            test_health_service.record_command(100 + i, False)
        
        # Should keep only the last 1000
        assert len(test_health_service.response_times) == 1000
        assert test_health_service.command_count == 1200
        assert test_health_service.response_times[0] == 300  # 100 + 200 (1200 - 1000)
        assert test_health_service.response_times[-1] == 1299  # 100 + 1199
    
    @pytest.mark.asyncio
    async def test_get_health_status(self, test_health_service):
        """Test comprehensive health status"""
        # Mock some dependencies to avoid real system calls
        with patch.object(test_health_service, '_run_health_checks') as mock_checks, \
             patch.object(test_health_service, '_collect_metrics') as mock_metrics:
            
            mock_checks.return_value = {
                "database": {"status": "healthy"},
                "system_resources": {"status": "healthy"}
            }
            mock_metrics.return_value = {
                "system": {"cpu_percent": 10.0},
                "bot": {"total_commands_processed": 5}
            }
            
            health_status = await test_health_service.get_health_status()
            
            assert health_status.status == "healthy"
            assert health_status.uptime_seconds >= 0
            assert "database" in health_status.checks
            assert "system" in health_status.metrics
            mock_checks.assert_called_once()
            mock_metrics.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_status_error_handling(self, test_health_service):
        """Test health status error handling"""
        with patch.object(test_health_service, '_run_health_checks') as mock_checks:
            mock_checks.side_effect = Exception("Test error")
            
            health_status = await test_health_service.get_health_status()
            
            assert health_status.status == "unhealthy"
            assert "health_check_error" in health_status.checks
            assert "Test error" in health_status.checks["health_check_error"]
    
    async def test_get_simple_health(self, test_health_service):
        """Test simple health check"""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('database.async_connection.get_async_session_context') as mock_session:
            
            mock_cpu.return_value = 15.0
            mock_memory.return_value = Mock(percent=60.0)
            
            # Mock async database session and query
            mock_session_instance = Mock()
            mock_session_instance.execute = AsyncMock(return_value=Mock(scalar=Mock(return_value=1)))
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            health = await test_health_service.get_simple_health()
            
            assert health["status"] == "healthy"
            assert health["uptime_seconds"] >= 0
            assert health["checks"]["database"] == "healthy"
            assert health["checks"]["cpu_ok"] is True
            assert health["checks"]["memory_ok"] is True
    
    async def test_get_simple_health_degraded(self, test_health_service):
        """Test simple health check with degraded status"""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('database.async_connection.get_async_session_context') as mock_session:
            
            mock_cpu.return_value = 85.0  # High CPU
            mock_memory.return_value = Mock(percent=85.0)  # High memory
            
            # Mock async database session 
            mock_session_instance = Mock()
            mock_session_instance.execute = AsyncMock(return_value=Mock(scalar=Mock(return_value=1)))
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            health = await test_health_service.get_simple_health()
            
            assert health["status"] == "degraded"
            assert health["checks"]["cpu_ok"] is False
            assert health["checks"]["memory_ok"] is False
    
    def test_get_system_metrics(self, test_health_service):
        """Test system metrics collection"""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_cpu.return_value = 25.5
            mock_memory.return_value = Mock(
                percent=45.0,
                used=4 * 1024 * 1024 * 1024,  # 4GB
                total=8 * 1024 * 1024 * 1024   # 8GB
            )
            mock_disk.return_value = Mock(
                percent=30.0,
                used=100 * 1024 * 1024 * 1024,  # 100GB
                total=500 * 1024 * 1024 * 1024   # 500GB
            )
            
            metrics = test_health_service._get_system_metrics()
            
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_percent == 25.5
            assert metrics.memory_percent == 45.0
            assert metrics.memory_used_mb == 4096  # 4GB in MB
            assert metrics.memory_total_mb == 8192  # 8GB in MB
            assert metrics.disk_percent == 30.0
            assert metrics.disk_used_gb == 100.0
            assert metrics.disk_total_gb == 500.0
    
    def test_get_bot_metrics(self, test_health_service):
        """Test bot metrics calculation"""
        # Record some operations
        test_health_service.record_command(100, False)
        test_health_service.record_command(200, False)
        test_health_service.record_command(300, True)  # Error
        test_health_service.record_audio_processing(1000, False)
        test_health_service.record_audio_processing(1500, True)  # Error
        
        metrics = test_health_service._get_bot_metrics()
        
        assert isinstance(metrics, BotMetrics)
        assert metrics.total_commands_processed == 3
        assert metrics.total_audio_processed == 2
        assert metrics.average_response_time_ms == 620.0  # (100+200+300+1000+1500)/5
        assert metrics.error_rate_percent == 40.0  # 2 errors out of 5 total
        assert metrics.active_sessions == 0  # Not implemented yet
    
    def test_get_bot_metrics_no_data(self, test_health_service):
        """Test bot metrics with no recorded data"""
        metrics = test_health_service._get_bot_metrics()
        
        assert metrics.total_commands_processed == 0
        assert metrics.total_audio_processed == 0
        assert metrics.average_response_time_ms == 0
        assert metrics.error_rate_percent == 0
        assert metrics.active_sessions == 0
    
    def test_determine_overall_status(self, test_health_service):
        """Test overall status determination"""
        # All healthy
        checks = {
            "database": {"status": "healthy"},
            "system": {"status": "healthy"}
        }
        status = test_health_service._determine_overall_status(checks)
        assert status == "healthy"
        
        # One degraded
        checks = {
            "database": {"status": "healthy"},
            "system": {"status": "degraded"}
        }
        status = test_health_service._determine_overall_status(checks)
        assert status == "degraded"
        
        # One unhealthy
        checks = {
            "database": {"status": "unhealthy"},
            "system": {"status": "healthy"}
        }
        status = test_health_service._determine_overall_status(checks)
        assert status == "unhealthy"
        
        # Mixed with unhealthy taking precedence
        checks = {
            "database": {"status": "unhealthy"},
            "system": {"status": "degraded"},
            "config": {"status": "healthy"}
        }
        status = test_health_service._determine_overall_status(checks)
        assert status == "unhealthy"


class TestHealthServiceSystemChecks:
    """Test system-level health checks"""
    
    def test_check_system_resources_healthy(self, test_health_service):
        """Test system resources check - healthy scenario"""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_cpu.return_value = 50.0  # Normal CPU
            mock_memory.return_value = Mock(percent=60.0)  # Normal memory
            mock_disk.return_value = Mock(percent=70.0)  # Normal disk
            
            result = test_health_service._check_system_resources()
            
            assert result["status"] == "healthy"
            assert result["cpu_percent"] == 50.0
            assert result["memory_percent"] == 60.0
            assert result["disk_percent"] == 70.0
            assert result["warnings"] == []
    
    def test_check_system_resources_degraded(self, test_health_service):
        """Test system resources check - degraded scenario"""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            mock_cpu.return_value = 85.0  # High CPU
            mock_memory.return_value = Mock(percent=85.0)  # High memory
            mock_disk.return_value = Mock(percent=95.0)  # High disk
            
            result = test_health_service._check_system_resources()
            
            assert result["status"] == "degraded"
            assert len(result["warnings"]) == 3
            assert "High CPU usage: 85.0%" in result["warnings"]
            assert "High memory usage: 85.0%" in result["warnings"]
            assert "High disk usage: 95.0%" in result["warnings"]
    
    def test_check_dependencies(self, test_health_service):
        """Test dependencies check"""
        result = test_health_service._check_dependencies()
        
        assert result["status"] == "healthy"
        assert "versions" in result
        assert "aiosqlite" in result["versions"]
        assert "sqlalchemy" in result["versions"]
        assert "python-telegram-bot" in result["versions"]
    
    def test_check_configuration_healthy(self, test_health_service):
        """Test configuration check - healthy scenario"""
        with patch('services.health_service.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = "valid_token"
            mock_settings.DATABASE_URL = "sqlite:///test.db"
            mock_settings.GROQ_API_KEY = "valid_key"
            
            result = test_health_service._check_configuration()
            
            assert result["status"] == "healthy"
            assert result["issues"] == []
            assert result["warnings"] == []
    
    def test_check_configuration_issues(self, test_health_service):
        """Test configuration check - with issues"""
        with patch('services.health_service.settings') as mock_settings:
            mock_settings.TELEGRAM_BOT_TOKEN = None
            mock_settings.DATABASE_URL = None
            mock_settings.GROQ_API_KEY = None
            
            result = test_health_service._check_configuration()
            
            assert result["status"] == "unhealthy"
            assert "TELEGRAM_BOT_TOKEN not configured" in result["issues"]
            assert "DATABASE_URL not configured" in result["issues"]