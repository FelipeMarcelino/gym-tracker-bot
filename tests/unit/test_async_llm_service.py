"""Unit tests for LLMParsingService focusing on real functionality"""

import json
import pytest
from unittest.mock import AsyncMock, Mock, patch

from config.settings import settings
from services.async_llm_service import LLMParsingService
from services.exceptions import (
    ErrorCode,
    LLMParsingError,
    ServiceUnavailableError,
    ValidationError,
)


class TestLLMParsingServiceInitialization:
    """Test LLMParsingService initialization behavior"""

    def test_successful_initialization(self):
        """Test service initializes correctly with valid API key"""
        with patch.object(settings, 'GROQ_API_KEY', 'valid-api-key'):
            service = LLMParsingService()
            assert service.model == settings.LLM_MODEL
            assert service.client is not None

    def test_initialization_fails_without_api_key(self):
        """Test initialization raises error when API key is missing"""
        with patch.object(settings, 'GROQ_API_KEY', None):
            with pytest.raises(ServiceUnavailableError) as exc_info:
                LLMParsingService()
            
            assert "GROQ_API_KEY não configurada" in str(exc_info.value)
            assert exc_info.value.error_code == ErrorCode.GROQ_API_ERROR

    def test_initialization_fails_with_empty_api_key(self):
        """Test initialization raises error when API key is empty string"""
        with patch.object(settings, 'GROQ_API_KEY', ''):
            with pytest.raises(ServiceUnavailableError):
                LLMParsingService()


class TestLLMParsingServiceInputValidation:
    """Test input validation logic"""

    @pytest.fixture
    def service(self):
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            return LLMParsingService()

    @pytest.mark.asyncio
    async def test_rejects_empty_transcription(self, service):
        """Test validation rejects empty transcription"""
        with pytest.raises(ValidationError) as exc_info:
            await service.parse_workout("")
        
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert "Transcrição vazia ou inválida" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rejects_whitespace_only_transcription(self, service):
        """Test validation rejects whitespace-only input"""
        with pytest.raises(ValidationError):
            await service.parse_workout("   \n\t   ")

    @pytest.mark.asyncio
    async def test_rejects_none_transcription(self, service):
        """Test validation rejects None input"""
        with pytest.raises(ValidationError):
            await service.parse_workout(None)

    @pytest.mark.asyncio
    async def test_rejects_oversized_transcription(self, service):
        """Test validation rejects transcriptions exceeding max length"""
        oversized_text = "a" * (settings.MAX_TRANSCRIPTION_LENGTH + 1)
        
        with pytest.raises(ValidationError) as exc_info:
            await service.parse_workout(oversized_text)
        
        assert exc_info.value.error_code == ErrorCode.VALUE_OUT_OF_RANGE
        assert "muito longa" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_accepts_valid_transcription_length(self, service):
        """Test validation accepts transcription at maximum allowed length"""
        max_length_text = "a" * settings.MAX_TRANSCRIPTION_LENGTH
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = '{"test": "valid"}'
            mock_create.return_value = mock_response
            
            result = await service.parse_workout(max_length_text)
            assert result == {"test": "valid"}


class TestLLMParsingServiceWorkoutParsing:
    """Test actual workout parsing functionality"""

    @pytest.fixture
    def service(self):
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            return LLMParsingService()

    @pytest.mark.asyncio
    async def test_parses_simple_workout_successfully(self, service):
        """Test successful parsing of a simple workout description"""
        transcription = "Fiz 3 séries de supino com 60kg"
        expected_workout = {
            "resistance_exercises": [{
                "name": "supino reto com barra",
                "sets": 3,
                "reps": [12, 12, 12],
                "weights_kg": [60, 60, 60]
            }]
        }
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps(expected_workout)
            mock_create.return_value = mock_response
            
            result = await service.parse_workout(transcription)
            
            assert result == expected_workout
            # Verify the API was called with correct parameters
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs['model'] == settings.LLM_MODEL
            assert call_kwargs['temperature'] == settings.LLM_TEMPERATURE
            assert call_kwargs['max_completion_tokens'] == settings.LLM_MAX_TOKENS

    @pytest.mark.asyncio
    async def test_handles_json_response_with_markdown_blocks(self, service):
        """Test parsing when LLM returns JSON wrapped in markdown code blocks"""
        transcription = "Treino básico"
        workout_data = {"exercises": [{"name": "teste", "sets": 1}]}
        markdown_wrapped = f"```json\n{json.dumps(workout_data)}\n```"
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = markdown_wrapped
            mock_create.return_value = mock_response
            
            result = await service.parse_workout(transcription)
            assert result == workout_data

    @pytest.mark.asyncio
    async def test_raises_error_for_invalid_json_response(self, service):
        """Test error handling when LLM returns invalid JSON"""
        transcription = "Treino básico"
        invalid_json = "This is not valid JSON at all"
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = invalid_json
            mock_create.return_value = mock_response
            
            with pytest.raises(LLMParsingError) as exc_info:
                await service.parse_workout(transcription)
            
            assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE
            assert "não é JSON válido" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_raises_error_for_non_dict_json_response(self, service):
        """Test error handling when LLM returns JSON that's not a dictionary"""
        transcription = "Treino básico"
        list_json = json.dumps(["this", "is", "a", "list"])
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = list_json
            mock_create.return_value = mock_response
            
            with pytest.raises(LLMParsingError) as exc_info:
                await service.parse_workout(transcription)
            
            assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE
            assert "deve ser um objeto JSON" in str(exc_info.value)


class TestLLMParsingServiceErrorHandling:
    """Test error handling for various API failure scenarios"""

    @pytest.fixture
    def service(self):
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            return LLMParsingService()

    @pytest.mark.asyncio
    async def test_handles_empty_api_response(self, service):
        """Test handling when API returns empty response"""
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = []
            mock_create.return_value = mock_response
            
            with pytest.raises(LLMParsingError) as exc_info:
                await service.parse_workout("test workout")
            
            assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE
            assert "Resposta vazia do LLM" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self, service):
        """Test handling of rate limit errors from API"""
        rate_limit_error = Exception("rate_limit exceeded")
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = rate_limit_error
            
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.parse_workout("test workout")
            
            assert exc_info.value.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED
            assert "Limite de taxa" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handles_authentication_error(self, service):
        """Test handling of authentication errors from API"""
        auth_error = Exception("unauthorized access")
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = auth_error
            
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.parse_workout("test workout")
            
            assert exc_info.value.error_code == ErrorCode.GROQ_API_ERROR
            assert "Chave API Groq inválida" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handles_timeout_error(self, service):
        """Test handling of timeout errors from API"""
        timeout_error = Exception("connection timed out")
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = timeout_error
            
            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.parse_workout("test workout")
            
            assert exc_info.value.error_code == ErrorCode.LLM_TIMEOUT
            assert "Timeout na conexão" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handles_generic_unexpected_error(self, service):
        """Test handling of unexpected generic errors"""
        unexpected_error = Exception("Something completely unexpected happened")
        
        with patch.object(service.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = unexpected_error
            
            with pytest.raises(LLMParsingError) as exc_info:
                await service.parse_workout("test workout")
            
            assert exc_info.value.error_code == ErrorCode.LLM_PARSING_FAILED
            assert "Erro inesperado no parsing" in str(exc_info.value)


class TestLLMParsingServicePromptBuilding:
    """Test prompt construction functionality"""

    @pytest.fixture
    def service(self):
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            return LLMParsingService()

    def test_prompt_includes_user_transcription(self, service):
        """Test that the built prompt includes the user's transcription"""
        user_input = "Fiz supino reto 3 séries de 12 com 80kg, estava bem pesado"
        prompt = service._build_prompt(user_input)
        
        assert user_input in prompt
        assert "Você é um assistente especializado em fitness brasileiro" in prompt

    def test_prompt_contains_exercise_naming_guidelines(self, service):
        """Test that prompt includes comprehensive exercise naming guidelines"""
        prompt = service._build_prompt("treino teste")
        
        # Should include equipment specifications
        assert "com barra" in prompt
        assert "com halteres" in prompt
        assert "na máquina" in prompt
        assert "peso corporal" in prompt
        
        # Should include specific exercise variations
        assert "supino reto" in prompt
        assert "supino inclinado" in prompt
        assert "rosca direta" in prompt
        assert "agachamento livre" in prompt

    def test_prompt_contains_weight_handling_instructions(self, service):
        """Test that prompt includes proper weight array handling instructions"""
        prompt = service._build_prompt("treino teste")
        
        assert "weights_kg" in prompt
        assert "array" in prompt
        assert "mesmo tamanho que o número de séries" in prompt

    def test_prompt_contains_difficulty_guidelines(self, service):
        """Test that prompt includes RPE (difficulty) guidelines"""
        prompt = service._build_prompt("treino teste")
        
        assert "perceived_difficulty" in prompt
        assert "RPE" in prompt
        assert "1-10" in prompt
        assert "fácil" in prompt
        assert "pesado" in prompt
        assert "difícil" in prompt

    def test_prompt_contains_rest_time_instructions(self, service):
        """Test that prompt includes rest time conversion instructions"""
        prompt = service._build_prompt("treino teste")
        
        assert "rest_seconds" in prompt
        assert "minuto" in prompt
        assert "segundos" in prompt

    def test_prompt_contains_json_structure_requirements(self, service):
        """Test that prompt specifies required JSON structure"""
        prompt = service._build_prompt("treino teste")
        
        assert "resistance_exercises" in prompt
        assert "aerobic_exercises" in prompt
        assert "body_weight_kg" in prompt
        assert "energy_level" in prompt

    def test_prompt_includes_aerobic_exercise_guidelines(self, service):
        """Test that prompt includes aerobic exercise parsing guidelines"""
        prompt = service._build_prompt("treino teste")
        
        assert "aerobic_exercises" in prompt
        assert "duration_minutes" in prompt
        assert "intensity_level" in prompt
        assert "calories_burned" in prompt
        assert "average_heart_rate" in prompt

    def test_prompt_enforces_portuguese_language(self, service):
        """Test that prompt enforces Portuguese language usage"""
        prompt = service._build_prompt("treino teste")
        
        assert "português brasileiro" in prompt
        assert "minúsculas" in prompt

    def test_prompt_includes_practical_examples(self, service):
        """Test that prompt includes concrete parsing examples"""
        prompt = service._build_prompt("treino teste")
        
        # Should include practical examples of correct parsing
        assert "Exemplo" in prompt or "exemplo" in prompt
        assert "Entrada:" in prompt or "entrada:" in prompt
        assert "Saída:" in prompt or "saída:" in prompt or "resultado:" in prompt