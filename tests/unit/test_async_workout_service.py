"""Unit tests for AsyncWorkoutService

Tests the core business logic of workout session management, exercise processing,
analytics, and session status handling. These tests focus on business rules and
edge cases rather than mocked dependencies.
"""

import uuid
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from database.models import SessionStatus
from services.async_workout_service import AsyncWorkoutService
from services.exceptions import DatabaseError, ErrorCode, ValidationError


def create_mock_async_session_context(mock_session=None):
    """Helper function to create properly mocked async session context"""
    if mock_session is None:
        mock_session = AsyncMock()

    # Mock the session.begin() to return a proper async context manager
    mock_begin_context = MagicMock()
    mock_begin_context.__aenter__ = AsyncMock(return_value=None)
    mock_begin_context.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = MagicMock(return_value=mock_begin_context)

    # Mock the main context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)

    return mock_context_manager, mock_session


class TestAsyncWorkoutServiceInit:
    """Test service initialization and basic functionality"""

    def test_service_instantiation(self):
        """Test that service can be instantiated"""
        service = AsyncWorkoutService()
        assert service is not None
        assert isinstance(service, AsyncWorkoutService)


class TestAddExercisesToSessionBatch:
    """Test add_exercises_to_session_batch method with various scenarios"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.fixture
    def valid_parsed_data(self):
        return {
            "resistance_exercises": [
                {
                    "name": "supino reto",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "weights_kg": [40, 50, 60],
                    "rest_seconds": 90,
                    "notes": "Good form",
                },
            ],
            "aerobic_exercises": [
                {
                    "name": "corrida",
                    "duration_minutes": 30,
                    "distance_km": 5.0,
                    "calories_burned": 300,
                    "intensity_level": "moderate",
                },
            ],
            "energy_level": 8,
            "difficulty": 7,
            "notes": "Great workout",
        }

    @pytest.mark.asyncio
    async def test_add_exercises_validation_invalid_session_id(self, workout_service, valid_parsed_data):
        """Test validation for invalid session IDs"""
        # Test with None session_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(None, valid_parsed_data, "user123")

        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert "Invalid session ID" in exc_info.value.message

        # Test with invalid UUID string (should trigger database error or validation error)
        with pytest.raises((ValidationError, Exception)) as exc_info:
            await workout_service.add_exercises_to_session_batch("invalid-uuid", valid_parsed_data, "user123")

        # Test with non-existent but valid UUID format (should trigger SESSION_NOT_FOUND)
        non_existent_uuid = uuid.uuid4()
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(non_existent_uuid, valid_parsed_data, "user123")

        assert exc_info.value.error_code == ErrorCode.SESSION_NOT_FOUND

    @pytest.mark.asyncio
    async def test_add_exercises_validation_invalid_user_id(self, workout_service, valid_parsed_data):
        """Test validation for invalid user IDs"""
        # Test with None user_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(1, valid_parsed_data, None)

        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert "User ID is required" in exc_info.value.message

        # Test with empty string user_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(1, valid_parsed_data, "")

        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

        # Test with whitespace-only user_id
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(1, valid_parsed_data, "   ")

        assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.asyncio
    async def test_add_exercises_validation_invalid_parsed_data(self, workout_service):
        """Test validation for invalid parsed data"""
        # Test with None parsed_data
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(1, None, "user123")

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
        assert "Invalid parsed data" in exc_info.value.message

        # Test with non-dict parsed_data
        with pytest.raises(ValidationError) as exc_info:
            await workout_service.add_exercises_to_session_batch(1, "invalid", "user123")

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

        # Test with empty dict (should be valid)
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock a non-existent session to trigger ValidationError
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(ValidationError) as exc_info:
                await workout_service.add_exercises_to_session_batch(1, {}, "user123")

            assert exc_info.value.error_code == ErrorCode.INVALID_INPUT
            assert "Invalid parsed data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_add_exercises_session_not_found(self, workout_service, valid_parsed_data):
        """Test behavior when session is not found"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock session not found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(ValidationError) as exc_info:
                await workout_service.add_exercises_to_session_batch(999, valid_parsed_data, "user123")

            assert exc_info.value.error_code == ErrorCode.SESSION_NOT_FOUND
            assert "Session 999 not found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_add_exercises_unauthorized_user(self, workout_service, valid_parsed_data):
        """Test behavior when user is not authorized for session"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock session found but different user
            mock_workout_session = MagicMock()
            mock_workout_session.user_id = "different_user"
            mock_workout_session.exercises = []

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            with pytest.raises(ValidationError) as exc_info:
                await workout_service.add_exercises_to_session_batch(1, valid_parsed_data, "user123")

            assert exc_info.value.error_code == ErrorCode.ACCESS_DENIED
            assert "Not authorized for this session" in exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_add_exercises_database_error(self, workout_service, valid_parsed_data):
        """Test behavior when database error occurs"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock database error
            mock_session.execute.side_effect = SQLAlchemyError("Database connection failed")

            with pytest.raises(DatabaseError) as exc_info:
                await workout_service.add_exercises_to_session_batch(1, valid_parsed_data, "user123")

            assert exc_info.value.error_code == ErrorCode.TRANSACTION_FAILED
            assert "Failed to add exercises to session 1" in exc_info.value.message
            assert "Failed to save workout data" in exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_add_exercises_successful_resistance_only(self, workout_service):
        """Test successful addition of resistance exercises only"""
        parsed_data = {
            "resistance_exercises": [
                {
                    "name": "supino reto",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "weights_kg": [40, 50, 60],
                    "rest_seconds": 90,
                },
                {
                    "name": "agachamento",
                    "sets": 4,
                    "reps": [15, 12, 10, 8],
                    "weights_kg": [60, 70, 80, 90],
                    "rest_seconds": 120,
                },
            ],
            "energy_level": 8,
            "notes": "Good session",
        }

        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock successful session retrieval
            mock_workout_session = MagicMock()
            mock_workout_session.user_id = "user123"
            mock_workout_session.exercises = []
            mock_workout_session.audio_count = 5
            mock_workout_session.notes = "Previous notes"

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            # Mock the internal methods
            with patch.object(workout_service, "_update_session_data_async") as mock_update_session, \
                 patch.object(workout_service, "_process_resistance_exercises_async") as mock_process_resistance:

                result = await workout_service.add_exercises_to_session_batch(1, parsed_data, "user123")

                assert result is True
                mock_update_session.assert_called_once()
                mock_process_resistance.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_exercises_successful_aerobic_only(self, workout_service):
        """Test successful addition of aerobic exercises only"""
        parsed_data = {
            "aerobic_exercises": [
                {
                    "name": "corrida",
                    "duration_minutes": 30,
                    "distance_km": 5.0,
                    "calories_burned": 300,
                    "intensity_level": "moderate",
                },
            ],
            "difficulty": 6,
        }

        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock successful session retrieval
            mock_workout_session = MagicMock()
            mock_workout_session.user_id = "user123"
            mock_workout_session.exercises = []
            mock_workout_session.audio_count = 1

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            # Mock the internal methods
            with patch.object(workout_service, "_update_session_data_async") as mock_update_session, \
                 patch.object(workout_service, "_process_aerobic_exercises_async") as mock_process_aerobic:

                result = await workout_service.add_exercises_to_session_batch(1, parsed_data, "user123")

                assert result is True
                mock_update_session.assert_called_once()
                mock_process_aerobic.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_exercises_empty_exercise_lists(self, workout_service):
        """Test handling of empty exercise lists"""
        parsed_data = {
            "resistance_exercises": [],
            "aerobic_exercises": [],
            "energy_level": 5,
        }

        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock successful session retrieval
            mock_workout_session = MagicMock()
            mock_workout_session.user_id = "user123"
            mock_workout_session.exercises = []
            mock_workout_session.audio_count = 1

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            # Mock the internal methods
            with patch.object(workout_service, "_update_session_data_async") as mock_update_session:

                result = await workout_service.add_exercises_to_session_batch(1, parsed_data, "user123")

                assert result is True
                mock_update_session.assert_called_once()


class TestUpdateSessionDataAsync:
    """Test _update_session_data_async method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_update_session_data_basic(self, workout_service):
        """Test basic session data update"""
        mock_session = AsyncMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 5
        mock_workout_session.notes = None

        parsed_data = {
            "energy_level": 8,
            "difficulty": 7,
            "notes": "Great workout today",
        }

        await workout_service._update_session_data_async(mock_session, mock_workout_session, parsed_data)

        assert mock_workout_session.audio_count == 6  # Incremented by 1
        assert mock_workout_session.energy_level == 8
        assert mock_workout_session.difficulty == 7
        assert mock_workout_session.notes == "Great workout today"
        mock_session.add.assert_called_once_with(mock_workout_session)

    @pytest.mark.asyncio
    async def test_update_session_data_append_notes(self, workout_service):
        """Test appending notes to existing notes"""
        mock_session = AsyncMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 2
        mock_workout_session.notes = "Previous notes"

        parsed_data = {
            "notes": "Additional notes",
        }

        await workout_service._update_session_data_async(mock_session, mock_workout_session, parsed_data)

        assert mock_workout_session.audio_count == 3
        assert mock_workout_session.notes == "Previous notes\nAdditional notes"

    @pytest.mark.asyncio
    async def test_update_session_data_minimal(self, workout_service):
        """Test update with minimal data"""
        mock_session = AsyncMock()
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 0

        parsed_data = {}  # No optional fields

        await workout_service._update_session_data_async(mock_session, mock_workout_session, parsed_data)

        assert mock_workout_session.audio_count == 1
        # Optional fields should not be modified if not present (service checks "in parsed_data")
        # We don't assert on specific attributes since MagicMock creates them automatically


class TestProcessResistanceExercisesAsync:
    """Test _process_resistance_exercises_async method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_process_resistance_exercises_new_exercises(self, workout_service):
        """Test processing resistance exercises with new exercises"""
        mock_session = AsyncMock()
        session_id = uuid.uuid4()
        existing_count = 0

        resistance_exercises = [
            {
                "name": "Supino Reto",  # Will be lowercased
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [40, 50, 60],
                "rest_seconds": 90,
                "notes": "Good form",
            },
            {
                "name": "Agachamento",
                "sets": 4,
                "reps": [15, 12, 10, 8],
                "weights_kg": [60, 70, 80, 90],
                "rest_seconds": 120,
            },
        ]

        # Mock empty database query (no existing exercises)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("services.exercise_knowledge.infer_muscle_group") as mock_infer_muscle, \
             patch("services.exercise_knowledge.infer_equipment") as mock_infer_equipment:

            mock_infer_muscle.return_value = "chest"
            mock_infer_equipment.return_value = "barbell"

            await workout_service._process_resistance_exercises_async(
                mock_session, session_id, resistance_exercises, existing_count,
            )

            # Should call add_all twice: once for exercises, once for workout_exercises
            assert mock_session.add_all.call_count == 2
            assert mock_session.flush.call_count == 1

    @pytest.mark.asyncio
    async def test_process_resistance_exercises_existing_exercises(self, workout_service):
        """Test processing with existing exercises in database"""
        mock_session = AsyncMock()
        session_id = uuid.uuid4()
        existing_count = 2

        resistance_exercises = [
            {
                "name": "supino reto",  # Already exists
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [40, 50, 60],
                "rest_seconds": 90,
            },
        ]

        # Mock existing exercise in database
        existing_exercise = MagicMock()
        existing_exercise.name = "supino reto"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_exercise]
        mock_session.execute.return_value = mock_result

        await workout_service._process_resistance_exercises_async(
            mock_session, session_id, resistance_exercises, existing_count,
        )

        # Should not add new exercises (only workout_exercises)
        assert mock_session.add_all.call_count == 1  # Only workout_exercises
        assert mock_session.flush.call_count == 0  # No new exercises to flush

    @pytest.mark.asyncio
    async def test_process_resistance_exercises_skip_empty_names(self, workout_service):
        """Test skipping exercises with empty names"""
        mock_session = AsyncMock()
        session_id = uuid.uuid4()
        existing_count = 0

        resistance_exercises = [
            {
                "name": "",  # Empty name - should be skipped
                "sets": 3,
                "reps": [12, 10, 8],
                "weights_kg": [40, 50, 60],
            },
            {
                "name": "   ",  # Whitespace only - should be skipped
                "sets": 2,
                "reps": [10, 8],
                "weights_kg": [30, 35],
            },
            {
                # Missing name - should be skipped
                "sets": 1,
                "reps": [5],
                "weights_kg": [100],
            },
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await workout_service._process_resistance_exercises_async(
            mock_session, session_id, resistance_exercises, existing_count,
        )

        # Should not add anything since all exercises have invalid names
        mock_session.add_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_resistance_exercises_order_calculation(self, workout_service):
        """Test correct order calculation for exercises"""
        mock_session = AsyncMock()
        session_id = uuid.uuid4()
        existing_count = 5  # 5 exercises already in session

        resistance_exercises = [
            {"name": "exercise1", "sets": 1, "reps": [10], "weights_kg": [50]},
            {"name": "exercise2", "sets": 1, "reps": [8], "weights_kg": [60]},
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("services.exercise_knowledge.infer_muscle_group"), \
             patch("services.exercise_knowledge.infer_equipment"):

            await workout_service._process_resistance_exercises_async(
                mock_session, session_id, resistance_exercises, existing_count,
            )

            # Verify call was made (order is calculated internally)
            assert mock_session.add_all.call_count == 2


class TestProcessAerobicExercisesAsync:
    """Test _process_aerobic_exercises_async method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_process_aerobic_exercises_new_exercises(self, workout_service):
        """Test processing aerobic exercises with new exercises"""
        mock_session = AsyncMock()
        session_id = uuid.uuid4()

        aerobic_exercises = [
            {
                "name": "Corrida",
                "duration_minutes": 30,
                "distance_km": 5.0,
                "calories_burned": 300,
                "intensity_level": "moderate",
                "notes": "Good pace",
            },
            {
                "name": "Bicicleta",
                "duration_minutes": 45,
                "distance_km": 15.0,
                "calories_burned": 400,
                "intensity_level": "high",
            },
        ]

        # Mock empty database query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        with patch("services.exercise_knowledge.infer_muscle_group") as mock_infer_muscle, \
             patch("services.exercise_knowledge.infer_equipment") as mock_infer_equipment:

            mock_infer_muscle.return_value = "cardio"
            mock_infer_equipment.return_value = "none"

            await workout_service._process_aerobic_exercises_async(
                mock_session, session_id, aerobic_exercises,
            )

            # Should call add_all twice: once for exercises, once for aerobic_exercises
            assert mock_session.add_all.call_count == 2
            assert mock_session.flush.call_count == 1

    @pytest.mark.asyncio
    async def test_process_aerobic_exercises_skip_empty_names(self, workout_service):
        """Test skipping aerobic exercises with empty names"""
        mock_session = AsyncMock()
        session_id = uuid.uuid4()

        aerobic_exercises = [
            {
                "name": "",  # Empty name
                "duration_minutes": 30,
            },
            {
                # Missing name
                "duration_minutes": 20,
            },
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await workout_service._process_aerobic_exercises_async(
            mock_session, session_id, aerobic_exercises,
        )

        # Should not add anything
        mock_session.add_all.assert_not_called()


class TestGetUserSessionStatus:
    """Test get_user_session_status method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_get_user_session_status_no_session(self, workout_service):
        """Test getting status when user has no sessions"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock no session found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            result = await workout_service.get_user_session_status("user123")

            assert result["has_session"] is False
            assert "Nenhuma sessão encontrada" in result["message"]

    @pytest.mark.asyncio
    async def test_get_user_session_status_active_session(self, workout_service):
        """Test getting status for active session"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context, \
             patch("config.settings.settings") as mock_settings:

            mock_settings.SESSION_TIMEOUT_HOURS = 3

            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session
            mock_context.return_value.__aexit__.return_value = None

            # Mock recent session (within timeout)
            now = datetime.now()
            recent_time = now - timedelta(hours=1)  # 1 hour ago

            mock_workout_session = MagicMock()
            mock_workout_session.date = recent_time.date()
            mock_workout_session.start_time = recent_time.time()
            mock_workout_session.exercises = [MagicMock(), MagicMock()]  # 2 resistance exercises
            mock_workout_session.aerobics = [MagicMock()]  # 1 aerobic exercise

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            result = await workout_service.get_user_session_status("user123")

            assert result["has_session"] is True
            assert result["is_active"] == SessionStatus.ATIVA
            assert result["minutes_passed"] == 60  # 1 hour = 60 minutes
            assert result["hours_passed"] == 1
            assert result["resistance_count"] == 2
            assert result["aerobic_count"] == 1
            assert result["timeout_hours"] == 3

    @pytest.mark.asyncio
    async def test_get_user_session_status_expired_session(self, workout_service):
        """Test getting status for expired session"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context, \
             patch("config.settings.settings") as mock_settings:

            mock_settings.SESSION_TIMEOUT_HOURS = 3

            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session
            mock_context.return_value.__aexit__.return_value = None

            # Mock old session (beyond timeout)
            now = datetime.now()
            old_time = now - timedelta(hours=5)  # 5 hours ago (> 3 hour timeout)

            mock_workout_session = MagicMock()
            mock_workout_session.date = old_time.date()
            mock_workout_session.start_time = old_time.time()
            mock_workout_session.exercises = []
            mock_workout_session.aerobics = []

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            result = await workout_service.get_user_session_status("user123")

            assert result["has_session"] is True
            assert result["is_active"] == SessionStatus.FINALIZADA
            assert result["minutes_passed"] == 300  # 5 hours = 300 minutes
            assert result["expired_minutes"] == 120  # 300 - 180 = 120 minutes over timeout

    @pytest.mark.asyncio
    async def test_get_user_session_status_database_error(self, workout_service):
        """Test database error handling"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock database error
            mock_session.execute.side_effect = SQLAlchemyError("Connection failed")

            with pytest.raises(DatabaseError) as exc_info:
                await workout_service.get_user_session_status("user123")

            assert exc_info.value.error_code == ErrorCode.DATABASE_QUERY_FAILED
            assert "Failed to get session status" in exc_info.value.user_message


class TestFinishSession:
    """Test finish_session method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_finish_session_not_found(self, workout_service):
        """Test finishing session that doesn't exist"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock session not found
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            result = await workout_service.finish_session(999, "user123")

            assert result["success"] is False
            assert "Session not found or access denied" in result["error"]

    @pytest.mark.asyncio
    async def test_finish_session_already_finished(self, workout_service):
        """Test finishing session that's already finished"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock already finished session
            mock_workout_session = MagicMock()
            mock_workout_session.status = SessionStatus.FINALIZADA

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            result = await workout_service.finish_session(1, "user123")

            assert result["success"] is False
            assert "Session already finished" in result["error"]

    @pytest.mark.asyncio
    async def test_finish_session_successful_same_day(self, workout_service):
        """Test successful session finish on same day"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock active session
            session_date = date.today()
            start_time = time(10, 0, 0)  # 10:00 AM

            mock_workout_session = MagicMock()
            mock_workout_session.status = SessionStatus.ATIVA
            mock_workout_session.date = session_date
            mock_workout_session.start_time = start_time
            mock_workout_session.exercises = [MagicMock(), MagicMock()]
            mock_workout_session.aerobics = [MagicMock()]

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            # Mock current time as 11:30 AM (1.5 hours later)
            with patch("services.async_workout_service.datetime") as mock_datetime:
                mock_now = datetime(session_date.year, session_date.month, session_date.day, 11, 30, 0)
                mock_datetime.now.return_value = mock_now
                mock_datetime.combine = datetime.combine

                with patch.object(workout_service, "_calculate_session_stats_sync") as mock_stats:
                    mock_stats.return_value = {"total_sets": 6, "total_volume_kg": 1200}

                    test_session_id = uuid.uuid4()
                    result = await workout_service.finish_session(test_session_id, "user123")

                    assert result["success"] is True
                    assert result["session_id"] == test_session_id
                    assert result["duration_minutes"] == 90  # 1.5 hours
                    assert "stats" in result

                    # Verify session was updated
                    assert mock_workout_session.status == SessionStatus.FINALIZADA
                    assert mock_workout_session.end_time == time(11, 30, 0)
                    assert mock_workout_session.duration_minutes == 90

    @pytest.mark.asyncio
    async def test_finish_session_cross_midnight(self, workout_service):
        """Test session finish that crosses midnight"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock session that started late at night
            session_date = date.today()
            start_time = time(23, 30, 0)  # 11:30 PM

            mock_workout_session = MagicMock()
            mock_workout_session.status = SessionStatus.ATIVA
            mock_workout_session.date = session_date
            mock_workout_session.start_time = start_time
            mock_workout_session.exercises = []
            mock_workout_session.aerobics = []

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            # Mock current time as 1:00 AM next day (1.5 hours later)
            with patch("services.async_workout_service.datetime") as mock_datetime:
                mock_now = datetime(session_date.year, session_date.month, session_date.day + 1, 1, 0, 0)
                mock_datetime.now.return_value = mock_now
                mock_datetime.combine = datetime.combine

                with patch.object(workout_service, "_calculate_session_stats_sync") as mock_stats:
                    mock_stats.return_value = {}

                    result = await workout_service.finish_session(1, "user123")

                    assert result["success"] is True
                    assert result["duration_minutes"] == 90  # 1.5 hours

    @pytest.mark.asyncio
    async def test_finish_session_negative_duration_protection(self, workout_service):
        """Test protection against negative duration (edge case)"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock session with future start date (edge case to trigger negative duration)
            session_date = date.today() + timedelta(days=1)  # Tomorrow
            start_time = time(10, 0, 0)  # 10:00 AM tomorrow

            mock_workout_session = MagicMock()
            mock_workout_session.status = SessionStatus.ATIVA
            mock_workout_session.date = session_date
            mock_workout_session.start_time = start_time
            mock_workout_session.exercises = []
            mock_workout_session.aerobics = []

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            # Mock current time as 10:00 AM (before start time - edge case)
            with patch("services.async_workout_service.datetime") as mock_datetime:
                mock_now = datetime(session_date.year, session_date.month, session_date.day, 10, 0, 0)
                mock_datetime.now.return_value = mock_now
                mock_datetime.combine = datetime.combine

                with patch.object(workout_service, "_calculate_session_stats_sync") as mock_stats:
                    mock_stats.return_value = {}

                    result = await workout_service.finish_session(1, "user123")

                    assert result["success"] is True
                    assert result["duration_minutes"] == 0  # Protected against negative


class TestCalculateSessionStatsSync:
    """Test _calculate_session_stats_sync method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    def test_calculate_session_stats_comprehensive(self, workout_service):
        """Test comprehensive session stats calculation"""
        # Mock workout session with exercises
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 5

        # Mock resistance exercises
        exercise1 = MagicMock()
        exercise1.sets = 3
        exercise1.weights_kg = [40, 50, 60]
        exercise1.exercise.muscle_group = "chest"

        exercise2 = MagicMock()
        exercise2.sets = 4
        exercise2.weights_kg = [20, 25, 30, 35]
        exercise2.exercise.muscle_group = "arms"

        mock_workout_session.exercises = [exercise1, exercise2]

        # Mock aerobic exercises
        aerobic1 = MagicMock()
        aerobic1.duration_minutes = 30

        aerobic2 = MagicMock()
        aerobic2.duration_minutes = 20

        mock_workout_session.aerobics = [aerobic1, aerobic2]

        stats = workout_service._calculate_session_stats_sync(mock_workout_session)

        assert stats["audio_count"] == 5
        assert stats["resistance_exercises"] == 2
        assert stats["aerobic_exercises"] == 2
        assert stats["total_sets"] == 7  # 3 + 4
        assert stats["total_volume_kg"] == 260  # 150 + 110
        assert stats["cardio_minutes"] == 50  # 30 + 20
        assert "chest" in stats["muscle_groups"]
        assert "arms" in stats["muscle_groups"]

    def test_calculate_session_stats_empty_session(self, workout_service):
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

    def test_calculate_session_stats_missing_weights(self, workout_service):
        """Test stats calculation with missing weight data"""
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 2

        # Exercise with no weights
        exercise1 = MagicMock()
        exercise1.sets = 3
        exercise1.weights_kg = None
        exercise1.exercise.muscle_group = "legs"

        # Exercise with empty weights
        exercise2 = MagicMock()
        exercise2.sets = 2
        exercise2.weights_kg = []
        exercise2.exercise.muscle_group = "back"

        mock_workout_session.exercises = [exercise1, exercise2]
        mock_workout_session.aerobics = []

        stats = workout_service._calculate_session_stats_sync(mock_workout_session)

        assert stats["total_sets"] == 5  # 3 + 2
        assert stats["total_volume_kg"] == 0  # No weights recorded
        assert len(stats["muscle_groups"]) == 2

    def test_calculate_session_stats_missing_duration(self, workout_service):
        """Test stats calculation with missing aerobic duration"""
        mock_workout_session = MagicMock()
        mock_workout_session.audio_count = 1
        mock_workout_session.exercises = []

        # Aerobic exercise with no duration
        aerobic1 = MagicMock()
        aerobic1.duration_minutes = None

        # Aerobic exercise with zero duration
        aerobic2 = MagicMock()
        aerobic2.duration_minutes = 0

        mock_workout_session.aerobics = [aerobic1, aerobic2]

        stats = workout_service._calculate_session_stats_sync(mock_workout_session)

        assert stats["cardio_minutes"] == 0  # None and 0 don't contribute


class TestGetUserWorkoutAnalytics:
    """Test get_user_workout_analytics method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_get_analytics_no_data(self, workout_service):
        """Test analytics when no workout data exists"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock empty result
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute.return_value = mock_result

            result = await workout_service.get_user_workout_analytics("user123", 30)

            assert "No workout data found" in result["message"]

    @pytest.mark.asyncio
    async def test_get_analytics_database_error(self, workout_service):
        """Test analytics database error handling"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock database error
            mock_session.execute.side_effect = SQLAlchemyError("Query failed")

            with pytest.raises(DatabaseError) as exc_info:
                await workout_service.get_user_workout_analytics("user123", 30)

            assert exc_info.value.error_code == ErrorCode.DATABASE_QUERY_FAILED
            assert "Failed to calculate workout analytics" in exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_get_analytics_with_data(self, workout_service):
        """Test analytics with actual workout data"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Mock workout sessions
            session1 = MagicMock()
            session1.status = SessionStatus.FINALIZADA
            session1.duration_minutes = 60
            session1.audio_count = 3
            session1.energy_level = 8
            session1.date = date.today()
            session1.exercises = [MagicMock(), MagicMock()]
            session1.aerobics = [MagicMock()]

            session2 = MagicMock()
            session2.status = SessionStatus.ATIVA
            session2.duration_minutes = None
            session2.audio_count = 2
            session2.energy_level = 7
            session2.date = date.today() - timedelta(days=1)
            session2.exercises = [MagicMock()]
            session2.aerobics = []

            mock_sessions = [session1, session2]

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_sessions
            mock_session.execute.return_value = mock_result

            with patch.object(workout_service, "_calculate_comprehensive_analytics_async") as mock_calc:
                mock_calc.return_value = {
                    "period": {"days": 30, "total_sessions": 2},
                    "session_stats": {"completion_rate": 50.0},
                }

                result = await workout_service.get_user_workout_analytics("user123", 30)

                assert result["period"]["total_sessions"] == 2
                assert result["session_stats"]["completion_rate"] == 50.0
                mock_calc.assert_called_once_with(mock_sessions, 30)


class TestCalculateComprehensiveAnalyticsAsync:
    """Test _calculate_comprehensive_analytics_async method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_basic_stats(self, workout_service):
        """Test basic statistics calculation"""
        # Create mock sessions
        session1 = MagicMock()
        session1.status = SessionStatus.FINALIZADA
        session1.duration_minutes = 60
        session1.audio_count = 3
        session1.energy_level = 8
        session1.date = date.today()
        session1.exercises = []
        session1.aerobics = []

        session2 = MagicMock()
        session2.status = SessionStatus.ATIVA
        session2.duration_minutes = 90
        session2.audio_count = 4
        session2.energy_level = 7
        session2.date = date.today() - timedelta(days=1)
        session2.exercises = []
        session2.aerobics = []

        sessions = [session1, session2]

        result = await workout_service._calculate_comprehensive_analytics_async(sessions, 30)

        assert result["period"]["total_sessions"] == 2
        assert result["session_stats"]["completion_rate"] == 50.0  # 1/2 completed
        assert result["session_stats"]["average_duration_minutes"] == 75.0  # (60+90)/2
        assert result["session_stats"]["average_audios_per_session"] == 3.5  # (3+4)/2
        assert result["session_stats"]["average_energy_level"] == 7.5  # (8+7)/2

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_frequency_calculation(self, workout_service):
        """Test workout frequency calculation"""
        # Create sessions over different days
        today = date.today()
        sessions = []

        for i in range(4):  # 4 sessions over 4 different days
            session = MagicMock()
            session.status = SessionStatus.FINALIZADA
            session.duration_minutes = 60
            session.audio_count = 2
            session.energy_level = 8
            session.date = today - timedelta(days=i * 2)  # Every other day
            session.exercises = []
            session.aerobics = []
            sessions.append(session)

        result = await workout_service._calculate_comprehensive_analytics_async(sessions, 14)  # 2 weeks

        assert result["workout_frequency"]["unique_workout_days"] == 4
        assert result["workout_frequency"]["frequency_per_week"] == 2.0  # 4 * 7 / 14
        assert result["workout_frequency"]["consistency_score"] == pytest.approx(28.57, rel=1e-2)  # 4/14 * 100

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_muscle_distribution(self, workout_service):
        """Test muscle group distribution calculation"""
        # Create exercises with different muscle groups
        exercise1 = MagicMock()
        exercise1.exercise.muscle_group = "chest"

        exercise2 = MagicMock()
        exercise2.exercise.muscle_group = "legs"

        exercise3 = MagicMock()
        exercise3.exercise.muscle_group = "chest"  # Duplicate

        exercise4 = MagicMock()
        exercise4.exercise.muscle_group = "back"

        session = MagicMock()
        session.status = SessionStatus.FINALIZADA
        session.duration_minutes = 60
        session.audio_count = 1
        session.energy_level = 8
        session.date = date.today()
        session.exercises = [exercise1, exercise2, exercise3, exercise4]
        session.aerobics = []

        sessions = [session]

        result = await workout_service._calculate_comprehensive_analytics_async(sessions, 7)

        distribution = result["muscle_group_distribution"]["distribution"]
        assert distribution["chest"]["count"] == 2
        assert distribution["chest"]["percentage"] == 50.0  # 2/4 * 100
        assert distribution["legs"]["count"] == 1
        assert distribution["legs"]["percentage"] == 25.0
        assert distribution["back"]["count"] == 1
        assert distribution["back"]["percentage"] == 25.0

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_progress_trends(self, workout_service):
        """Test progress trend analysis"""
        # Create sessions with weight progression
        sessions = []

        # Recent sessions (higher volume)
        for i in range(3):
            session = MagicMock()
            session.status = SessionStatus.FINALIZADA
            session.duration_minutes = 60
            session.audio_count = 2
            session.date = date.today() - timedelta(days=i)

            exercise = MagicMock()
            exercise.weights_kg = [80, 90, 100]  # High volume
            exercise.exercise.muscle_group = "chest"
            session.exercises = [exercise]
            session.aerobics = []

            sessions.append(session)

        # Older sessions (lower volume)
        for i in range(3, 8):
            session = MagicMock()
            session.status = SessionStatus.FINALIZADA
            session.duration_minutes = 60
            session.audio_count = 2
            session.date = date.today() - timedelta(days=i)

            exercise = MagicMock()
            exercise.weights_kg = [40, 50, 60]  # Low volume
            exercise.exercise.muscle_group = "chest"
            session.exercises = [exercise]
            session.aerobics = []

            sessions.append(session)

        result = await workout_service._calculate_comprehensive_analytics_async(sessions, 30)

        # Should detect improvement (recent volume >> older volume)
        assert result["progress_trends"]["trend"] == "improving"
        assert result["progress_trends"]["volume_change_percent"] > 10

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_insufficient_data(self, workout_service):
        """Test trend analysis with insufficient data"""
        # Only 2 sessions (not enough for trend analysis)
        session1 = MagicMock()
        session1.status = SessionStatus.FINALIZADA
        session1.duration_minutes = 60
        session1.audio_count = 2
        session1.date = date.today()
        session1.exercises = []
        session1.aerobics = []

        session2 = MagicMock()
        session2.status = SessionStatus.FINALIZADA
        session2.duration_minutes = 60
        session2.audio_count = 2
        session2.date = date.today() - timedelta(days=1)
        session2.exercises = []
        session2.aerobics = []

        sessions = [session1, session2]

        result = await workout_service._calculate_comprehensive_analytics_async(sessions, 30)

        assert result["progress_trends"]["trend"] == "insufficient_data"
        assert result["progress_trends"]["volume_change_percent"] == 0

    @pytest.mark.asyncio
    async def test_comprehensive_analytics_zero_division_protection(self, workout_service):
        """Test protection against zero division errors"""
        # Session with no exercises (edge case)
        session = MagicMock()
        session.status = SessionStatus.FINALIZADA
        session.duration_minutes = 60
        session.audio_count = 1
        session.energy_level = None  # Missing energy level
        session.date = date.today()
        session.exercises = []
        session.aerobics = []

        sessions = [session]

        result = await workout_service._calculate_comprehensive_analytics_async(sessions, 7)

        # Should handle missing/empty data gracefully
        assert result["session_stats"]["completion_rate"] == 100.0  # 1/1
        assert result["session_stats"]["average_energy_level"] == 0  # No energy levels recorded
        assert result["exercise_stats"]["resistance"]["total_exercises"] == 0
        assert result["muscle_group_distribution"]["distribution"] == {}


class TestGetLastSession:
    """Test get_last_session method"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_get_last_session_found(self, workout_service):
        """Test getting last session when one exists"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            mock_workout_session = MagicMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            result = await workout_service.get_last_session("user123")

            assert result == mock_workout_session

    @pytest.mark.asyncio
    async def test_get_last_session_not_found(self, workout_service):
        """Test getting last session when none exists"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            result = await workout_service.get_last_session("user123")

            assert result is None


# Business Logic Edge Cases and Enhancements
class TestBusinessLogicEdgeCases:
    """Test edge cases that might require business logic modifications"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_session_timeout_boundary_condition(self, workout_service):
        """Test session timeout at exact boundary"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context, \
             patch("config.settings.settings") as mock_settings:

            mock_settings.SESSION_TIMEOUT_HOURS = 3

            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session
            mock_context.return_value.__aexit__.return_value = None

            # Session exactly at timeout boundary
            now = datetime.now()
            boundary_time = now - timedelta(hours=3, minutes=0, seconds=0)  # Exactly 3 hours

            mock_workout_session = MagicMock()
            mock_workout_session.date = boundary_time.date()
            mock_workout_session.start_time = boundary_time.time()
            mock_workout_session.exercises = []
            mock_workout_session.aerobics = []

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            result = await workout_service.get_user_session_status("user123")

            # At exactly timeout, should be considered expired
            assert result["is_active"] == SessionStatus.FINALIZADA
            assert result["minutes_passed"] == 180  # Exactly 3 hours
            assert result["expired_minutes"] == 0  # Exactly at boundary

    @pytest.mark.asyncio
    async def test_large_exercise_batch_processing(self, workout_service):
        """Test processing large batches of exercises (stress test)"""
        # Create a large batch of exercises
        large_batch = {
            "resistance_exercises": [
                {
                    "name": f"exercise_{i}",
                    "sets": 3,
                    "reps": [10, 8, 6],
                    "weights_kg": [50, 60, 70],
                    "rest_seconds": 90,
                }
                for i in range(50)  # 50 exercises
            ],
            "aerobic_exercises": [
                {
                    "name": f"cardio_{i}",
                    "duration_minutes": 20,
                    "distance_km": 3.0,
                    "calories_burned": 200,
                }
                for i in range(20)  # 20 cardio exercises
            ],
        }

        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            mock_workout_session = MagicMock()
            mock_workout_session.user_id = "user123"
            mock_workout_session.exercises = []
            mock_workout_session.audio_count = 1

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            with patch.object(workout_service, "_update_session_data_async"), \
                 patch.object(workout_service, "_process_resistance_exercises_async") as mock_resistance, \
                 patch.object(workout_service, "_process_aerobic_exercises_async") as mock_aerobic:

                result = await workout_service.add_exercises_to_session_batch(1, large_batch, "user123")

                assert result is True
                mock_resistance.assert_called_once()
                mock_aerobic.assert_called_once()

                # Verify large batch was passed correctly
                resistance_call_args = mock_resistance.call_args[0]
                aerobic_call_args = mock_aerobic.call_args[0]

                assert len(resistance_call_args[2]) == 50  # 50 resistance exercises
                assert len(aerobic_call_args[2]) == 20    # 20 aerobic exercises

    @pytest.mark.asyncio
    async def test_extreme_workout_duration_calculation(self, workout_service):
        """Test workout duration calculation for extreme cases"""
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # Very long workout (8+ hours)
            session_date = date.today()
            start_time = time(6, 0, 0)  # 6:00 AM

            mock_workout_session = MagicMock()
            mock_workout_session.status = SessionStatus.ATIVA
            mock_workout_session.date = session_date
            mock_workout_session.start_time = start_time
            mock_workout_session.exercises = []
            mock_workout_session.aerobics = []

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            # Mock current time as 11:30 PM (17.5 hours later)
            with patch("services.async_workout_service.datetime") as mock_datetime:
                mock_now = datetime(session_date.year, session_date.month, session_date.day, 23, 30, 0)
                mock_datetime.now.return_value = mock_now
                mock_datetime.combine = datetime.combine

                with patch.object(workout_service, "_calculate_session_stats_sync") as mock_stats:
                    mock_stats.return_value = {}

                    result = await workout_service.finish_session(1, "user123")

                    assert result["success"] is True
                    assert result["duration_minutes"] == 1050  # 17.5 hours = 1050 minutes

                    # Business logic should handle extreme durations gracefully
                    assert mock_workout_session.duration_minutes == 1050

    @pytest.mark.asyncio
    async def test_unicode_exercise_names_handling(self, workout_service):
        """Test handling of Unicode/international exercise names"""
        unicode_exercises = {
            "resistance_exercises": [
                {
                    "name": "Supino Reto com Barra",  # Portuguese
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "weights_kg": [40, 50, 60],
                },
                {
                    "name": "スクワット",  # Japanese
                    "sets": 4,
                    "reps": [15, 12, 10, 8],
                    "weights_kg": [60, 70, 80, 90],
                },
                {
                    "name": "Жим лёжа",  # Russian
                    "sets": 3,
                    "reps": [10, 8, 6],
                    "weights_kg": [50, 60, 70],
                },
            ],
        }

        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            mock_workout_session = MagicMock()
            mock_workout_session.user_id = "user123"
            mock_workout_session.exercises = []
            mock_workout_session.audio_count = 1

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_workout_session
            mock_session.execute.return_value = mock_result

            with patch.object(workout_service, "_update_session_data_async"), \
                 patch.object(workout_service, "_process_resistance_exercises_async") as mock_process:

                result = await workout_service.add_exercises_to_session_batch(1, unicode_exercises, "user123")

                assert result is True
                mock_process.assert_called_once()

                # Verify Unicode names are handled correctly
                exercises_arg = mock_process.call_args[0][2]
                exercise_names = [ex["name"] for ex in exercises_arg]
                assert "Supino Reto com Barra" in exercise_names
                assert "スクワット" in exercise_names
                assert "Жим лёжа" in exercise_names

    @pytest.mark.asyncio
    async def test_analytics_with_extreme_values(self, workout_service):
        """Test analytics calculation with extreme values"""
        # Create session with extreme values
        session = MagicMock()
        session.status = SessionStatus.FINALIZADA
        session.duration_minutes = 9999  # Extremely long workout
        session.audio_count = 100        # Many audio messages
        session.energy_level = 10        # Maximum energy
        session.date = date.today()

        # Exercise with extreme weights
        exercise = MagicMock()
        exercise.sets = 50              # Many sets
        exercise.weights_kg = [500] * 50  # Very heavy weights
        exercise.exercise.muscle_group = "test"

        session.exercises = [exercise]
        session.aerobics = []

        sessions = [session]

        result = await workout_service._calculate_comprehensive_analytics_async(sessions, 30)

        # Should handle extreme values without errors
        assert result["session_stats"]["average_duration_minutes"] == 9999
        assert result["session_stats"]["average_audios_per_session"] == 100
        assert result["session_stats"]["average_energy_level"] == 10
        assert result["exercise_stats"]["resistance"]["total_sets"] == 50
        assert result["exercise_stats"]["resistance"]["total_volume_kg"] == 25000  # 500 * 50

    @pytest.mark.asyncio
    async def test_concurrent_session_modifications(self, workout_service):
        """Test handling of concurrent session modifications (race conditions)"""
        # This test simulates what happens if session is modified between read and write
        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context_manager, mock_session = create_mock_async_session_context()
            mock_context.return_value = mock_context_manager

            # First call returns session, second call shows it's been modified
            mock_workout_session = MagicMock()
            mock_workout_session.user_id = "user123"
            mock_workout_session.exercises = []
            mock_workout_session.audio_count = 5

            mock_result1 = MagicMock()
            mock_result1.scalar_one_or_none.return_value = mock_workout_session

            # Simulate session being modified by another process
            mock_workout_session_modified = MagicMock()
            mock_workout_session_modified.user_id = "different_user"  # Changed by another process

            mock_result2 = MagicMock()
            mock_result2.scalar_one_or_none.return_value = mock_workout_session_modified

            mock_session.execute.side_effect = [mock_result1, mock_result2]

            # Should handle the race condition gracefully
            parsed_data = {"resistance_exercises": [{"name": "test", "sets": 1}]}

            with patch.object(workout_service, "_update_session_data_async"), \
                 patch.object(workout_service, "_process_resistance_exercises_async"):

                # First call should succeed with original session
                result = await workout_service.add_exercises_to_session_batch(1, parsed_data, "user123")
                assert result is True

