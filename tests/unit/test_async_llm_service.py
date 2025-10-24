"""
Comprehensive unit tests for LLMParsingService

This test file demonstrates how to test non-deterministic LLM code by:
1. Mocking the LLM client to make tests deterministic
2. Testing parsing logic with controlled responses
3. Testing error handling for various failure scenarios
4. Testing edge cases (rate limits, timeouts, malformed responses)

Key Testing Strategy:
- We DON'T test if Groq API works (that's their job)
- We DO test if OUR code correctly handles valid/invalid LLM responses
- We use mocks to simulate all possible LLM behaviors
"""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from config.settings import settings
from services.async_llm_service import LLMParsingService
from services.exceptions import (
    ErrorCode,
    LLMParsingError,
    ServiceUnavailableError,
    ValidationError,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_groq_client():
    """Mock Groq client for testing"""
    mock = AsyncMock()
    # Create mock response structure
    mock.chat = AsyncMock()
    mock.chat.completions = AsyncMock()
    mock.chat.completions.create = AsyncMock()
    return mock


@pytest.fixture
def llm_service(mock_groq_client, monkeypatch):
    """Create LLMParsingService with mocked Groq client"""
    # Set API key to avoid initialization error
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-api-key-123")

    with patch("services.async_llm_service.AsyncGroq") as mock_async_groq:
        mock_async_groq.return_value = mock_groq_client
        service = LLMParsingService()
        # Replace the client with our mock
        service.client = mock_groq_client
        return service


@pytest.fixture
def valid_workout_json() -> Dict[str, Any]:
    """Valid workout JSON response from LLM"""
    return {
        "body_weight_kg": 75.5,
        "energy_level": 8,
        "start_time": "10:00",
        "end_time": "11:30",
        "resistance_exercises": [
            {
                "name": "supino reto com barra",
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [60, 70, 80],
                "rest_seconds": 90,
                "perceived_difficulty": 7,
                "notes": None,
            },
            {
                "name": "leg press 45 graus",
                "sets": 4,
                "reps": [15, 15, 12, 10],
                "weights_kg": [200, 200, 220, 240],
                "rest_seconds": 60,
                "perceived_difficulty": 8,
                "notes": None,
            },
        ],
        "aerobic_exercises": [
            {
                "name": "corrida na esteira",
                "duration_minutes": 20,
                "distance_km": 3.5,
                "average_heart_rate": 145,
                "calories_burned": 250,
                "intensity_level": "moderate",
                "notes": None,
            }
        ],
        "notes": None,
    }


@pytest.fixture
def mock_groq_response(valid_workout_json):
    """Create a mock Groq API response"""
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()

    # Set up the response structure
    mock_message.content = json.dumps(valid_workout_json)
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    return mock_response


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestLLMServiceInitialization:
    """Test LLMParsingService initialization"""

    def test_init_without_api_key(self, monkeypatch):
        """Test initialization fails without GROQ_API_KEY"""
        # Remove the API key
        monkeypatch.setattr(settings, "GROQ_API_KEY", None)

        with pytest.raises(ServiceUnavailableError) as exc_info:
            LLMParsingService()

        assert "GROQ_API_KEY não configurada" in str(exc_info.value)

    def test_init_with_api_key_success(self, monkeypatch):
        """Test successful initialization with API key"""
        monkeypatch.setattr(settings, "GROQ_API_KEY", "test-api-key-123")

        with patch("services.async_llm_service.AsyncGroq") as mock_async_groq:
            mock_client = AsyncMock()
            mock_async_groq.return_value = mock_client

            service = LLMParsingService()

            assert service.client == mock_client
            assert service.model == settings.LLM_MODEL
            mock_async_groq.assert_called_once_with(api_key="test-api-key-123")

    def test_init_groq_client_failure(self, monkeypatch):
        """Test initialization fails when Groq client creation fails"""
        monkeypatch.setattr(settings, "GROQ_API_KEY", "test-api-key")

        with patch("services.async_llm_service.AsyncGroq") as mock_async_groq:
            mock_async_groq.side_effect = Exception("Connection failed")

            with pytest.raises(ServiceUnavailableError) as exc_info:
                LLMParsingService()

            assert "Falha ao inicializar cliente Groq LLM" in str(exc_info.value)


# =============================================================================
# INPUT VALIDATION TESTS
# =============================================================================


class TestParseWorkoutInputValidation:
    """Test input validation in parse_workout method"""

    @pytest.mark.asyncio
    async def test_empty_transcription(self, llm_service):
        """Test that empty transcription raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout("")

        error = exc_info.value
        assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert "Transcrição vazia ou inválida" in error.message
        assert "conteúdo válido" in error.user_message

    @pytest.mark.asyncio
    async def test_whitespace_only_transcription(self, llm_service):
        """Test that whitespace-only transcription raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout("   \n\t  ")

        error = exc_info.value
        assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.asyncio
    async def test_transcription_too_long(self, llm_service, monkeypatch):
        """Test that overly long transcription raises ValidationError"""
        # Set a low limit for testing
        monkeypatch.setattr(settings, "MAX_TRANSCRIPTION_LENGTH", 100)

        long_transcription = "a" * 101  # Exceeds limit

        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout(long_transcription)

        error = exc_info.value
        assert error.error_code == ErrorCode.VALUE_OUT_OF_RANGE
        assert "muito longa" in error.message.lower()
        assert "100" in error.message

    @pytest.mark.asyncio
    async def test_transcription_at_max_length(self, llm_service, monkeypatch, mock_groq_response):
        """Test that transcription at exactly max length is accepted"""
        monkeypatch.setattr(settings, "MAX_TRANSCRIPTION_LENGTH", 100)

        # Create transcription at exactly max length
        transcription = "a" * 100

        # Mock successful LLM response
        llm_service.client.chat.completions.create.return_value = mock_groq_response

        # Should not raise exception
        result = await llm_service.parse_workout(transcription)
        assert isinstance(result, dict)


# =============================================================================
# LLM RESPONSE PARSING TESTS
# =============================================================================


class TestParseWorkoutResponseParsing:
    """Test parsing of LLM responses"""

    @pytest.mark.asyncio
    async def test_parse_valid_json_response(self, llm_service, mock_groq_response):
        """Test parsing of valid JSON response from LLM"""
        llm_service.client.chat.completions.create.return_value = mock_groq_response

        result = await llm_service.parse_workout("Fiz 3 séries de supino com 60kg")

        assert isinstance(result, dict)
        assert "resistance_exercises" in result
        assert len(result["resistance_exercises"]) == 2
        assert result["body_weight_kg"] == 75.5
        assert result["energy_level"] == 8

    @pytest.mark.asyncio
    async def test_parse_json_with_markdown_wrapper(self, llm_service, valid_workout_json):
        """Test parsing JSON wrapped in markdown code blocks"""
        # Create response with markdown wrapper
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()

        # LLM sometimes returns JSON wrapped in markdown
        mock_message.content = f"```json\n{json.dumps(valid_workout_json)}\n```"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        result = await llm_service.parse_workout("Test transcription")

        assert isinstance(result, dict)
        assert result == valid_workout_json

    @pytest.mark.asyncio
    async def test_parse_minimal_valid_response(self, llm_service):
        """Test parsing minimal valid response (empty exercises)"""
        minimal_json = {
            "body_weight_kg": None,
            "energy_level": None,
            "start_time": None,
            "end_time": None,
            "resistance_exercises": [],
            "aerobic_exercises": [],
            "notes": None,
        }

        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps(minimal_json)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        result = await llm_service.parse_workout("Não fiz nada hoje")

        assert result == minimal_json
        assert result["resistance_exercises"] == []
        assert result["aerobic_exercises"] == []

    @pytest.mark.asyncio
    async def test_empty_choices_list(self, llm_service):
        """Test handling of empty choices list in response"""
        mock_response = Mock()
        mock_response.choices = []  # Empty choices

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "Resposta vazia do LLM" in error.message

    @pytest.mark.asyncio
    async def test_none_choices(self, llm_service):
        """Test handling of None choices in response"""
        mock_response = Mock()
        mock_response.choices = None  # None instead of list

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE

    @pytest.mark.asyncio
    async def test_empty_message_content(self, llm_service):
        """Test handling of empty message content"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = ""  # Empty content
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "Conteúdo vazio" in error.message

    @pytest.mark.asyncio
    async def test_none_message_content(self, llm_service):
        """Test handling of None message content"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = None  # None content
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE


# =============================================================================
# INVALID JSON RESPONSE TESTS
# =============================================================================


class TestParseWorkoutInvalidJSON:
    """Test handling of invalid JSON responses"""

    @pytest.mark.asyncio
    async def test_invalid_json_syntax(self, llm_service):
        """Test handling of malformed JSON"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = '{"invalid": json syntax}'  # Invalid JSON
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "não é JSON válido" in error.message
        assert "forma mais clara" in error.user_message

    @pytest.mark.asyncio
    async def test_json_array_instead_of_object(self, llm_service):
        """Test handling of JSON array instead of expected object"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        # LLM returns array instead of object
        mock_message.content = json.dumps([{"exercise": "supino"}])
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "objeto JSON" in error.message
        assert "list" in error.details

    @pytest.mark.asyncio
    async def test_json_string_instead_of_object(self, llm_service):
        """Test handling of JSON string instead of object"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        # LLM returns string instead of object
        mock_message.content = json.dumps("just a string")
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "str" in error.details

    @pytest.mark.asyncio
    async def test_plain_text_response(self, llm_service):
        """Test handling of plain text response (not JSON at all)"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "This is just plain text, not JSON"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "não é JSON válido" in error.message


# =============================================================================
# ERROR HANDLING TESTS (RATE LIMITS, TIMEOUTS, AUTH)
# =============================================================================


class TestParseWorkoutErrorHandling:
    """Test error handling for various failure scenarios"""

    @pytest.mark.asyncio
    async def test_rate_limit_error_with_429_status(self, llm_service):
        """Test handling of rate limit error with HTTP 429 status"""
        # Create exception with status_code attribute
        error = Exception("Rate limit exceeded")
        error.status_code = 429

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED
        assert "Limite de taxa" in error.message
        assert error.context.to_dict().get("retry_after") == 30
        assert "alguns segundos" in error.user_message

    @pytest.mark.asyncio
    async def test_rate_limit_error_with_rate_limit_in_message(self, llm_service):
        """Test handling of rate limit error by message content"""
        error = Exception("rate_limit exceeded by user")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED

    @pytest.mark.asyncio
    async def test_rate_limit_error_with_too_many_requests(self, llm_service):
        """Test handling of 'too many requests' error"""
        error = Exception("Too many requests, please slow down")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED

    @pytest.mark.asyncio
    async def test_authentication_error_with_401_status(self, llm_service):
        """Test handling of authentication error with HTTP 401"""
        error = Exception("Unauthorized")
        error.status_code = 401

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.GROQ_API_ERROR
        assert "Chave API Groq inválida" in error.message
        assert "administrador" in error.user_message

    @pytest.mark.asyncio
    async def test_authentication_error_invalid_key_message(self, llm_service):
        """Test handling of invalid API key error by message"""
        error = Exception("Invalid API key provided")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.GROQ_API_ERROR

    @pytest.mark.asyncio
    async def test_timeout_error_with_timeout_message(self, llm_service):
        """Test handling of timeout error"""
        error = Exception("Request timed out")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_TIMEOUT
        assert "Timeout" in error.message
        assert "demorou muito" in error.user_message

    @pytest.mark.asyncio
    async def test_timeout_error_with_504_status(self, llm_service):
        """Test handling of timeout with HTTP 504 status"""
        error = Exception("Gateway timeout")
        error.status_code = 504

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_TIMEOUT

    @pytest.mark.asyncio
    async def test_generic_error(self, llm_service):
        """Test handling of generic unexpected error"""
        error = Exception("Some unexpected error occurred")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_PARSING_FAILED
        assert "Erro inesperado" in error.message
        assert "Some unexpected error occurred" in error.details

    @pytest.mark.asyncio
    async def test_network_error(self, llm_service):
        """Test handling of network connectivity error"""
        error = Exception("Network connection failed")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test transcription")

        # Generic errors fall through to LLMParsingError
        error = exc_info.value
        assert error.error_code == ErrorCode.LLM_PARSING_FAILED


# =============================================================================
# PROMPT BUILDING TESTS
# =============================================================================


class TestPromptBuilding:
    """Test the _build_prompt method"""

    def test_build_prompt_structure(self, llm_service):
        """Test that prompt includes transcription and instructions"""
        transcription = "Fiz 3 séries de supino com 60kg"
        prompt = llm_service._build_prompt(transcription)

        # Verify transcription is in prompt
        assert transcription in prompt

        # Verify key instructions are present
        assert "assistente especializado em fitness brasileiro" in prompt
        assert "weights_kg" in prompt  # Array format instruction
        assert "resistance_exercises" in prompt
        assert "aerobic_exercises" in prompt
        assert "APENAS o JSON" in prompt  # JSON-only output instruction

    def test_build_prompt_with_special_characters(self, llm_service):
        """Test prompt building with special characters in transcription"""
        transcription = 'Fiz supino: 3x12 @ 60kg! "Muito pesado"'
        prompt = llm_service._build_prompt(transcription)

        # Should handle special characters correctly
        assert transcription in prompt

    def test_build_prompt_with_line_breaks(self, llm_service):
        """Test prompt building with line breaks"""
        transcription = "Treino:\nSupino 3x12\nLeg press 4x15"
        prompt = llm_service._build_prompt(transcription)

        assert transcription in prompt


# =============================================================================
# INTEGRATION-STYLE TESTS (LLM PARAMETERS)
# =============================================================================


class TestLLMAPIParameters:
    """Test that correct parameters are sent to LLM API"""

    @pytest.mark.asyncio
    async def test_api_call_parameters(self, llm_service, mock_groq_response, monkeypatch):
        """Test that LLM API is called with correct parameters"""
        # Set specific values for testing
        monkeypatch.setattr(settings, "LLM_TEMPERATURE", 0.2)
        monkeypatch.setattr(settings, "LLM_MAX_TOKENS", 5000)
        monkeypatch.setattr(settings, "LLM_MODEL", "test-model-v1")

        llm_service.model = "test-model-v1"
        llm_service.client.chat.completions.create.return_value = mock_groq_response

        transcription = "Test workout"
        await llm_service.parse_workout(transcription)

        # Verify API was called with correct parameters
        call_args = llm_service.client.chat.completions.create.call_args
        assert call_args is not None

        kwargs = call_args.kwargs
        assert kwargs["model"] == "test-model-v1"
        assert kwargs["temperature"] == 0.2
        assert kwargs["max_completion_tokens"] == 5000

        # Verify message structure
        messages = kwargs["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "Test workout" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_api_called_once_per_parse(self, llm_service, mock_groq_response):
        """Test that API is called exactly once per parse_workout call"""
        llm_service.client.chat.completions.create.return_value = mock_groq_response

        await llm_service.parse_workout("First workout")
        assert llm_service.client.chat.completions.create.call_count == 1

        await llm_service.parse_workout("Second workout")
        assert llm_service.client.chat.completions.create.call_count == 2


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_very_large_valid_json_response(self, llm_service):
        """Test handling of very large but valid JSON response"""
        # Create a response with many exercises
        large_json = {
            "body_weight_kg": 80,
            "energy_level": 7,
            "start_time": "08:00",
            "end_time": "10:00",
            "resistance_exercises": [
                {
                    "name": f"exercise_{i}",
                    "sets": 3,
                    "reps": [10, 10, 10],
                    "weights_kg": [50, 50, 50],
                    "rest_seconds": 60,
                    "perceived_difficulty": 7,
                    "notes": None,
                }
                for i in range(50)  # 50 exercises
            ],
            "aerobic_exercises": [],
            "notes": None,
        }

        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps(large_json)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        result = await llm_service.parse_workout("Long workout session")

        assert len(result["resistance_exercises"]) == 50

    @pytest.mark.asyncio
    async def test_unicode_characters_in_response(self, llm_service):
        """Test handling of unicode characters in LLM response"""
        unicode_json = {
            "body_weight_kg": None,
            "energy_level": None,
            "start_time": None,
            "end_time": None,
            "resistance_exercises": [
                {
                    "name": "supino com barra olímpica",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "weights_kg": [60, 70, 80],
                    "rest_seconds": None,
                    "perceived_difficulty": None,
                    "notes": "Foi ótimo! 💪",
                }
            ],
            "aerobic_exercises": [],
            "notes": "Treino excelente 🏋️",
        }

        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps(unicode_json, ensure_ascii=False)
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        result = await llm_service.parse_workout("Workout with unicode")

        assert "olímpica" in result["resistance_exercises"][0]["name"]
        assert "💪" in result["resistance_exercises"][0]["notes"]

    @pytest.mark.asyncio
    async def test_json_with_extra_whitespace(self, llm_service, valid_workout_json):
        """Test handling of JSON with excessive whitespace"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()

        # JSON with lots of whitespace
        json_str = json.dumps(valid_workout_json, indent=4)
        whitespace_json = f"\n\n   {json_str}   \n\n"

        mock_message.content = whitespace_json
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        result = await llm_service.parse_workout("Test")

        # Should strip whitespace and parse correctly
        assert result == valid_workout_json

    @pytest.mark.asyncio
    async def test_concurrent_parse_calls(self, llm_service, mock_groq_response):
        """Test that service handles concurrent parse calls correctly"""
        import asyncio

        llm_service.client.chat.completions.create.return_value = mock_groq_response

        # Make multiple concurrent calls
        tasks = [
            llm_service.parse_workout(f"Workout {i}")
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        assert all(isinstance(r, dict) for r in results)

        # API should be called 5 times
        assert llm_service.client.chat.completions.create.call_count == 5

    @pytest.mark.asyncio
    async def test_response_truncation_in_error_log(self, llm_service):
        """Test that long responses are truncated in error messages"""
        # Create a very long invalid response
        long_invalid_response = "Not JSON: " + ("x" * 10000)

        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = long_invalid_response
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        error = exc_info.value
        # Response should be stored but truncated in context
        assert hasattr(error, "context")
        # The full response is in the error.response attribute
        # Context should have truncated preview
        context_dict = error.context.to_dict()
        if "response_preview" in context_dict:
            assert len(context_dict["response_preview"]) <= 203  # 200 + "..."


# =============================================================================
# EXCEPTION RE-RAISING TESTS
# =============================================================================


class TestExceptionReRaising:
    """Test that custom exceptions are re-raised correctly"""

    @pytest.mark.asyncio
    async def test_validation_error_is_reraised(self, llm_service):
        """Test that ValidationError is re-raised without wrapping"""
        # Empty transcription raises ValidationError
        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout("")

        # Should be the original ValidationError, not wrapped
        assert isinstance(exc_info.value, ValidationError)
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.asyncio
    async def test_llm_parsing_error_from_invalid_json_is_raised(self, llm_service):
        """Test that LLMParsingError from invalid JSON is raised correctly"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "invalid json"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        # Should be LLMParsingError
        assert isinstance(exc_info.value, LLMParsingError)
        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE
