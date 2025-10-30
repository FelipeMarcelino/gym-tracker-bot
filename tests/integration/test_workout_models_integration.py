"""Integration tests for workout models with real-world scenarios"""

import json
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


class TestWorkoutModelsIntegration:
    """Integration tests for workout models with realistic scenarios"""

    def test_complete_strength_training_workout(self):
        """Test creating a complete strength training workout"""
        # Arrange - Realistic strength training session
        exercises = [
            ResistanceExercise(
                name="Barbell Back Squat",
                sets=4,
                reps=[12, 10, 8, 6],
                weights_kg=[100.0, 110.0, 120.0, 130.0],
                rest_seconds=180,
                perceived_difficulty=8,
                notes="Good depth, knees tracking well"
            ),
            ResistanceExercise(
                name="Bench Press",
                sets=3,
                reps=[10, 8, 6],
                weights_kg=[80.0, 85.0, 90.0],
                rest_seconds=120,
                perceived_difficulty=7
            ),
            ResistanceExercise(
                name="Deadlift",
                sets=3,
                reps=[8, 6, 5],
                weights_kg=[140.0, 150.0, 160.0],
                rest_seconds=240,
                perceived_difficulty=9,
                notes="Form getting heavy on last set"
            )
        ]
        
        # Act
        workout = WorkoutData(
            body_weight_kg=85.5,
            energy_level=8,
            start_time="07:30",
            end_time="09:15",
            resistance_exercises=exercises,
            notes="Great strength session, progressive overload working well"
        )
        
        # Assert
        assert workout.body_weight_kg == 85.5
        assert workout.energy_level == 8
        assert len(workout.resistance_exercises) == 3
        assert len(workout.aerobic_exercises) == 0
        
        # Verify exercise details
        squat = workout.resistance_exercises[0]
        assert squat.name == "Barbell Back Squat"
        assert squat.sets == 4
        assert sum(squat.reps) == 36  # Total reps
        assert max(squat.weights_kg) == 130.0  # Max weight
        
        # Verify workout timing
        assert workout.start_time == "07:30"
        assert workout.end_time == "09:15"

    def test_complete_cardio_workout(self):
        """Test creating a complete cardio workout"""
        # Arrange - Realistic cardio session
        exercises = [
            AerobicExercise(
                name="Treadmill Running",
                duration_minutes=25.0,
                distance_km=5.5,
                average_heart_rate=165,
                calories_burned=350,
                intensity_level="moderate",
                notes="Steady pace, felt good throughout"
            ),
            AerobicExercise(
                name="Rowing Machine",
                duration_minutes=15.0,
                distance_km=3.2,
                average_heart_rate=155,
                calories_burned=180,
                intensity_level="moderate"
            ),
            AerobicExercise(
                name="Cycling Cool Down",
                duration_minutes=10.0,
                distance_km=2.8,
                average_heart_rate=125,
                calories_burned=80,
                intensity_level="low"
            )
        ]
        
        # Act
        workout = WorkoutData(
            body_weight_kg=70.2,
            energy_level=7,
            start_time="18:00",
            end_time="19:30",
            aerobic_exercises=exercises,
            notes="Good cardio session, heart rate zones on target"
        )
        
        # Assert
        assert len(workout.aerobic_exercises) == 3
        assert len(workout.resistance_exercises) == 0
        
        # Calculate totals
        total_duration = sum(ex.duration_minutes for ex in workout.aerobic_exercises)
        total_distance = sum(ex.distance_km for ex in workout.aerobic_exercises if ex.distance_km)
        total_calories = sum(ex.calories_burned for ex in workout.aerobic_exercises if ex.calories_burned)
        
        assert total_duration == 50.0  # 25 + 15 + 10
        assert total_distance == 11.5  # 5.5 + 3.2 + 2.8
        assert total_calories == 610   # 350 + 180 + 80

    def test_mixed_workout_session(self):
        """Test creating a workout with both resistance and cardio"""
        # Arrange - Mixed training session
        resistance_exercises = [
            ResistanceExercise(
                name="Push-ups",
                sets=3,
                reps=[20, 18, 15],
                weights_kg=[75.0, 75.0, 75.0],  # Bodyweight
                rest_seconds=60,
                perceived_difficulty=6
            ),
            ResistanceExercise(
                name="Pull-ups",
                sets=3,
                reps=[8, 6, 5],
                weights_kg=[75.0, 75.0, 75.0],  # Bodyweight
                rest_seconds=90,
                perceived_difficulty=8
            )
        ]
        
        aerobic_exercises = [
            AerobicExercise(
                name="Jump Rope",
                duration_minutes=10.0,
                calories_burned=120,
                intensity_level="high",
                notes="Good coordination today"
            )
        ]
        
        # Act
        workout = WorkoutData(
            body_weight_kg=75.0,
            energy_level=8,
            start_time="12:00",
            end_time="13:00",
            resistance_exercises=resistance_exercises,
            aerobic_exercises=aerobic_exercises,
            notes="Circuit training style workout"
        )
        
        # Assert
        assert len(workout.resistance_exercises) == 2
        assert len(workout.aerobic_exercises) == 1
        assert workout.body_weight_kg == 75.0

    def test_cross_midnight_workout_realistic(self):
        """Test realistic cross-midnight workout scenario"""
        # Arrange - Late night workout
        exercise = ResistanceExercise(
            name="Home Workout",
            sets=2,
            reps=[15, 12],
            weights_kg=[50.0, 55.0],
            perceived_difficulty=5
        )
        
        # Act - Workout from 23:30 to 01:15 (1h 45m)
        workout = WorkoutData(
            start_time="23:30",
            end_time="01:15",
            resistance_exercises=[exercise],
            notes="Late workout due to work schedule"
        )
        
        # Assert
        assert workout.start_time == "23:30"
        assert workout.end_time == "01:15"

    def test_maximum_workout_duration(self):
        """Test workout at maximum allowed duration (6 hours)"""
        # Arrange - Ultra-endurance event
        exercise = AerobicExercise(
            name="Ultra Marathon Training",
            duration_minutes=360.0,  # 6 hours
            distance_km=42.0,
            average_heart_rate=140,
            calories_burned=3000,
            intensity_level="low"
        )
        
        # Act
        workout = WorkoutData(
            start_time="06:00",
            end_time="12:00",  # Exactly 6 hours
            aerobic_exercises=[exercise],
            notes="Long endurance training session"
        )
        
        # Assert
        assert workout.start_time == "06:00"
        assert workout.end_time == "12:00"

    def test_llm_parse_result_successful_integration(self):
        """Test successful LLM parsing with complete workout data"""
        # Arrange - Simulated LLM parsing success
        workout_data = WorkoutData(
            body_weight_kg=80.0,
            energy_level=7,
            start_time="14:00",
            end_time="15:30",
            resistance_exercises=[
                ResistanceExercise(
                    name="Squats",
                    sets=3,
                    reps=[15, 12, 10],
                    weights_kg=[100.0, 110.0, 120.0]
                )
            ],
            aerobic_exercises=[
                AerobicExercise(
                    name="Running",
                    duration_minutes=20.0,
                    distance_km=3.5
                )
            ]
        )
        
        # Act
        parse_result = LLMParseResult(
            success=True,
            workout_data=workout_data,
            raw_text="I did 3 sets of squats with 100, 110, and 120kg for 15, 12, and 10 reps. Then ran 3.5km in 20 minutes.",
            parsing_notes="Successfully identified mixed workout with resistance and cardio",
            confidence=0.92,
            errors=[]
        )
        
        # Assert
        assert parse_result.success is True
        assert parse_result.workout_data is not None
        assert parse_result.confidence == 0.92
        assert len(parse_result.errors) == 0
        assert "squats" in parse_result.raw_text.lower()

    def test_llm_parse_result_failed_integration(self):
        """Test failed LLM parsing with detailed error information"""
        # Act
        parse_result = LLMParseResult(
            success=False,
            raw_text="zzz unclear mumbling zzz weights something zzz",
            parsing_notes="Audio quality too poor for reliable parsing",
            confidence=0.15,
            errors=[
                "Could not identify exercise names",
                "No clear numeric values found",
                "Audio transcription confidence too low"
            ]
        )
        
        # Assert
        assert parse_result.success is False
        assert parse_result.workout_data is None
        assert parse_result.confidence == 0.15
        assert len(parse_result.errors) == 3

    def test_exercise_summary_integration(self):
        """Test exercise summary with realistic workout data"""
        # Arrange - Complex workout for summary
        workout = WorkoutData(
            resistance_exercises=[
                ResistanceExercise(name="Squat", sets=4, reps=[12, 10, 8, 6], weights_kg=[100, 110, 120, 130]),
                ResistanceExercise(name="Bench", sets=3, reps=[10, 8, 6], weights_kg=[80, 85, 90]),
                ResistanceExercise(name="Row", sets=3, reps=[12, 10, 8], weights_kg=[70, 75, 80])
            ],
            aerobic_exercises=[
                AerobicExercise(name="Treadmill", duration_minutes=15.0),
                AerobicExercise(name="Bike", duration_minutes=10.0)
            ]
        )
        
        # Act - Create summary
        summary = ExerciseSummary(
            total_resistance_exercises=len(workout.resistance_exercises),
            total_aerobic_exercises=len(workout.aerobic_exercises),
            total_sets=sum(ex.sets for ex in workout.resistance_exercises),
            estimated_duration_minutes=90,
            muscle_groups=["legs", "chest", "back", "core"]
        )
        
        # Assert
        assert summary.total_resistance_exercises == 3
        assert summary.total_aerobic_exercises == 2
        assert summary.total_sets == 10  # 4 + 3 + 3
        assert summary.estimated_duration_minutes == 90
        assert "legs" in summary.muscle_groups

    def test_workout_validation_error_integration(self):
        """Test workout validation error with detailed context"""
        # Act
        validation_error = WorkoutValidationError(
            field="weights_kg",
            error_type="array_length_mismatch",
            message="Number of weight values (2) must match sets count (3)",
            value=[100.0, 110.0],  # Missing third weight
            exercise_index=1
        )
        
        # Assert
        assert validation_error.field == "weights_kg"
        assert validation_error.error_type == "array_length_mismatch"
        assert "must match sets count" in validation_error.message
        assert len(validation_error.value) == 2
        assert validation_error.exercise_index == 1

    def test_model_serialization_deserialization(self):
        """Test JSON serialization and deserialization of workout models"""
        # Arrange - Create workout
        original_workout = WorkoutData(
            body_weight_kg=75.5,
            energy_level=8,
            start_time="09:00",
            end_time="10:30",
            resistance_exercises=[
                ResistanceExercise(
                    name="Deadlift",
                    sets=3,
                    reps=[8, 6, 5],
                    weights_kg=[140.0, 150.0, 160.0],
                    rest_seconds=180,
                    perceived_difficulty=9
                )
            ],
            notes="Personal best on third set!"
        )
        
        # Act - Serialize to JSON and back
        json_data = original_workout.model_dump()
        json_string = json.dumps(json_data)
        restored_data = json.loads(json_string)
        restored_workout = WorkoutData(**restored_data)
        
        # Assert - Data integrity maintained
        assert restored_workout.body_weight_kg == original_workout.body_weight_kg
        assert restored_workout.energy_level == original_workout.energy_level
        assert restored_workout.start_time == original_workout.start_time
        assert restored_workout.end_time == original_workout.end_time
        assert restored_workout.notes == original_workout.notes
        
        # Check exercise data
        original_ex = original_workout.resistance_exercises[0]
        restored_ex = restored_workout.resistance_exercises[0]
        assert restored_ex.name == original_ex.name
        assert restored_ex.sets == original_ex.sets
        assert restored_ex.reps == original_ex.reps
        assert restored_ex.weights_kg == original_ex.weights_kg

    def test_complex_validation_scenario(self):
        """Test complex validation with multiple potential failure points"""
        # This tests the interaction between multiple validators
        
        # Test 1: Workout with inconsistent arrays should fail
        with pytest.raises(ValidationError, match="Number of rep values"):
            WorkoutData(
                resistance_exercises=[
                    ResistanceExercise(
                        name="Test Exercise",
                        sets=3,
                        reps=[10, 8],  # Only 2 reps for 3 sets
                        weights_kg=[50.0, 55.0, 60.0]  # 3 weights for 3 sets
                    )
                ]
            )
        
        # Test 2: Workout with valid arrays should pass
        valid_workout = WorkoutData(
            resistance_exercises=[
                ResistanceExercise(
                    name="Test Exercise",
                    sets=3,
                    reps=[10, 8, 6],  # 3 reps for 3 sets
                    weights_kg=[50.0, 55.0, 60.0]  # 3 weights for 3 sets
                )
            ]
        )
        assert len(valid_workout.resistance_exercises) == 1

    def test_edge_case_combinations(self):
        """Test edge case combinations that might occur in real usage"""
        # Minimum viable workout
        minimal_workout = WorkoutData(
            resistance_exercises=[
                ResistanceExercise(
                    name="A",  # Minimum name length
                    sets=1,    # Minimum sets
                    reps=[1],  # Minimum reps
                    weights_kg=[0.1]  # Very light weight
                )
            ]
        )
        assert minimal_workout.resistance_exercises[0].name == "A"
        
        # Maximum values workout (testing boundaries)
        max_workout = WorkoutData(
            body_weight_kg=500.0,  # Maximum body weight
            energy_level=10,       # Maximum energy
            start_time="00:00",    # Midnight start
            end_time="06:00",      # 6 hours later (maximum duration)
            resistance_exercises=[
                ResistanceExercise(
                    name="x" * 100,   # Maximum name length
                    sets=20,          # Maximum sets
                    reps=[1000] * 20, # Very high reps
                    weights_kg=[999.9] * 20,  # Very heavy weights
                    rest_seconds=1800,  # Maximum rest (30 minutes)
                    perceived_difficulty=10,  # Maximum RPE
                    notes="x" * 500   # Maximum notes length
                )
            ],
            aerobic_exercises=[
                AerobicExercise(
                    name="y" * 100,        # Maximum name length
                    duration_minutes=1440.0,  # Maximum duration (24 hours)
                    distance_km=999.9,     # Very long distance
                    average_heart_rate=220, # Maximum heart rate
                    calories_burned=10000,  # Maximum calories
                    intensity_level="hiit", # High intensity
                    notes="y" * 500        # Maximum notes length
                )
            ],
            notes="z" * 1000  # Maximum workout notes length
        )
        assert max_workout.body_weight_kg == 500.0
        assert len(max_workout.notes) == 1000

    def test_realistic_user_input_patterns(self):
        """Test realistic patterns of user input that might be parsed"""
        # Pattern 1: Voice note workout log
        voice_workout = WorkoutData(
            start_time="06:30",
            end_time="07:45",
            resistance_exercises=[
                ResistanceExercise(
                    name="morning push-ups",
                    sets=3,
                    reps=[25, 20, 18],
                    weights_kg=[70.0, 70.0, 70.0],  # Bodyweight
                    notes="felt strong this morning"
                )
            ],
            notes="quick workout before work"
        )
        assert "morning" in voice_workout.resistance_exercises[0].name
        
        # Pattern 2: Gym session with metrics
        gym_workout = WorkoutData(
            body_weight_kg=82.3,
            energy_level=6,
            start_time="17:30",
            end_time="19:15",
            resistance_exercises=[
                ResistanceExercise(
                    name="Barbell Squat",
                    sets=5,
                    reps=[8, 8, 8, 6, 4],
                    weights_kg=[135.0, 145.0, 155.0, 165.0, 175.0],
                    rest_seconds=180,
                    perceived_difficulty=8
                )
            ],
            aerobic_exercises=[
                AerobicExercise(
                    name="Warm-up Treadmill",
                    duration_minutes=10.0,
                    intensity_level="low"
                )
            ],
            notes="progressive overload week 3"
        )
        assert gym_workout.energy_level == 6
        assert len(gym_workout.resistance_exercises[0].weights_kg) == 5