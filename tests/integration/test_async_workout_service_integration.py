"""Integration tests for AsyncWorkoutService

Tests the complete workflow integration between AsyncWorkoutService and the database,
covering real database operations, transaction handling, and data consistency.
These tests use real database connections and verify end-to-end functionality.
"""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from database.async_connection import get_async_session_context
from database.models import AerobicExercise, Exercise, ExerciseType, SessionStatus, WorkoutExercise, WorkoutSession
from services.async_workout_service import AsyncWorkoutService
from services.exceptions import DatabaseError, ValidationError


class TestAsyncWorkoutServiceDatabaseIntegration:
    """Test AsyncWorkoutService with real database operations"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.fixture
    async def test_user_session(self, populated_test_database):
        """Create a test user and workout session"""
        async with get_async_session_context() as session:
            # Create test session with unique user ID
            unique_suffix = datetime.now().microsecond
            user_id = f"test_user_{unique_suffix}"

            workout_session = WorkoutSession(
                user_id=user_id,
                date=date.today(),
                start_time=time(10, 0, 0),
                energy_level=7,
                notes="Test session",
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add(workout_session)
            await session.commit()
            await session.refresh(workout_session)

            return workout_session.session_id, user_id

    @pytest.mark.asyncio
    async def test_add_exercises_full_workflow(self, workout_service, test_user_session, populated_test_database):
        """Test complete exercise addition workflow with database"""
        session_id, user_id = test_user_session
        unique_suffix = datetime.now().microsecond

        parsed_data = {
            "resistance_exercises": [
                {
                    "name": f"supino reto com barra {unique_suffix}",
                    "sets": 3,
                    "reps": [12, 10, 8],
                    "weights_kg": [40, 50, 60],
                    "rest_seconds": 90,
                    "notes": "Good form today",
                },
                {
                    "name": f"agachamento livre {unique_suffix}",
                    "sets": 4,
                    "reps": [15, 12, 10, 8],
                    "weights_kg": [60, 70, 80, 90],
                    "rest_seconds": 120,
                },
            ],
            "aerobic_exercises": [
                {
                    "name": f"corrida na esteira {unique_suffix}",
                    "duration_minutes": 30,
                    "distance_km": 5.0,
                    "calories_burned": 300,
                    "intensity_level": "moderate",
                    "notes": "Steady pace",
                },
            ],
            "energy_level": 8,
            "difficulty": 7,
            "notes": "Excellent workout session",
        }

        # Add exercises to session
        result = await workout_service.add_exercises_to_session_batch(
            session_id, parsed_data, user_id,
        )

        assert result is True

        # Verify data was saved correctly
        async with get_async_session_context() as session:
            # Check session was updated
            stmt = select(WorkoutSession).where(WorkoutSession.session_id == session_id)
            result = await session.execute(stmt)
            updated_session = result.scalar_one()

            assert updated_session.audio_count == 2  # Was 1, now 2
            assert updated_session.energy_level == 8
            assert "Excellent workout session" in updated_session.notes

            # Check resistance exercises were created
            stmt = select(WorkoutExercise).where(WorkoutExercise.session_id == session_id)
            result = await session.execute(stmt)
            workout_exercises = result.scalars().all()

            assert len(workout_exercises) == 2

            # Verify exercise order
            exercise_by_order = {ex.order_in_workout: ex for ex in workout_exercises}
            assert 1 in exercise_by_order
            assert 2 in exercise_by_order

            # Check first exercise details
            first_exercise = exercise_by_order[1]
            assert first_exercise.sets == 3
            assert first_exercise.reps == [12, 10, 8]
            assert first_exercise.weights_kg == [40, 50, 60]
            assert first_exercise.rest_seconds == 90
            assert first_exercise.notes == "Good form today"

            # Check aerobic exercises were created
            stmt = select(AerobicExercise).where(AerobicExercise.session_id == session_id)
            result = await session.execute(stmt)
            aerobic_exercises = result.scalars().all()

            assert len(aerobic_exercises) == 1
            aerobic = aerobic_exercises[0]
            assert aerobic.duration_minutes == 30
            assert aerobic.distance_km == 5.0
            assert aerobic.calories_burned == 300
            assert aerobic.intensity_level == "moderate"
            assert aerobic.notes == "Steady pace"

            # Check exercises were created/found in catalog
            stmt = select(Exercise).where(Exercise.name.in_([
                f"supino reto com barra {unique_suffix}",
                f"agachamento livre {unique_suffix}",
                f"corrida na esteira {unique_suffix}",
            ]))
            result = await session.execute(stmt)
            exercises = result.scalars().all()

            assert len(exercises) >= 3  # At least our 3 exercises
            exercise_names = [ex.name for ex in exercises]
            assert f"supino reto com barra {unique_suffix}" in exercise_names
            assert f"agachamento livre {unique_suffix}" in exercise_names
            assert f"corrida na esteira {unique_suffix}" in exercise_names

    @pytest.mark.asyncio
    async def test_add_exercises_with_existing_exercises(self, workout_service, test_user_session, populated_test_database):
        """Test adding exercises when some already exist in catalog"""
        session_id, user_id = test_user_session
        unique_suffix = datetime.now().microsecond

        # First, add an exercise to the catalog
        async with get_async_session_context() as session:
            # Check if exercise already exists
            exercise_name = f"supino reto teste {unique_suffix}"
            stmt = select(Exercise).where(Exercise.name == exercise_name)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                existing_exercise = Exercise(
                    name=exercise_name,
                    type=ExerciseType.RESISTENCIA,
                    muscle_group="chest",
                    equipment="barbell",
                )
                session.add(existing_exercise)
                await session.commit()

        parsed_data = {
            "resistance_exercises": [
                {
                    "name": f"Supino Reto Teste {unique_suffix}",  # Should match existing (case insensitive)
                    "sets": 3,
                    "reps": [10, 8, 6],
                    "weights_kg": [50, 60, 70],
                },
                {
                    "name": f"novo exercicio {unique_suffix}_2",  # Unique name
                    "sets": 2,
                    "reps": [12, 10],
                    "weights_kg": [30, 35],
                },
            ],
        }

        result = await workout_service.add_exercises_to_session_batch(
            session_id, parsed_data, user_id,
        )

        assert result is True

        # Verify both exercises were linked correctly
        async with get_async_session_context() as session:
            stmt = (
                select(WorkoutExercise)
                .options(selectinload(WorkoutExercise.exercise))
                .where(WorkoutExercise.session_id == session_id)
            )
            result = await session.execute(stmt)
            workout_exercises = result.scalars().all()

            assert len(workout_exercises) == 2

            # Check that existing exercise was reused
            exercise_names = [we.exercise.name for we in workout_exercises]
            assert f"supino reto teste {unique_suffix}" in exercise_names
            # Check that new exercise was created (name contains "novo exercicio")
            assert any(f"novo exercicio {unique_suffix}_2" in name for name in exercise_names)

    @pytest.mark.asyncio
    async def test_add_exercises_transaction_rollback(self, workout_service, test_user_session, populated_test_database):
        """Test that transactions rollback properly on errors"""
        session_id, user_id = test_user_session
        unique_suffix = datetime.now().microsecond

        # Force an error by using an invalid exercise structure
        parsed_data = {
            "resistance_exercises": [
                {
                    "name": f"valid exercise {unique_suffix}",
                    "sets": 3,
                    "reps": [10, 8, 6],
                    "weights_kg": [50, 60, 70],
                },
            ],
        }

        # Get initial state
        async with get_async_session_context() as session:
            stmt = select(WorkoutSession).where(WorkoutSession.session_id == session_id)
            result = await session.execute(stmt)
            initial_session = result.scalar_one()
            initial_audio_count = initial_session.audio_count

        # Simulate an error during processing by using wrong user_id
        with pytest.raises(ValidationError):
            # Use wrong user_id to trigger authorization error
            await workout_service.add_exercises_to_session_batch(
                session_id, parsed_data, "wrong_user_123",
            )

        # Verify session was not modified (transaction rolled back)
        async with get_async_session_context() as session:
            stmt = select(WorkoutSession).where(WorkoutSession.session_id == session_id)
            result = await session.execute(stmt)
            final_session = result.scalar_one()

            # Session should be unchanged
            assert final_session.audio_count == initial_audio_count

    @pytest.mark.asyncio
    async def test_get_user_session_status_with_real_data(self, workout_service, populated_test_database):
        """Test session status retrieval with real database data"""
        # Create multiple sessions for a user
        async with get_async_session_context() as session:
            # Older session
            older_session = WorkoutSession(
                user_id="status_test_user",
                date=date.today() - timedelta(days=2),
                start_time=time(9, 0, 0),
                status=SessionStatus.FINALIZADA,
                audio_count=3,
            )

            # Recent active session
            recent_session = WorkoutSession(
                user_id="status_test_user",
                date=date.today(),
                start_time=(datetime.now() - timedelta(hours=1)).time(),  # 1 hour ago
                status=SessionStatus.ATIVA,
                audio_count=2,
            )

            session.add_all([older_session, recent_session])
            await session.commit()
            await session.refresh(recent_session)

            # Add some exercises to recent session
            unique_suffix = datetime.now().microsecond
            exercise = Exercise(
                name=f"test exercise {unique_suffix}",
                type=ExerciseType.RESISTENCIA,
                muscle_group="test",
            )
            session.add(exercise)
            await session.flush()

            workout_exercise = WorkoutExercise(
                session_id=recent_session.session_id,
                exercise_id=exercise.exercise_id,
                order_in_workout=1,
                sets=3,
            )

            aerobic_exercise_def = Exercise(
                name=f"test cardio {unique_suffix}",
                type=ExerciseType.AEROBICO,
                muscle_group="cardio",
            )
            session.add(aerobic_exercise_def)
            await session.flush()

            aerobic = AerobicExercise(
                session_id=recent_session.session_id,
                exercise_id=aerobic_exercise_def.exercise_id,
                duration_minutes=20,
            )

            session.add_all([workout_exercise, aerobic])
            await session.commit()

        # Test getting session status
        result = await workout_service.get_user_session_status("status_test_user")

        assert result["has_session"] is True
        assert result["session"].session_id == recent_session.session_id
        assert result["is_active"] == SessionStatus.ATIVA
        assert result["resistance_count"] == 1
        assert result["aerobic_count"] == 1
        assert result["minutes_passed"] >= 55  # Around 1 hour (allowing for test execution time)
        assert result["hours_passed"] >= 0

    @pytest.mark.asyncio
    async def test_finish_session_complete_workflow(self, workout_service, populated_test_database):
        """Test complete session finishing workflow"""
        # Create active session with exercises
        async with get_async_session_context() as session:
            workout_session = WorkoutSession(
                user_id="finish_test_user",
                date=date.today(),
                start_time=time(10, 0, 0),
                status=SessionStatus.ATIVA,
                audio_count=5,
            )

            session.add(workout_session)
            await session.flush()

            # Add resistance exercise
            unique_suffix = datetime.now().microsecond
            exercise = Exercise(
                name=f"bench press {unique_suffix}",
                type=ExerciseType.RESISTENCIA,
                muscle_group="chest",
            )
            session.add(exercise)
            await session.flush()

            workout_exercise = WorkoutExercise(
                session_id=workout_session.session_id,
                exercise_id=exercise.exercise_id,
                order_in_workout=1,
                sets=3,
                weights_kg=[40, 50, 60],
            )

            # Add aerobic exercise
            cardio_exercise = Exercise(
                name=f"running {unique_suffix}",
                type=ExerciseType.AEROBICO,
                muscle_group="cardio",
            )
            session.add(cardio_exercise)
            await session.flush()

            aerobic = AerobicExercise(
                session_id=workout_session.session_id,
                exercise_id=cardio_exercise.exercise_id,
                duration_minutes=30,
            )

            session.add_all([workout_exercise, aerobic])
            await session.commit()

            session_id = workout_session.session_id

        # Finish the session
        result = await workout_service.finish_session(session_id, "finish_test_user")

        assert result["success"] is True
        assert result["session_id"] == session_id
        assert result["duration_minutes"] >= 0

        # Verify stats
        stats = result["stats"]
        assert stats["audio_count"] == 5
        assert stats["resistance_exercises"] == 1
        assert stats["aerobic_exercises"] == 1
        assert stats["total_sets"] == 3
        assert stats["total_volume_kg"] == 150  # 40+50+60
        assert stats["cardio_minutes"] == 30
        assert "chest" in stats["muscle_groups"]

        # Verify session was updated in database
        async with get_async_session_context() as session:
            stmt = select(WorkoutSession).where(WorkoutSession.session_id == session_id)
            result = await session.execute(stmt)
            updated_session = result.scalar_one()

            assert updated_session.status == SessionStatus.FINALIZADA
            assert updated_session.end_time is not None
            assert updated_session.duration_minutes >= 0

    @pytest.mark.asyncio
    async def test_workout_analytics_with_real_data(self, workout_service, populated_test_database):
        """Test workout analytics with real database data"""
        # Create multiple sessions with varying data
        async with get_async_session_context() as session:
            user_id = "analytics_test_user"
            sessions_data = []

            # Create sessions over last 30 days
            for i in range(10):
                workout_session = WorkoutSession(
                    user_id=user_id,
                    date=date.today() - timedelta(days=i * 3),
                    start_time=time(10, 0, 0),
                    status=SessionStatus.FINALIZADA if i < 8 else SessionStatus.ATIVA,  # 2 incomplete
                    audio_count=2 + i % 3,
                    energy_level=6 + i % 5,
                    duration_minutes=60 + i * 10,
                )

                session.add(workout_session)
                await session.flush()
                sessions_data.append(workout_session)

                # Add resistance exercises
                for j in range(2):
                    exercise = Exercise(
                        name=f"exercise_{i}_{j}",
                        type=ExerciseType.RESISTENCIA,
                        muscle_group=["chest", "legs", "back", "arms"][(i * 2 + j) % 4],
                    )
                    session.add(exercise)
                    await session.flush()

                    workout_exercise = WorkoutExercise(
                        session_id=workout_session.session_id,
                        exercise_id=exercise.exercise_id,
                        order_in_workout=j + 1,
                        sets=3,
                        weights_kg=[40 + i * 5, 50 + i * 5, 60 + i * 5],
                    )
                    session.add(workout_exercise)

                # Add aerobic exercise every other session
                if i % 2 == 0:
                    cardio_exercise = Exercise(
                        name=f"cardio_{i}",
                        type=ExerciseType.AEROBICO,
                        muscle_group="cardio",
                    )
                    session.add(cardio_exercise)
                    await session.flush()

                    aerobic = AerobicExercise(
                        session_id=workout_session.session_id,
                        exercise_id=cardio_exercise.exercise_id,
                        duration_minutes=20 + i * 2,
                    )
                    session.add(aerobic)

            await session.commit()

        # Get analytics
        analytics = await workout_service.get_user_workout_analytics(user_id, 30)

        # Verify comprehensive analytics
        assert analytics["period"]["total_sessions"] == 10
        assert analytics["session_stats"]["completion_rate"] == 80.0  # 8/10 completed
        assert analytics["session_stats"]["average_duration_minutes"] > 0
        assert analytics["session_stats"]["average_audios_per_session"] > 0
        assert analytics["session_stats"]["average_energy_level"] > 0

        # Exercise stats
        assert analytics["exercise_stats"]["resistance"]["total_exercises"] == 20  # 10 sessions * 2 exercises
        assert analytics["exercise_stats"]["resistance"]["total_sets"] == 60  # 20 exercises * 3 sets
        assert analytics["exercise_stats"]["resistance"]["total_volume_kg"] > 0
        assert analytics["exercise_stats"]["aerobic"]["total_exercises"] == 5  # Every other session

        # Frequency analysis
        assert analytics["workout_frequency"]["unique_workout_days"] == 10
        assert analytics["workout_frequency"]["frequency_per_week"] > 0
        assert analytics["workout_frequency"]["consistency_score"] > 0

        # Muscle group distribution
        distribution = analytics["muscle_group_distribution"]["distribution"]
        assert len(distribution) == 4  # chest, legs, back, arms
        for muscle_group in ["chest", "legs", "back", "arms"]:
            assert muscle_group in distribution
            assert distribution[muscle_group]["count"] > 0
            assert distribution[muscle_group]["percentage"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_session_access(self, workout_service, populated_test_database):
        """Test concurrent access to the same session"""
        # Create a session
        async with get_async_session_context() as session:
            workout_session = WorkoutSession(
                user_id="concurrent_test_user",
                date=date.today(),
                start_time=time(10, 0, 0),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add(workout_session)
            await session.commit()
            await session.refresh(workout_session)
            session_id = workout_session.session_id

        # Simulate concurrent additions
        import asyncio

        unique_suffix = datetime.now().microsecond
        parsed_data1 = {
            "resistance_exercises": [
                {
                    "name": f"exercise_1_{unique_suffix}",
                    "sets": 3,
                    "reps": [10, 8, 6],
                    "weights_kg": [50, 60, 70],
                },
            ],
            "notes": "First batch",
        }

        parsed_data2 = {
            "resistance_exercises": [
                {
                    "name": f"exercise_2_{unique_suffix}",
                    "sets": 2,
                    "reps": [12, 10],
                    "weights_kg": [40, 45],
                },
            ],
            "notes": "Second batch",
        }

        # Execute concurrently
        results = await asyncio.gather(
            workout_service.add_exercises_to_session_batch(
                session_id, parsed_data1, "concurrent_test_user",
            ),
            workout_service.add_exercises_to_session_batch(
                session_id, parsed_data2, "concurrent_test_user",
            ),
            return_exceptions=True,
        )

        # At least one should succeed (depending on transaction isolation)
        successful_results = [r for r in results if r is True]
        assert len(successful_results) >= 1

        # Verify final state is consistent
        async with get_async_session_context() as session:
            stmt = select(WorkoutExercise).where(WorkoutExercise.session_id == session_id)
            result = await session.execute(stmt)
            exercises = result.scalars().all()

            # Should have at least 1 exercise, possibly 2
            assert len(exercises) >= 1
            assert len(exercises) <= 2

            # Verify session audio count increased appropriately
            stmt = select(WorkoutSession).where(WorkoutSession.session_id == session_id)
            result = await session.execute(stmt)
            final_session = result.scalar_one()

            # Audio count should reflect successful operations
            assert final_session.audio_count >= 2  # Was 1, should increase

    @pytest.mark.asyncio
    async def test_large_dataset_performance(self, workout_service, populated_test_database):
        """Test performance with larger datasets"""
        # Create a user with many sessions
        async with get_async_session_context() as session:
            user_id = "performance_test_user"

            # Create 100 sessions
            for i in range(100):
                workout_session = WorkoutSession(
                    user_id=user_id,
                    date=date.today() - timedelta(days=i),
                    start_time=time(10, 0, 0),
                    status=SessionStatus.FINALIZADA,
                    audio_count=3,
                    energy_level=7,
                    duration_minutes=60,
                )

                session.add(workout_session)
                await session.flush()

                # Add multiple exercises per session
                for j in range(5):
                    exercise = Exercise(
                        name=f"perf_exercise_{i}_{j}",
                        type=ExerciseType.RESISTENCIA,
                        muscle_group=["chest", "legs", "back", "arms", "shoulders"][j],
                    )
                    session.add(exercise)
                    await session.flush()

                    workout_exercise = WorkoutExercise(
                        session_id=workout_session.session_id,
                        exercise_id=exercise.exercise_id,
                        order_in_workout=j + 1,
                        sets=3,
                        weights_kg=[40, 50, 60],
                    )
                    session.add(workout_exercise)

            await session.commit()

        # Test analytics performance
        import time as time_module
        start_time = time_module.time()

        analytics = await workout_service.get_user_workout_analytics(user_id, 365)  # Full year

        end_time = time_module.time()
        execution_time = end_time - start_time

        # Should complete within reasonable time (adjust threshold as needed)
        assert execution_time < 5.0  # 5 seconds max

        # Verify correct data
        assert analytics["period"]["total_sessions"] == 100
        assert analytics["exercise_stats"]["resistance"]["total_exercises"] == 500  # 100 * 5
        assert analytics["exercise_stats"]["resistance"]["total_sets"] == 1500  # 500 * 3

        # Test session status performance
        start_time = time_module.time()

        status = await workout_service.get_user_session_status(user_id)

        end_time = time_module.time()
        execution_time = end_time - start_time

        # Should be very fast
        assert execution_time < 1.0  # 1 second max
        assert status["has_session"] is True

    @pytest.mark.asyncio
    async def test_data_consistency_after_errors(self, workout_service, populated_test_database):
        """Test data consistency after various error conditions"""
        # Create a session
        async with get_async_session_context() as session:
            workout_session = WorkoutSession(
                user_id="consistency_test_user",
                date=date.today(),
                start_time=time(10, 0, 0),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add(workout_session)
            await session.commit()
            await session.refresh(workout_session)
            session_id = workout_session.session_id

        # Try various invalid operations
        invalid_operations = [
            # Invalid user
            {"session_id": session_id, "data": {"resistance_exercises": []}, "user": "wrong_user"},
            # Invalid session
            {"session_id": 99999, "data": {"resistance_exercises": []}, "user": "consistency_test_user"},
            # Invalid data
            {"session_id": session_id, "data": None, "user": "consistency_test_user"},
        ]

        for operation in invalid_operations:
            try:
                await workout_service.add_exercises_to_session_batch(
                    operation["session_id"],
                    operation["data"],
                    operation["user"],
                )
            except (ValidationError, DatabaseError):
                pass  # Expected

        # Verify original session is unchanged
        async with get_async_session_context() as session:
            stmt = select(WorkoutSession).where(WorkoutSession.session_id == session_id)
            result = await session.execute(stmt)
            final_session = result.scalar_one()

            assert final_session.audio_count == 1  # Unchanged
            assert final_session.status == SessionStatus.ATIVA  # Unchanged

            # No exercises should have been added
            stmt = select(WorkoutExercise).where(WorkoutExercise.session_id == session_id)
            result = await session.execute(stmt)
            exercises = result.scalars().all()
            assert len(exercises) == 0

    @pytest.mark.asyncio
    async def test_session_timeout_edge_cases(self, workout_service, populated_test_database):
        """Test session timeout calculations with edge cases"""
        async with get_async_session_context() as session:
            user_id = "timeout_test_user"

            # Session exactly at timeout boundary
            timeout_hours = 3
            boundary_time = datetime.now() - timedelta(hours=timeout_hours, seconds=0)

            boundary_session = WorkoutSession(
                user_id=user_id,
                date=boundary_time.date(),
                start_time=boundary_time.time(),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            # Session just before timeout
            almost_timeout_time = datetime.now() - timedelta(hours=timeout_hours, seconds=-1)

            almost_session = WorkoutSession(
                user_id=f"{user_id}_almost",
                date=almost_timeout_time.date(),
                start_time=almost_timeout_time.time(),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            # Session just after timeout
            expired_time = datetime.now() - timedelta(hours=timeout_hours, minutes=+1)

            expired_session = WorkoutSession(
                user_id=f"{user_id}_expired",
                date=expired_time.date(),
                start_time=expired_time.time(),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add_all([boundary_session, almost_session, expired_session])
            await session.commit()

        # Test boundary session (exactly at timeout)
        with patch("config.settings.settings") as mock_settings:
            mock_settings.SESSION_TIMEOUT_HOURS = timeout_hours

            status = await workout_service.get_user_session_status(user_id)
            assert status["is_active"] == SessionStatus.FINALIZADA
            assert status["expired_minutes"] >= 0

            # Test almost timeout session
            status = await workout_service.get_user_session_status(f"{user_id}_almost")
            assert status["is_active"] == SessionStatus.ATIVA

            # Test expired session
            status = await workout_service.get_user_session_status(f"{user_id}_expired")
            assert status["is_active"] == SessionStatus.FINALIZADA
            assert status["expired_minutes"] > 0


class TestAsyncWorkoutServiceErrorRecovery:
    """Test error recovery and resilience in integration scenarios"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_database_connection_recovery(self, workout_service, populated_test_database):
        """Test recovery from database connection issues"""
        # This would require more complex setup to actually test connection recovery
        # For now, we test that appropriate errors are raised

        with patch("services.async_workout_service.get_async_session_context") as mock_context:
            mock_context.side_effect = SQLAlchemyError("Connection lost")

            with pytest.raises(DatabaseError) as exc_info:
                await workout_service.get_user_session_status("test_user")

            assert exc_info.value.error_code.value >= 1300  # Database error range
            assert "Failed to get session status" in exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_partial_data_handling(self, workout_service, populated_test_database):
        """Test handling of partial/corrupted data scenarios"""
        # Create session with some exercises that have partial data
        async with get_async_session_context() as session:
            workout_session = WorkoutSession(
                user_id="partial_data_user",
                date=date.today(),
                start_time=time(10, 0, 0),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add(workout_session)
            await session.flush()

            # Add exercise with missing/null data
            exercise = Exercise(
                name="partial_exercise",
                type=ExerciseType.RESISTENCIA,
                muscle_group=None,  # Missing data
            )
            session.add(exercise)
            await session.flush()

            workout_exercise = WorkoutExercise(
                session_id=workout_session.session_id,
                exercise_id=exercise.exercise_id,
                order_in_workout=1,
                sets=3,
                weights_kg=None,  # Missing weights
                reps=None,  # Missing reps
            )
            session.add(workout_exercise)
            await session.commit()

            session_id = workout_session.session_id

        # Service should handle partial data gracefully
        status = await workout_service.get_user_session_status("partial_data_user")
        assert status["has_session"] is True
        assert status["resistance_count"] == 1

        # Analytics should handle missing data
        analytics = await workout_service.get_user_workout_analytics("partial_data_user", 7)
        assert analytics["exercise_stats"]["resistance"]["total_exercises"] == 1
        assert analytics["exercise_stats"]["resistance"]["total_volume_kg"] == 0  # No weights

        # Finishing should work despite partial data
        result = await workout_service.finish_session(session_id, "partial_data_user")
        assert result["success"] is True
        assert result["stats"]["total_volume_kg"] == 0  # Handles missing weights


class TestAsyncWorkoutServiceBusinessRules:
    """Test business rules and domain logic in integration context"""

    @pytest.fixture
    def workout_service(self):
        return AsyncWorkoutService()

    @pytest.mark.asyncio
    async def test_exercise_ordering_business_rule(self, workout_service, populated_test_database):
        """Test that exercise ordering follows business rules"""
        # Create session with existing exercises
        async with get_async_session_context() as session:
            workout_session = WorkoutSession(
                user_id="ordering_test_user",
                date=date.today(),
                start_time=time(10, 0, 0),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add(workout_session)
            await session.flush()

            # Add 3 initial exercises
            for i in range(3):
                exercise = Exercise(
                    name=f"initial_exercise_{i}",
                    type=ExerciseType.RESISTENCIA,
                    muscle_group="test",
                )
                session.add(exercise)
                await session.flush()

                workout_exercise = WorkoutExercise(
                    session_id=workout_session.session_id,
                    exercise_id=exercise.exercise_id,
                    order_in_workout=i + 1,
                    sets=1,
                )
                session.add(workout_exercise)

            await session.commit()
            session_id = workout_session.session_id

        # Add more exercises - should continue ordering from 4
        parsed_data = {
            "resistance_exercises": [
                {"name": "new_exercise_1", "sets": 1, "reps": [10], "weights_kg": [50]},
                {"name": "new_exercise_2", "sets": 1, "reps": [10], "weights_kg": [50]},
            ],
        }

        await workout_service.add_exercises_to_session_batch(
            session_id, parsed_data, "ordering_test_user",
        )

        # Verify ordering
        async with get_async_session_context() as session:
            stmt = (
                select(WorkoutExercise)
                .where(WorkoutExercise.session_id == session_id)
                .order_by(WorkoutExercise.order_in_workout)
            )
            result = await session.execute(stmt)
            exercises = result.scalars().all()

            assert len(exercises) == 5

            # Verify continuous ordering
            for i, exercise in enumerate(exercises):
                assert exercise.order_in_workout == i + 1

    @pytest.mark.asyncio
    async def test_session_state_transitions(self, workout_service, populated_test_database):
        """Test session state transitions follow business rules"""
        # Create active session
        async with get_async_session_context() as session:
            workout_session = WorkoutSession(
                user_id="state_test_user",
                date=date.today(),
                start_time=time(10, 0, 0),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add(workout_session)
            await session.commit()
            await session.refresh(workout_session)
            session_id = workout_session.session_id

        # Active -> Finished should work
        result = await workout_service.finish_session(session_id, "state_test_user")
        assert result["success"] is True

        # Verify state changed
        async with get_async_session_context() as session:
            stmt = select(WorkoutSession).where(WorkoutSession.session_id == session_id)
            result = await session.execute(stmt)
            updated_session = result.scalar_one()
            assert updated_session.status == SessionStatus.FINALIZADA

        # Finished -> Finished should fail gracefully
        result = await workout_service.finish_session(session_id, "state_test_user")
        assert result["success"] is False
        assert "already finished" in result["error"]

    @pytest.mark.asyncio
    async def test_muscle_group_inference_integration(self, workout_service, populated_test_database):
        """Test muscle group inference works in full integration"""
        # Create session
        async with get_async_session_context() as session:
            workout_session = WorkoutSession(
                user_id="muscle_test_user",
                date=date.today(),
                start_time=time(10, 0, 0),
                status=SessionStatus.ATIVA,
                audio_count=1,
            )

            session.add(workout_session)
            await session.commit()
            await session.refresh(workout_session)
            session_id = workout_session.session_id

        # Add exercises with recognizable names
        parsed_data = {
            "resistance_exercises": [
                {"name": "bench press", "sets": 3, "reps": [10], "weights_kg": [50]},
                {"name": "squat", "sets": 3, "reps": [10], "weights_kg": [50]},
                {"name": "deadlift", "sets": 3, "reps": [10], "weights_kg": [50]},
            ],
        }

        await workout_service.add_exercises_to_session_batch(
            session_id, parsed_data, "muscle_test_user",
        )

        # Verify exercises were created with inferred muscle groups
        async with get_async_session_context() as session:
            stmt = (
                select(Exercise)
                .where(Exercise.name.in_(["bench press", "squat", "deadlift"]))
            )
            result = await session.execute(stmt)
            exercises = result.scalars().all()

            assert len(exercises) == 3

            # Each should have a muscle group inferred
            for exercise in exercises:
                assert exercise.muscle_group is not None
                assert exercise.muscle_group != ""

        # Verify analytics include the muscle groups
        analytics = await workout_service.get_user_workout_analytics("muscle_test_user", 7)
        muscle_distribution = analytics["muscle_group_distribution"]["distribution"]

        # Should have multiple muscle groups represented
        assert len(muscle_distribution) >= 2  # Different exercises target different groups

