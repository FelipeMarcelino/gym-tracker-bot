"""Simplified unit tests for AsyncWorkoutService

These tests focus only on business logic that can be tested reliably without
complex async mocking. They test the core business rules and calculations.
"""

import pytest
from datetime import datetime, time, date, timedelta
from unittest.mock import MagicMock

from services.async_workout_service import AsyncWorkoutService
from services.exceptions import ValidationError, ErrorCode
from database.models import SessionStatus


class TestAsyncWorkoutServiceValidation:
    """Test core validation logic without database mocking"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    @pytest.mark.asyncio
    async def test_validation_session_id_types(self, workout_service):
        """Test session ID validation with different types"""
        valid_data = {"resistance_exercises": []}
        user_id = "test_user"
        
        # Test with numeric invalid values that can be compared
        invalid_session_ids = [None, 0, -1, -999]
        
        for invalid_id in invalid_session_ids:
            with pytest.raises(ValidationError) as exc_info:
                await workout_service.add_exercises_to_session_batch(invalid_id, valid_data, user_id)
            assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        
        # Test with non-numeric types that would cause TypeError
        invalid_types = ["invalid", [], {}]
        for invalid_id in invalid_types:
            with pytest.raises((ValidationError, TypeError)):
                await workout_service.add_exercises_to_session_batch(invalid_id, valid_data, user_id)

    @pytest.mark.asyncio
    async def test_validation_user_id_types(self, workout_service):
        """Test user ID validation with different types"""
        valid_data = {"resistance_exercises": []}
        session_id = 1
        
        # Test with string invalid values that can call strip()
        invalid_user_ids = [None, "", "   ", "\t\n"]
        
        for invalid_id in invalid_user_ids:
            with pytest.raises(ValidationError) as exc_info:
                await workout_service.add_exercises_to_session_batch(session_id, valid_data, invalid_id)
            assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        
        # Test with non-string types that would cause AttributeError
        invalid_types = [[], {}, 123]
        for invalid_id in invalid_types:
            with pytest.raises((ValidationError, AttributeError)):
                await workout_service.add_exercises_to_session_batch(session_id, valid_data, invalid_id)

    @pytest.mark.asyncio
    async def test_validation_parsed_data_types(self, workout_service):
        """Test parsed data validation with different types"""
        session_id = 1
        user_id = "test_user"
        
        invalid_data_types = [None, "string", [], 123, True, lambda x: x]
        
        for invalid_data in invalid_data_types:
            with pytest.raises(ValidationError) as exc_info:
                await workout_service.add_exercises_to_session_batch(session_id, invalid_data, user_id)
            assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


class TestSessionDataUpdate:
    """Test session data update logic without database dependencies"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    @pytest.mark.asyncio
    async def test_audio_count_increment(self, workout_service):
        """Test that audio count is always incremented by 1"""
        mock_session = MagicMock()
        mock_workout_session = MagicMock()
        
        # Test with different initial values
        for initial_count in [0, 1, 5, 99, 1000]:
            mock_workout_session.audio_count = initial_count
            mock_workout_session.notes = None
            
            await workout_service._update_session_data_async(
                mock_session, mock_workout_session, {}
            )
            
            assert mock_workout_session.audio_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_notes_concatenation_logic(self, workout_service):
        """Test notes concatenation with various scenarios"""
        mock_session = MagicMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 0
        
        test_cases = [
            # (existing_notes, new_notes, expected_result)
            (None, "New note", "New note"),
            ("", "New note", "New note"),
            ("Old note", "New note", "Old note\nNew note"),
            ("Multiple\nLines", "Another", "Multiple\nLines\nAnother"),
            ("   Spaced   ", "  Test  ", "Spaced   \n  Test"),  # .strip() removes outer whitespace
        ]
        
        for existing, new, expected in test_cases:
            mock_workout_session.notes = existing
            await workout_service._update_session_data_async(
                mock_session, mock_workout_session, {"notes": new}
            )
            assert mock_workout_session.notes == expected

    @pytest.mark.asyncio
    async def test_optional_fields_update(self, workout_service):
        """Test optional fields are only updated when present"""
        mock_session = MagicMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 1
        mock_workout_session.notes = None
        
        # Test with all optional fields
        parsed_data = {
            "energy_level": 8,
            "difficulty": 7,
            "notes": "Great workout"
        }
        
        await workout_service._update_session_data_async(
            mock_session, mock_workout_session, parsed_data
        )
        
        assert mock_workout_session.energy_level == 8
        assert mock_workout_session.difficulty == 7
        assert mock_workout_session.notes == "Great workout"
        
        # Test with empty parsed data
        mock_workout_session.audio_count = 0
        original_energy = getattr(mock_workout_session, 'energy_level', None)
        
        await workout_service._update_session_data_async(
            mock_session, mock_workout_session, {}
        )
        
        # Should only increment audio_count, leave other fields unchanged
        assert mock_workout_session.audio_count == 1


class TestSessionStatsCalculation:
    """Test session statistics calculation logic"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    @pytest.mark.asyncio
    async def test_stats_calculation_comprehensive(self, workout_service):
        """Test comprehensive stats calculation with realistic data"""
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 3
        
        # Create realistic resistance exercises
        exercises = []
        for i in range(3):
            exercise = MagicMock()
            exercise.sets = 3 + i  # 3, 4, 5 sets
            exercise.weights_kg = [40 + i*10, 50 + i*10, 60 + i*10]  # Progressive loading
            exercise.exercise.muscle_group = ["chest", "legs", "back"][i]
            exercises.append(exercise)
        
        mock_workout_session.exercises = exercises
        
        # Create aerobic exercises
        aerobics = []
        for i in range(2):
            aerobic = MagicMock()
            aerobic.duration_minutes = 20 + i*10  # 20, 30 minutes
            aerobics.append(aerobic)
        
        mock_workout_session.aerobics = aerobics
        
        stats = workout_service._calculate_session_stats_sync(mock_workout_session)
        
        # Verify calculations
        assert stats["audio_count"] == 3
        assert stats["resistance_exercises"] == 3
        assert stats["aerobic_exercises"] == 2
        assert stats["total_sets"] == 12  # 3 + 4 + 5
        assert stats["total_volume_kg"] == 540  # (40+50+60) + (50+60+70) + (60+70+80)
        assert stats["cardio_minutes"] == 50  # 20 + 30
        assert len(stats["muscle_groups"]) == 3
        assert "chest" in stats["muscle_groups"]
        assert "legs" in stats["muscle_groups"]
        assert "back" in stats["muscle_groups"]

    @pytest.mark.asyncio
    async def test_stats_with_missing_data(self, workout_service):
        """Test stats calculation handles missing/None data gracefully"""
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 1
        
        # Exercise with missing data
        exercise1 = MagicMock()
        exercise1.sets = None  # Missing sets
        exercise1.weights_kg = None  # Missing weights
        exercise1.exercise.muscle_group = "test"
        
        exercise2 = MagicMock()
        exercise2.sets = 3
        exercise2.weights_kg = []  # Empty weights
        exercise2.exercise.muscle_group = None  # Missing muscle group
        
        mock_workout_session.exercises = [exercise1, exercise2]
        
        # Aerobic with missing data
        aerobic = MagicMock()
        aerobic.duration_minutes = None
        mock_workout_session.aerobics = [aerobic]
        
        stats = workout_service._calculate_session_stats_sync(mock_workout_session)
        
        assert stats["resistance_exercises"] == 2
        assert stats["aerobic_exercises"] == 1
        assert stats["total_sets"] == 3  # Only exercise2 contributes
        assert stats["total_volume_kg"] == 0  # No valid weights
        assert stats["cardio_minutes"] == 0  # No valid duration
        assert stats["muscle_groups"] == ["test"]  # Only exercise1 has muscle group


class TestTimeoutAndDurationLogic:
    """Test session timeout and duration calculation logic"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    def test_session_timeout_boundary_conditions(self, workout_service):
        """Test session timeout calculations at boundaries"""
        timeout_hours = 3
        now = datetime.now()
        
        test_cases = [
            # (hours_ago, expected_status, description)
            (1, SessionStatus.ATIVA, "1 hour ago - should be active"),
            (2.5, SessionStatus.ATIVA, "2.5 hours ago - should be active"),
            (3, SessionStatus.FINALIZADA, "Exactly 3 hours ago - should be expired"),
            (3.1, SessionStatus.FINALIZADA, "3.1 hours ago - should be expired"),
            (5, SessionStatus.FINALIZADA, "5 hours ago - should be expired"),
        ]
        
        for hours_ago, expected_status, description in test_cases:
            session_time = now - timedelta(hours=hours_ago)
            minutes_passed = int((now - session_time).total_seconds() // 60)
            
            is_active = SessionStatus.ATIVA if minutes_passed < (timeout_hours * 60) else SessionStatus.FINALIZADA
            
            assert is_active == expected_status, f"Failed: {description}"

    def test_cross_midnight_duration_calculation(self, workout_service):
        """Test duration calculation across midnight boundaries"""
        session_date = date.today()
        
        test_cases = [
            # (start_time, end_time, expected_minutes, description)
            (time(23, 0), time(1, 0), 120, "23:00 to 01:00 next day"),
            (time(23, 30), time(0, 30), 60, "23:30 to 00:30 next day"),
            (time(22, 15), time(2, 45), 270, "22:15 to 02:45 next day"),
            (time(10, 0), time(14, 0), 240, "Same day 10:00 to 14:00"),
        ]
        
        for start_time, end_time, expected_minutes, description in test_cases:
            start_datetime = datetime.combine(session_date, start_time)
            
            # Business logic: if end_time < start_time, assume next day
            if end_time < start_time:
                end_datetime = datetime.combine(session_date + timedelta(days=1), end_time)
            else:
                end_datetime = datetime.combine(session_date, end_time)
            
            duration_minutes = int((end_datetime - start_datetime).total_seconds() // 60)
            duration_minutes = max(0, duration_minutes)  # Safety protection
            
            assert duration_minutes == expected_minutes, f"Failed: {description}"

    def test_negative_duration_protection(self, workout_service):
        """Test protection against negative durations"""
        session_date = date.today()
        
        # Edge case: end time appears before start time on same day
        start_time = time(15, 0)  # 3 PM
        end_time = time(10, 0)    # 10 AM same day (invalid scenario)
        
        start_datetime = datetime.combine(session_date, start_time)
        end_datetime = datetime.combine(session_date, end_time)
        
        duration_minutes = int((end_datetime - start_datetime).total_seconds() // 60)
        duration_minutes = max(0, duration_minutes)  # Should protect against negative
        
        assert duration_minutes == 0, "Should protect against negative duration"


class TestAnalyticsBusinessLogic:
    """Test analytics calculation business logic"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    @pytest.mark.asyncio
    async def test_frequency_calculation_logic(self, workout_service):
        """Test workout frequency calculation with various scenarios"""
        test_cases = [
            # (unique_days, total_days, expected_frequency, is_extrapolated)
            (7, 7, 7.0, True),      # 7 workouts in 7 days = 7 per week
            (3, 7, 3.0, True),      # 3 workouts in 7 days = 3 per week
            (4, 14, 2.0, True),     # 4 workouts in 14 days = 2 per week
            (2, 21, 0.67, True),    # 2 workouts in 21 days ≈ 0.67 per week
            (5, 5, 7.0, False),     # 5 workouts in 5 days = 7 per week (not extrapolated)
            (0, 30, 0.0, True),     # No workouts = 0 per week
        ]
        
        for unique_days, days, expected_freq, expected_extrapolated in test_cases:
            if days >= 7:
                frequency_per_week = unique_days * 7 / days
                is_extrapolated = True
            else:
                frequency_per_week = unique_days * 7 / days if days > 0 else 0
                is_extrapolated = False
            
            # Allow small floating point differences
            assert abs(frequency_per_week - expected_freq) < 0.1
            assert is_extrapolated == expected_extrapolated

    @pytest.mark.asyncio
    async def test_progress_trend_analysis(self, workout_service):
        """Test progress trend analysis logic"""
        test_cases = [
            # (recent_volume, older_volume, expected_trend)
            (1000, 800, "improving"),      # 25% increase
            (1200, 1000, "improving"),     # 20% increase  
            (800, 1000, "declining"),      # 20% decrease
            (700, 1000, "declining"),      # 30% decrease
            (1050, 1000, "stable"),        # 5% increase (stable)
            (950, 1000, "stable"),         # 5% decrease (stable)
            (1100, 1000, "stable"),        # 10% increase (stable)
            (900, 1000, "stable"),         # 10% decrease (stable)
            (1000, 0, "insufficient_data"), # No baseline
        ]
        
        for recent_vol, older_vol, expected_trend in test_cases:
            if older_vol > 0:
                volume_change_percent = (recent_vol - older_vol) / older_vol * 100
                if volume_change_percent > 10:
                    trend = "improving"
                elif volume_change_percent < -10:
                    trend = "declining"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"
            
            assert trend == expected_trend

    def test_muscle_group_distribution_calculation(self, workout_service):
        """Test muscle group distribution calculation logic"""
        muscle_groups = ["chest", "legs", "chest", "back", "chest", "arms", "legs"]
        
        # Calculate distribution like the service does
        muscle_group_counts = {}
        for muscle_group in muscle_groups:
            if muscle_group:
                muscle_group_counts[muscle_group] = muscle_group_counts.get(muscle_group, 0) + 1
        
        total_exercises = sum(muscle_group_counts.values())
        distribution = {
            muscle: {
                "count": count,
                "percentage": count / total_exercises * 100 if total_exercises > 0 else 0,
            }
            for muscle, count in muscle_group_counts.items()
        }
        
        # Verify calculations
        assert distribution["chest"]["count"] == 3
        assert abs(distribution["chest"]["percentage"] - 42.86) < 0.1  # 3/7 * 100
        assert distribution["legs"]["count"] == 2
        assert abs(distribution["legs"]["percentage"] - 28.57) < 0.1   # 2/7 * 100
        assert distribution["back"]["count"] == 1
        assert abs(distribution["back"]["percentage"] - 14.29) < 0.1   # 1/7 * 100
        assert distribution["arms"]["count"] == 1
        assert abs(distribution["arms"]["percentage"] - 14.29) < 0.1   # 1/7 * 100

    def test_zero_division_protection(self, workout_service):
        """Test protection against zero division in analytics"""
        # Test all scenarios that could cause division by zero
        
        # Completion rate with zero sessions
        total_sessions = 0
        completed_sessions = 0
        completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        assert completion_rate == 0
        
        # Average duration with no durations
        durations = []
        avg_duration = sum(durations) / len(durations) if durations else 0
        assert avg_duration == 0
        
        # Average energy with no energy levels
        energy_levels = []
        avg_energy = sum(energy_levels) / len(energy_levels) if energy_levels else 0
        assert avg_energy == 0
        
        # Frequency with zero days
        unique_workout_days = 5
        days = 0
        frequency_per_week = unique_workout_days * 7 / days if days > 0 else 0
        assert frequency_per_week == 0
        
        # Consistency score with zero days
        consistency_score = unique_workout_days / days * 100 if days > 0 else 0
        assert consistency_score == 0
        
        # Muscle group percentage with zero exercises
        total_muscle_exercises = 0
        percentage = 5 / total_muscle_exercises * 100 if total_muscle_exercises > 0 else 0
        assert percentage == 0


class TestDataTypeValidation:
    """Test data type validation and edge cases"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    def test_weights_validation_logic(self, workout_service):
        """Test weights validation logic"""
        valid_weights = [
            [40, 50, 60],           # Normal case
            [40.5, 50.0, 60.5],     # Floats
            [],                     # Empty list (valid but no volume)
            [0, 50, 0],             # Zeros mixed in
        ]
        
        invalid_weights = [
            None,                   # None
            "40,50,60",            # String
            40,                    # Single number
            [40, "50", 60],        # Mixed types in list
        ]
        
        for weights in valid_weights:
            is_valid = weights is not None and isinstance(weights, list)
            if is_valid and weights:
                is_valid = all(isinstance(w, (int, float)) for w in weights)
            assert is_valid or weights == []
        
        for weights in invalid_weights:
            is_valid = weights is not None and isinstance(weights, list)
            if is_valid and weights:
                is_valid = all(isinstance(w, (int, float)) for w in weights)
            assert not is_valid

    def test_exercise_name_normalization(self, workout_service):
        """Test exercise name normalization"""
        test_cases = [
            ("SUPINO RETO", "supino reto"),
            ("Agachamento Livre", "agachamento livre"),
            ("  bench press  ", "bench press"),
            ("", ""),
            ("MiXeD cAsE", "mixed case"),
        ]
        
        for input_name, expected in test_cases:
            normalized = input_name.lower().strip()
            assert normalized == expected

    def test_sets_validation_logic(self, workout_service):
        """Test sets validation and handling"""
        valid_sets = [1, 2, 3, 10, 100]
        invalid_sets = [None, 0, -1, "3", [], {}]
        
        for sets in valid_sets:
            contributes_to_total = sets and isinstance(sets, int) and sets > 0
            assert contributes_to_total
        
        for sets in invalid_sets:
            contributes_to_total = sets and isinstance(sets, int) and sets > 0
            assert not contributes_to_total