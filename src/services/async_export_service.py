"""Async export service for workout data in multiple formats"""

import csv
import json
import logging
from datetime import date, datetime
from io import StringIO
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database.async_connection import get_async_session_context
from database.models import (
    AerobicExercise,
    SessionStatus,
    WorkoutExercise,
    WorkoutSession,
)
from models.service_models import DateRange, ExportPreview, ExportResult, ExportSummary
from services.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


class AsyncExportService:
    """Async service for exporting workout data in various formats"""

    async def export_user_data(
        self,
        user_id: str,
        format: str = "json",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_active: bool = True,
    ) -> ExportResult:
        """Export all workout data for a user (async)

        Args:
            user_id: User ID to export data for
            format: Export format ('json' or 'csv')
            start_date: Optional start date filter
            end_date: Optional end date filter
            include_active: Whether to include active (non-finished) sessions

        Returns:
            ExportResult with exported data and metadata

        Raises:
            ValidationError: If parameters are invalid
            DatabaseError: If database operation fails

        """
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        if format not in ["json", "csv"]:
            raise ValidationError("Format must be 'json' or 'csv'")

        async with get_async_session_context() as session:
            try:
                # Get user's workout sessions
                sessions = await self._get_user_sessions(
                    session,
                    user_id,
                    start_date,
                    end_date,
                    include_active,
                )

                if not sessions:
                    # Return empty result with message
                    return ExportResult(
                        success=False,
                        format=format,
                        data="",
                        summary=ExportSummary(
                            total_sessions=0,
                            completed_sessions=0,
                            active_sessions=0,
                            total_exercises=0,
                            resistance_exercises=0,
                            aerobic_exercises=0,
                            total_duration_minutes=0,
                            date_range=None,
                        ),
                        export_date=datetime.now().isoformat(),
                        user_id=user_id,
                        message="No workout data found for export",
                    )

                # Export data based on format
                if format == "json":
                    export_data = await self._export_to_json(sessions)
                else:  # csv
                    export_data = await self._export_to_csv(sessions)

                # Calculate summary statistics
                summary = await self._calculate_export_summary(sessions)

                return ExportResult(
                    success=True,
                    format=format,
                    data=export_data,
                    summary=summary,
                    export_date=datetime.now().isoformat(),
                    user_id=user_id,
                )

            except Exception as e:
                logger.exception(f"Error exporting data for user {user_id}")
                raise DatabaseError(f"Failed to export data: {e!s}")

    async def get_export_summary(self, user_id: str) -> ExportPreview:
        """Get summary of data available for export (async)

        Args:
            user_id: User ID

        Returns:
            ExportPreview with export summary

        """
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        async with get_async_session_context() as session:
            try:
                # Get all sessions for user
                sessions_stmt = (
                    select(WorkoutSession)
                    .where(
                        WorkoutSession.user_id == user_id,
                    )
                    .options(
                        joinedload(WorkoutSession.exercises),
                        joinedload(WorkoutSession.aerobics),
                    )
                )

                result = await session.execute(sessions_stmt)
                sessions = result.scalars().unique().all()

                if not sessions:
                    return ExportPreview(
                        total_sessions=0,
                        completed_sessions=0,
                        active_sessions=0,
                        total_exercises=0,
                        resistance_exercises=0,
                        aerobic_exercises=0,
                        date_range=None,
                        estimated_size_mb=0.0,
                    )

                # Calculate summary
                completed_sessions = len([s for s in sessions if s.status == SessionStatus.FINALIZADA])
                active_sessions = len([s for s in sessions if s.status == SessionStatus.ATIVA])

                total_resistance = sum(len(s.exercises) for s in sessions)
                total_aerobic = sum(len(s.aerobics) for s in sessions)
                total_exercises = total_resistance + total_aerobic

                # Date range
                dates = [s.date for s in sessions]
                date_range = (
                    DateRange(
                        start=min(dates).strftime("%d/%m/%Y"),
                        end=max(dates).strftime("%d/%m/%Y"),
                    )
                    if dates
                    else None
                )

                # Estimate export size (rough calculation)
                estimated_size_mb = await self._estimate_export_size(sessions)

                return ExportPreview(
                    total_sessions=len(sessions),
                    completed_sessions=completed_sessions,
                    active_sessions=active_sessions,
                    total_exercises=total_exercises,
                    resistance_exercises=total_resistance,
                    aerobic_exercises=total_aerobic,
                    date_range=date_range,
                    estimated_size_mb=estimated_size_mb,
                )

            except Exception as e:
                logger.exception(f"Error getting export summary for user {user_id}")
                raise DatabaseError(f"Failed to get export summary: {e!s}")

    async def _get_user_sessions(
        self,
        session,
        user_id: str,
        start_date: Optional[date],
        end_date: Optional[date],
        include_active: bool,
    ) -> List[WorkoutSession]:
        """Get user sessions with filters (async)"""
        # Build query
        stmt = (
            select(WorkoutSession)
            .where(
                WorkoutSession.user_id == user_id,
            )
            .options(
                joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.exercise),
                joinedload(WorkoutSession.aerobics).joinedload(AerobicExercise.exercise),
            )
        )

        # Add date filters
        if start_date:
            stmt = stmt.where(WorkoutSession.date >= start_date)
        if end_date:
            stmt = stmt.where(WorkoutSession.date <= end_date)

        # Add status filter
        if not include_active:
            stmt = stmt.where(WorkoutSession.status == SessionStatus.FINALIZADA)

        # Order by date
        stmt = stmt.order_by(WorkoutSession.date.desc())

        result = await session.execute(stmt)
        return result.scalars().unique().all()

    async def _export_to_json(self, sessions: List[WorkoutSession]) -> str:
        """Export sessions to JSON format (async)"""
        export_data = {
            "export_info": {
                "format": "json",
                "export_date": datetime.now().isoformat(),
                "total_sessions": len(sessions),
            },
            "sessions": [],
        }

        for session in sessions:
            session_data = {
                "session_id": session.session_id,
                "date": session.date.isoformat(),
                "status": session.status.value,
                "duration_minutes": session.duration_minutes,
                "notes": session.notes,
                "created_at": session.created_at.isoformat(),
                "workout_exercises": [],
                "aerobic_exercises": [],
            }

            # Add workout exercises
            for we in session.exercises:
                exercise_data = {
                    "exercise_name": we.exercise.name if we.exercise else "Unknown",
                    "muscle_group": we.exercise.muscle_group if we.exercise else None,
                    "equipment": we.exercise.equipment if we.exercise else None,
                    "sets": we.sets,
                    "reps": we.reps,
                    "weight": we.weights_kg,
                    "rest_seconds": we.rest_seconds,
                    "notes": we.notes,
                }
                session_data["workout_exercises"].append(exercise_data)

            # Add aerobic exercises
            for ae in session.aerobics:
                aerobic_data = {
                    "exercise_name": ae.exercise.name if ae.exercise else "Unknown",
                    "duration_minutes": ae.duration_minutes,
                    "distance_km": ae.distance_km,
                    "calories_burned": ae.calories_burned,
                    "intensity_level": ae.intensity_level,
                    "notes": ae.notes,
                }
                session_data["aerobic_exercises"].append(aerobic_data)

            export_data["sessions"].append(session_data)

        return json.dumps(export_data, indent=2, ensure_ascii=False)

    async def _export_to_csv(self, sessions: List[WorkoutSession]) -> str:
        """Export sessions to CSV format (async)"""
        output = StringIO()

        # Create CSV writer
        fieldnames = [
            "session_id",
            "date",
            "status",
            "duration_minutes",
            "exercise_type",
            "exercise_name",
            "muscle_group",
            "equipment",
            "sets",
            "reps",
            "weight",
            "rest_seconds",
            "duration_minutes_cardio",
            "distance_km",
            "calories",
            "intensity",
            "notes",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for session in sessions:
            base_row = {
                "session_id": session.session_id,
                "date": session.date.isoformat(),
                "status": session.status.value,
                "duration_minutes": session.duration_minutes,
            }

            # Write workout exercises
            for we in session.exercises:
                row = base_row.copy()
                row.update(
                    {
                        "exercise_type": "resistance",
                        "exercise_name": we.exercise.name if we.exercise else "Unknown",
                        "muscle_group": (we.exercise.muscle_group if we.exercise else None),
                        "equipment": we.exercise.equipment if we.exercise else None,
                        "sets": we.sets,
                        "reps": we.reps,
                        "weight": we.weights_kg,
                        "rest_seconds": we.rest_seconds,
                        "notes": we.notes,
                    }
                )
                writer.writerow(row)

            # Write aerobic exercises
            for ae in session.aerobics:
                row = base_row.copy()
                row.update(
                    {
                        "exercise_type": "aerobic",
                        "exercise_name": ae.exercise.name if ae.exercise else "Unknown",
                        "duration_minutes_cardio": ae.duration_minutes,
                        "distance_km": ae.distance_km,
                        "calories": ae.calories_burned,
                        "intensity": ae.intensity_level,
                        "notes": ae.notes,
                    }
                )
                writer.writerow(row)

            # If session has no exercises, write a row for the session itself
            if not session.exercises and not session.aerobics:
                row = base_row.copy()
                row.update({"notes": session.notes})
                writer.writerow(row)

        return output.getvalue()

    async def _calculate_export_summary(self, sessions: List[WorkoutSession]) -> ExportSummary:
        """Calculate summary statistics for exported data (async)"""
        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s.status == SessionStatus.FINALIZADA])

        total_resistance = sum(len(s.exercises) for s in sessions)
        total_aerobic = sum(len(s.aerobics) for s in sessions)
        total_exercises = total_resistance + total_aerobic

        # Date range
        dates = [s.date for s in sessions]
        date_range = (
            DateRange(
                start=min(dates).strftime("%d/%m/%Y"),
                end=max(dates).strftime("%d/%m/%Y"),
            )
            if dates
            else None
        )

        # Total duration
        total_duration = sum(s.duration_minutes or 0 for s in sessions)

        return ExportSummary(
            total_sessions=total_sessions,
            completed_sessions=completed_sessions,
            active_sessions=total_sessions - completed_sessions,
            total_exercises=total_exercises,
            resistance_exercises=total_resistance,
            aerobic_exercises=total_aerobic,
            total_duration_minutes=total_duration,
            date_range=date_range,
        )

    async def _estimate_export_size(self, sessions: List[WorkoutSession]) -> float:
        """Estimate export file size in MB (async)"""
        # Rough calculation based on data complexity
        base_size_per_session = 0.5  # KB
        base_size_per_exercise = 0.2  # KB

        total_exercises = sum(len(s.exercises) + len(s.aerobics) for s in sessions)

        estimated_kb = (len(sessions) * base_size_per_session) + (total_exercises * base_size_per_exercise)
        estimated_mb = estimated_kb / 1024

        return round(estimated_mb, 2)
