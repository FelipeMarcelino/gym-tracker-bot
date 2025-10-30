"""Async workout service for improved database performance"""

from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from config.logging_config import get_logger
from config.settings import settings
from database.async_connection import get_async_session_context
from database.models import AerobicExercise, Exercise, ExerciseType, SessionStatus, WorkoutExercise, WorkoutSession
from services.exceptions import DatabaseError, ErrorCode, ValidationError
from services.exercise_knowledge import infer_equipment, infer_muscle_group

logger = get_logger(__name__)


class AsyncWorkoutService:
    """Async service for managing workout sessions with optimized database operations"""

    async def add_exercises_to_session_batch(
        self,
        session_id: UUID,
        parsed_data: Dict[str, Any],
        user_id: str,
    ) -> bool:
        """Optimized async version that handles all operations in a single transaction
        
        Args:
            session_id: Session ID
            parsed_data: Parsed data from LLM
            user_id: User ID for validation
            
        Returns:
            True if successful
            
        Raises:
            ValidationError: If data is invalid
            DatabaseError: If database operation fails

        """
        if not session_id:
            raise ValidationError(
                message="Invalid session ID",
                field="session_id",
                value=session_id,
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                user_message="Invalid session ID",
            )

        if not user_id or not user_id.strip():
            raise ValidationError(
                message="User ID is required",
                field="user_id",
                value=user_id,
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                user_message="User ID is required",
            )

        if not parsed_data or not isinstance(parsed_data, dict):
            raise ValidationError(
                message="Invalid parsed data",
                field="parsed_data",
                value=str(parsed_data),
                error_code=ErrorCode.INVALID_INPUT,
                user_message="Invalid workout data",
            )

        try:
            async with get_async_session_context() as session:
                async with session.begin():
                    # 1. Get workout session with optimized query
                    stmt = (
                        select(WorkoutSession)
                        .options(selectinload(WorkoutSession.exercises))
                        .where(WorkoutSession.session_id == session_id)
                    )
                    result = await session.execute(stmt)
                    workout_session = result.scalar_one_or_none()

                    if not workout_session:
                        raise ValidationError(
                            message=f"Session {session_id} not found",
                            field="session_id",
                            value=session_id,
                            error_code=ErrorCode.SESSION_NOT_FOUND,
                            user_message="Session not found",
                        )

                    if workout_session.user_id != user_id:
                        raise ValidationError(
                            message="User not authorized for this session",
                            field="user_id",
                            value=user_id,
                            error_code=ErrorCode.ACCESS_DENIED,
                            user_message="Not authorized for this session",
                        )

                    # 2. Update session data
                    await self._update_session_data_async(session, workout_session, parsed_data)

                    # 3. Count existing exercises
                    existing_resistance = len(workout_session.exercises)

                    # 4. Process resistance exercises in batch
                    resistance_exercises = parsed_data.get("resistance_exercises", [])
                    if resistance_exercises:
                        await self._process_resistance_exercises_async(
                            session, session_id, resistance_exercises, existing_resistance,
                        )

                    # 5. Process aerobic exercises in batch
                    aerobic_exercises = parsed_data.get("aerobic_exercises", [])
                    if aerobic_exercises:
                        await self._process_aerobic_exercises_async(
                            session, session_id, aerobic_exercises,
                        )

                    # Commit is automatic with begin() context manager

                resistance_count = len(resistance_exercises)
                aerobic_count = len(aerobic_exercises)

                logger.info(
                    f"Successfully added {resistance_count} resistance + {aerobic_count} aerobic exercises "
                    f"to session {session_id}",
                )
                return True

        except ValidationError:
            raise
        except SQLAlchemyError as e:
            logger.exception(f"Database error adding exercises to session {session_id}")
            raise DatabaseError(
                message=f"Failed to add exercises to session {session_id}",
                operation="add_exercises_to_session_batch",
                error_code=ErrorCode.TRANSACTION_FAILED,
                user_message="Failed to save workout data",
                cause=e,
            )

    async def _update_session_data_async(
        self,
        session,
        workout_session: WorkoutSession,
        parsed_data: Dict[str, Any],
    ) -> None:
        """Update session metadata (async)"""
        workout_session.audio_count += 1

        # Update optional metadata
        if "energy_level" in parsed_data:
            workout_session.energy_level = parsed_data["energy_level"]
        if "difficulty" in parsed_data:
            workout_session.difficulty = parsed_data["difficulty"]
        if "notes" in parsed_data:
            current_notes = workout_session.notes or ""
            new_notes = parsed_data["notes"]
            workout_session.notes = f"{current_notes}\n{new_notes}".strip()

        session.add(workout_session)

    async def _process_resistance_exercises_async(
        self,
        session,
        session_id: UUID,
        resistance_exercises: List[Dict[str, Any]],
        existing_count: int,
    ) -> None:
        """Process resistance exercises in batch (async)"""
        exercise_objects = []
        workout_exercise_objects = []

        # Get all unique exercise names for batch lookup
        exercise_names = {ex.get("name", "").lower().strip() for ex in resistance_exercises if ex.get("name")}

        # Batch lookup existing exercises
        if exercise_names:
            stmt = select(Exercise).where(Exercise.name.in_(exercise_names))
            result = await session.execute(stmt)
            existing_exercises = {ex.name.lower(): ex for ex in result.scalars().all()}
        else:
            existing_exercises = {}

        for i, exercise_data in enumerate(resistance_exercises):
            exercise_name = exercise_data.get("name", "").strip()
            if not exercise_name:
                continue

            exercise_name_lower = exercise_name.lower()

            # Get or create exercise
            if exercise_name_lower in existing_exercises:
                exercise = existing_exercises[exercise_name_lower]
            else:
                # Create new exercise
                exercise = Exercise(
                    name=exercise_name_lower,
                    type=ExerciseType.RESISTENCIA,
                    muscle_group=infer_muscle_group(exercise_name),
                    equipment=infer_equipment(exercise_name),
                )
                exercise_objects.append(exercise)
                existing_exercises[exercise_name_lower] = exercise

            # Create workout exercise
            workout_exercise = WorkoutExercise(
                session_id=session_id,
                exercise=exercise,
                order_in_workout=existing_count + i + 1,
                sets=exercise_data.get("sets", 1),
                reps=exercise_data.get("reps", []),
                weights_kg=exercise_data.get("weights_kg", []),
                rest_seconds=exercise_data.get("rest_seconds"),
                notes=exercise_data.get("notes"),
            )
            workout_exercise_objects.append(workout_exercise)

        # Batch insert new exercises
        if exercise_objects:
            session.add_all(exercise_objects)
            await session.flush()  # Get IDs for exercises

        # Batch insert workout exercises
        if workout_exercise_objects:
            session.add_all(workout_exercise_objects)

    async def _process_aerobic_exercises_async(
        self,
        session,
        session_id: UUID,
        aerobic_exercises: List[Dict[str, Any]],
    ) -> None:
        """Process aerobic exercises in batch (async)"""
        exercise_objects = []
        aerobic_objects = []

        # Get all unique exercise names for batch lookup
        exercise_names = {ex.get("name", "").lower().strip() for ex in aerobic_exercises if ex.get("name")}

        # Batch lookup existing exercises
        if exercise_names:
            stmt = select(Exercise).where(
                Exercise.name.in_(exercise_names),
                Exercise.type == ExerciseType.AEROBICO,
            )
            result = await session.execute(stmt)
            existing_exercises = {ex.name.lower(): ex for ex in result.scalars().all()}
        else:
            existing_exercises = {}

        for exercise_data in aerobic_exercises:
            exercise_name = exercise_data.get("name", "").strip()
            if not exercise_name:
                continue

            exercise_name_lower = exercise_name.lower()

            # Get or create exercise
            if exercise_name_lower in existing_exercises:
                exercise = existing_exercises[exercise_name_lower]
            else:
                # Create new exercise
                exercise = Exercise(
                    name=exercise_name_lower,
                    type=ExerciseType.AEROBICO,
                    muscle_group=infer_muscle_group(exercise_name, ExerciseType.AEROBICO.value),
                    equipment=infer_equipment(exercise_name, ExerciseType.AEROBICO.value),
                )
                exercise_objects.append(exercise)
                existing_exercises[exercise_name_lower] = exercise

            # Create aerobic exercise
            aerobic_exercise = AerobicExercise(
                session_id=session_id,
                exercise=exercise,
                duration_minutes=exercise_data.get("duration_minutes", 0),
                distance_km=exercise_data.get("distance_km"),
                calories_burned=exercise_data.get("calories_burned"),
                intensity_level=exercise_data.get("intensity_level"),
                notes=exercise_data.get("notes"),
            )
            aerobic_objects.append(aerobic_exercise)

        # Batch insert new exercises
        if exercise_objects:
            session.add_all(exercise_objects)
            await session.flush()

        # Batch insert aerobic exercises
        if aerobic_objects:
            session.add_all(aerobic_objects)

    async def get_user_session_status(self, user_id: str) -> Dict[str, Any]:
        """Get user's current session status with optimized query (async)
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with session status information

        """
        try:
            async with get_async_session_context() as session:
                # Get latest session with related data in single query
                stmt = (
                    select(WorkoutSession)
                    .options(
                        selectinload(WorkoutSession.exercises),
                        selectinload(WorkoutSession.aerobics),
                    )
                    .where(WorkoutSession.user_id == user_id)
                    .order_by(WorkoutSession.date.desc(), WorkoutSession.start_time.desc())
                    .limit(1)
                )
                result = await session.execute(stmt)
                last_session = result.scalar_one_or_none()

                if not last_session:
                    return {
                        "has_session": False,
                        "message": "Nenhuma sessão encontrada. Envie um áudio para começar!",
                    }

                # Calculate session stats
                now = datetime.now()
                time_diff = now - datetime.combine(last_session.date, last_session.start_time)
                minutes_passed = int(time_diff.total_seconds() // 60)
                hours_passed = minutes_passed // 60
                timeout_hours = settings.SESSION_TIMEOUT_HOURS

                # Determine session status
                is_active = SessionStatus.ATIVA if minutes_passed < (timeout_hours * 60) else SessionStatus.FINALIZADA

                expired_minutes = minutes_passed - (timeout_hours * 60)


                # Count exercises
                resistance_count = len(last_session.exercises)
                aerobic_count = len(last_session.aerobics)

                return {
                    "has_session": True,
                    "session": last_session,
                    "is_active": is_active,
                    "minutes_passed": minutes_passed,
                    "hours_passed": hours_passed,
                    "resistance_count": resistance_count,
                    "aerobic_count": aerobic_count,
                    "timeout_hours": timeout_hours,
                    "expired_minutes": expired_minutes,
                }

        except SQLAlchemyError as e:
            logger.exception(f"Error getting session status for user {user_id}")
            raise DatabaseError(
                message=f"Failed to get session status for user {user_id}",
                operation="get_user_session_status",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to get session status",
                cause=e,
            )

    async def get_last_session(self, user_id: str) -> WorkoutSession | None:
        """Get the most recent session for a user (async)"""
        async with get_async_session_context() as session:
            stmt = (
                select(WorkoutSession)
                .where(WorkoutSession.user_id == user_id)
                .order_by(WorkoutSession.date.desc(), WorkoutSession.start_time.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def finish_session(
        self, session_id: UUID, user_id: str,
    ) -> Dict[str, Any]:
        """Finish a workout session with optimized stats calculation (async)
        
        Args:
            session_id: Session ID to finish
            user_id: User ID for validation
            
        Returns:
            Dict with session finish results and stats

        """
        try:
            async with get_async_session_context() as session:
                async with session.begin():
                    # Get session with all related data including exercise relationships
                    stmt = (
                        select(WorkoutSession)
                        .options(
                            selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise),
                            selectinload(WorkoutSession.aerobics).selectinload(AerobicExercise.exercise),
                        )
                        .where(
                            WorkoutSession.session_id == session_id,
                            WorkoutSession.user_id == user_id,
                        )
                    )
                    result = await session.execute(stmt)
                    workout_session = result.scalar_one_or_none()

                    if not workout_session:
                        return {
                            "success": False,
                            "error": "Session not found or access denied",
                        }

                    if workout_session.status == SessionStatus.FINALIZADA:
                        return {
                            "success": False,
                            "error": "Session already finished",
                        }

                    # Calculate session duration and stats
                    now = datetime.now()
                    end_time = now.time()
                    start_datetime = datetime.combine(workout_session.date, workout_session.start_time)

                    # Handle cross-midnight sessions: if end_time is before start_time,
                    # assume we crossed midnight and the session ended the next day
                    if end_time < workout_session.start_time:
                        end_datetime = datetime.combine(workout_session.date + timedelta(days=1), end_time)
                    else:
                        end_datetime = datetime.combine(workout_session.date, end_time)

                    duration_minutes = int((end_datetime - start_datetime).total_seconds() // 60)

                    # Ensure duration is not negative (safety check)
                    duration_minutes = max(0, duration_minutes)

                    # Calculate exercise stats within session context
                    stats = self._calculate_session_stats_sync(workout_session)

                    # Update session
                    workout_session.status = SessionStatus.FINALIZADA
                    workout_session.end_time = end_time
                    workout_session.duration_minutes = duration_minutes

                    session.add(workout_session)
                    # Commit is automatic

                    logger.info(f"Session {session_id} finished for user {user_id}")

                    return {
                        "success": True,
                        "session_id": session_id,
                        "duration_minutes": duration_minutes,
                        "stats": stats,
                    }

        except SQLAlchemyError as e:
            logger.exception(f"Error finishing session {session_id}")
            raise DatabaseError(
                message=f"Failed to finish session {session_id}",
                operation="finish_session",
                error_code=ErrorCode.TRANSACTION_FAILED,
                user_message="Failed to finish session",
                cause=e,
            )

    def _calculate_session_stats_sync(self, workout_session: WorkoutSession) -> Dict[str, Any]:
        """Calculate session statistics (synchronous, within session context)"""
        resistance_exercises = len(workout_session.exercises)
        aerobic_exercises = len(workout_session.aerobics)

        # Calculate resistance stats
        total_sets = sum(ex.sets for ex in workout_session.exercises if ex.sets)
        total_volume_kg = sum(
            sum(weights) for ex in workout_session.exercises
            if ex.weights_kg and isinstance(ex.weights_kg, list) for weights in [ex.weights_kg]
        )

        # Calculate aerobic stats
        cardio_minutes = sum(
            ex.duration_minutes for ex in workout_session.aerobics
            if ex.duration_minutes
        )

        # Get muscle groups (safely access the loaded relationship)
        muscle_groups = list(set(
            ex.exercise.muscle_group for ex in workout_session.exercises
            if ex.exercise and ex.exercise.muscle_group
        ))

        return {
            "audio_count": workout_session.audio_count,
            "resistance_exercises": resistance_exercises,
            "aerobic_exercises": aerobic_exercises,
            "total_sets": total_sets,
            "total_volume_kg": total_volume_kg,
            "cardio_minutes": cardio_minutes,
            "muscle_groups": muscle_groups,
        }

    async def get_user_workout_analytics(
        self,
        user_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get comprehensive workout analytics for a user (async)
        
        Args:
            user_id: User ID
            days: Number of days to analyze
            
        Returns:
            Dict with analytics data

        """
        try:
            async with get_async_session_context() as session:
                # Calculate date range
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=days)

                # Get sessions with exercises in optimized query including exercise relationships
                stmt = (
                    select(WorkoutSession)
                    .options(
                        selectinload(WorkoutSession.exercises).selectinload(WorkoutExercise.exercise),
                        selectinload(WorkoutSession.aerobics).selectinload(AerobicExercise.exercise),
                    )
                    .where(
                        WorkoutSession.user_id == user_id,
                        WorkoutSession.date >= start_date,
                        WorkoutSession.date <= end_date,
                    )
                    .order_by(WorkoutSession.date.desc())
                )
                result = await session.execute(stmt)
                sessions = list(result.scalars().all())

                if not sessions:
                    return {"message": "No workout data found for the specified period"}

                # Calculate comprehensive analytics
                return await self._calculate_comprehensive_analytics_async(sessions, days)

        except SQLAlchemyError as e:
            logger.exception(f"Error getting analytics for user {user_id}")
            raise DatabaseError(
                message=f"Failed to get analytics for user {user_id}",
                operation="get_user_workout_analytics",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to calculate workout analytics",
                cause=e,
            )

    async def _calculate_comprehensive_analytics_async(
        self,
        sessions: List[WorkoutSession],
        days: int,
    ) -> Dict[str, Any]:
        """Calculate comprehensive analytics from sessions (async)"""
        # Basic stats
        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s.status == SessionStatus.FINALIZADA])
        completion_rate = (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0

        # Session stats
        durations = [s.duration_minutes for s in sessions if s.duration_minutes]
        avg_duration = sum(durations) / len(durations) if durations else 0
        avg_audios = sum(s.audio_count for s in sessions) / total_sessions if total_sessions > 0 else 0

        # Energy levels
        energy_levels = [s.energy_level for s in sessions if s.energy_level]
        avg_energy = sum(energy_levels) / len(energy_levels) if energy_levels else 0

        # Exercise stats
        all_resistance = [ex for s in sessions for ex in s.exercises]
        all_aerobic = [ex for s in sessions for ex in s.aerobics]

        total_resistance_exercises = len(all_resistance)
        total_sets = sum(ex.sets for ex in all_resistance if ex.sets)
        total_volume = sum(
            sum(weights) for ex in all_resistance
            if ex.weights_kg and isinstance(ex.weights_kg, list) for weights in [ex.weights_kg]
        )

        # Difficulty levels
        difficulties = [ex.difficulty for s in sessions for ex in s.exercises if hasattr(ex, "difficulty") and ex.difficulty]
        avg_difficulty = sum(difficulties) / len(difficulties) if difficulties else 0

        # Frequency calculation
        unique_dates = set(s.date for s in sessions)
        unique_workout_days = len(unique_dates)

        if days >= 7:
            frequency_per_week = unique_workout_days * 7 / days
            is_extrapolated = True
        else:
            frequency_per_week = unique_workout_days * 7 / days if days > 0 else 0
            is_extrapolated = False

        # Muscle group distribution
        muscle_groups = {}
        for ex in all_resistance:
            if ex.exercise and ex.exercise.muscle_group:
                muscle_groups[ex.exercise.muscle_group] = muscle_groups.get(ex.exercise.muscle_group, 0) + 1

        total_muscle_exercises = sum(muscle_groups.values())
        muscle_distribution = {
            muscle: {
                "count": count,
                "percentage": count / total_muscle_exercises * 100 if total_muscle_exercises > 0 else 0,
            }
            for muscle, count in muscle_groups.items()
        }

        # Progress trends (simplified)
        recent_sessions = sessions[:5]  # Last 5 sessions
        older_sessions = sessions[5:10] if len(sessions) > 5 else []

        if recent_sessions and older_sessions:
            recent_volume = sum(
                sum(weights) for s in recent_sessions for ex in s.exercises
                if ex.weights_kg and isinstance(ex.weights_kg, list) for weights in [ex.weights_kg]
            )
            older_volume = sum(
                sum(weights) for s in older_sessions for ex in s.exercises
                if ex.weights_kg and isinstance(ex.weights_kg, list) for weights in [ex.weights_kg]
            )

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
                volume_change_percent = 0
        else:
            trend = "insufficient_data"
            volume_change_percent = 0

        return {
            "period": {
                "days": days,
                "total_sessions": total_sessions,
            },
            "session_stats": {
                "completion_rate": completion_rate,
                "average_duration_minutes": avg_duration,
                "average_audios_per_session": avg_audios,
                "average_energy_level": avg_energy,
            },
            "exercise_stats": {
                "resistance": {
                    "total_exercises": total_resistance_exercises,
                    "total_sets": total_sets,
                    "total_volume_kg": total_volume,
                    "average_difficulty": avg_difficulty,
                },
                "aerobic": {
                    "total_exercises": len(all_aerobic),
                },
            },
            "workout_frequency": {
                "unique_workout_days": unique_workout_days,
                "frequency_per_week": frequency_per_week,
                "is_extrapolated": is_extrapolated,
                "analysis_period_days": days,
                "consistency_score": unique_workout_days / days * 100 if days > 0 else 0,
                "longest_streak_days": 1,  # Simplified for now
            },
            "muscle_group_distribution": {
                "distribution": muscle_distribution,
            },
            "progress_trends": {
                "trend": trend,
                "volume_change_percent": volume_change_percent,
            },
        }

