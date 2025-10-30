"""Unit tests for workout models"""

import pytest
from pydantic import ValidationError

from src.models.workout_models import (
    ResistanceExercise,
    AerobicExercise, 
    WorkoutData,
    LLMParseResult,
    ExerciseSummary,
    WorkoutValidationError
)


class TestResistanceExercise:
    """Test cases for ResistanceExercise model"""

    def test_valid_resistance_exercise_creation(self):
        """Test creating a valid resistance exercise"""
        # Arrange & Act
        exercise = ResistanceExercise(
            name="Bench Press",
            sets=3,
            reps=[10, 8, 6],
            weights_kg=[80.0, 85.0, 90.0],
            rest_seconds=120,
            perceived_difficulty=7,
            notes="Good form maintained"
        )
        
        # Assert
        assert exercise.name == "Bench Press"
        assert exercise.sets == 3
        assert exercise.reps == [10, 8, 6]
        assert exercise.weights_kg == [80.0, 85.0, 90.0]
        assert exercise.rest_seconds == 120
        assert exercise.perceived_difficulty == 7
        assert exercise.notes == "Good form maintained"

    def test_valid_resistance_exercise_minimal_fields(self):
        """Test creating a resistance exercise with only required fields"""
        # Arrange & Act
        exercise = ResistanceExercise(
            name="Squat",
            sets=2,
            reps=[12, 10],
            weights_kg=[100.0, 105.0]
        )
        
        # Assert
        assert exercise.name == "Squat"
        assert exercise.sets == 2
        assert exercise.reps == [12, 10]
        assert exercise.weights_kg == [100.0, 105.0]
        assert exercise.rest_seconds is None
        assert exercise.perceived_difficulty is None
        assert exercise.notes is None

    def test_exercise_name_validation(self):
        """Test exercise name validation constraints"""
        # Test empty name
        with pytest.raises(ValidationError, match="at least 1 character"):
            ResistanceExercise(
                name="",
                sets=1,
                reps=[10],
                weights_kg=[50.0]
            )
        
        # Test name too long
        long_name = "a" * 101  # 101 characters
        with pytest.raises(ValidationError, match="at most 100 characters"):
            ResistanceExercise(
                name=long_name,
                sets=1,
                reps=[10],
                weights_kg=[50.0]
            )

    def test_sets_validation(self):
        """Test sets count validation"""
        # Test zero sets
        with pytest.raises(ValidationError, match="greater than 0"):
            ResistanceExercise(
                name="Push-up",
                sets=0,
                reps=[10],
                weights_kg=[0.0]
            )
        
        # Test too many sets
        with pytest.raises(ValidationError, match="less than or equal to 20"):
            ResistanceExercise(
                name="Push-up",
                sets=21,
                reps=[10] * 21,
                weights_kg=[0.0] * 21
            )

    def test_reps_validation(self):
        """Test reps validation"""
        # Test negative reps
        with pytest.raises(ValidationError, match="All rep values must be positive"):
            ResistanceExercise(
                name="Pull-up",
                sets=2,
                reps=[10, -5],  # Negative rep
                weights_kg=[0.0, 0.0]
            )
        
        # Test zero reps
        with pytest.raises(ValidationError, match="All rep values must be positive"):
            ResistanceExercise(
                name="Pull-up",
                sets=2,
                reps=[10, 0],  # Zero rep
                weights_kg=[0.0, 0.0]
            )

    def test_weights_validation(self):
        """Test weights validation"""
        # Test negative weights
        with pytest.raises(ValidationError, match="All weight values must be positive"):
            ResistanceExercise(
                name="Deadlift",
                sets=2,
                reps=[8, 6],
                weights_kg=[120.0, -100.0]  # Negative weight
            )
        
        # Test zero weights
        with pytest.raises(ValidationError, match="All weight values must be positive"):
            ResistanceExercise(
                name="Deadlift",
                sets=2,
                reps=[8, 6],
                weights_kg=[120.0, 0.0]  # Zero weight
            )

    def test_arrays_consistency_validation(self):
        """Test that reps and weights arrays match sets count"""
        # Test reps count mismatch
        with pytest.raises(ValidationError, match="Number of rep values .* must match sets count"):
            ResistanceExercise(
                name="Curl",
                sets=3,
                reps=[12, 10],  # Only 2 rep values for 3 sets
                weights_kg=[20.0, 22.5, 25.0]
            )
        
        # Test weights count mismatch
        with pytest.raises(ValidationError, match="Number of weight values .* must match sets count"):
            ResistanceExercise(
                name="Curl",
                sets=3,
                reps=[12, 10, 8],
                weights_kg=[20.0, 22.5]  # Only 2 weight values for 3 sets
            )

    def test_rest_seconds_validation(self):
        """Test rest seconds validation"""
        # Test negative rest time
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ResistanceExercise(
                name="Squat",
                sets=1,
                reps=[10],
                weights_kg=[100.0],
                rest_seconds=-30
            )
        
        # Test excessive rest time (more than 30 minutes)
        with pytest.raises(ValidationError, match="less than or equal to 1800"):
            ResistanceExercise(
                name="Squat",
                sets=1,
                reps=[10],
                weights_kg=[100.0],
                rest_seconds=1801
            )

    def test_perceived_difficulty_validation(self):
        """Test perceived difficulty (RPE) validation"""
        # Test below range
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            ResistanceExercise(
                name="Squat",
                sets=1,
                reps=[10],
                weights_kg=[100.0],
                perceived_difficulty=0
            )
        
        # Test above range
        with pytest.raises(ValidationError, match="less than or equal to 10"):
            ResistanceExercise(
                name="Squat",
                sets=1,
                reps=[10],
                weights_kg=[100.0],
                perceived_difficulty=11
            )

    def test_notes_max_length_validation(self):
        """Test notes maximum length validation"""
        long_notes = "a" * 501  # 501 characters
        with pytest.raises(ValidationError, match="at most 500 characters"):
            ResistanceExercise(
                name="Squat",
                sets=1,
                reps=[10],
                weights_kg=[100.0],
                notes=long_notes
            )

    def test_edge_case_maximum_values(self):
        """Test exercise creation with maximum allowed values"""
        # Maximum sets with corresponding arrays
        max_reps = [20] * 20  # 20 sets with 20 reps each
        max_weights = [500.0] * 20  # 20 sets with heavy weights
        
        exercise = ResistanceExercise(
            name="a" * 100,  # Maximum name length
            sets=20,  # Maximum sets
            reps=max_reps,
            weights_kg=max_weights,
            rest_seconds=1800,  # Maximum rest (30 minutes)
            perceived_difficulty=10,  # Maximum RPE
            notes="a" * 500  # Maximum notes length
        )
        
        assert exercise.sets == 20
        assert len(exercise.reps) == 20
        assert len(exercise.weights_kg) == 20


class TestAerobicExercise:
    """Test cases for AerobicExercise model"""

    def test_valid_aerobic_exercise_creation(self):
        """Test creating a valid aerobic exercise with all fields"""
        # Arrange & Act
        exercise = AerobicExercise(
            name="Running",
            duration_minutes=30.5,
            distance_km=5.2,
            average_heart_rate=150,
            calories_burned=300,
            intensity_level="moderate",
            notes="Good pace maintained"
        )
        
        # Assert
        assert exercise.name == "Running"
        assert exercise.duration_minutes == 30.5
        assert exercise.distance_km == 5.2
        assert exercise.average_heart_rate == 150
        assert exercise.calories_burned == 300
        assert exercise.intensity_level == "moderate"
        assert exercise.notes == "Good pace maintained"

    def test_valid_aerobic_exercise_minimal_fields(self):
        """Test creating aerobic exercise with only required fields"""
        # Arrange & Act
        exercise = AerobicExercise(
            name="Walking",
            duration_minutes=20.0
        )
        
        # Assert
        assert exercise.name == "Walking"
        assert exercise.duration_minutes == 20.0
        assert exercise.distance_km is None
        assert exercise.average_heart_rate is None
        assert exercise.calories_burned is None
        assert exercise.intensity_level is None
        assert exercise.notes is None

    def test_exercise_name_validation(self):
        """Test aerobic exercise name validation"""
        # Test empty name
        with pytest.raises(ValidationError, match="at least 1 character"):
            AerobicExercise(
                name="",
                duration_minutes=10.0
            )
        
        # Test name too long
        long_name = "a" * 101
        with pytest.raises(ValidationError, match="at most 100 characters"):
            AerobicExercise(
                name=long_name,
                duration_minutes=10.0
            )

    def test_duration_validation(self):
        """Test duration validation"""
        # Test zero duration
        with pytest.raises(ValidationError, match="greater than 0"):
            AerobicExercise(
                name="Swimming",
                duration_minutes=0.0
            )
        
        # Test negative duration
        with pytest.raises(ValidationError, match="greater than 0"):
            AerobicExercise(
                name="Swimming",
                duration_minutes=-10.0
            )
        
        # Test excessive duration (more than 24 hours)
        with pytest.raises(ValidationError, match="less than or equal to 1440"):
            AerobicExercise(
                name="Swimming",
                duration_minutes=1441.0
            )

    def test_distance_validation(self):
        """Test distance validation"""
        # Test negative distance
        with pytest.raises(ValidationError, match="greater than 0"):
            AerobicExercise(
                name="Cycling",
                duration_minutes=60.0,
                distance_km=-5.0
            )
        
        # Test zero distance
        with pytest.raises(ValidationError, match="greater than 0"):
            AerobicExercise(
                name="Cycling",
                duration_minutes=60.0,
                distance_km=0.0
            )

    def test_heart_rate_validation(self):
        """Test average heart rate validation"""
        # Test below minimum
        with pytest.raises(ValidationError, match="greater than or equal to 40"):
            AerobicExercise(
                name="Yoga",
                duration_minutes=30.0,
                average_heart_rate=39
            )
        
        # Test above maximum
        with pytest.raises(ValidationError, match="less than or equal to 220"):
            AerobicExercise(
                name="Sprint",
                duration_minutes=5.0,
                average_heart_rate=221
            )

    def test_calories_validation(self):
        """Test calories burned validation"""
        # Test zero calories
        with pytest.raises(ValidationError, match="greater than 0"):
            AerobicExercise(
                name="Walking",
                duration_minutes=30.0,
                calories_burned=0
            )
        
        # Test negative calories
        with pytest.raises(ValidationError, match="greater than 0"):
            AerobicExercise(
                name="Walking",
                duration_minutes=30.0,
                calories_burned=-100
            )
        
        # Test excessive calories
        with pytest.raises(ValidationError, match="less than or equal to 10000"):
            AerobicExercise(
                name="Marathon",
                duration_minutes=180.0,
                calories_burned=10001
            )

    def test_intensity_level_validation(self):
        """Test intensity level enumeration validation"""
        # Test valid intensity levels
        valid_levels = ["low", "moderate", "high", "hiit"]
        for level in valid_levels:
            exercise = AerobicExercise(
                name="Test",
                duration_minutes=30.0,
                intensity_level=level
            )
            assert exercise.intensity_level == level
        
        # Test invalid intensity level
        with pytest.raises(ValidationError, match="Input should be"):
            AerobicExercise(
                name="Test",
                duration_minutes=30.0,
                intensity_level="extreme"  # Not in allowed values
            )

    def test_notes_max_length_validation(self):
        """Test notes maximum length validation"""
        long_notes = "a" * 501
        with pytest.raises(ValidationError, match="at most 500 characters"):
            AerobicExercise(
                name="Running",
                duration_minutes=30.0,
                notes=long_notes
            )


class TestWorkoutData:
    """Test cases for WorkoutData model"""

    def test_valid_workout_with_resistance_exercises(self):
        """Test creating a valid workout with resistance exercises"""
        # Arrange
        resistance_exercise = ResistanceExercise(
            name="Squat",
            sets=3,
            reps=[10, 8, 6],
            weights_kg=[100.0, 110.0, 120.0]
        )
        
        # Act
        workout = WorkoutData(
            body_weight_kg=75.5,
            energy_level=8,
            start_time="14:30",
            end_time="15:45",
            resistance_exercises=[resistance_exercise],
            notes="Great workout session"
        )
        
        # Assert
        assert workout.body_weight_kg == 75.5
        assert workout.energy_level == 8
        assert workout.start_time == "14:30"
        assert workout.end_time == "15:45"
        assert len(workout.resistance_exercises) == 1
        assert len(workout.aerobic_exercises) == 0
        assert workout.notes == "Great workout session"

    def test_valid_workout_with_aerobic_exercises(self):
        """Test creating a valid workout with aerobic exercises"""
        # Arrange
        aerobic_exercise = AerobicExercise(
            name="Running",
            duration_minutes=30.0,
            distance_km=5.0
        )
        
        # Act
        workout = WorkoutData(
            body_weight_kg=70.0,
            energy_level=7,
            aerobic_exercises=[aerobic_exercise]
        )
        
        # Assert
        assert workout.body_weight_kg == 70.0
        assert workout.energy_level == 7
        assert len(workout.resistance_exercises) == 0
        assert len(workout.aerobic_exercises) == 1

    def test_valid_workout_with_mixed_exercises(self):
        """Test creating a workout with both resistance and aerobic exercises"""
        # Arrange
        resistance_exercise = ResistanceExercise(
            name="Bench Press",
            sets=2,
            reps=[10, 8],
            weights_kg=[80.0, 85.0]
        )
        
        aerobic_exercise = AerobicExercise(
            name="Treadmill",
            duration_minutes=15.0
        )
        
        # Act
        workout = WorkoutData(
            resistance_exercises=[resistance_exercise],
            aerobic_exercises=[aerobic_exercise],
            start_time="09:00",
            end_time="10:30"
        )
        
        # Assert
        assert len(workout.resistance_exercises) == 1
        assert len(workout.aerobic_exercises) == 1

    def test_body_weight_validation(self):
        """Test body weight validation"""
        resistance_exercise = ResistanceExercise(
            name="Push-up",
            sets=1,
            reps=[10],
            weights_kg=[70.0]  # Bodyweight exercise
        )
        
        # Test negative body weight
        with pytest.raises(ValidationError, match="greater than 0"):
            WorkoutData(
                body_weight_kg=-70.0,
                resistance_exercises=[resistance_exercise]
            )
        
        # Test zero body weight
        with pytest.raises(ValidationError, match="greater than 0"):
            WorkoutData(
                body_weight_kg=0.0,
                resistance_exercises=[resistance_exercise]
            )
        
        # Test excessive body weight
        with pytest.raises(ValidationError, match="less than or equal to 500"):
            WorkoutData(
                body_weight_kg=501.0,
                resistance_exercises=[resistance_exercise]
            )

    def test_energy_level_validation(self):
        """Test energy level validation"""
        resistance_exercise = ResistanceExercise(
            name="Push-up",
            sets=1,
            reps=[10],
            weights_kg=[70.0]  # Bodyweight exercise
        )
        
        # Test below range
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            WorkoutData(
                energy_level=0,
                resistance_exercises=[resistance_exercise]
            )
        
        # Test above range
        with pytest.raises(ValidationError, match="less than or equal to 10"):
            WorkoutData(
                energy_level=11,
                resistance_exercises=[resistance_exercise]
            )

    def test_time_format_validation(self):
        """Test time format validation"""
        resistance_exercise = ResistanceExercise(
            name="Push-up",
            sets=1,
            reps=[10],
            weights_kg=[70.0]  # Bodyweight exercise
        )
        
        # Test invalid time format
        with pytest.raises(ValidationError, match="String should match pattern"):
            WorkoutData(
                start_time="2:30",  # Missing leading zero
                resistance_exercises=[resistance_exercise]
            )
        
        # Test invalid time range - hours
        with pytest.raises(ValidationError, match="Time must be in HH:MM format"):
            WorkoutData(
                start_time="25:30",  # Invalid hour
                resistance_exercises=[resistance_exercise]
            )
        
        # Test invalid time range - minutes
        with pytest.raises(ValidationError, match="Time must be in HH:MM format"):
            WorkoutData(
                start_time="14:60",  # Invalid minute
                resistance_exercises=[resistance_exercise]
            )

    def test_workout_content_validation(self):
        """Test that workout must contain at least one exercise"""
        # Test empty workout
        with pytest.raises(ValidationError, match="Workout must contain at least one exercise"):
            WorkoutData(
                body_weight_kg=75.0,
                energy_level=7
            )

    def test_time_sequence_validation(self):
        """Test time sequence validation (start < end)"""
        resistance_exercise = ResistanceExercise(
            name="Push-up",
            sets=1,
            reps=[10],
            weights_kg=[70.0]  # Bodyweight exercise
        )
        
        # Test end time before start time (same day)
        with pytest.raises(ValidationError, match="Workout duration cannot exceed 6 hours"):
            WorkoutData(
                start_time="15:30",
                end_time="14:30",  # End before start
                resistance_exercises=[resistance_exercise]
            )

    def test_workout_duration_validation(self):
        """Test workout duration limits"""
        resistance_exercise = ResistanceExercise(
            name="Push-up",
            sets=1,
            reps=[10],
            weights_kg=[70.0]  # Bodyweight exercise
        )
        
        # Test excessive workout duration
        with pytest.raises(ValidationError, match="Workout duration cannot exceed 6 hours"):
            WorkoutData(
                start_time="08:00",
                end_time="15:00",  # 7 hours duration
                resistance_exercises=[resistance_exercise]
            )

    def test_cross_midnight_workout_handling(self):
        """Test workout that spans midnight"""
        resistance_exercise = ResistanceExercise(
            name="Push-up",
            sets=1,
            reps=[10],
            weights_kg=[70.0]  # Bodyweight exercise
        )
        
        # Valid cross-midnight workout (under 6 hours)
        workout = WorkoutData(
            start_time="23:00",
            end_time="03:00",  # Next day, 4 hours duration
            resistance_exercises=[resistance_exercise]
        )
        
        assert workout.start_time == "23:00"
        assert workout.end_time == "03:00"

    def test_notes_max_length_validation(self):
        """Test workout notes maximum length validation"""
        resistance_exercise = ResistanceExercise(
            name="Push-up",
            sets=1,
            reps=[10],
            weights_kg=[70.0]  # Bodyweight exercise
        )
        
        long_notes = "a" * 1001  # 1001 characters
        with pytest.raises(ValidationError, match="at most 1000 characters"):
            WorkoutData(
                resistance_exercises=[resistance_exercise],
                notes=long_notes
            )


class TestLLMParseResult:
    """Test cases for LLMParseResult model"""

    def test_successful_parse_result(self):
        """Test creating a successful parse result"""
        # Arrange
        workout_data = WorkoutData(
            resistance_exercises=[
                ResistanceExercise(
                    name="Squat",
                    sets=1,
                    reps=[10],
                    weights_kg=[100.0]
                )
            ]
        )
        
        # Act
        result = LLMParseResult(
            success=True,
            workout_data=workout_data,
            raw_text="I did 10 squats with 100kg",
            parsing_notes="Successfully parsed resistance exercise",
            confidence=0.95
        )
        
        # Assert
        assert result.success is True
        assert result.workout_data is not None
        assert result.raw_text == "I did 10 squats with 100kg"
        assert result.parsing_notes == "Successfully parsed resistance exercise"
        assert result.confidence == 0.95
        assert len(result.errors) == 0

    def test_failed_parse_result(self):
        """Test creating a failed parse result"""
        # Act
        result = LLMParseResult(
            success=False,
            raw_text="unintelligible text xyzabc",
            confidence=0.1,
            errors=["Could not identify exercises", "Invalid format"]
        )
        
        # Assert
        assert result.success is False
        assert result.workout_data is None
        assert result.raw_text == "unintelligible text xyzabc"
        assert result.confidence == 0.1
        assert len(result.errors) == 2

    def test_result_consistency_validation_success_without_data(self):
        """Test validation fails when success=True but no workout_data"""
        with pytest.raises(ValidationError, match="Success=True requires workout_data to be present"):
            LLMParseResult(
                success=True,  # Success but no data
                workout_data=None,
                raw_text="test text"
            )

    def test_result_consistency_validation_failure_without_errors(self):
        """Test validation fails when success=False but no errors"""
        with pytest.raises(ValidationError, match="Success=False requires at least one error message"):
            LLMParseResult(
                success=False,  # Failed but no errors
                raw_text="test text",
                errors=[]  # Empty errors list
            )

    def test_confidence_validation(self):
        """Test confidence score validation"""
        workout_data = WorkoutData(
            resistance_exercises=[
                ResistanceExercise(
                    name="Test",
                    sets=1,
                    reps=[1],
                    weights_kg=[1.0]
                )
            ]
        )
        
        # Test below range
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            LLMParseResult(
                success=True,
                workout_data=workout_data,
                raw_text="test",
                confidence=-0.1
            )
        
        # Test above range
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            LLMParseResult(
                success=True,
                workout_data=workout_data,
                raw_text="test",
                confidence=1.1
            )


class TestExerciseSummary:
    """Test cases for ExerciseSummary model"""

    def test_valid_exercise_summary(self):
        """Test creating a valid exercise summary"""
        # Act
        summary = ExerciseSummary(
            total_resistance_exercises=3,
            total_aerobic_exercises=2,
            total_sets=12,
            estimated_duration_minutes=90,
            muscle_groups=["chest", "back", "legs"]
        )
        
        # Assert
        assert summary.total_resistance_exercises == 3
        assert summary.total_aerobic_exercises == 2
        assert summary.total_sets == 12
        assert summary.estimated_duration_minutes == 90
        assert summary.muscle_groups == ["chest", "back", "legs"]

    def test_exercise_summary_with_minimal_fields(self):
        """Test exercise summary with minimal required fields"""
        # Act
        summary = ExerciseSummary(
            total_resistance_exercises=1,
            total_aerobic_exercises=0,
            total_sets=3
        )
        
        # Assert
        assert summary.total_resistance_exercises == 1
        assert summary.total_aerobic_exercises == 0
        assert summary.total_sets == 3
        assert summary.estimated_duration_minutes is None
        assert summary.muscle_groups == []

    def test_negative_values_validation(self):
        """Test that negative values are not allowed"""
        # Test negative resistance exercises
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ExerciseSummary(
                total_resistance_exercises=-1,
                total_aerobic_exercises=0,
                total_sets=0
            )
        
        # Test negative aerobic exercises
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ExerciseSummary(
                total_resistance_exercises=0,
                total_aerobic_exercises=-1,
                total_sets=0
            )
        
        # Test negative sets
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ExerciseSummary(
                total_resistance_exercises=0,
                total_aerobic_exercises=0,
                total_sets=-1
            )
        
        # Test negative duration
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            ExerciseSummary(
                total_resistance_exercises=0,
                total_aerobic_exercises=0,
                total_sets=0,
                estimated_duration_minutes=-30
            )


class TestWorkoutValidationError:
    """Test cases for WorkoutValidationError model"""

    def test_valid_workout_validation_error(self):
        """Test creating a valid workout validation error"""
        # Act
        error = WorkoutValidationError(
            field="sets",
            error_type="value_error",
            message="Sets must be greater than 0",
            value=0,
            exercise_index=2
        )
        
        # Assert
        assert error.field == "sets"
        assert error.error_type == "value_error"
        assert error.message == "Sets must be greater than 0"
        assert error.value == 0
        assert error.exercise_index == 2

    def test_workout_validation_error_minimal_fields(self):
        """Test validation error with only required fields"""
        # Act
        error = WorkoutValidationError(
            field="name",
            error_type="missing",
            message="Exercise name is required"
        )
        
        # Assert
        assert error.field == "name"
        assert error.error_type == "missing"
        assert error.message == "Exercise name is required"
        assert error.value is None
        assert error.exercise_index is None

    def test_workout_validation_error_with_complex_value(self):
        """Test validation error with complex value types"""
        # Act
        error = WorkoutValidationError(
            field="reps",
            error_type="consistency_error",
            message="Reps array length mismatch",
            value=[10, 8, 6],  # List value
            exercise_index=0
        )
        
        # Assert
        assert error.field == "reps"
        assert error.value == [10, 8, 6]