"""Unit tests for workout data validation"""

import pytest

from services.workout_validation import (
    ValidationError,
    validate_exercise_data,
    infer_sets_from_reps,
    format_validation_error_message
)


class TestWorkoutValidation:
    """Test cases for workout validation functions"""

    def test_validate_complete_exercise_data(self):
        """Test validation passes with complete data"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [12, 10, 8],
            "weights_kg": [60, 70, 80]
        }
        
        # Should not raise any exception
        result = validate_exercise_data(exercise_data)
        assert result is True

    def test_validate_missing_reps(self):
        """Test validation fails when reps are missing"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "weights_kg": [60, 70, 80]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        assert "repetições" in str(exc_info.value).lower()

    def test_validate_empty_reps(self):
        """Test validation fails when reps array is empty"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [],
            "weights_kg": [60, 70, 80]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        assert "repetições" in str(exc_info.value).lower()

    def test_validate_missing_weights(self):
        """Test validation fails when weights are missing"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [12, 10, 8]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        assert "pesos" in str(exc_info.value).lower() or "kg" in str(exc_info.value).lower()

    def test_validate_empty_weights(self):
        """Test validation fails when weights array is empty"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [12, 10, 8],
            "weights_kg": []
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        assert "pesos" in str(exc_info.value).lower() or "kg" in str(exc_info.value).lower()

    def test_validate_mismatched_reps_weights_count(self):
        """Test validation fails when reps and weights count don't match"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [12, 10, 8],
            "weights_kg": [60, 70]  # Missing one weight
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        error_msg = str(exc_info.value).lower()
        assert "número" in error_msg or "quantidade" in error_msg

    def test_validate_aerobic_exercise_skips_validation(self):
        """Test that aerobic exercises don't require reps/weights validation"""
        exercise_data = {
            "name": "corrida na esteira",
            "duration_minutes": 30,
            "distance_km": 5.0
        }
        
        # Should not raise any exception
        result = validate_exercise_data(exercise_data, exercise_type="aerobic")
        assert result is True

    def test_infer_sets_from_reps(self):
        """Test inferring number of sets from reps array"""
        # Test with array of reps
        assert infer_sets_from_reps([12, 10, 8]) == 3
        assert infer_sets_from_reps([15, 15, 15, 15]) == 4
        assert infer_sets_from_reps([10]) == 1
        
        # Test with empty array
        assert infer_sets_from_reps([]) == 0
        
        # Test with None
        assert infer_sets_from_reps(None) == 0

    def test_validate_with_missing_sets_but_valid_reps(self):
        """Test validation infers sets from reps when sets is missing"""
        exercise_data = {
            "name": "supino reto com barra",
            "reps": [12, 10, 8],
            "weights_kg": [60, 70, 80]
        }
        
        # Should not raise exception and should infer sets=3
        result = validate_exercise_data(exercise_data)
        assert result is True
        assert exercise_data["sets"] == 3

    def test_validate_with_sets_mismatch_reps_count(self):
        """Test validation corrects sets when it doesn't match reps count"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 5,  # Wrong value
            "reps": [12, 10, 8],
            "weights_kg": [60, 70, 80]
        }
        
        # Should correct sets to 3
        result = validate_exercise_data(exercise_data)
        assert result is True
        assert exercise_data["sets"] == 3

    def test_format_validation_error_message(self):
        """Test formatting of validation error messages"""
        # Test missing reps message
        msg = format_validation_error_message("missing_reps", "Supino")
        assert "Supino" in msg
        assert "repetições" in msg.lower()
        
        # Test missing weights message
        msg = format_validation_error_message("missing_weights", "Agachamento")
        assert "Agachamento" in msg
        assert "peso" in msg.lower() or "kg" in msg.lower()
        
        # Test mismatched count message
        msg = format_validation_error_message("mismatched_count", "Rosca", reps_count=3, weights_count=2)
        assert "Rosca" in msg
        assert "3" in msg
        assert "2" in msg

    def test_validate_zero_weights(self):
        """Test validation handles zero weights appropriately"""
        exercise_data = {
            "name": "flexão de braço",
            "sets": 3,
            "reps": [15, 12, 10],
            "weights_kg": [0, 0, 0]  # Body weight exercise
        }
        
        # Should pass validation (zero is valid for bodyweight exercises)
        result = validate_exercise_data(exercise_data)
        assert result is True

    def test_validate_partial_data_multiple_exercises(self):
        """Test validation of multiple exercises with some having incomplete data"""
        exercises = [
            {
                "name": "supino reto",
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [60, 70, 80]
            },
            {
                "name": "supino inclinado",
                "sets": 3,
                "reps": [10, 8, 6]
                # Missing weights
            },
            {
                "name": "crucifixo",
                "sets": 3,
                # Missing reps
                "weights_kg": [15, 15, 15]
            }
        ]
        
        errors = []
        for exercise in exercises:
            try:
                validate_exercise_data(exercise)
            except ValidationError as e:
                errors.append((exercise["name"], str(e)))
        
        assert len(errors) == 2
        assert any("supino inclinado" in error[0] for error in errors)
        assert any("crucifixo" in error[0] for error in errors)

    def test_validate_with_null_values(self):
        """Test validation handles null/None values"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": None,
            "reps": None,
            "weights_kg": None
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        assert "repetições" in str(exc_info.value).lower()

    def test_validate_negative_values(self):
        """Test validation rejects negative values"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [12, -10, 8],  # Negative rep
            "weights_kg": [60, 70, 80]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        assert "negativ" in str(exc_info.value).lower() or "inválid" in str(exc_info.value).lower()

    def test_validate_non_numeric_values(self):
        """Test validation rejects non-numeric values"""
        exercise_data = {
            "name": "supino reto com barra",
            "sets": 3,
            "reps": [12, "dez", 8],  # String instead of number
            "weights_kg": [60, 70, 80]
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validate_exercise_data(exercise_data)
        
        assert "número" in str(exc_info.value).lower() or "numérico" in str(exc_info.value).lower()