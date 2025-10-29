"""Unit tests for AudioTranscriptionService

These tests focus on business logic validation, error handling patterns,
and audio processing edge cases without external API dependencies.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from services.audio_service import AudioTranscriptionService
from services.exceptions import AudioProcessingError, ServiceUnavailableError, ValidationError


class MockAsyncContextManager:
    """Simple async context manager returning the provided mock file object."""

    def __init__(self, mock_file):
        self.mock_file = mock_file

    async def __aenter__(self):
        return self.mock_file

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def configure_mock_aiofiles_open(mock_open, *, read_data=b""):
    """Configure aiofiles.open mock to behave as an async context manager."""

    def _open_side_effect(*args, **kwargs):
        mode = ""
        if len(args) > 1:
            mode = args[1] or ""
        elif "mode" in kwargs:
            mode = kwargs["mode"] or ""

        file_mock = AsyncMock()

        # Provide async write capability for write modes
        file_mock.write = AsyncMock(return_value=None)

        # Provide async read capability when reading the file
        if "r" in mode:
            file_mock.read = AsyncMock(return_value=read_data)
        else:
            file_mock.read = AsyncMock(return_value=b"")

        return MockAsyncContextManager(file_mock)

    mock_open.side_effect = _open_side_effect

    return mock_open


class TestAudioServiceInstantiation:
    """Test audio service instantiation and configuration"""

    @patch('services.audio_service.settings')
    def test_service_instantiation_success(self, mock_settings):
        """Test successful service instantiation"""
        mock_settings.GROQ_API_KEY = "test_api_key"
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_client = MagicMock()
            mock_groq.return_value = mock_client
            
            service = AudioTranscriptionService()
            
            assert service is not None
            assert isinstance(service, AudioTranscriptionService)
            assert service.client == mock_client
            mock_groq.assert_called_once_with(api_key="test_api_key")

    @patch('services.audio_service.settings')
    def test_service_instantiation_no_api_key(self, mock_settings):
        """Test service instantiation fails without API key"""
        mock_settings.GROQ_API_KEY = None
        
        with pytest.raises(ServiceUnavailableError) as exc_info:
            AudioTranscriptionService()
        
        assert "GROQ_API_KEY não configurada" in str(exc_info.value)

    @patch('services.audio_service.settings')
    def test_service_instantiation_empty_api_key(self, mock_settings):
        """Test service instantiation fails with empty API key"""
        mock_settings.GROQ_API_KEY = ""
        
        with pytest.raises(ServiceUnavailableError) as exc_info:
            AudioTranscriptionService()
        
        assert "GROQ_API_KEY não configurada" in str(exc_info.value)

    @patch('services.audio_service.settings')
    def test_service_instantiation_client_failure(self, mock_settings):
        """Test service instantiation fails when client creation fails"""
        mock_settings.GROQ_API_KEY = "test_api_key"
        
        with patch('services.audio_service.AsyncGroq') as mock_groq:
            mock_groq.side_effect = Exception("Client creation failed")
            
            with pytest.raises(ServiceUnavailableError) as exc_info:
                AudioTranscriptionService()
            
            assert "Falha ao inicializar cliente Groq" in str(exc_info.value)
            assert "Client creation failed" in str(exc_info.value)

    @patch('services.audio_service.settings')
    def test_service_has_gym_vocabulary(self, mock_settings):
        """Test service includes gym vocabulary"""
        mock_settings.GROQ_API_KEY = "test_api_key"
        
        with patch('services.audio_service.AsyncGroq'):
            service = AudioTranscriptionService()
            
            assert hasattr(service, 'gym_vocabulary')
            assert "supino" in service.gym_vocabulary
            assert "agachamento" in service.gym_vocabulary
            assert "musculação" in service.gym_vocabulary
            assert "repetições" in service.gym_vocabulary


class TestAudioFileValidation:
    """Test audio file validation business logic"""

    @pytest.fixture
    def audio_service(self):
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_api_key"
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
            mock_settings.WHISPER_MODEL = "whisper-large-v3"
            
            with patch('services.audio_service.AsyncGroq') as mock_groq:
                mock_client = MagicMock()
                mock_groq.return_value = mock_client
                
                service = AudioTranscriptionService()
                service.client = mock_client
                return service

    @pytest.mark.asyncio
    async def test_empty_file_validation(self, audio_service):
        """Test validation with empty audio file"""
        empty_files = [b"", None]
        
        for empty_file in empty_files:
            with pytest.raises(ValidationError) as exc_info:
                await audio_service.transcribe_telegram_voice(empty_file)
            
            assert "Arquivo de áudio vazio" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_size_validation_edge_cases(self, audio_service):
        """Test file size validation with edge cases"""
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 1  # 1MB limit
            
            # Test just over limit
            oversized_file = b"x" * (1 * 1024 * 1024 + 1)
            
            # Oversized should fail
            with pytest.raises(ValidationError) as exc_info:
                await audio_service.transcribe_telegram_voice(oversized_file)
            assert "muito grande" in str(exc_info.value)
            assert "1MB" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_size_validation_with_different_limits(self, audio_service):
        """Test file size validation with different size limits"""
        invalid_cases = [
            (0.5, b"x" * (600 * 1024)),  # 0.5MB limit, 600KB file (invalid)
            (5, b"x" * (6 * 1024 * 1024)),  # 5MB limit, 6MB file (invalid)
        ]
        
        for limit_mb, file_data in invalid_cases:
            with patch('services.audio_service.settings') as mock_settings:
                mock_settings.MAX_AUDIO_FILE_SIZE_MB = limit_mb
                
                # Should fail validation
                with pytest.raises(ValidationError) as exc_info:
                    await audio_service.transcribe_telegram_voice(file_data)
                assert "muito grande" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_content_type_variations(self, audio_service):
        """Test service handles various file content patterns"""
        # Test that non-empty files pass basic validation
        test_file = b"OggS" + b"x" * 996  # Ogg header
        
        # Just test that it doesn't fail with validation error
        try:
            await audio_service.transcribe_telegram_voice(test_file)
        except ValidationError as e:
            if "muito grande" in str(e) or "vazio" in str(e):
                pytest.fail("Valid binary data should not fail basic validation")
        except Exception:
            # Other exceptions expected due to mocking/processing
            pass


class TestTranscriptionErrorHandling:
    """Test transcription error handling patterns"""

    @pytest.fixture
    def audio_service(self):
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_api_key"
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
            mock_settings.WHISPER_MODEL = "whisper-large-v3"
            with patch('services.audio_service.AsyncGroq'):
                return AudioTranscriptionService()

    @pytest.mark.asyncio
    async def test_rate_limit_error_detection(self, audio_service):
        """Test rate limit error detection patterns"""
        test_file = b"valid_audio_data"
        
        rate_limit_errors = [
            Exception("Rate limit exceeded"),
            Exception("HTTP 429 Too Many Requests"),
            Exception("too many requests received"),
            Exception("rate_limit error occurred"),
        ]
        
        # Mock rate limit error with status code
        rate_limit_with_status = Exception("API Error")
        rate_limit_with_status.status_code = 429
        rate_limit_errors.append(rate_limit_with_status)
        
        for error in rate_limit_errors:
            mock_temp_file = MagicMock()
            mock_temp_file.name = "/tmp/test_audio.ogg"

            with patch('asyncio.to_thread', return_value=mock_temp_file), \
                 patch('aiofiles.open') as mock_open, \
                 patch('aiofiles.os.remove'):
                configure_mock_aiofiles_open(mock_open, read_data=test_file)

                audio_service.client.audio.transcriptions.create = AsyncMock(side_effect=error)

                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await audio_service.transcribe_telegram_voice(test_file)
                
                assert "Limite de taxa" in str(exc_info.value) or "rate" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_authentication_error_detection(self, audio_service):
        """Test authentication error detection patterns"""
        test_file = b"valid_audio_data"
        
        auth_errors = [
            Exception("Unauthorized access"),
            Exception("HTTP 401 Unauthorized"),
            Exception("Invalid API key provided"),
            Exception("invalid key format"),
        ]
        
        # Mock auth error with status code
        auth_error_with_status = Exception("API Error")
        auth_error_with_status.status_code = 401
        auth_errors.append(auth_error_with_status)
        
        for error in auth_errors:
            with patch('asyncio.to_thread'), \
                 patch('aiofiles.open') as mock_open, \
                 patch('aiofiles.os.remove'):
                configure_mock_aiofiles_open(mock_open, read_data=test_file)

                audio_service.client.audio.transcriptions.create = AsyncMock(side_effect=error)

                with pytest.raises(ServiceUnavailableError) as exc_info:
                    await audio_service.transcribe_telegram_voice(test_file)
                
                assert "Chave API" in str(exc_info.value) or "inválida" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generic_api_error_handling(self, audio_service):
        """Test generic API error handling"""
        test_file = b"valid_audio_data"
        
        generic_errors = [
            Exception("Network timeout"),
            Exception("Connection refused"),
            Exception("Service temporarily unavailable"),
            Exception("Unknown API error"),
        ]
        
        for error in generic_errors:
            with patch('asyncio.to_thread'), \
                 patch('aiofiles.open') as mock_open, \
                 patch('aiofiles.os.remove'):
                configure_mock_aiofiles_open(mock_open, read_data=test_file)

                audio_service.client.audio.transcriptions.create = AsyncMock(side_effect=error)

                with pytest.raises(AudioProcessingError) as exc_info:
                    await audio_service.transcribe_telegram_voice(test_file)
                
                assert "Falha na transcrição" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_transcription_handling(self, audio_service):
        """Test handling of empty transcription results"""
        test_file = b"valid_audio_data"
        
        empty_results = ["", "   ", "\t\n", "\r\n   \t"]
        
        for empty_result in empty_results:
            with patch('asyncio.to_thread'), \
                 patch('aiofiles.open') as mock_open, \
                 patch('aiofiles.os.remove'):
                configure_mock_aiofiles_open(mock_open, read_data=test_file)

                audio_service.client.audio.transcriptions.create = AsyncMock(return_value=empty_result)

                with pytest.raises(AudioProcessingError) as exc_info:
                    await audio_service.transcribe_telegram_voice(test_file)
                
                assert "texto vazio" in str(exc_info.value)


class TestFileSystemOperations:
    """Test file system operations and temporary file handling"""

    @pytest.fixture
    def audio_service(self):
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_api_key"
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
            mock_settings.WHISPER_MODEL = "whisper-large-v3"
            with patch('services.audio_service.AsyncGroq'):
                return AudioTranscriptionService()

    @pytest.mark.asyncio
    async def test_temporary_file_creation_failure(self, audio_service):
        """Test handling of temporary file creation failure"""
        test_file = b"valid_audio_data"
        
        with patch('asyncio.to_thread') as mock_to_thread:
            mock_to_thread.side_effect = Exception("Failed to create temp file")
            
            with pytest.raises(AudioProcessingError) as exc_info:
                await audio_service.transcribe_telegram_voice(test_file)
            
            assert "Erro inesperado" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_write_failure(self, audio_service):
        """Test handling of file write failures"""
        test_file = b"valid_audio_data"
        
        with patch('asyncio.to_thread'), \
             patch('aiofiles.open') as mock_open:
            
            # Mock file write failure
            mock_file = AsyncMock()
            mock_file.write.side_effect = Exception("Disk full")
            mock_open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_open.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(AudioProcessingError) as exc_info:
                await audio_service.transcribe_telegram_voice(test_file)
            
            assert "Erro inesperado" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_file_read_failure(self, audio_service):
        """Test handling of file read failures"""
        test_file = b"valid_audio_data"
        
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open:
            
            # First call (write) succeeds, second call (read) fails
            write_file = AsyncMock()
            read_file = AsyncMock()
            read_file.read.side_effect = Exception("File corrupted")
            
            mock_open.side_effect = [
                MockAsyncContextManager(write_file),  # Write context
                MockAsyncContextManager(read_file),   # Read context
            ]
            
            with pytest.raises(AudioProcessingError) as exc_info:
                await audio_service.transcribe_telegram_voice(test_file)
            
            assert "Erro inesperado" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_temporary_file_cleanup_success(self, audio_service):
        """Test successful temporary file cleanup"""
        test_file = b"valid_audio_data"
        
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open, \
             patch('aiofiles.os.remove') as mock_remove:
            configure_mock_aiofiles_open(mock_open, read_data=test_file)

            # Mock successful transcription
            audio_service.client.audio.transcriptions.create = AsyncMock(return_value="transcription result")

            result = await audio_service.transcribe_telegram_voice(test_file)
            
            assert result == "transcription result"
            mock_remove.assert_called_once_with("/tmp/test_audio.ogg")

    @pytest.mark.asyncio
    async def test_temporary_file_cleanup_failure(self, audio_service):
        """Test handling of temporary file cleanup failure"""
        test_file = b"valid_audio_data"
        
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open, \
             patch('aiofiles.os.remove') as mock_remove:
            configure_mock_aiofiles_open(mock_open, read_data=test_file)

            # Mock successful transcription but failed cleanup
            audio_service.client.audio.transcriptions.create = AsyncMock(return_value="transcription result")
            mock_remove.side_effect = Exception("Permission denied")
            
            # Should still return result despite cleanup failure
            result = await audio_service.transcribe_telegram_voice(test_file)
            
            assert result == "transcription result"
            mock_remove.assert_called_once_with("/tmp/test_audio.ogg")


class TestTranscriptionConfiguration:
    """Test transcription configuration and parameters"""

    @pytest.fixture
    def audio_service(self):
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_api_key"
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
            mock_settings.WHISPER_MODEL = "whisper-large-v3"
            with patch('services.audio_service.AsyncGroq'):
                return AudioTranscriptionService()

    @pytest.mark.asyncio
    async def test_transcription_parameters(self, audio_service):
        """Test transcription API call parameters"""
        test_file = b"valid_audio_data"
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open, \
             patch('aiofiles.os.remove'):
            configure_mock_aiofiles_open(mock_open, read_data=test_file)

            audio_service.client.audio.transcriptions.create = AsyncMock(return_value="transcription result")

            await audio_service.transcribe_telegram_voice(test_file)
            
            # Verify API call parameters
            call_args = audio_service.client.audio.transcriptions.create.call_args
            assert call_args.kwargs["model"] == "whisper-large-v3"
            assert call_args.kwargs["language"] == "pt"
            assert call_args.kwargs["response_format"] == "text"
            assert call_args.kwargs["temperature"] == 0
            assert "prompt" in call_args.kwargs
            assert "supino" in call_args.kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_gym_vocabulary_in_prompt(self, audio_service):
        """Test gym vocabulary is included in transcription prompt"""
        test_file = b"valid_audio_data"
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open, \
             patch('aiofiles.os.remove'):
            configure_mock_aiofiles_open(mock_open, read_data=test_file)

            audio_service.client.audio.transcriptions.create = AsyncMock(return_value="transcription result")

            await audio_service.transcribe_telegram_voice(test_file)
            
            call_args = audio_service.client.audio.transcriptions.create.call_args
            prompt = call_args.kwargs["prompt"]
            
            # Check for key gym terms
            gym_terms = ["supino", "agachamento", "musculação", "repetições", "séries", "quilos"]
            for term in gym_terms:
                assert term in prompt, f"Gym term '{term}' should be in prompt"

    @pytest.mark.asyncio
    async def test_file_format_specification(self, audio_service):
        """Test file format is correctly specified"""
        test_file = b"valid_audio_data"
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/test_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open, \
             patch('aiofiles.os.remove'):
            configure_mock_aiofiles_open(mock_open, read_data=test_file)

            audio_service.client.audio.transcriptions.create = AsyncMock(return_value="transcription result")

            await audio_service.transcribe_telegram_voice(test_file)
            
            call_args = audio_service.client.audio.transcriptions.create.call_args
            file_param = call_args.kwargs["file"]
            
            # Should be tuple of (filename, data)
            assert isinstance(file_param, tuple)
            assert len(file_param) == 2
            assert file_param[0].endswith(".ogg")


class TestEdgeCasesAndStress:
    """Test edge cases and stress scenarios"""

    @pytest.fixture
    def audio_service(self):
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_api_key"
            mock_settings.MAX_AUDIO_FILE_SIZE_MB = 10
            mock_settings.WHISPER_MODEL = "whisper-large-v3"
            with patch('services.audio_service.AsyncGroq'):
                return AudioTranscriptionService()

    @pytest.mark.asyncio
    async def test_very_large_valid_file(self, audio_service):
        """Test handling of very large but valid files"""
        # Create 5MB file (under 10MB limit)
        large_file = b"x" * (5 * 1024 * 1024)
        
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/large_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open, \
             patch('aiofiles.os.remove'):
            configure_mock_aiofiles_open(mock_open, read_data=large_file)

            audio_service.client.audio.transcriptions.create = AsyncMock(return_value="large file transcription")

            result = await audio_service.transcribe_telegram_voice(large_file)
            assert result == "large file transcription"

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters_in_result(self, audio_service):
        """Test handling of unicode and special characters in transcription"""
        test_file = b"valid_audio_data"
        
        unicode_results = [
            "Transcrição com acentos: ção, ã, õ",
            "Emoji result: 💪 treino forte hoje! 🏋️‍♂️",
            "Special chars: @#$%^&*()_+-=[]{}|;':\",./<>?",
            "Numbers: 123 séries de 15 repetições com 50kg",
            "Mixed: Fiz 3x15 supino com 80kg 💪",
        ]
        
        for unicode_result in unicode_results:
            mock_temp_file = MagicMock()
            mock_temp_file.name = "/tmp/test_audio.ogg"
            
            with patch('asyncio.to_thread', return_value=mock_temp_file), \
                 patch('aiofiles.open') as mock_open, \
                 patch('aiofiles.os.remove'):
                configure_mock_aiofiles_open(mock_open, read_data=test_file)

                audio_service.client.audio.transcriptions.create = AsyncMock(return_value=unicode_result)

                result = await audio_service.transcribe_telegram_voice(test_file)
                assert result == unicode_result

    @pytest.mark.asyncio
    async def test_whitespace_trimming_edge_cases(self, audio_service):
        """Test whitespace trimming in transcription results"""
        test_file = b"valid_audio_data"
        
        whitespace_cases = [
            ("  normal result  ", "normal result"),
            ("\t\ttab result\t\t", "tab result"),
            ("\n\nnewline result\n\n", "newline result"),
            ("\r\ncarriage return result\r\n", "carriage return result"),
            ("   \t\n\r  mixed whitespace  \r\n\t   ", "mixed whitespace"),
        ]
        
        for input_result, expected_output in whitespace_cases:
            mock_temp_file = MagicMock()
            mock_temp_file.name = "/tmp/test_audio.ogg"
            
            with patch('asyncio.to_thread', return_value=mock_temp_file), \
                 patch('aiofiles.open') as mock_open, \
                 patch('aiofiles.os.remove'):
                configure_mock_aiofiles_open(mock_open, read_data=test_file)

                audio_service.client.audio.transcriptions.create = AsyncMock(return_value=input_result)

                result = await audio_service.transcribe_telegram_voice(test_file)
                assert result == expected_output

    @pytest.mark.asyncio
    async def test_concurrent_transcription_stress(self, audio_service):
        """Test concurrent transcription requests"""
        test_files = [
            b"audio_data_1",
            b"audio_data_2", 
            b"audio_data_3",
            b"audio_data_4",
            b"audio_data_5",
        ]
        
        mock_temp_file = MagicMock()
        mock_temp_file.name = "/tmp/concurrent_audio.ogg"
        
        with patch('asyncio.to_thread', return_value=mock_temp_file), \
             patch('aiofiles.open') as mock_open, \
             patch('aiofiles.os.remove'):
            configure_mock_aiofiles_open(mock_open, read_data=b"")

            # Mock different results for each call
            audio_service.client.audio.transcriptions.create = AsyncMock(
                side_effect=[f"result_{i}" for i in range(len(test_files))]
            )
            
            # Run concurrent transcriptions
            tasks = [
                audio_service.transcribe_telegram_voice(file_data) 
                for file_data in test_files
            ]
            
            results = await asyncio.gather(*tasks)
            
            assert len(results) == len(test_files)
            for i, result in enumerate(results):
                assert result == f"result_{i}"

    @pytest.mark.asyncio
    async def test_api_key_format_variations(self, audio_service):
        """Test service handles various API key formats"""
        # This test verifies the service was initialized with different key formats
        test_keys = [
            "sk-1234567890abcdef",  # Standard format
            "gsk_1234567890abcdef", # Groq format
            "key123",               # Simple format
            "very_long_api_key_" + "x" * 100,  # Long key
        ]
        
        for api_key in test_keys:
            with patch('services.audio_service.settings') as mock_settings:
                mock_settings.GROQ_API_KEY = api_key
                with patch('services.audio_service.AsyncGroq') as mock_groq:
                    service = AudioTranscriptionService()
                    mock_groq.assert_called_with(api_key=api_key)
class TestServiceConfigurationEdgeCases:
    """Test service configuration edge cases"""

    def test_whisper_model_configuration(self):
        """Test whisper model configuration"""
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            mock_settings.WHISPER_MODEL = "custom-model-v1"
            
            with patch('services.audio_service.AsyncGroq'):
                service = AudioTranscriptionService()
                
                # Model should be used from settings
                assert hasattr(service, 'client')

    def test_max_file_size_configuration_edge_cases(self):
        """Test max file size configuration edge cases"""
        edge_cases = [0.1, 0.5, 1, 5, 10, 25, 100]  # Various MB limits
        
        for size_mb in edge_cases:
            with patch('services.audio_service.settings') as mock_settings:
                mock_settings.GROQ_API_KEY = "test_key"
                mock_settings.MAX_AUDIO_FILE_SIZE_MB = size_mb
                
                with patch('services.audio_service.AsyncGroq'):
                    service = AudioTranscriptionService()
                    
                    # Service should be created successfully
                    assert service is not None

    def test_gym_vocabulary_completeness(self):
        """Test gym vocabulary includes expected terms"""
        with patch('services.audio_service.settings') as mock_settings:
            mock_settings.GROQ_API_KEY = "test_key"
            
            with patch('services.audio_service.AsyncGroq'):
                service = AudioTranscriptionService()
                
                vocab = service.gym_vocabulary.lower()
                
                # Exercise types
                exercise_terms = ["supino", "agachamento", "levantamento terra", "leg press"]
                for term in exercise_terms:
                    assert term in vocab
                
                # Equipment terms
                equipment_terms = ["barra", "esteira", "bicicleta", "elíptico"]
                for term in equipment_terms:
                    assert term in vocab
                
                # Measurement terms
                measurement_terms = ["repetições", "séries", "quilos", "kg", "carga"]
                for term in measurement_terms:
                    assert term in vocab