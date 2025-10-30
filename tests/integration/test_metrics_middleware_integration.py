"""Integration tests for metrics middleware with real health service"""

import asyncio
import os
import tempfile
from unittest.mock import MagicMock
import pytest
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

from src.bot.metrics_middleware import track_command_metrics, track_audio_metrics
from src.services.async_health_service import HealthService


class TestMetricsMiddlewareIntegration:
    """Integration tests with real HealthService instance"""

    @pytest.fixture
    def health_service_instance(self):
        """Create a fresh HealthService instance for testing"""
        return HealthService()

    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram Update object with realistic structure"""
        user = User(
            id=12345,
            first_name="Test",
            last_name="User",
            username="testuser",
            is_bot=False
        )
        
        chat = Chat(
            id=12345,
            type="private"
        )
        
        message = Message(
            message_id=1,
            date=None,
            chat=chat,
            from_user=user,
            text="/start"
        )
        
        update = Update(
            update_id=1,
            message=message
        )
        
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Telegram Context object"""
        return MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    @pytest.mark.asyncio
    async def test_end_to_end_command_metrics_collection(self, health_service_instance, mock_update, mock_context):
        """Test end-to-end metrics collection for commands using real health service"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            # Verify initial state
            assert health_service_instance.command_count == 0
            assert health_service_instance.error_count == 0
            assert len(health_service_instance.response_times) == 0
            
            @track_command_metrics("start_command")
            async def start_command(update, context):
                await asyncio.sleep(0.001)  # Simulate processing
                return "Welcome to the gym tracker!"
            
            # Act
            result = await start_command(mock_update, mock_context)
            
            # Assert
            assert result == "Welcome to the gym tracker!"
            assert health_service_instance.command_count == 1
            assert health_service_instance.error_count == 0
            assert len(health_service_instance.response_times) == 1
            assert health_service_instance.response_times[0] > 0
            
            # Test average response time calculation
            avg_response_time = health_service_instance.get_average_response_time()
            assert avg_response_time > 0
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_end_to_end_audio_metrics_collection(self, health_service_instance, mock_update, mock_context):
        """Test end-to-end metrics collection for audio processing using real health service"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            # Verify initial state
            assert health_service_instance.audio_count == 0
            assert health_service_instance.error_count == 0
            
            @track_audio_metrics("transcribe_voice")
            async def transcribe_voice(update, context):
                await asyncio.sleep(0.002)  # Simulate audio processing
                return "Transcribed text from audio"
            
            # Act
            result = await transcribe_voice(mock_update, mock_context)
            
            # Assert
            assert result == "Transcribed text from audio"
            assert health_service_instance.audio_count == 1
            assert health_service_instance.error_count == 0
            assert len(health_service_instance.response_times) == 1
            assert health_service_instance.response_times[0] > 0
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_error_metrics_integration(self, health_service_instance, mock_update, mock_context):
        """Test error metrics collection integration"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            @track_command_metrics("failing_command")
            async def failing_command(update, context):
                raise ValueError("Something went wrong")
            
            # Act & Assert
            with pytest.raises(ValueError, match="Something went wrong"):
                await failing_command(mock_update, mock_context)
            
            # Verify error was recorded
            assert health_service_instance.command_count == 1
            assert health_service_instance.error_count == 1
            assert len(health_service_instance.response_times) == 1
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_concurrent_operations_integration(self, health_service_instance, mock_update, mock_context):
        """Test concurrent operations with real health service"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            @track_command_metrics("concurrent_command")
            async def concurrent_command(update, context, delay):
                await asyncio.sleep(delay)
                return f"completed_{delay}"
            
            # Act - Run multiple operations concurrently
            tasks = [
                concurrent_command(mock_update, mock_context, 0.001),
                concurrent_command(mock_update, mock_context, 0.002),
                concurrent_command(mock_update, mock_context, 0.003),
            ]
            results = await asyncio.gather(*tasks)
            
            # Assert
            assert len(results) == 3
            assert "completed_0.001" in results
            assert "completed_0.002" in results
            assert "completed_0.003" in results
            
            # All operations should be recorded
            assert health_service_instance.command_count == 3
            assert health_service_instance.error_count == 0
            assert len(health_service_instance.response_times) == 3
            
            # Check that all response times are > 0
            for response_time in health_service_instance.response_times:
                assert response_time > 0
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_mixed_command_and_audio_metrics(self, health_service_instance, mock_update, mock_context):
        """Test collecting both command and audio metrics in the same session"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            @track_command_metrics("text_command")
            async def text_command(update, context):
                await asyncio.sleep(0.001)
                return "text_result"
            
            @track_audio_metrics("audio_command")
            async def audio_command(update, context):
                await asyncio.sleep(0.002)
                return "audio_result"
            
            # Act - Execute both types of operations
            text_result = await text_command(mock_update, mock_context)
            audio_result = await audio_command(mock_update, mock_context)
            
            # Assert
            assert text_result == "text_result"
            assert audio_result == "audio_result"
            
            # Verify metrics were recorded for both types
            assert health_service_instance.command_count == 1
            assert health_service_instance.audio_count == 1
            assert health_service_instance.error_count == 0
            assert len(health_service_instance.response_times) == 2
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_response_time_calculations_integration(self, health_service_instance, mock_update, mock_context):
        """Test response time calculations with varying operation durations"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            @track_command_metrics("timed_command")
            async def timed_command(update, context, duration):
                await asyncio.sleep(duration)
                return f"completed_in_{duration}"
            
            # Execute operations with different durations
            durations = [0.001, 0.005, 0.010, 0.002, 0.008]
            
            for duration in durations:
                await timed_command(mock_update, mock_context, duration)
            
            # Assert
            assert health_service_instance.command_count == len(durations)
            assert len(health_service_instance.response_times) == len(durations)
            
            # Test average calculation
            avg_response_time = health_service_instance.get_average_response_time()
            assert avg_response_time > 0
            
            # Test percentile calculation
            percentile_95 = health_service_instance.get_percentile_response_time(0.95)
            assert percentile_95 > 0
            assert percentile_95 >= avg_response_time  # 95th percentile should be >= average
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_error_rate_calculation_integration(self, health_service_instance, mock_update, mock_context):
        """Test error rate calculation with mixed success/failure operations"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            @track_command_metrics("test_command")
            async def success_command(update, context):
                return "success"
            
            @track_command_metrics("test_command")
            async def failing_command(update, context):
                raise RuntimeError("Failure")
            
            # Execute 3 successful operations
            for _ in range(3):
                await success_command(mock_update, mock_context)
            
            # Execute 1 failing operation
            with pytest.raises(RuntimeError):
                await failing_command(mock_update, mock_context)
            
            # Assert metrics
            assert health_service_instance.command_count == 4
            assert health_service_instance.error_count == 1
            
            # Calculate error rate: 1 error out of 4 operations = 25%
            total_operations = health_service_instance.command_count + health_service_instance.audio_count
            error_rate = (health_service_instance.error_count / total_operations * 100) if total_operations > 0 else 0
            
            assert error_rate == 25.0
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_realistic_telegram_bot_workflow(self, health_service_instance, mock_update, mock_context):
        """Test realistic workflow simulating actual bot commands"""
        # Arrange - Inject our test health service instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        src.bot.metrics_middleware.health_service = health_service_instance
        
        try:
            # Simulate typical bot commands
            @track_command_metrics("start")
            async def start_command(update, context):
                await asyncio.sleep(0.001)
                return "Bot started successfully"
            
            @track_command_metrics("help")
            async def help_command(update, context):
                await asyncio.sleep(0.002)
                return "Help information"
            
            @track_command_metrics("create_workout")
            async def create_workout_command(update, context):
                await asyncio.sleep(0.005)  # More complex operation
                return "Workout created"
            
            @track_audio_metrics("process_voice_note")
            async def process_voice_note(update, context):
                await asyncio.sleep(0.010)  # Audio processing takes longer
                return "Voice note processed"
            
            # Simulate user interaction flow
            start_result = await start_command(mock_update, mock_context)
            help_result = await help_command(mock_update, mock_context)
            workout_result = await create_workout_command(mock_update, mock_context)
            voice_result = await process_voice_note(mock_update, mock_context)
            
            # Assert workflow completed successfully
            assert start_result == "Bot started successfully"
            assert help_result == "Help information"
            assert workout_result == "Workout created"
            assert voice_result == "Voice note processed"
            
            # Verify comprehensive metrics collection
            assert health_service_instance.command_count == 3  # start, help, create_workout
            assert health_service_instance.audio_count == 1    # process_voice_note
            assert health_service_instance.error_count == 0
            assert len(health_service_instance.response_times) == 4  # All operations
            
            # Verify performance metrics are reasonable
            avg_response_time = health_service_instance.get_average_response_time()
            assert avg_response_time > 0
            assert avg_response_time < 20  # Should be under 20ms for test operations
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service

    @pytest.mark.asyncio
    async def test_health_service_state_isolation(self, mock_update, mock_context):
        """Test that different health service instances maintain separate state"""
        # Create two separate health service instances
        health_service_1 = HealthService()
        health_service_2 = HealthService()
        
        # Inject first instance
        import src.bot.metrics_middleware
        original_health_service = src.bot.metrics_middleware.health_service
        
        try:
            # Test with first instance
            src.bot.metrics_middleware.health_service = health_service_1
            
            @track_command_metrics("test1")
            async def test_command_1(update, context):
                return "result1"
            
            await test_command_1(mock_update, mock_context)
            
            # Switch to second instance
            src.bot.metrics_middleware.health_service = health_service_2
            
            @track_command_metrics("test2")
            async def test_command_2(update, context):
                return "result2"
            
            await test_command_2(mock_update, mock_context)
            
            # Assert state isolation
            assert health_service_1.command_count == 1
            assert health_service_2.command_count == 1
            assert len(health_service_1.response_times) == 1
            assert len(health_service_2.response_times) == 1
            
            # Verify they are truly independent
            assert health_service_1.response_times != health_service_2.response_times
            
        finally:
            # Restore original health service
            src.bot.metrics_middleware.health_service = original_health_service