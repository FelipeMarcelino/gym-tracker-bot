"""Unit tests for metrics middleware"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.metrics_middleware import track_command_metrics, track_audio_metrics


class TestTrackCommandMetrics:
    """Test cases for track_command_metrics decorator"""

    @pytest.fixture
    def mock_health_service(self):
        """Mock health service for testing"""
        with patch('src.bot.metrics_middleware.health_service') as mock:
            mock.record_command = MagicMock()
            yield mock

    @pytest.fixture
    def mock_update(self):
        """Mock Telegram Update object"""
        return MagicMock(spec=Update)

    @pytest.fixture
    def mock_context(self):
        """Mock Telegram Context object"""
        return MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    @pytest.mark.asyncio
    async def test_successful_command_execution_records_metrics(self, mock_health_service, mock_update, mock_context):
        """Test that successful command execution records metrics correctly"""
        # Arrange
        expected_result = "success"
        
        @track_command_metrics("test_command")
        async def test_function(update, context):
            await asyncio.sleep(0.001)  # Small delay to test timing
            return expected_result
        
        # Act
        result = await test_function(mock_update, mock_context)
        
        # Assert
        assert result == expected_result
        mock_health_service.record_command.assert_called_once()
        
        # Check that response time was recorded (should be > 0)
        call_args = mock_health_service.record_command.call_args
        response_time_ms = call_args[0][0]
        is_error = call_args[0][1]
        
        assert response_time_ms > 0
        assert is_error is False

    @pytest.mark.asyncio
    async def test_command_error_records_error_metrics(self, mock_health_service, mock_update, mock_context):
        """Test that command errors are recorded as error metrics"""
        # Arrange
        test_exception = ValueError("Test error")
        
        @track_command_metrics("test_command")
        async def test_function(update, context):
            raise test_exception
        
        # Act & Assert
        with pytest.raises(ValueError, match="Test error"):
            await test_function(mock_update, mock_context)
        
        # Check error was recorded
        mock_health_service.record_command.assert_called_once()
        call_args = mock_health_service.record_command.call_args
        response_time_ms = call_args[0][0]
        is_error = call_args[0][1]
        
        assert response_time_ms >= 0
        assert is_error is True

    @pytest.mark.asyncio
    async def test_auto_detect_command_name_from_function(self, mock_health_service, mock_update, mock_context):
        """Test that command name is auto-detected from function name"""
        # Arrange
        @track_command_metrics()
        async def start_command(update, context):
            return "started"
        
        # Act
        await start_command(mock_update, mock_context)
        
        # Assert
        mock_health_service.record_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_command_name_override(self, mock_health_service, mock_update, mock_context):
        """Test that custom command name overrides function name"""
        # Arrange
        @track_command_metrics("custom_name")
        async def original_function_name(update, context):
            return "result"
        
        # Act
        await original_function_name(mock_update, mock_context)
        
        # Assert
        mock_health_service.record_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self, mock_health_service):
        """Test that decorator preserves original function metadata"""
        # Arrange
        @track_command_metrics("test")
        async def test_function(update, context):
            """Test function docstring"""
            return "result"
        
        # Assert
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring"

    @pytest.mark.asyncio
    async def test_very_fast_operation_timing(self, mock_health_service, mock_update, mock_context):
        """Test timing for very fast operations (edge case)"""
        # Arrange
        @track_command_metrics("fast_command")
        async def fast_function(update, context):
            return "fast"
        
        # Act
        await fast_function(mock_update, mock_context)
        
        # Assert
        mock_health_service.record_command.assert_called_once()
        call_args = mock_health_service.record_command.call_args
        response_time_ms = call_args[0][0]
        
        # Even very fast operations should have >= 0 response time
        assert response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_different_return_types(self, mock_health_service, mock_update, mock_context):
        """Test decorator works with different return types"""
        # Test cases for different return types
        test_cases = [
            "test_string",
            42,
            [1, 2, 3],
            {"key": "value"},
            None,
        ]
        
        for expected_result in test_cases:
            @track_command_metrics("test")
            async def test_function(update, context):
                return expected_result
            
            # Act
            result = await test_function(mock_update, mock_context)
            
            # Assert
            assert result == expected_result

    @pytest.mark.asyncio
    async def test_multiple_exception_types(self, mock_health_service, mock_update, mock_context):
        """Test handling of different exception types"""
        exception_types = [
            ValueError("Value error"),
            RuntimeError("Runtime error"),
            TypeError("Type error"),
            KeyError("Key error"),
        ]
        
        for exception in exception_types:
            @track_command_metrics("test")
            async def test_function(update, context):
                raise exception
            
            # Act & Assert
            with pytest.raises(type(exception)):
                await test_function(mock_update, mock_context)
            
            # Verify error was recorded
            mock_health_service.record_command.assert_called()
            call_args = mock_health_service.record_command.call_args
            is_error = call_args[0][1]
            assert is_error is True
            
            # Reset mock for next iteration
            mock_health_service.reset_mock()


class TestTrackAudioMetrics:
    """Test cases for track_audio_metrics decorator"""

    @pytest.fixture
    def mock_health_service(self):
        """Mock health service for testing"""
        with patch('src.bot.metrics_middleware.health_service') as mock:
            mock.record_audio_processing = MagicMock()
            yield mock

    @pytest.fixture
    def mock_update(self):
        """Mock Telegram Update object"""
        return MagicMock(spec=Update)

    @pytest.fixture
    def mock_context(self):
        """Mock Telegram Context object"""
        return MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    @pytest.mark.asyncio
    async def test_successful_audio_processing_records_metrics(self, mock_health_service, mock_update, mock_context):
        """Test that successful audio processing records metrics correctly"""
        # Arrange
        expected_result = "audio_processed"
        
        @track_audio_metrics("transcribe_audio")
        async def process_audio(update, context):
            await asyncio.sleep(0.001)  # Simulate processing time
            return expected_result
        
        # Act
        result = await process_audio(mock_update, mock_context)
        
        # Assert
        assert result == expected_result
        mock_health_service.record_audio_processing.assert_called_once()
        
        # Check that processing time was recorded
        call_args = mock_health_service.record_audio_processing.call_args
        processing_time_ms = call_args[0][0]
        is_error = call_args[0][1]
        
        assert processing_time_ms > 0
        assert is_error is False

    @pytest.mark.asyncio
    async def test_audio_processing_error_records_error_metrics(self, mock_health_service, mock_update, mock_context):
        """Test that audio processing errors are recorded as error metrics"""
        # Arrange
        test_exception = RuntimeError("Audio processing failed")
        
        @track_audio_metrics("transcribe_audio")
        async def process_audio(update, context):
            raise test_exception
        
        # Act & Assert
        with pytest.raises(RuntimeError, match="Audio processing failed"):
            await process_audio(mock_update, mock_context)
        
        # Check error was recorded
        mock_health_service.record_audio_processing.assert_called_once()
        call_args = mock_health_service.record_audio_processing.call_args
        processing_time_ms = call_args[0][0]
        is_error = call_args[0][1]
        
        assert processing_time_ms >= 0
        assert is_error is True

    @pytest.mark.asyncio
    async def test_auto_detect_operation_name_from_function(self, mock_health_service, mock_update, mock_context):
        """Test that operation name is auto-detected from function name"""
        # Arrange
        @track_audio_metrics()
        async def transcribe_voice_message(update, context):
            return "transcribed"
        
        # Act
        await transcribe_voice_message(mock_update, mock_context)
        
        # Assert
        mock_health_service.record_audio_processing.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_operation_name_override(self, mock_health_service, mock_update, mock_context):
        """Test that custom operation name overrides function name"""
        # Arrange
        @track_audio_metrics("custom_audio_op")
        async def original_function_name(update, context):
            return "result"
        
        # Act
        await original_function_name(mock_update, mock_context)
        
        # Assert
        mock_health_service.record_audio_processing.assert_called_once()

    @pytest.mark.asyncio
    async def test_preserves_function_metadata_for_audio(self, mock_health_service):
        """Test that audio decorator preserves original function metadata"""
        # Arrange
        @track_audio_metrics("test_audio")
        async def audio_processor(update, context):
            """Process audio file"""
            return "processed"
        
        # Assert
        assert audio_processor.__name__ == "audio_processor"
        assert audio_processor.__doc__ == "Process audio file"

    @pytest.mark.asyncio
    async def test_audio_processing_with_different_file_types(self, mock_health_service, mock_update, mock_context):
        """Test audio processing metrics with different file types simulation"""
        # Simulate processing different audio formats
        audio_formats = ["mp3", "wav", "ogg", "m4a"]
        
        for audio_format in audio_formats:
            @track_audio_metrics(f"process_{audio_format}")
            async def process_audio_format(update, context):
                # Simulate different processing times for different formats
                if audio_format == "wav":
                    await asyncio.sleep(0.002)  # WAV takes longer
                else:
                    await asyncio.sleep(0.001)
                return f"processed_{audio_format}"
            
            # Act
            result = await process_audio_format(mock_update, mock_context)
            
            # Assert
            assert result == f"processed_{audio_format}"
            mock_health_service.record_audio_processing.assert_called()
            
            # Reset for next iteration
            mock_health_service.reset_mock()


class TestEdgeCases:
    """Test edge cases for both decorators"""

    @pytest.fixture
    def mock_health_service(self):
        """Mock health service for testing"""
        with patch('src.bot.metrics_middleware.health_service') as mock:
            mock.record_command = MagicMock()
            mock.record_audio_processing = MagicMock()
            yield mock

    @pytest.mark.asyncio
    async def test_function_with_args_and_kwargs(self, mock_health_service):
        """Test decorators work with functions that have additional args/kwargs"""
        # Arrange
        @track_command_metrics("test_command")
        async def function_with_args(update, context, extra_arg, extra_kwarg=None):
            return f"args: {extra_arg}, kwargs: {extra_kwarg}"
        
        mock_update = MagicMock()
        mock_context = MagicMock()
        
        # Act
        result = await function_with_args(mock_update, mock_context, "test_arg", extra_kwarg="test_kwarg")
        
        # Assert
        assert result == "args: test_arg, kwargs: test_kwarg"
        mock_health_service.record_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_nested_decorators(self, mock_health_service):
        """Test behavior when decorators are nested or combined"""
        # Arrange
        @track_command_metrics("outer_command")
        @track_audio_metrics("inner_audio")
        async def nested_function(update, context):
            return "nested_result"
        
        mock_update = MagicMock()
        mock_context = MagicMock()
        
        # Act
        result = await nested_function(mock_update, mock_context)
        
        # Assert
        assert result == "nested_result"
        # Both decorators should record metrics
        mock_health_service.record_command.assert_called_once()
        mock_health_service.record_audio_processing.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, mock_health_service):
        """Test that concurrent operations are handled correctly"""
        # Arrange
        @track_command_metrics("concurrent_command")
        async def concurrent_function(update, context, delay):
            await asyncio.sleep(delay)
            return f"completed_after_{delay}"
        
        mock_update = MagicMock()
        mock_context = MagicMock()
        
        # Act - Run multiple operations concurrently
        tasks = [
            concurrent_function(mock_update, mock_context, 0.001),
            concurrent_function(mock_update, mock_context, 0.002),
            concurrent_function(mock_update, mock_context, 0.003),
        ]
        results = await asyncio.gather(*tasks)
        
        # Assert
        assert len(results) == 3
        assert results[0] == "completed_after_0.001"
        assert results[1] == "completed_after_0.002"
        assert results[2] == "completed_after_0.003"
        
        # All operations should be recorded
        assert mock_health_service.record_command.call_count == 3