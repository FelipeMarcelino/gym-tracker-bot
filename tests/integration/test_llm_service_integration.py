"""Integration tests for LLMParsingService with real-world scenarios"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from config.settings import settings
from services.async_llm_service import LLMParsingService
from services.exceptions import ErrorCode, LLMParsingError, ServiceUnavailableError


class TestLLMParsingServiceRealWorldScenarios:
    """Test LLM service with realistic workout descriptions"""

    @pytest.fixture
    def service(self):
        with patch.object(settings, "GROQ_API_KEY", "integration-test-key"):
            return LLMParsingService()

    def _mock_llm_response(self, mock_create, response_data):
        """Helper to mock LLM API response"""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(response_data)
        mock_create.return_value = mock_response

    @pytest.mark.asyncio
    async def test_complete_resistance_workout_parsing(self, service):
        """Test parsing a complete resistance training session"""
        transcription = """
        Hoje fiz um treino de peito e tríceps. Comecei com supino reto na barra livre,
        fiz 4 séries: primeira de 12 com 60kg, segunda de 10 com 70kg, terceira de 8 com 80kg
        e quarta de 6 com 85kg. Descansava 2 minutos entre as séries e estava bem pesado.
        Depois fiz supino inclinado com halteres, 3 séries de 10 com 30kg cada braço,
        descanso de 90 segundos, tranquilo. Finalizei com tríceps na polia alta com corda,
        3 séries de 15 repetições, estava leve.
        """

        expected_response = {
            "body_weight_kg": None,
            "energy_level": None,
            "start_time": None,
            "end_time": None,
            "resistance_exercises": [
                {
                    "name": "supino reto com barra",
                    "sets": 4,
                    "reps": [12, 10, 8, 6],
                    "weights_kg": [60, 70, 80, 85],
                    "rest_seconds": 120,
                    "perceived_difficulty": 8,
                    "notes": None,
                },
                {
                    "name": "supino inclinado com halteres",
                    "sets": 3,
                    "reps": [10, 10, 10],
                    "weights_kg": [30, 30, 30],
                    "rest_seconds": 90,
                    "perceived_difficulty": 5,
                    "notes": None,
                },
                {
                    "name": "tríceps na polia com corda",
                    "sets": 3,
                    "reps": [15, 15, 15],
                    "weights_kg": [20, 25, 30],
                    "rest_seconds": None,
                    "perceived_difficulty": 3,
                    "notes": None,
                },
            ],
            "aerobic_exercises": [],
            "notes": None,
        }

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            self._mock_llm_response(mock_create, expected_response)

            result = await service.parse_workout(transcription)

            # Verify structure is correct
            assert "resistance_exercises" in result
            assert "aerobic_exercises" in result
            assert len(result["resistance_exercises"]) == 3

            # Verify first exercise details
            first_exercise = result["resistance_exercises"][0]
            assert first_exercise["name"] == "supino reto com barra"
            assert first_exercise["sets"] == 4
            assert first_exercise["reps"] == [12, 10, 8, 6]
            assert first_exercise["weights_kg"] == [60, 70, 80, 85]
            assert first_exercise["rest_seconds"] == 120
            assert first_exercise["perceived_difficulty"] == 8

    @pytest.mark.asyncio
    async def test_mixed_cardio_and_resistance_workout(self, service):
        """Test parsing a workout with both cardio and resistance exercises"""
        transcription = """
        Comecei com 20 minutos de corrida na esteira, ritmo moderado,
        queimei aproximadamente 200 calorias. Depois fiz agachamento livre
        com barra, 4 séries de 12 repetições com 100kg, estava bem puxado.
        Terminei com mais 10 minutos de caminhada na esteira para relaxar.
        """

        expected_response = {
            "resistance_exercises": [
                {
                    "name": "agachamento livre com barra",
                    "sets": 4,
                    "reps": [12, 12, 12, 12],
                    "weights_kg": [100, 100, 100, 100],
                    "rest_seconds": None,
                    "perceived_difficulty": 8,
                    "notes": None,
                },
            ],
            "aerobic_exercises": [
                {
                    "name": "corrida na esteira",
                    "duration_minutes": 20,
                    "distance_km": None,
                    "average_heart_rate": None,
                    "calories_burned": 200,
                    "intensity_level": "moderate",
                    "notes": None,
                },
                {
                    "name": "caminhada na esteira",
                    "duration_minutes": 10,
                    "distance_km": None,
                    "average_heart_rate": None,
                    "calories_burned": None,
                    "intensity_level": "low",
                    "notes": None,
                },
            ],
            "body_weight_kg": None,
            "energy_level": None,
            "notes": None,
        }

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            self._mock_llm_response(mock_create, expected_response)

            result = await service.parse_workout(transcription)

            # Verify both exercise types are present
            assert len(result["resistance_exercises"]) == 1
            assert len(result["aerobic_exercises"]) == 2

            # Verify resistance exercise
            resistance_ex = result["resistance_exercises"][0]
            assert resistance_ex["name"] == "agachamento livre com barra"
            assert resistance_ex["weights_kg"] == [100, 100, 100, 100]

            # Verify aerobic exercises
            cardio_1 = result["aerobic_exercises"][0]
            assert cardio_1["name"] == "corrida na esteira"
            assert cardio_1["duration_minutes"] == 20
            assert cardio_1["calories_burned"] == 200

            cardio_2 = result["aerobic_exercises"][1]
            assert cardio_2["name"] == "caminhada na esteira"
            assert cardio_2["duration_minutes"] == 10

    @pytest.mark.asyncio
    async def test_workout_with_dropsets_and_progressive_weight(self, service):
        """Test parsing complex workout with dropsets and progressive loading"""
        transcription = """
        Fiz leg press hoje. Primeira série com 200kg para 15 repetições,
        segunda série dropset: comecei com 220kg para 10 reps, tirei peso e
        fiz mais 10 com 180kg, e terminei com 140kg para mais 10.
        Terceira série normal: 200kg para 12 repetições.
        Descansava 3 minutos entre as séries principais.
        """

        expected_response = {
            "resistance_exercises": [
                {
                    "name": "leg press 45 graus",
                    "sets": 3,
                    "reps": [15, 30, 12],  # Second set is dropset with total 30 reps
                    "weights_kg": [200, 180, 200],  # Average weight for dropset
                    "rest_seconds": 180,
                    "perceived_difficulty": 7,
                    "notes": "Segunda série foi dropset: 220kg x10, 180kg x10, 140kg x10",
                },
            ],
            "aerobic_exercises": [],
            "body_weight_kg": None,
            "energy_level": None,
            "notes": None,
        }

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            self._mock_llm_response(mock_create, expected_response)

            result = await service.parse_workout(transcription)

            # Verify complex exercise parsing
            exercise = result["resistance_exercises"][0]
            assert exercise["name"] == "leg press 45 graus"
            assert exercise["sets"] == 3
            assert exercise["rest_seconds"] == 180

    @pytest.mark.asyncio
    async def test_workout_with_bodyweight_and_machine_exercises(self, service):
        """Test parsing workout with bodyweight and machine exercises"""
        transcription = """
        Treino funcional hoje. Comecei com flexões de braço peso corporal,
        4 séries de 20, 18, 15, 12 repetições, estava ficando difícil.
        Depois fui para a máquina de desenvolvimento, 3 séries de 12 com 40kg.
        Terminei com prancha abdominal, 3 séries de 60 segundos cada.
        """

        expected_response = {
            "resistance_exercises": [
                {
                    "name": "flexão de braço peso corporal",
                    "sets": 4,
                    "reps": [20, 18, 15, 12],
                    "weights_kg": [0, 0, 0, 0],
                    "rest_seconds": None,
                    "perceived_difficulty": 7,
                    "notes": None,
                },
                {
                    "name": "desenvolvimento na máquina",
                    "sets": 3,
                    "reps": [12, 12, 12],
                    "weights_kg": [40, 40, 40],
                    "rest_seconds": None,
                    "perceived_difficulty": None,
                    "notes": None,
                },
                {
                    "name": "prancha abdominal",
                    "sets": 3,
                    "reps": [1, 1, 1],  # Duration exercises represented as single rep
                    "weights_kg": [0, 0, 0],
                    "rest_seconds": None,
                    "perceived_difficulty": None,
                    "notes": "60 segundos por série",
                },
            ],
            "aerobic_exercises": [],
            "body_weight_kg": None,
            "energy_level": None,
            "notes": None,
        }

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            self._mock_llm_response(mock_create, expected_response)

            result = await service.parse_workout(transcription)

            # Verify bodyweight exercise
            pushups = result["resistance_exercises"][0]
            assert pushups["name"] == "flexão de braço peso corporal"
            assert pushups["weights_kg"] == [0, 0, 0, 0]

            # Verify machine exercise
            shoulder_press = result["resistance_exercises"][1]
            assert shoulder_press["name"] == "desenvolvimento na máquina"
            assert shoulder_press["weights_kg"] == [40, 40, 40]


class TestLLMParsingServiceErrorRecovery:
    """Test error recovery and resilience in integration scenarios"""

    @pytest.fixture
    def service(self):
        with patch.object(settings, "GROQ_API_KEY", "integration-test-key"):
            return LLMParsingService()

    @pytest.mark.asyncio
    async def test_handles_malformed_llm_response_gracefully(self, service):
        """Test service handles malformed API responses gracefully"""
        transcription = "Fiz supino reto 3x12 com 60kg"
        malformed_json = '{"resistance_exercises": [{"name": "supino", "sets": 3,}]}'  # Extra comma

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = malformed_json
            mock_create.return_value = mock_response

            with pytest.raises(LLMParsingError) as exc_info:
                await service.parse_workout(transcription)

            assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE
            # Should provide user-friendly error message
            assert "sistema de IA retornou uma resposta inválida" in exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_handles_partial_api_failures(self, service):
        """Test handling when API returns partial or incomplete responses"""
        transcription = "Treino completo de hoje"

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = None  # Incomplete response
            mock_create.return_value = mock_response

            with pytest.raises(LLMParsingError) as exc_info:
                await service.parse_workout(transcription)

            assert exc_info.value.error_code == ErrorCode.LLM_INVALID_RESPONSE

    @pytest.mark.asyncio
    async def test_maintains_user_context_in_error_messages(self, service):
        """Test that error messages maintain context relevant to users"""
        transcription = "Descrição de treino muito específica"

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            # Simulate API timeout
            mock_create.side_effect = Exception("timeout occurred")

            with pytest.raises(ServiceUnavailableError) as exc_info:
                await service.parse_workout(transcription)

            # Error message should be in Portuguese and user-friendly
            assert "sistema de ia" in exc_info.value.user_message.lower()
            assert exc_info.value.error_code == ErrorCode.LLM_TIMEOUT


class TestLLMParsingServiceSystemIntegration:
    """Test integration with other system components"""

    @pytest.fixture
    def service(self):
        with patch.object(settings, "GROQ_API_KEY", "integration-test-key"):
            return LLMParsingService()

    @pytest.mark.asyncio
    async def test_respects_system_configuration_settings(self, service):
        """Test service respects global configuration settings"""
        transcription = "Treino básico"

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = '{"test": "response"}'
            mock_create.return_value = mock_response

            await service.parse_workout(transcription)

            # Verify API call uses system settings
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["model"] == settings.LLM_MODEL
            assert call_kwargs["temperature"] == settings.LLM_TEMPERATURE
            assert call_kwargs["max_completion_tokens"] == settings.LLM_MAX_TOKENS

    @pytest.mark.asyncio
    async def test_handles_different_input_encodings(self, service):
        """Test service handles different text encodings properly"""
        # Test with special Portuguese characters and emojis
        transcription = "Fiz agachamento búlgaro com halteres 💪. Estava difícil demais!"

        expected_response = {
            "resistance_exercises": [{
                "name": "agachamento búlgaro com halteres",
                "sets": 3,
                "reps": [12, 12, 12],
                "weights_kg": [20, 20, 20],
                "perceived_difficulty": 8,
            }],
            "aerobic_exercises": [],
        }

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps(expected_response, ensure_ascii=False)
            mock_create.return_value = mock_response

            result = await service.parse_workout(transcription)

            # Should handle special characters correctly
            exercise = result["resistance_exercises"][0]
            assert "búlgaro" in exercise["name"]

    @pytest.mark.asyncio
    async def test_prompt_construction_integrates_user_input_correctly(self, service):
        """Test that user input is properly integrated into the prompt"""
        user_transcription = "Fiz deadlift com 140kg, 5 séries de 5, estava muito pesado"

        with patch.object(service.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = '{"test": "response"}'
            mock_create.return_value = mock_response

            await service.parse_workout(user_transcription)

            # Verify the transcription was included in the prompt
            call_args = mock_create.call_args[1]
            messages = call_args["messages"]
            assert len(messages) == 1
            assert messages[0]["role"] == "user"
            assert user_transcription in messages[0]["content"]

