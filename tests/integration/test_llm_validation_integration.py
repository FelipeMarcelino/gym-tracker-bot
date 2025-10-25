"""Integration tests for LLM service with workout validation"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from types import SimpleNamespace

from services.async_llm_service import LLMParsingService
from services.exceptions import ValidationError, ErrorCode
from config.settings import settings


class TestLLMValidationIntegration:
    """Test LLM service with integrated workout validation"""

    @pytest.fixture
    async def mock_groq_response_complete(self):
        """Mock a complete workout response from Groq"""
        # Create a mock response object with proper structure
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
        {
            "body_weight_kg": 75.5,
            "energy_level": 8,
            "resistance_exercises": [
                {
                    "name": "supino reto com barra",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "weights_kg": [60, 70, 80],
                    "rest_seconds": 90,
                    "perceived_difficulty": 7
                }
            ],
            "aerobic_exercises": []
        }
        '''
        return response

    @pytest.fixture
    async def mock_groq_response_missing_weights(self):
        """Mock response missing weights"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
        {
            "resistance_exercises": [
                {
                    "name": "supino reto com barra",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "rest_seconds": 90
                }
            ]
        }
        '''
        return response

    @pytest.fixture
    async def mock_groq_response_missing_reps(self):
        """Mock response missing reps"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
        {
            "resistance_exercises": [
                {
                    "name": "agachamento livre",
                    "sets": 4,
                    "weights_kg": [100, 110, 120, 130]
                }
            ]
        }
        '''
        return response

    @pytest.mark.asyncio
    async def test_llm_with_complete_data_passes_validation(self, mock_groq_response_complete):
        """Test that complete workout data passes validation"""
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_groq_response_complete
            service.client = mock_client
            
            # Should not raise any exception
            result = await service.parse_workout("Fiz supino 3x12,10,8 com 60,70,80kg")
            
            assert "resistance_exercises" in result
            assert len(result["resistance_exercises"]) == 1
            assert result["resistance_exercises"][0]["name"] == "supino reto com barra"

    @pytest.mark.asyncio
    async def test_llm_with_missing_weights_raises_validation_error(self, mock_groq_response_missing_weights):
        """Test that missing weights triggers validation error"""
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_groq_response_missing_weights
            service.client = mock_client
            
            # Should raise ValidationError with user-friendly message
            with pytest.raises(ValidationError) as exc_info:
                await service.parse_workout("Fiz supino 3x12,10,8")
            
            error = exc_info.value
            assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD
            assert "supino reto com barra" in error.user_message
            assert "pesos" in error.user_message.lower()
            assert "Por favor" in error.user_message

    @pytest.mark.asyncio
    async def test_llm_with_missing_reps_raises_validation_error(self, mock_groq_response_missing_reps):
        """Test that missing reps triggers validation error"""
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_groq_response_missing_reps
            service.client = mock_client
            
            # Should raise ValidationError with user-friendly message
            with pytest.raises(ValidationError) as exc_info:
                await service.parse_workout("Fiz agachamento com 100,110,120,130kg")
            
            error = exc_info.value
            assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD
            assert "agachamento livre" in error.user_message
            assert "repetições" in error.user_message.lower()
            assert "Por favor" in error.user_message

    @pytest.mark.asyncio
    async def test_llm_with_multiple_exercises_some_invalid(self):
        """Test validation with multiple exercises where some are invalid"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
                    {
                        "resistance_exercises": [
                            {
                                "name": "supino reto",
                                "sets": 3,
                                "reps": [12, 10, 8],
                                "weights_kg": [60, 70, 80]
                            },
                            {
                                "name": "desenvolvimento",
                                "sets": 3,
                                "weights_kg": [40, 40, 40]
                            },
                            {
                                "name": "triceps polia",
                                "sets": 3,
                                "reps": [15, 12, 10]
                            }
                        ]
                    }
                    '''
        
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = response
            service.client = mock_client
            
            # Should raise ValidationError listing all problems
            with pytest.raises(ValidationError) as exc_info:
                await service.parse_workout("Treino de push completo")
            
            error = exc_info.value
            # Check that both exercises with problems are mentioned
            assert "desenvolvimento" in error.user_message
            assert "triceps polia" in error.user_message
            # Check that the error message has the proper sections
            assert "Faltam as repetições" in error.user_message
            assert "Faltam os pesos" in error.user_message

    @pytest.mark.asyncio
    async def test_llm_infers_sets_from_reps(self):
        """Test that LLM + validation correctly infers sets from reps"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
                    {
                        "resistance_exercises": [
                            {
                                "name": "leg press",
                                "reps": [20, 15, 12, 10],
                                "weights_kg": [200, 250, 300, 350]
                            }
                        ]
                    }
                    '''
        
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = response
            service.client = mock_client
            
            # Should not raise exception and should have sets=4
            result = await service.parse_workout("Leg press 20,15,12,10 com 200,250,300,350kg")
            
            assert result["resistance_exercises"][0]["sets"] == 4

    @pytest.mark.asyncio
    async def test_llm_aerobic_exercises_skip_validation(self):
        """Test that aerobic exercises don't require reps/weights validation"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
                    {
                        "resistance_exercises": [],
                        "aerobic_exercises": [
                            {
                                "name": "corrida na esteira",
                                "duration_minutes": 30,
                                "distance_km": 5.0,
                                "intensity_level": "moderate"
                            }
                        ]
                    }
                    '''
        
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = response
            service.client = mock_client
            
            # Should not raise any exception
            result = await service.parse_workout("Corri 30 minutos na esteira, 5km")
            
            assert len(result["aerobic_exercises"]) == 1
            assert result["aerobic_exercises"][0]["duration_minutes"] == 30