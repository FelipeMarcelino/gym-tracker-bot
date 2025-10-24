"""
Unit tests for LLMParsingService - Testing Business Logic Only

This test file focuses on testing the actual business logic and validation rules
in our LLM service, NOT testing that mocks return what we set them to return.

What we DO test (valuable):
1. OUR input validation rules (empty, too long, etc.)
2. OUR error detection and classification logic
3. OUR data transformation (markdown stripping, JSON parsing)
4. OUR exception handling and re-raising
5. OUR prompt building logic

What we DON'T test (circular/no value):
- That mocks return the data we configured them to return
- That external APIs work correctly
- Simple data pass-through with no transformation
"""

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

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
    mock.chat = AsyncMock()
    mock.chat.completions = AsyncMock()
    mock.chat.completions.create = AsyncMock()
    return mock


@pytest.fixture
def llm_service(mock_groq_client, monkeypatch):
    """Create LLMParsingService with mocked Groq client"""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-api-key-123")

    with patch("services.async_llm_service.AsyncGroq") as mock_async_groq:
        mock_async_groq.return_value = mock_groq_client
        service = LLMParsingService()
        service.client = mock_groq_client
        return service


@pytest.fixture
def valid_workout_json() -> Dict[str, Any]:
    """Valid workout JSON response for testing data transformation"""
    return {
        "body_weight_kg": 75.5,
        "energy_level": 8,
        "resistance_exercises": [
            {
                "name": "supino reto com barra",
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [60, 70, 80],
                "rest_seconds": 90,
                "perceived_difficulty": 7,
                "notes": None,
            }
        ],
        "aerobic_exercises": [],
        "notes": None,
    }


# =============================================================================
# INITIALIZATION TESTS - Testing OUR validation logic
# =============================================================================


class TestLLMServiceInitialization:
    """Test initialization and configuration validation"""

    def test_init_without_api_key(self, monkeypatch):
        """Test that we validate GROQ_API_KEY is configured"""
        monkeypatch.setattr(settings, "GROQ_API_KEY", None)

        with pytest.raises(ServiceUnavailableError) as exc_info:
            LLMParsingService()

        assert "GROQ_API_KEY não configurada" in str(exc_info.value)

    def test_init_groq_client_failure(self, monkeypatch):
        """Test that we handle Groq client creation failures"""
        monkeypatch.setattr(settings, "GROQ_API_KEY", "test-api-key")

        with patch("services.async_llm_service.AsyncGroq") as mock_async_groq:
            mock_async_groq.side_effect = Exception("Connection failed")

            with pytest.raises(ServiceUnavailableError) as exc_info:
                LLMParsingService()

            assert "Falha ao inicializar cliente Groq LLM" in str(exc_info.value)


# =============================================================================
# INPUT VALIDATION TESTS - Testing OUR validation rules
# =============================================================================


class TestInputValidation:
    """Test our input validation business rules"""

    @pytest.mark.asyncio
    async def test_empty_transcription_rejected(self, llm_service):
        """Test that we reject empty transcriptions"""
        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout("")

        error = exc_info.value
        assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert "Transcrição vazia ou inválida" in error.message

    @pytest.mark.asyncio
    async def test_whitespace_only_transcription_rejected(self, llm_service):
        """Test that we reject whitespace-only input"""
        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout("   \n\t  ")

        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.asyncio
    async def test_transcription_length_limit_enforced(self, llm_service, monkeypatch):
        """Test that we enforce MAX_TRANSCRIPTION_LENGTH limit"""
        monkeypatch.setattr(settings, "MAX_TRANSCRIPTION_LENGTH", 100)

        long_transcription = "a" * 101  # Exceeds limit by 1

        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout(long_transcription)

        error = exc_info.value
        assert error.error_code == ErrorCode.VALUE_OUT_OF_RANGE
        assert "muito longa" in error.message.lower()
        assert "100" in error.message  # Verify limit is mentioned

    @pytest.mark.asyncio
    async def test_transcription_at_max_length_accepted(self, llm_service, monkeypatch):
        """Test boundary: exactly at max length should be accepted"""
        monkeypatch.setattr(settings, "MAX_TRANSCRIPTION_LENGTH", 100)

        transcription = "a" * 100  # Exactly at limit

        # Create minimal valid response
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps({"resistance_exercises": []})
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        llm_service.client.chat.completions.create.return_value = mock_response

        # Should not raise ValidationError
        result = await llm_service.parse_workout(transcription)
        assert isinstance(result, dict)


# =============================================================================
# DATA TRANSFORMATION TESTS - Testing OUR parsing logic
# =============================================================================


class TestDataTransformation:
    """Test our data transformation and parsing logic"""

    @pytest.mark.asyncio
    async def test_markdown_wrapper_stripped(self, llm_service, valid_workout_json):
        """Test that we strip markdown code blocks from LLM response"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()

        # LLM often wraps JSON in markdown - we should strip it
        mock_message.content = f"```json\n{json.dumps(valid_workout_json)}\n```"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        result = await llm_service.parse_workout("Test transcription")

        # Verify we successfully stripped markdown and parsed JSON
        assert isinstance(result, dict)
        assert result == valid_workout_json

    @pytest.mark.asyncio
    async def test_whitespace_stripped_from_response(self, llm_service, valid_workout_json):
        """Test that we strip whitespace from LLM responses"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()

        # Response with excessive whitespace
        json_str = json.dumps(valid_workout_json)
        mock_message.content = f"\n\n   {json_str}   \n\n"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        result = await llm_service.parse_workout("Test")

        # Verify we stripped whitespace and parsed correctly
        assert result == valid_workout_json


# =============================================================================
# ERROR DETECTION TESTS - Testing OUR error classification logic
# =============================================================================


class TestErrorDetectionAndClassification:
    """Test that we correctly detect and classify different error types"""

    @pytest.mark.asyncio
    async def test_detect_empty_choices_as_invalid_response(self, llm_service):
        """Test that we detect empty choices array as invalid response"""
        mock_response = Mock()
        mock_response.choices = []  # Empty

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE

    @pytest.mark.asyncio
    async def test_detect_none_choices_as_invalid_response(self, llm_service):
        """Test that we detect None choices as invalid response"""
        mock_response = Mock()
        mock_response.choices = None

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE

    @pytest.mark.asyncio
    async def test_detect_empty_content_as_invalid_response(self, llm_service):
        """Test that we detect empty message content"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = ""
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE

    @pytest.mark.asyncio
    async def test_detect_none_content_as_invalid_response(self, llm_service):
        """Test that we detect None message content"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = None
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE

    @pytest.mark.asyncio
    async def test_detect_rate_limit_by_status_code_429(self, llm_service):
        """Test that we detect rate limits by HTTP 429 status code"""
        error = Exception("Rate limit exceeded")
        error.status_code = 429

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED

    @pytest.mark.asyncio
    async def test_detect_rate_limit_by_message_content(self, llm_service):
        """Test that we detect rate limits by message content"""
        error = Exception("rate_limit exceeded by user")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED

    @pytest.mark.asyncio
    async def test_detect_rate_limit_by_too_many_requests(self, llm_service):
        """Test that we detect 'too many requests' as rate limit"""
        error = Exception("Too many requests, please slow down")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED

    @pytest.mark.asyncio
    async def test_detect_auth_error_by_status_code_401(self, llm_service):
        """Test that we detect auth errors by HTTP 401 status code"""
        error = Exception("Unauthorized")
        error.status_code = 401

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.GROQ_API_ERROR

    @pytest.mark.asyncio
    async def test_detect_auth_error_by_invalid_key_message(self, llm_service):
        """Test that we detect invalid API key by message content"""
        error = Exception("Invalid API key provided")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.GROQ_API_ERROR

    @pytest.mark.asyncio
    async def test_detect_timeout_by_message_content(self, llm_service):
        """Test that we detect timeout by message content"""
        error = Exception("Request timed out")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_TIMEOUT

    @pytest.mark.asyncio
    async def test_detect_timeout_by_status_code_504(self, llm_service):
        """Test that we detect timeout by HTTP 504 status code"""
        error = Exception("Gateway timeout")
        error.status_code = 504

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(ServiceUnavailableError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_TIMEOUT

    @pytest.mark.asyncio
    async def test_generic_errors_wrapped_in_llm_parsing_error(self, llm_service):
        """Test that unknown errors are wrapped in LLMParsingError"""
        error = Exception("Some unexpected error")

        llm_service.client.chat.completions.create.side_effect = error

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_PARSING_FAILED


# =============================================================================
# JSON VALIDATION TESTS - Testing OUR type checking logic
# =============================================================================


class TestJSONValidation:
    """Test that we validate JSON structure correctly"""

    @pytest.mark.asyncio
    async def test_reject_malformed_json(self, llm_service):
        """Test that we reject syntactically invalid JSON"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = '{"invalid": json syntax}'  # Invalid
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "não é JSON válido" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_reject_json_array_when_object_expected(self, llm_service):
        """Test that we reject JSON arrays when we expect objects"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps([{"exercise": "supino"}])  # Array, not object
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE
        assert "objeto JSON" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_reject_json_string_when_object_expected(self, llm_service):
        """Test that we reject JSON strings when we expect objects"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps("just a string")  # String, not object
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE

    @pytest.mark.asyncio
    async def test_reject_plain_text_response(self, llm_service):
        """Test that we reject non-JSON responses"""
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = "This is just plain text, not JSON"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        llm_service.client.chat.completions.create.return_value = mock_response

        with pytest.raises(LLMParsingError) as exc_info:
            await llm_service.parse_workout("Test")

        assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE


# =============================================================================
# PROMPT BUILDING TESTS - Testing OUR prompt construction logic
# =============================================================================


class TestPromptBuilding:
    """Test our prompt building logic"""

    def test_prompt_contains_transcription(self, llm_service):
        """Test that we include the transcription in the prompt"""
        transcription = "Fiz 3 séries de supino com 60kg"
        prompt = llm_service._build_prompt(transcription)

        assert transcription in prompt

    def test_prompt_contains_key_instructions(self, llm_service):
        """Test that we include critical instructions in prompt"""
        prompt = llm_service._build_prompt("test")

        # Verify key formatting instructions are present
        assert "weights_kg" in prompt  # Array format instruction
        assert "APENAS o JSON" in prompt  # JSON-only output
        assert "assistente especializado em fitness brasileiro" in prompt

    def test_prompt_handles_special_characters(self, llm_service):
        """Test that we handle special characters in transcription"""
        transcription = 'Supino: 3x12 @ 60kg! "Pesado"'
        prompt = llm_service._build_prompt(transcription)

        # Should not crash and should include the transcription
        assert transcription in prompt


# =============================================================================
# EXCEPTION HANDLING TESTS - Testing OUR exception re-raising logic
# =============================================================================


class TestExceptionHandling:
    """Test that we correctly re-raise custom exceptions"""

    @pytest.mark.asyncio
    async def test_validation_error_reraised_without_wrapping(self, llm_service):
        """Test that ValidationError is re-raised, not wrapped"""
        # Empty transcription triggers ValidationError
        with pytest.raises(ValidationError) as exc_info:
            await llm_service.parse_workout("")

        # Should be the original ValidationError, not wrapped
        assert isinstance(exc_info.value, ValidationError)
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.asyncio
    async def test_concurrent_parse_calls_handled(self, llm_service):
        """Test that we handle concurrent async calls correctly"""
        import asyncio

        # Mock response
        mock_response = Mock()
        mock_choice = Mock()
        mock_message = Mock()
        mock_message.content = json.dumps({"resistance_exercises": []})
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        llm_service.client.chat.completions.create.return_value = mock_response

        # Make 5 concurrent calls
        tasks = [llm_service.parse_workout(f"Workout {i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        assert all(isinstance(r, dict) for r in results)
