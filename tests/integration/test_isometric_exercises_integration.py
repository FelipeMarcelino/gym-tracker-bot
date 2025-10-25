"""Integration tests for isometric exercises (like plank)"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from services.async_llm_service import LLMParsingService
from services.exceptions import ErrorCode
from config.settings import settings


class TestIsometricExercisesIntegration:
    """Test isometric exercises work end-to-end through the LLM service"""

    @pytest.fixture
    async def mock_groq_response_isometric(self):
        """Mock response with isometric exercises"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
        {
            "body_weight_kg": 70,
            "energy_level": 7,
            "resistance_exercises": [
                {
                    "name": "prancha abdominal",
                    "sets": 3,
                    "reps": [60, 45, 30],
                    "weights_kg": [0, 0, 0],
                    "rest_seconds": 30,
                    "perceived_difficulty": 8
                },
                {
                    "name": "prancha lateral",
                    "sets": 2,
                    "reps": [30, 30],
                    "weights_kg": [0, 0],
                    "rest_seconds": 30,
                    "perceived_difficulty": 9
                }
            ],
            "aerobic_exercises": []
        }
        '''
        return response

    @pytest.fixture
    async def mock_groq_response_mixed_exercises(self):
        """Mock response with both isometric and regular exercises"""
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
                    "weights_kg": [60, 70, 80]
                },
                {
                    "name": "prancha abdominal",
                    "sets": 3,
                    "reps": [60, 50, 40],
                    "weights_kg": [0, 0, 0]
                },
                {
                    "name": "desenvolvimento com halteres",
                    "sets": 3,
                    "reps": [10, 10, 10],
                    "weights_kg": [20, 20, 20]
                }
            ]
        }
        '''
        return response

    @pytest.fixture
    async def mock_groq_response_isometric_missing_weights(self):
        """Mock response with isometric exercise but missing weights array"""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = '''
        {
            "resistance_exercises": [
                {
                    "name": "prancha abdominal",
                    "sets": 4,
                    "reps": [60, 50, 45, 40],
                    "rest_seconds": 30
                }
            ]
        }
        '''
        return response

    @pytest.mark.asyncio
    async def test_llm_parses_isometric_exercises_correctly(self, mock_groq_response_isometric):
        """Test that LLM correctly parses isometric exercises with zero weights"""
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_groq_response_isometric
            service.client = mock_client
            
            # Should not raise any exception
            result = await service.parse_workout("Fiz prancha abdominal 3 séries de 60, 45 e 30 segundos, depois prancha lateral 2x30 segundos")
            
            assert "resistance_exercises" in result
            assert len(result["resistance_exercises"]) == 2
            
            # Check prancha abdominal
            plank = result["resistance_exercises"][0]
            assert plank["name"] == "prancha abdominal"
            assert plank["reps"] == [60, 45, 30]
            assert plank["weights_kg"] == [0, 0, 0]
            
            # Check prancha lateral
            side_plank = result["resistance_exercises"][1]
            assert side_plank["name"] == "prancha lateral"
            assert side_plank["reps"] == [30, 30]
            assert side_plank["weights_kg"] == [0, 0]

    @pytest.mark.asyncio
    async def test_llm_mixed_isometric_and_regular_exercises(self, mock_groq_response_mixed_exercises):
        """Test that both isometric and regular exercises are validated correctly"""
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_groq_response_mixed_exercises
            service.client = mock_client
            
            # Should not raise any exception
            result = await service.parse_workout("Treino completo com supino, prancha e desenvolvimento")
            
            assert len(result["resistance_exercises"]) == 3
            
            # Regular exercise should have weights
            supino = result["resistance_exercises"][0]
            assert supino["name"] == "supino reto com barra"
            assert supino["weights_kg"] == [60, 70, 80]
            
            # Isometric exercise should have zero weights
            plank = result["resistance_exercises"][1]
            assert plank["name"] == "prancha abdominal"
            assert plank["weights_kg"] == [0, 0, 0]
            
            # Another regular exercise
            desenvolvimento = result["resistance_exercises"][2]
            assert desenvolvimento["name"] == "desenvolvimento com halteres"
            assert desenvolvimento["weights_kg"] == [20, 20, 20]

    @pytest.mark.asyncio
    async def test_llm_isometric_auto_fills_zero_weights(self, mock_groq_response_isometric_missing_weights):
        """Test that validation auto-fills zero weights for isometric exercises"""
        with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
            service = LLMParsingService()
            
            # Mock the Groq client
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_groq_response_isometric_missing_weights
            service.client = mock_client
            
            # Should not raise exception - validation should auto-fill zeros
            result = await service.parse_workout("Fiz prancha 4 séries")
            
            plank = result["resistance_exercises"][0]
            assert plank["name"] == "prancha abdominal"
            assert plank["weights_kg"] == [0, 0, 0, 0]  # Auto-filled with zeros

    @pytest.mark.asyncio
    async def test_llm_recognizes_various_isometric_exercises(self):
        """Test that LLM recognizes different isometric exercise names"""
        isometric_variations = [
            ("prancha", "prancha abdominal"),
            ("ponte", "ponte"),
            ("isometria de agachamento", "isometria de agachamento"),
            ("wall sit", "wall sit"),
            ("prancha frontal", "prancha frontal"),
            ("prancha lateral direita", "prancha lateral")
        ]
        
        for input_name, expected_name in isometric_variations:
            response = Mock()
            response.choices = [Mock()]
            response.choices[0].message = Mock()
            response.choices[0].message.content = f'''
            {{
                "resistance_exercises": [
                    {{
                        "name": "{expected_name}",
                        "sets": 3,
                        "reps": [45, 40, 35],
                        "weights_kg": [0, 0, 0]
                    }}
                ]
            }}
            '''
            
            with patch.object(settings, 'GROQ_API_KEY', 'test-key'):
                service = LLMParsingService()
                
                # Mock the Groq client
                mock_client = AsyncMock()
                mock_client.chat.completions.create.return_value = response
                service.client = mock_client
                
                # Should not raise any exception
                result = await service.parse_workout(f"Fiz {input_name} 3 séries")
                
                exercise = result["resistance_exercises"][0]
                assert expected_name in exercise["name"].lower()
                assert exercise["weights_kg"] == [0, 0, 0]