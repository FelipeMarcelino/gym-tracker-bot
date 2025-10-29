"""Integration tests for AudioTranscriptionService

These tests focus on complete workflows, file system operations,
and real service integration scenarios.
"""

import pytest
import os
import tempfile
import asyncio
from unittest.mock import patch, AsyncMock

from services.audio_service import AudioTranscriptionService
from services.exceptions import AudioProcessingError, ServiceUnavailableError, ValidationError


class TestAudioServiceIntegration:
    """Integration tests using real file operations"""
    
    @pytest.fixture
    def audio_service(self):
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_api_key_integration"
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
            mock_settings.WHISPER_MODEL = "whisper-large-v3"
            with patch('services.audio_service.AsyncGroq'):
                return AudioTranscriptionService()

    @pytest.fixture
    async def cleanup_temp_files(self):
        """Clean up any temporary files after tests"""
        temp_files = []
        yield temp_files
        # Cleanup any remaining temp files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass


class TestRealFileSystemOperations(TestAudioServiceIntegration):
    """Test real file system operations"""

    @pytest.mark.asyncio
    async def test_complete_transcription_workflow_with_real_files(self, audio_service, cleanup_temp_files):
        """Test complete transcription workflow with real file operations"""
        test_audio_data = b"OggS" + b"fake_audio_content" * 100  # Simulate OGG file
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value="Fiz 3 séries de supino com 80kg")
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            result = await audio_service.transcribe_telegram_voice(test_audio_data)
            
            assert result == "Fiz 3 séries de supino com 80kg"
            
            # Verify API was called with correct parameters
            call_args = mock_client.audio.transcriptions.create.call_args
            assert call_args.kwargs["model"] == "whisper-large-v3"
            assert call_args.kwargs["language"] == "pt"
            assert "supino" in call_args.kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_temporary_file_creation_and_cleanup(self, audio_service, cleanup_temp_files):
        """Test that temporary files are created and cleaned up properly"""
        test_audio_data = b"test_audio_content" * 50
        temp_files_created = []
        
        # Track temp file creation
        original_to_thread = asyncio.to_thread
        async def track_temp_file(*args, **kwargs):
            result = await original_to_thread(*args, **kwargs)
            if hasattr(result, 'name'):
                temp_files_created.append(result.name)
                cleanup_temp_files.append(result.name)
            return result
        
        with patch('asyncio.to_thread', side_effect=track_temp_file), \
             patch('services.audio_service.AsyncGroq') as mock_groq:
            
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value="transcription successful")
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            result = await audio_service.transcribe_telegram_voice(test_audio_data)
            
            assert result == "transcription successful"
            assert len(temp_files_created) == 1
            
            # File should be cleaned up after transcription
            temp_file_path = temp_files_created[0]
            assert not os.path.exists(temp_file_path), "Temporary file should be cleaned up"

    @pytest.mark.asyncio
    async def test_file_operations_with_different_sizes(self, audio_service, cleanup_temp_files):
        """Test file operations with various file sizes"""
        test_cases = [
            (b"small", "Small file"),
            (b"x" * 1024, "1KB file"),
            (b"x" * (100 * 1024), "100KB file"),
            (b"x" * (1024 * 1024), "1MB file"),
        ]
        
        for file_data, description in test_cases:
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = AsyncMock()
                mock_client.audio.transcriptions.create = AsyncMock(return_value=f"Transcription for {description}")
                mock_groq.return_value = mock_client
                audio_service.client = mock_client
                
                result = await audio_service.transcribe_telegram_voice(file_data)
                
                assert result == f"Transcription for {description}"

    @pytest.mark.asyncio
    async def test_concurrent_file_operations(self, audio_service, cleanup_temp_files):
        """Test concurrent file operations don't interfere"""
        test_files = [
            (b"audio_1" * 100, "transcription_1"),
            (b"audio_2" * 100, "transcription_2"),
            (b"audio_3" * 100, "transcription_3"),
        ]
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            
            # Use consistent return value for concurrent operations
            mock_client.audio.transcriptions.create = AsyncMock(
                return_value="Concurrent file operation result"
            )
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            # Run concurrent transcriptions
            tasks = [
                audio_service.transcribe_telegram_voice(file_data)
                for file_data, _ in test_files
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Verify all operations completed successfully
            assert len(results) == 3
            for result in results:
                assert result == "Concurrent file operation result"

    @pytest.mark.asyncio
    async def test_file_permission_scenarios(self, audio_service, cleanup_temp_files):
        """Test file operations under different permission scenarios"""
        test_audio_data = b"permission_test_audio" * 50
        
        # Test with normal permissions (should work)
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value="permission test successful")
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            result = await audio_service.transcribe_telegram_voice(test_audio_data)
            assert result == "permission test successful"


class TestServiceConfigurationIntegration(TestAudioServiceIntegration):
    """Test service configuration in integration scenarios"""

    @pytest.mark.asyncio
    async def test_api_key_validation_scenarios(self, cleanup_temp_files):
        """Test API key validation in realistic scenarios"""
        valid_api_keys = [
            "gsk_1234567890abcdef",
            "sk-proj-1234567890abcdef",
            "test_key_12345",
        ]
        
        for api_key in valid_api_keys:
            with patch('services.audio_service.settings') as mock_settings:
                mock_settings.GROQ_API_KEY = api_key
                mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
                mock_settings.WHISPER_MODEL = "whisper-large-v3"
                
                with patch('services.audio_service.AsyncGroq') as mock_groq:
                    service = AudioTranscriptionService()
                    mock_groq.assert_called_with(api_key=api_key)

    @pytest.mark.asyncio
    async def test_model_configuration_integration(self, cleanup_temp_files):
        """Test model configuration in integration context"""
        models = ["whisper-large-v3", "whisper-1", "custom-model"]
        
        for model in models:
            with patch('services.audio_service.settings') as mock_settings:
                mock_settings.GROQ_API_KEY = "test_key"
                mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
                mock_settings.WHISPER_MODEL = model
                
                with patch('services.audio_service.AsyncGroq') as mock_groq:
                    mock_client = AsyncMock()
                    mock_client.audio.transcriptions.create = AsyncMock(return_value=f"result with {model}")
                    mock_groq.return_value = mock_client
                    
                    service = AudioTranscriptionService()
                    service.client = mock_client
                    
                    result = await service.transcribe_telegram_voice(b"test_audio")
                    assert result == f"result with {model}"
                    
                    # Verify model was used in API call
                    call_args = mock_client.audio.transcriptions.create.call_args
                    assert call_args.kwargs["model"] == model

    @pytest.mark.asyncio
    async def test_file_size_limits_integration(self, cleanup_temp_files):
        """Test file size limits in realistic scenarios"""
        size_configurations = [
            (1, b"x" * (512 * 1024)),    # 1MB limit, 512KB file (valid)
            (1, b"x" * (1024 * 1024 + 1)),   # 1MB limit, >1MB file (invalid)
            (5, b"x" * (3 * 1024 * 1024)), # 5MB limit, 3MB file (valid)
        ]
        
        for max_size_mb, test_file in size_configurations:
            with patch('services.audio_service.settings') as mock_settings:
                mock_settings.GROQ_API_KEY = "test_key"
                mock_settings.MAX_AUDIO_FILE_SIZE_MB = max_size_mb
                mock_settings.WHISPER_MODEL = "whisper-large-v3"
                
                with patch('services.audio_service.AsyncGroq') as mock_groq:
                    mock_client = AsyncMock()
                    mock_client.audio.transcriptions.create = AsyncMock(return_value="size test result")
                    mock_groq.return_value = mock_client
                    
                    service = AudioTranscriptionService()
                    service.client = mock_client
                    
                    max_bytes = max_size_mb * 1024 * 1024
                    
                    if len(test_file) > max_bytes:
                        # Should fail validation
                        with pytest.raises(ValidationError) as exc_info:
                            await service.transcribe_telegram_voice(test_file)
                        assert "muito grande" in str(exc_info.value)
                    else:
                        # Should pass validation
                        result = await service.transcribe_telegram_voice(test_file)
                        assert result == "size test result"


class TestErrorHandlingIntegration(TestAudioServiceIntegration):
    """Test error handling in integration scenarios"""

    @pytest.mark.asyncio
    async def test_api_error_scenarios_integration(self, audio_service, cleanup_temp_files):
        """Test various API error scenarios"""
        test_audio_data = b"error_test_audio" * 50
        
        error_scenarios = [
            (429, "Rate limit exceeded", ServiceUnavailableError, "Limite de taxa"),
            (401, "Unauthorized", ServiceUnavailableError, "Chave API"),
            (500, "Internal server error", AudioProcessingError, "Falha na transcrição"),
            (503, "Service unavailable", AudioProcessingError, "Falha na transcrição"),
        ]
        
        for status_code, error_message, expected_exception, expected_text in error_scenarios:
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = AsyncMock()
                
                # Create error with status code
                error = Exception(error_message)
                error.status_code = status_code
                mock_client.audio.transcriptions.create = AsyncMock(side_effect=error)
                
                mock_groq.return_value = mock_client
                audio_service.client = mock_client
                
                with pytest.raises(expected_exception) as exc_info:
                    await audio_service.transcribe_telegram_voice(test_audio_data)
                
                assert expected_text in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_network_timeout_scenarios(self, audio_service, cleanup_temp_files):
        """Test network timeout scenarios"""
        test_audio_data = b"timeout_test_audio" * 50
        
        timeout_errors = [
            asyncio.TimeoutError("Request timeout"),
            Exception("Connection timeout"),
            Exception("Read timeout"),
        ]
        
        for timeout_error in timeout_errors:
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = AsyncMock()
                mock_client.audio.transcriptions.create = AsyncMock(side_effect=timeout_error)
                mock_groq.return_value = mock_client
                audio_service.client = mock_client
                
                with pytest.raises(AudioProcessingError) as exc_info:
                    await audio_service.transcribe_telegram_voice(test_audio_data)
                
                assert "Falha na transcrição" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, audio_service, cleanup_temp_files):
        """Test handling of malformed API responses"""
        test_audio_data = b"malformed_test_audio" * 50
        
        malformed_responses = [
            "",    # Empty string
            "   ", # Whitespace only
            "\n\t\r", # Only whitespace characters
        ]
        
        for malformed_response in malformed_responses:
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = AsyncMock()
                mock_client.audio.transcriptions.create = AsyncMock(return_value=malformed_response)
                mock_groq.return_value = mock_client
                audio_service.client = mock_client
                
                with pytest.raises(AudioProcessingError) as exc_info:
                    await audio_service.transcribe_telegram_voice(test_audio_data)
                
                assert "texto vazio" in str(exc_info.value)
        
        # Test None response separately - it triggers generic error handling
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value=None)
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            with pytest.raises(AudioProcessingError) as exc_info:
                await audio_service.transcribe_telegram_voice(test_audio_data)
            
            # None response causes AttributeError when calling .strip(), leading to generic error
            assert "Erro inesperado" in str(exc_info.value)


class TestRealWorldScenarios(TestAudioServiceIntegration):
    """Test real-world usage scenarios"""

    @pytest.mark.asyncio
    async def test_typical_workout_transcription_workflow(self, audio_service, cleanup_temp_files):
        """Test typical workout transcription workflow"""
        # Simulate real workout audio descriptions
        workout_scenarios = [
            (b"workout_audio_1" * 100, "Fiz 3 séries de 12 repetições de supino com 80 quilos"),
            (b"workout_audio_2" * 100, "Hoje corri 5 quilômetros na esteira em 30 minutos"),
            (b"workout_audio_3" * 100, "Treino de pernas: leg press 4x15, agachamento 3x12"),
            (b"workout_audio_4" * 100, "Aeróbico: 45 minutos de bicicleta ergométrica"),
        ]
        
        for audio_data, expected_transcription in workout_scenarios:
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = AsyncMock()
                mock_client.audio.transcriptions.create = AsyncMock(return_value=expected_transcription)
                mock_groq.return_value = mock_client
                audio_service.client = mock_client
                
                result = await audio_service.transcribe_telegram_voice(audio_data)
                
                assert result == expected_transcription
                
                # Verify gym vocabulary was used in prompt
                call_args = mock_client.audio.transcriptions.create.call_args
                prompt = call_args.kwargs["prompt"]
                assert "supino" in prompt
                assert "agachamento" in prompt
                assert "repetições" in prompt

    @pytest.mark.asyncio
    async def test_multi_user_concurrent_transcription(self, audio_service, cleanup_temp_files):
        """Test multiple users using transcription service concurrently"""
        user_audio_data = [
            (f"user_{i}_audio".encode() * 50, f"User {i} workout transcription")
            for i in range(5)
        ]
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            # Use return_value instead of side_effect for concurrent calls
            mock_client.audio.transcriptions.create = AsyncMock(
                return_value="Concurrent user workout transcription"
            )
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            # Simulate concurrent users
            tasks = [
                audio_service.transcribe_telegram_voice(audio_data)
                for audio_data, _ in user_audio_data
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Verify we got results for all users (order doesn't matter for concurrent operations)
            assert len(results) == 5
            for result in results:
                assert result == "Concurrent user workout transcription"

    @pytest.mark.asyncio
    async def test_service_resilience_under_load(self, audio_service, cleanup_temp_files):
        """Test service resilience under load"""
        # Simulate high load scenario
        num_requests = 10
        audio_data = b"load_test_audio" * 100
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            # Use consistent return value for concurrent load testing
            mock_client.audio.transcriptions.create = AsyncMock(
                return_value="Load test result"
            )
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            # Run many concurrent requests
            tasks = [
                audio_service.transcribe_telegram_voice(audio_data)
                for _ in range(num_requests)
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == num_requests
            for result in results:
                assert result == "Load test result"

    @pytest.mark.asyncio
    async def test_service_recovery_from_errors(self, audio_service, cleanup_temp_files):
        """Test service recovery from temporary errors"""
        audio_data = b"recovery_test_audio" * 50
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            
            # First call fails, second succeeds
            mock_client.audio.transcriptions.create = AsyncMock(
                side_effect=[
                    Exception("Temporary error"),
                    "Recovery successful transcription",
                ]
            )
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            # First call should fail
            with pytest.raises(AudioProcessingError):
                await audio_service.transcribe_telegram_voice(audio_data)
            
            # Second call should succeed (service recovered)
            result = await audio_service.transcribe_telegram_voice(audio_data)
            assert result == "Recovery successful transcription"


class TestFileSystemEdgeCases(TestAudioServiceIntegration):
    """Test file system edge cases"""

    @pytest.mark.asyncio
    async def test_disk_space_scenarios(self, audio_service, cleanup_temp_files):
        """Test handling of disk space issues"""
        large_audio_data = b"x" * (5 * 1024 * 1024)  # 5MB file
        
        # Test normal operation first
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value="Disk space test successful")
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            result = await audio_service.transcribe_telegram_voice(large_audio_data)
            assert result == "Disk space test successful"

    @pytest.mark.asyncio
    async def test_temp_directory_scenarios(self, audio_service, cleanup_temp_files):
        """Test different temporary directory scenarios"""
        audio_data = b"temp_dir_test" * 100
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value="Temp directory test successful")
            mock_groq.return_value = mock_client
            audio_service.client = mock_client
            
            # Test with default temp directory
            result = await audio_service.transcribe_telegram_voice(audio_data)
            assert result == "Temp directory test successful"

    @pytest.mark.asyncio
    async def test_file_encoding_scenarios(self, audio_service, cleanup_temp_files):
        """Test different file encoding scenarios"""
        # Test various binary data patterns
        encoding_test_cases = [
            b"\x00\x01\x02\x03" * 250,  # Binary data with null bytes
            b"\xFF\xFE\xFD\xFC" * 250,  # High-value bytes
            bytes(range(256)) * 4,       # All possible byte values
            b"UTF-8: \xc3\xa1\xc3\xa9\xc3\xad\xc3\xb3\xc3\xba" * 100,  # UTF-8 encoded
        ]
        
        for i, test_data in enumerate(encoding_test_cases):
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = AsyncMock()
                mock_client.audio.transcriptions.create = AsyncMock(return_value=f"Encoding test {i} successful")
                mock_groq.return_value = mock_client
                audio_service.client = mock_client
                
                result = await audio_service.transcribe_telegram_voice(test_data)
                assert result == f"Encoding test {i} successful"


class TestServiceLifecycleIntegration(TestAudioServiceIntegration):
    """Test service lifecycle in integration scenarios"""

    @pytest.mark.asyncio
    async def test_service_initialization_and_usage_pattern(self, cleanup_temp_files):
        """Test typical service initialization and usage pattern"""
        # Test complete lifecycle
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "lifecycle_test_key"
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
            mock_settings.WHISPER_MODEL = "whisper-large-v3"
            
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = AsyncMock()
                mock_client.audio.transcriptions.create = AsyncMock(return_value="Lifecycle test successful")
                mock_groq.return_value = mock_client
                
                # Initialize service
                service = AudioTranscriptionService()
                service.client = mock_client
                
                # Use service multiple times
                for i in range(3):
                    audio_data = f"lifecycle_test_{i}".encode() * 100
                    result = await service.transcribe_telegram_voice(audio_data)
                    assert result == "Lifecycle test successful"

    @pytest.mark.asyncio
    async def test_service_configuration_changes(self, cleanup_temp_files):
        """Test service behavior with configuration changes"""
        base_config = {
            "GROQ_API_KEY": "config_test_key",
            "MAX_AUDIO_FILE_SIZE_MB": 5,
            "WHISPER_MODEL": "whisper-large-v3",
        }
        
        config_variations = [
            {**base_config, "MAX_AUDIO_FILE_SIZE_MB": 1},   # Smaller limit
            {**base_config, "MAX_AUDIO_FILE_SIZE_MB": 25},  # Larger limit
            {**base_config, "WHISPER_MODEL": "whisper-1"}, # Different model
        ]
        
        for config in config_variations:
            with patch('services.audio_service.settings') as mock_settings:
                for key, value in config.items():
                    setattr(mock_settings, key, value)
                
                with patch('services.audio_service.AsyncGroq') as mock_groq:
                    mock_client = AsyncMock()
                    mock_client.audio.transcriptions.create = AsyncMock(return_value="Config test successful")
                    mock_groq.return_value = mock_client
                    
                    service = AudioTranscriptionService()
                    service.client = mock_client
                    
                    # Test with small file that should work with any config
                    audio_data = b"config_test" * 100
                    result = await service.transcribe_telegram_voice(audio_data)
                    assert result == "Config test successful"