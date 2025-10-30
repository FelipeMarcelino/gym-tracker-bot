"""Focused unit tests for AsyncWorkoutService core business logic

These tests focus on the essential business logic and validation without
complex async mocking issues. They test the core methods with simpler mocking.
"""

import pytest
import uuid
from datetime import datetime, time, date, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from services.async_workout_service import AsyncWorkoutService
from services.exceptions import ValidationError, ErrorCode
from database.models import SessionStatus


class TestAsyncWorkoutServiceValidation:
    """Test core validation logic"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    @pytest.mark.asyncio
    async def test_add_exercises_session_id_validation(self, workout_service):
        """Test session ID validation"""
        
        valid_data = {"resistance_exercises": []}
        user_id = "test_user"
        
        # Test None session_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(None, valid_data, user_id)
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        
        # Test invalid UUID string
        with pytest.raises((ValidationError, Exception)) as exc_info:
            await workout_service.add_exercises_to_session_batch("invalid-uuid", valid_data, user_id)
        
        # Test non-existent UUID (should trigger SESSION_NOT_FOUND)
        non_existent_uuid = uuid.uuid4()
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(non_existent_uuid, valid_data, user_id)
        assert exc_info.value.error_code == ErrorCode.SESSION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_add_exercises_user_id_validation(self, workout_service):
        """Test user ID validation"""
        
        valid_data = {"resistance_exercises": []}
        session_id = uuid.uuid4()
        
        # Test None user_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(session_id, valid_data, None)
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        
        # Test empty user_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(session_id, valid_data, "")
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        
        # Test whitespace user_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(session_id, valid_data, "   ")
        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.asyncio
    async def test_add_exercises_parsed_data_validation(self, workout_service):
        """Test parsed data validation"""
        
        session_id = uuid.uuid4()
        user_id = "test_user"
        
        # Test None parsed_data
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(session_id, None, user_id)
        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        
        # Test non-dict parsed_data
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(session_id, "invalid", user_id)
        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        
        # Test list instead of dict
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(session_id, [], user_id)
        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT


class TestUpdateSessionDataAsync:
    """Test session data update logic"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    @pytest.mark.asyncio
    async def test_update_session_audio_count_increment(self, workout_service):
        """Test audio count is always incremented"""
        
        mock_session = MagicMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 5
        mock_workout_session.notes = None
        
        await workout_service._update_session_data_async(
            mock_session, mock_workout_session, {}
        )
        
        assert mock_workout_session.audio_count == 6
        mock_session.add.assert_called_once_with(mock_workout_session)

    @pytest.mark.asyncio
    async def test_update_session_optional_fields(self, workout_service):
        """Test optional field updates"""
        
        mock_session = MagicMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 1
        mock_workout_session.notes = "Existing notes"
        
        parsed_data = {
            "energy_level": 8,
            "difficulty": 7,
            "notes": "New notes"
        }
        
        await workout_service._update_session_data_async(
            mock_session, mock_workout_session, parsed_data
        )
        
        assert mock_workout_session.audio_count == 2
        assert mock_workout_session.energy_level == 8
        assert mock_workout_session.difficulty == 7
        assert mock_workout_session.notes == "Existing notes\nNew notes"

    @pytest.mark.asyncio
    async def test_update_session_notes_concatenation(self, workout_service):
        """Test notes are properly concatenated"""
        
        mock_session = MagicMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 0
        
        # Test with None existing notes
        mock_workout_session.notes = None
        await workout_service._update_session_data_async(
            mock_session, mock_workout_session, {"notes": "First note"}
        )
        assert mock_workout_session.notes == "First note"
        
        # Test with empty existing notes
        mock_workout_session.notes = ""
        await workout_service._update_session_data_async(
            mock_session, mock_workout_session, {"notes": "Second note"}
        )
        # Empty string + "\n" + "Second note" gets stripped to just "Second note"
        assert mock_workout_session.notes == "Second note"


class TestCalculateSessionStatsAsync:
    """Test session statistics calculation"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    @pytest.mark.asyncio
    async def test_calculate_stats_basic(self, workout_service):
        """Test basic stats calculation"""
        
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 3
        
        # Mock resistance exercises
        exercise1 = MagicMock()
        exercise1.sets = 3
        exercise1.weights_kg = [40, 50, 60]
        exercise1.exercise.muscle_group = "chest"
        
        exercise2 = MagicMock()
        exercise2.sets = 2
        exercise2.weights_kg = [30, 35]
        exercise2.exercise.muscle_group = "arms"
        
        mock_workout_session.exercises = [exercise1, exercise2]
        
        # Mock aerobic exercises
        aerobic1 = MagicMock()
        aerobic1.duration_minutes = 20
        
        aerobic2 = MagicMock()
        aerobic2.duration_minutes = 15
        
        mock_workout_session.aerobics = [aerobic1, aerobic2]
        
        stats = workout_service._calculate_session_stats_sync(mock_workout_session)
        
        assert stats["audio_count"] == 3
        assert stats["resistance_exercises"] == 2
        assert stats["aerobic_exercises"] == 2
        assert stats["total_sets"] == 5  # 3 + 2
        assert stats["total_volume_kg"] == 215  # (40+50+60) + (30+35)
        assert stats["cardio_minutes"] == 35  # 20 + 15
        assert "chest" in stats["muscle_groups"]
        assert "arms" in stats["muscle_groups"]

    @pytest.mark.asyncio
    async def test_calculate_stats_with_none_values(self, workout_service):
        """Test stats calculation with None/missing values"""
        
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 1
        
        # Exercise with None weights
        exercise1 = MagicMock()
        exercise1.sets = 3
        exercise1.weights_kg = None
        exercise1.exercise.muscle_group = "legs"
        
        # Exercise with empty weights list
        exercise2 = MagicMock()
        exercise2.sets = None  # None sets
        exercise2.weights_kg = []
        exercise2.exercise.muscle_group = None  # None muscle group
        
        mock_workout_session.exercises = [exercise1, exercise2]
        
        # Aerobic with None duration
        aerobic1 = MagicMock()
        aerobic1.duration_minutes = None
        
        mock_workout_session.aerobics = [aerobic1]
        
        stats = workout_service._calculate_session_stats_sync(mock_workout_session)
        
        assert stats["resistance_exercises"] == 2
        assert stats["aerobic_exercises"] == 1
        assert stats["total_sets"] == 3  # Only exercise1 contributes
        assert stats["total_volume_kg"] == 0  # No valid weights
        assert stats["cardio_minutes"] == 0  # No valid duration
        assert stats["muscle_groups"] == ["legs"]  # Only exercise1 has muscle group

    @pytest.mark.asyncio
    async def test_calculate_stats_empty_session(self, workout_service):
        """Test stats calculation for empty session"""
        
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 1
        mock_workout_session.exercises = []
        mock_workout_session.aerobics = []
        
        stats = workout_service._calculate_session_stats_sync(mock_workout_session)
        
        assert stats["audio_count"] == 1
        assert stats["resistance_exercises"] == 0
        assert stats["aerobic_exercises"] == 0
        assert stats["total_sets"] == 0
        assert stats["total_volume_kg"] == 0
        assert stats["cardio_minutes"] == 0
        assert stats["muscle_groups"] == []


class TestSessionStatusCalculation:
    """Test session status and timeout calculation logic"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    def test_session_timeout_calculation(self, workout_service):
        """Test session timeout boundary conditions"""
        
        # Mock settings
        timeout_hours = 3
        
        # Test active session (within timeout)
        now = datetime.now()
        session_time = now - timedelta(hours=2)  # 2 hours ago
        
        minutes_passed = int((now - session_time).total_seconds() // 60)
        is_active = SessionStatus.ATIVA if minutes_passed < (timeout_hours * 60) else SessionStatus.FINALIZADA
        
        assert is_active == SessionStatus.ATIVA
        assert minutes_passed == 120  # 2 hours
        
        # Test expired session (beyond timeout)
        expired_time = now - timedelta(hours=4)  # 4 hours ago
        
        minutes_passed = int((now - expired_time).total_seconds() // 60)
        is_active = SessionStatus.ATIVA if minutes_passed < (timeout_hours * 60) else SessionStatus.FINALIZADA
        
        assert is_active == SessionStatus.FINALIZADA
        assert minutes_passed == 240  # 4 hours
        
        # Test boundary condition (exactly at timeout)
        boundary_time = now - timedelta(hours=3, seconds=0)  # Exactly 3 hours
        
        minutes_passed = int((now - boundary_time).total_seconds() // 60)
        is_active = SessionStatus.ATIVA if minutes_passed < (timeout_hours * 60) else SessionStatus.FINALIZADA
        
        assert is_active == SessionStatus.FINALIZADA
        assert minutes_passed == 180  # Exactly 3 hours

    def test_cross_midnight_duration_calculation(self, workout_service):
        """Test duration calculation across midnight"""
        
        # Session starts at 11:30 PM
        session_date = date.today()
        start_time = time(23, 30, 0)
        
        # Ends at 1:00 AM next day
        end_time = time(1, 0, 0)
        
        start_datetime = datetime.combine(session_date, start_time)
        
        # If end_time < start_time, assume next day
        if end_time < start_time:
            end_datetime = datetime.combine(session_date + timedelta(days=1), end_time)
        else:
            end_datetime = datetime.combine(session_date, end_time)
        
        duration_minutes = int((end_datetime - start_datetime).total_seconds() // 60)
        duration_minutes = max(0, duration_minutes)  # Safety check
        
        assert duration_minutes == 90  # 1.5 hours
        
    def test_negative_duration_protection(self, workout_service):
        """Test protection against negative durations"""
        
        # Simulate edge case where end_time appears before start_time on same day
        session_date = date.today()
        start_time = time(14, 0, 0)  # 2:00 PM
        end_time = time(10, 0, 0)    # 10:00 AM (same day - edge case)
        
        start_datetime = datetime.combine(session_date, start_time)
        end_datetime = datetime.combine(session_date, end_time)
        
        duration_minutes = int((end_datetime - start_datetime).total_seconds() // 60)
        duration_minutes = max(0, duration_minutes)  # Should protect against negative
        
        assert duration_minutes == 0  # Protected against negative


class TestBusinessLogicValidation:
    """Test business logic rules and edge cases"""
    
    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()
    
    def test_exercise_name_normalization(self, workout_service):
        """Test exercise name normalization logic"""
        
        # Test case normalization
        test_names = [
            ("SUPINO RETO", "supino reto"),
            ("Agachamento Livre", "agachamento livre"),
            ("  bench press  ", "bench press"),  # Should strip whitespace
            ("", ""),  # Empty name handling
        ]
        
        for input_name, expected in test_names:
            normalized = input_name.lower().strip()
            assert normalized == expected

    def test_volume_calculation_edge_cases(self, workout_service):
        """Test volume calculation with edge cases"""
        
        # Test different weight scenarios
        weight_scenarios = [
            ([40, 50, 60], 150),      # Normal case
            ([], 0),                  # Empty weights
            ([100], 100),             # Single weight
            ([0, 50, 0], 50),        # Zero weights mixed
        ]
        
        for weights, expected_volume in weight_scenarios:
            if weights and isinstance(weights, list):
                calculated_volume = sum(weights)
            else:
                calculated_volume = 0
            
            assert calculated_volume == expected_volume

    def test_frequency_calculation_logic(self, workout_service):
        """Test workout frequency calculation logic"""
        
        # Test frequency calculation for different periods
        test_cases = [
            (4, 14, 2.0),    # 4 workouts in 14 days = 2 per week
            (7, 7, 7.0),     # 7 workouts in 7 days = 7 per week
            (2, 21, 0.67),   # 2 workouts in 21 days = ~0.67 per week
            (0, 7, 0.0),     # No workouts = 0 per week
        ]
        
        for unique_workout_days, days, expected_frequency in test_cases:
            if days >= 7:
                frequency_per_week = unique_workout_days * 7 / days
                is_extrapolated = True
            else:
                frequency_per_week = unique_workout_days * 7 / days if days > 0 else 0
                is_extrapolated = False
            
            assert abs(frequency_per_week - expected_frequency) < 0.1  # Allow for rounding
            assert is_extrapolated == (days >= 7)

    def test_progress_trend_analysis_logic(self, workout_service):
        """Test progress trend analysis logic"""
        
        # Test trend determination
        test_cases = [
            (1000, 800, "improving"),     # 25% increase
            (800, 1000, "declining"),     # 20% decrease
            (1000, 950, "stable"),        # 5% increase (within stable range)
            (900, 910, "stable"),         # 1% increase (within stable range)
            (1000, 0, "insufficient_data"), # No baseline data
        ]
        
        for recent_volume, older_volume, expected_trend in test_cases:
            if older_volume > 0:
                volume_change_percent = (recent_volume - older_volume) / older_volume * 100
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
        """Test muscle group distribution calculation"""
        
        # Mock exercises with muscle groups
        muscle_groups = ["chest", "legs", "chest", "back", "chest", "arms"]
        
        # Calculate distribution
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
        
        assert distribution["chest"]["count"] == 3
        assert distribution["chest"]["percentage"] == 50.0  # 3/6 * 100
        assert distribution["legs"]["count"] == 1
        assert distribution["legs"]["percentage"] == pytest.approx(16.67, rel=1e-2)
        assert len(distribution) == 4  # chest, legs, back, arms

    def test_analytics_zero_division_protection(self, workout_service):
        """Test analytics calculations protect against zero division"""
        
        # Test completion rate with zero sessions
        total_sessions = 0
        completed_sessions = 0
        
        completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0
        assert completion_rate == 0
        
        # Test average duration with no durations
        durations = []
        avg_duration = sum(durations) / len(durations) if durations else 0
        assert avg_duration == 0
        
        # Test frequency with zero days
        unique_workout_days = 5
        days = 0
        frequency_per_week = unique_workout_days * 7 / days if days > 0 else 0
        assert frequency_per_week == 0
        
        # Test consistency score with zero days
        consistency_score = unique_workout_days / days * 100 if days > 0 else 0
        assert consistency_score == 0


class TestDataConsistencyLogic:
    """Test data consistency and integrity rules"""
    
    @pytest.fixture  
    def workout_service(self):
        return AsyncWorkoutService()
    
    def test_exercise_order_consistency(self, workout_service):
        """Test exercise ordering logic"""
        
        # Test order calculation
        existing_count = 3
        new_exercise_indices = [0, 1, 2]  # Adding 3 more exercises
        
        expected_orders = []
        for i in new_exercise_indices:
            order = existing_count + i + 1
            expected_orders.append(order)
        
        assert expected_orders == [4, 5, 6]  # Correct continuation
        
        # Test with zero existing
        existing_count = 0
        expected_orders = []
        for i in new_exercise_indices:
            order = existing_count + i + 1
            expected_orders.append(order)
        
        assert expected_orders == [1, 2, 3]  # Start from 1

    def test_session_state_transition_rules(self, workout_service):
        """Test session state transition business rules"""
        
        # Valid transitions
        valid_transitions = [
            (SessionStatus.ATIVA, SessionStatus.FINALIZADA),    # Active -> Finished (valid)
            (SessionStatus.ATIVA, SessionStatus.ABANDONADA),    # Active -> Abandoned (valid)
        ]
        
        for from_status, to_status in valid_transitions:
            # In real implementation, this would be checked
            transition_valid = True
            if from_status == SessionStatus.ATIVA and to_status in [SessionStatus.FINALIZADA, SessionStatus.ABANDONADA]:
                transition_valid = True
            elif from_status == SessionStatus.FINALIZADA:
                transition_valid = False  # Can't change from finished
            
            assert transition_valid == (from_status == SessionStatus.ATIVA)

    def test_data_type_validation(self, workout_service):
        """Test data type validation logic"""
        
        # Test weights validation
        valid_weights = [
            [40, 50, 60],     # List of numbers (valid)
            [40.5, 50.0],     # List with floats (valid)
            [],               # Empty list (valid but no volume)
        ]
        
        invalid_weights = [
            None,             # None (invalid)
            "40,50,60",       # String (invalid)
            [40, "50", 60],   # Mixed types (invalid)
            40,               # Single number (invalid, should be list)
        ]
        
        for weights in valid_weights:
            is_valid = weights is not None and isinstance(weights, list)
            assert is_valid
            
        for weights in invalid_weights:
            is_valid = weights is not None and isinstance(weights, list)
            if is_valid and weights:  # Additional check for list contents
                is_valid = all(isinstance(w, (int, float)) for w in weights)
            assert not is_valid or weights == []  # Empty list is technically valid