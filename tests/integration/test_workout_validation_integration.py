"""Integration tests for workout validation with LLM parsing"""

import pytest

from services.workout_validation import (
    ValidationError,
    validate_workout_data,
    get_user_friendly_error_message
)


class TestWorkoutValidationIntegration:
    """Integration tests for workout validation in the complete flow"""

    def test_validate_complete_workout_data(self):
        """Test validation of complete workout data from LLM"""
        workout_data = {
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
                },
                {
                    "name": "supino inclinado com halteres",
                    "sets": 3,
                    "reps": [10, 8, 6],
                    "weights_kg": [30, 35, 40],
                    "rest_seconds": 90,
                    "perceived_difficulty": 8
                }
            ],
            "aerobic_exercises": [
                {
                    "name": "corrida na esteira",
                    "duration_minutes": 10,
                    "distance_km": 1.5,
                    "intensity_level": "moderate"
                }
            ]
        }
        
        # Should pass validation
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is True
        assert result["errors"] == []

    def test_validate_workout_with_missing_data(self):
        """Test validation catches exercises with missing data"""
        workout_data = {
            "resistance_exercises": [
                {
                    "name": "supino reto com barra",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "weights_kg": [60, 70, 80]
                },
                {
                    "name": "desenvolvimento",
                    "sets": 3,
                    # Missing reps
                    "weights_kg": [40, 40, 40]
                },
                {
                    "name": "triceps na polia",
                    "sets": 3,
                    "reps": [15, 12, 10]
                    # Missing weights
                }
            ]
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is False
        assert len(result["errors"]) == 2
        
        # Check error messages
        error_exercises = [error["exercise"] for error in result["errors"]]
        assert "desenvolvimento" in error_exercises
        assert "triceps na polia" in error_exercises

    def test_validate_workout_infers_missing_sets(self):
        """Test validation infers sets from reps when missing"""
        workout_data = {
            "resistance_exercises": [
                {
                    "name": "agachamento livre",
                    # Missing sets - should be inferred from reps
                    "reps": [15, 12, 10, 8],
                    "weights_kg": [100, 110, 120, 130]
                }
            ]
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is True
        assert workout_data["resistance_exercises"][0]["sets"] == 4

    def test_get_user_friendly_error_message(self):
        """Test user-friendly error message generation"""
        errors = [
            {
                "exercise": "Supino reto",
                "error_type": "missing_reps",
                "message": "Faltam as repetições"
            },
            {
                "exercise": "Agachamento",
                "error_type": "missing_weights",
                "message": "Faltam os pesos"
            }
        ]
        
        message = get_user_friendly_error_message(errors)
        
        # Check message contains key information
        assert "Supino reto" in message
        assert "Agachamento" in message
        assert "repetições" in message.lower()
        assert "peso" in message.lower()
        
        # Check it's formatted for user
        assert "Por favor" in message or "favor" in message.lower()
        assert "novamente" in message or "corrija" in message.lower()

    def test_validate_mixed_exercise_types(self):
        """Test validation with both resistance and aerobic exercises"""
        workout_data = {
            "resistance_exercises": [
                {
                    "name": "supino reto",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    # Missing weights
                },
                {
                    "name": "leg press",
                    "sets": 4,
                    "reps": [20, 15, 12, 10],
                    "weights_kg": [200, 250, 300, 350]
                }
            ],
            "aerobic_exercises": [
                {
                    "name": "corrida",
                    "duration_minutes": 20,
                    "distance_km": 3.5
                },
                {
                    "name": "bicicleta",
                    "duration_minutes": 15
                    # Distance is optional for bike
                }
            ]
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["exercise"] == "supino reto"

    def test_validate_corrects_mismatched_sets(self):
        """Test validation corrects sets count when it doesn't match reps/weights"""
        workout_data = {
            "resistance_exercises": [
                {
                    "name": "rosca direta",
                    "sets": 10,  # Wrong value
                    "reps": [12, 10, 8],
                    "weights_kg": [20, 25, 30]
                }
            ]
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is True
        assert workout_data["resistance_exercises"][0]["sets"] == 3

    def test_empty_workout_data(self):
        """Test validation of empty workout data"""
        workout_data = {
            "resistance_exercises": [],
            "aerobic_exercises": []
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is True
        assert result["errors"] == []

    def test_validate_text_description_scenarios(self):
        """Test validation for common text description scenarios"""
        # Scenario 1: User forgot to mention weights
        workout_data = {
            "resistance_exercises": [{
                "name": "supino com barra",
                "sets": 3,
                "reps": [12, 10, 8]
                # User said "3x12,10,8" but didn't mention weight
            }]
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is False
        error_msg = get_user_friendly_error_message(result["errors"])
        assert "supino com barra" in error_msg.lower()
        assert "peso" in error_msg.lower() or "kg" in error_msg.lower()

    def test_validate_progressive_overload_pattern(self):
        """Test validation handles progressive overload patterns"""
        workout_data = {
            "resistance_exercises": [
                {
                    "name": "agachamento",
                    "sets": 5,
                    "reps": [5, 5, 5, 5, 5],
                    "weights_kg": [100, 110, 120, 130, 140]  # Progressive overload
                }
            ]
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is True

    def test_validate_dropset_pattern(self):
        """Test validation handles dropset patterns"""
        workout_data = {
            "resistance_exercises": [
                {
                    "name": "leg press",
                    "sets": 3,
                    "reps": [12, 15, 20],  # Increasing reps
                    "weights_kg": [200, 150, 100]  # Decreasing weight (dropset)
                }
            ]
        }
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is True

    def test_real_world_incomplete_descriptions(self):
        """Test validation for real-world incomplete exercise descriptions"""
        test_cases = [
            # "Fiz supino 3x10" - missing weight
            {
                "resistance_exercises": [{
                    "name": "supino",
                    "sets": 3,
                    "reps": [10, 10, 10]
                }]
            },
            # "Agachamento com 100kg" - missing reps
            {
                "resistance_exercises": [{
                    "name": "agachamento",
                    "weights_kg": [100]
                }]
            },
            # "Rosca 3 séries" - missing both reps and weights
            {
                "resistance_exercises": [{
                    "name": "rosca",
                    "sets": 3
                }]
            }
        ]
        
        for workout_data in test_cases:
            result = validate_workout_data(workout_data)
            assert result["is_valid"] is False
            assert len(result["errors"]) > 0

    def test_batch_validation_performance(self):
        """Test validation performance with many exercises"""
        # Create workout with 20 exercises
        exercises = []
        for i in range(10):
            # Valid exercises
            exercises.append({
                "name": f"exercicio_{i}",
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [50, 60, 70]
            })
        
        for i in range(10, 20):
            # Invalid exercises (missing data)
            exercises.append({
                "name": f"exercicio_{i}",
                "sets": 3,
                "reps": [12, 10, 8]
                # Missing weights
            })
        
        workout_data = {"resistance_exercises": exercises}
        
        result = validate_workout_data(workout_data)
        assert result["is_valid"] is False
        assert len(result["errors"]) == 10

    @pytest.mark.parametrize("exercise_data,expected_valid", [
        # Valid cases
        ({"name": "test", "sets": 3, "reps": [10, 10, 10], "weights_kg": [50, 50, 50]}, True),
        ({"name": "test", "reps": [12, 10, 8], "weights_kg": [60, 70, 80]}, True),  # Infer sets
        
        # Invalid cases
        ({"name": "test", "sets": 3, "weights_kg": [50, 50, 50]}, False),  # Missing reps
        ({"name": "test", "sets": 3, "reps": [10, 10, 10]}, False),  # Missing weights
        ({"name": "test", "sets": 3, "reps": [], "weights_kg": []}, False),  # Empty arrays
    ])
    def test_validate_parametrized_cases(self, exercise_data, expected_valid):
        """Test validation with parametrized test cases"""
        workout_data = {"resistance_exercises": [exercise_data]}
        result = validate_workout_data(workout_data)
        assert result["is_valid"] == expected_valid