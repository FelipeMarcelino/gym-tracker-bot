"""Async analytics service for workout statistics and progress tracking"""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from sqlalchemy.orm import joinedload
from sqlalchemy import func, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.async_connection import get_async_session_context
from database.models import (
    WorkoutSession,
    WorkoutExercise,
    AerobicExercise,
    Exercise,
    SessionStatus,
)
from services.exceptions import ValidationError, DatabaseError

logger = logging.getLogger(__name__)


class AsyncAnalyticsService:
    """Async service for generating workout analytics and statistics"""

    async def get_workout_analytics(
        self, user_id: str, days: int = 30, include_active: bool = True
    ) -> Dict[str, Any]:
        """Get comprehensive workout analytics for a user (async)

        Args:
            user_id: User ID
            days: Number of days to look back (default: 30)
            include_active: Whether to include active sessions

        Returns:
            Dict with comprehensive analytics
        """
        if not user_id or not user_id.strip():
            raise ValidationError('User ID is required')

        if days <= 0:
            raise ValidationError('Days must be positive')

        async with get_async_session_context() as session:
            try:
                # Calculate date range
                end_date = date.today()
                start_date = end_date - timedelta(days=days)

                # Build session status filter
                allowed_statuses = [SessionStatus.FINALIZADA]
                if include_active:
                    allowed_statuses.append(SessionStatus.ATIVA)

                # Get sessions in date range
                sessions_stmt = (
                    select(WorkoutSession)
                    .where(
                        WorkoutSession.user_id == user_id,
                        WorkoutSession.date >= start_date,
                        WorkoutSession.date <= end_date,
                        WorkoutSession.status.in_(allowed_statuses),
                    )
                    .options(
                        joinedload(WorkoutSession.exercises).joinedload(
                            WorkoutExercise.exercise
                        ),
                        joinedload(WorkoutSession.aerobics),
                    )
                    .order_by(desc(WorkoutSession.date))
                )

                result = await session.execute(sessions_stmt)
                sessions = result.scalars().unique().all()

                if not sessions:
                    return {
                        'message': f'Nenhum treino encontrado nos últimos {days} dias',
                        'period': f'{days} dias',
                        'start_date': start_date.strftime('%d/%m/%Y'),
                        'end_date': end_date.strftime('%d/%m/%Y'),
                    }

                # Calculate analytics
                analytics = await self._calculate_comprehensive_analytics(
                    sessions, days, start_date, end_date
                )

                return analytics

            except Exception as e:
                logger.exception(
                    f'Error calculating workout analytics for user {user_id}'
                )
                raise DatabaseError(f'Failed to calculate analytics: {str(e)}')

    async def get_exercise_progress(
        self, user_id: str, exercise_name: str, days: int = 90
    ) -> Dict[str, Any]:
        """Get progress data for a specific exercise (async)

        Args:
            user_id: User ID
            exercise_name: Name of the exercise
            days: Number of days to look back

        Returns:
            Dict with exercise progress data
        """
        if not user_id or not user_id.strip():
            raise ValidationError('User ID is required')

        if not exercise_name or not exercise_name.strip():
            raise ValidationError('Exercise name is required')

        async with get_async_session_context() as session:
            try:
                # Calculate date range
                end_date = date.today()
                start_date = end_date - timedelta(days=days)

                # Find exercise
                exercise_stmt = select(Exercise).where(
                    func.lower(Exercise.name).like(
                        f'%{exercise_name.lower()}%'
                    )
                )
                result = await session.execute(exercise_stmt)
                exercise = result.scalar_one_or_none()

                if not exercise:
                    return {
                        'message': f"Exercício '{exercise_name}' não encontrado",
                        'exercise_name': exercise_name,
                    }

                # Get workout exercises for this exercise
                progress_stmt = (
                    select(WorkoutExercise)
                    .join(WorkoutSession)
                    .where(
                        WorkoutSession.user_id == user_id,
                        WorkoutExercise.exercise_id == exercise.exercise_id,
                        WorkoutSession.date >= start_date,
                        WorkoutSession.date <= end_date,
                        WorkoutSession.status == SessionStatus.FINALIZADA,
                    )
                    .options(joinedload(WorkoutExercise.session))
                    .order_by(WorkoutSession.date)
                )

                result = await session.execute(progress_stmt)
                workout_exercises = result.scalars().all()

                if not workout_exercises:
                    return {
                        'message': f"Nenhum progresso encontrado para '{exercise.name}' nos últimos {days} dias",
                        'exercise_name': exercise.name,
                        'period': f'{days} dias',
                    }

                # Calculate progress metrics
                progress_data = await self._calculate_exercise_progress(
                    workout_exercises, exercise, days
                )

                return progress_data

            except Exception as e:
                logger.exception(
                    f'Error calculating exercise progress for {exercise_name}'
                )
                raise DatabaseError(
                    f'Failed to calculate exercise progress: {str(e)}'
                )

    async def _calculate_comprehensive_analytics(
        self,
        sessions: List[WorkoutSession],
        days: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """Calculate comprehensive analytics from sessions (async)"""

        # Session statistics
        total_sessions = len(sessions)
        completed_sessions = len(
            [s for s in sessions if s.status == SessionStatus.FINALIZADA]
        )

        # Calculate total duration
        total_duration = sum(
            s.duration_minutes or 0 for s in sessions if s.duration_minutes
        )
        avg_duration = (
            total_duration / completed_sessions
            if completed_sessions > 0
            else 0
        )

        # Exercise statistics
        total_resistance = 0
        total_aerobic = 0
        total_sets = 0
        total_volume = 0.0
        muscle_groups = defaultdict(int)
        cardio_minutes = 0.0

        # Process resistance exercises
        for session in sessions:
            for we in session.exercises:
                total_resistance += 1
                total_sets += we.sets
                if we.weight and we.reps:
                    total_volume += we.weight * we.reps * we.sets
                if we.exercise and we.exercise.muscle_group:
                    muscle_groups[we.exercise.muscle_group] += 1

        # Process aerobic exercises
        for session in sessions:
            for ae in session.aerobics:
                total_aerobic += 1
                if ae.duration_minutes:
                    cardio_minutes += ae.duration_minutes

        # Workout frequency
        workout_frequency = await self._calculate_workout_frequency(
            sessions, days
        )

        # Muscle group distribution
        muscle_distribution = dict(muscle_groups) if muscle_groups else {}

        # Progress trends
        progress_trends = await self._calculate_progress_trends(sessions)

        return {
            'period': f'{days} dias',
            'start_date': start_date.strftime('%d/%m/%Y'),
            'end_date': end_date.strftime('%d/%m/%Y'),
            'session_stats': {
                'total_sessions': total_sessions,
                'completed_sessions': completed_sessions,
                'active_sessions': total_sessions - completed_sessions,
                'total_duration_minutes': total_duration,
                'avg_duration_minutes': round(avg_duration, 1),
            },
            'exercise_stats': {
                'total_exercises': total_resistance + total_aerobic,
                'resistance_exercises': total_resistance,
                'aerobic_exercises': total_aerobic,
                'total_sets': total_sets,
                'total_volume_kg': round(total_volume, 1),
                'cardio_minutes': round(cardio_minutes, 1),
            },
            'workout_frequency': workout_frequency,
            'muscle_group_distribution': muscle_distribution,
            'progress_trends': progress_trends,
        }

    async def _calculate_workout_frequency(
        self, sessions: List[WorkoutSession], days: int
    ) -> Dict[str, Any]:
        """Calculate workout frequency metrics (async)"""
        completed_sessions = [
            s for s in sessions if s.status == SessionStatus.FINALIZADA
        ]

        if not completed_sessions:
            return {
                'workouts_per_week': 0.0,
                'total_weeks': round(days / 7, 1),
                'consistency_score': 0.0,
            }

        # Calculate frequency
        workouts_per_week = len(completed_sessions) / (days / 7)

        # Calculate consistency (how evenly distributed are workouts)
        dates = [s.date for s in completed_sessions]
        dates.sort()

        consistency_score = 0.0
        if len(dates) > 1:
            # Calculate average gap between workouts
            gaps = [
                (dates[i] - dates[i - 1]).days for i in range(1, len(dates))
            ]
            avg_gap = sum(gaps) / len(gaps)
            ideal_gap = days / len(completed_sessions)

            # Consistency score: closer to ideal = higher score
            if ideal_gap > 0:
                consistency_score = max(
                    0, 1 - abs(avg_gap - ideal_gap) / ideal_gap
                )

        return {
            'workouts_per_week': round(workouts_per_week, 1),
            'total_weeks': round(days / 7, 1),
            'consistency_score': round(consistency_score * 100, 1),
        }

    async def _calculate_progress_trends(
        self, sessions: List[WorkoutSession]
    ) -> Dict[str, Any]:
        """Calculate progress trends over time (async)"""
        completed_sessions = [
            s for s in sessions if s.status == SessionStatus.FINALIZADA
        ]
        completed_sessions.sort(key=lambda x: x.date)

        if len(completed_sessions) < 2:
            return {
                'volume_trend': 'insufficient_data',
                'duration_trend': 'insufficient_data',
                'exercise_count_trend': 'insufficient_data',
            }

        # Split sessions into first and second half
        mid_point = len(completed_sessions) // 2
        first_half = completed_sessions[:mid_point]
        second_half = completed_sessions[mid_point:]

        # Calculate averages for each half
        first_avg_volume = await self._calculate_avg_volume(first_half)
        second_avg_volume = await self._calculate_avg_volume(second_half)

        first_avg_duration = sum(
            s.duration_minutes or 0 for s in first_half
        ) / len(first_half)
        second_avg_duration = sum(
            s.duration_minutes or 0 for s in second_half
        ) / len(second_half)

        first_avg_exercises = sum(
            len(s.workout_exercises) + len(s.aerobic_exercises)
            for s in first_half
        ) / len(first_half)
        second_avg_exercises = sum(
            len(s.workout_exercises) + len(s.aerobic_exercises)
            for s in second_half
        ) / len(second_half)

        # Determine trends
        volume_trend = (
            'increasing'
            if second_avg_volume > first_avg_volume * 1.05
            else 'decreasing'
            if second_avg_volume < first_avg_volume * 0.95
            else 'stable'
        )

        duration_trend = (
            'increasing'
            if second_avg_duration > first_avg_duration * 1.05
            else 'decreasing'
            if second_avg_duration < first_avg_duration * 0.95
            else 'stable'
        )

        exercise_trend = (
            'increasing'
            if second_avg_exercises > first_avg_exercises * 1.05
            else 'decreasing'
            if second_avg_exercises < first_avg_exercises * 0.95
            else 'stable'
        )

        return {
            'volume_trend': volume_trend,
            'duration_trend': duration_trend,
            'exercise_count_trend': exercise_trend,
            'volume_change_percent': round(
                (
                    (second_avg_volume - first_avg_volume)
                    / first_avg_volume
                    * 100
                )
                if first_avg_volume > 0
                else 0,
                1,
            ),
            'duration_change_percent': round(
                (
                    (second_avg_duration - first_avg_duration)
                    / first_avg_duration
                    * 100
                )
                if first_avg_duration > 0
                else 0,
                1,
            ),
        }

    async def _calculate_avg_volume(
        self, sessions: List[WorkoutSession]
    ) -> float:
        """Calculate average volume for a list of sessions (async)"""
        total_volume = 0.0
        total_exercises = 0

        for session in sessions:
            for we in session.exercises:
                if we.weight and we.reps:
                    total_volume += we.weight * we.reps * we.sets
                    total_exercises += 1

        return total_volume / total_exercises if total_exercises > 0 else 0.0

    async def _calculate_exercise_progress(
        self,
        workout_exercises: List[WorkoutExercise],
        exercise: Exercise,
        days: int,
    ) -> Dict[str, Any]:
        """Calculate progress metrics for a specific exercise (async)"""

        # Sort by date
        workout_exercises.sort(key=lambda x: x.session.date)

        # Calculate metrics
        total_workouts = len(workout_exercises)
        total_sets = sum(we.sets for we in workout_exercises)
        total_reps = sum(
            we.reps * we.sets for we in workout_exercises if we.reps
        )

        # Weight progression
        weights = [we.weight for we in workout_exercises if we.weight]
        max_weight = max(weights) if weights else 0
        min_weight = min(weights) if weights else 0
        avg_weight = sum(weights) / len(weights) if weights else 0

        # Volume progression
        volumes = []
        for we in workout_exercises:
            if we.weight and we.reps:
                volumes.append(we.weight * we.reps * we.sets)

        max_volume = max(volumes) if volumes else 0
        avg_volume = sum(volumes) / len(volumes) if volumes else 0

        # Progress trend
        progress_trend = 'insufficient_data'
        if len(volumes) >= 4:
            # Compare first quarter vs last quarter
            quarter_size = len(volumes) // 4
            first_quarter_avg = sum(volumes[:quarter_size]) / quarter_size
            last_quarter_avg = sum(volumes[-quarter_size:]) / quarter_size

            if last_quarter_avg > first_quarter_avg * 1.1:
                progress_trend = 'strong_improvement'
            elif last_quarter_avg > first_quarter_avg * 1.02:
                progress_trend = 'improvement'
            elif last_quarter_avg < first_quarter_avg * 0.9:
                progress_trend = 'declining'
            else:
                progress_trend = 'stable'

        # Recent performance (last 3 workouts)
        recent_workouts = (
            workout_exercises[-3:]
            if len(workout_exercises) >= 3
            else workout_exercises
        )
        recent_avg_weight = (
            sum(we.weight for we in recent_workouts if we.weight)
            / len([we for we in recent_workouts if we.weight])
            if any(we.weight for we in recent_workouts)
            else 0
        )
        recent_avg_volume = sum(
            we.weight * we.reps * we.sets
            for we in recent_workouts
            if we.weight and we.reps
        ) / len(recent_workouts)

        return {
            'exercise_name': exercise.name,
            'muscle_group': exercise.muscle_group,
            'period': f'{days} dias',
            'summary': {
                'total_workouts': total_workouts,
                'total_sets': total_sets,
                'total_reps': total_reps,
                'max_weight_kg': max_weight,
                'avg_weight_kg': round(avg_weight, 1),
                'max_volume_kg': round(max_volume, 1),
                'avg_volume_kg': round(avg_volume, 1),
            },
            'progress': {
                'trend': progress_trend,
                'weight_range': f'{min_weight}-{max_weight} kg'
                if weights
                else 'N/A',
                'recent_avg_weight_kg': round(recent_avg_weight, 1),
                'recent_avg_volume_kg': round(recent_avg_volume, 1),
            },
            'timeline': [
                {
                    'date': we.session.date.strftime('%d/%m'),
                    'weight': we.weight,
                    'sets': we.sets,
                    'reps': we.reps,
                    'volume': we.weight * we.reps * we.sets
                    if we.weight and we.reps
                    else 0,
                }
                for we in workout_exercises[-10:]  # Last 10 workouts
            ],
        }
