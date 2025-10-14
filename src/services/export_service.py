"""Export service for workout data in multiple formats"""

import csv
import json
import logging
from datetime import datetime, date
from io import StringIO
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import joinedload

from database.connection import db
from database.models import WorkoutSession, SessionStatus, WorkoutExercise, AerobicExercise, Exercise
from services.exceptions import ValidationError, DatabaseError

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting workout data in various formats"""

    def __init__(self):
        self.db = db

    def export_user_data(
        self, 
        user_id: str, 
        format: str = "json",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_active: bool = True
    ) -> Dict[str, Any]:
        """Export all workout data for a user
        
        Args:
            user_id: User ID to export data for
            format: Export format ('json' or 'csv')
            start_date: Optional start date filter
            end_date: Optional end date filter  
            include_active: Whether to include active (non-finished) sessions
            
        Returns:
            Dict with exported data and metadata
            
        Raises:
            ValidationError: If parameters are invalid
            DatabaseError: If database operation fails
        """
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")
            
        if format not in ["json", "csv"]:
            raise ValidationError("Format must be 'json' or 'csv'")

        session = self.db.get_session()
        
        try:
            # Build query with optional filters
            query = (
                session.query(WorkoutSession)
                .options(
                    joinedload(WorkoutSession.exercises).joinedload(WorkoutExercise.exercise),
                    joinedload(WorkoutSession.aerobics).joinedload(AerobicExercise.exercise)
                )
                .filter_by(user_id=user_id)
            )
            
            if start_date:
                query = query.filter(WorkoutSession.date >= start_date)
            if end_date:
                query = query.filter(WorkoutSession.date <= end_date)
            if not include_active:
                query = query.filter(WorkoutSession.status == SessionStatus.FINALIZADA)
                
            sessions = query.order_by(WorkoutSession.date.desc()).all()
            
            if not sessions:
                return {
                    "success": True,
                    "message": "No workout data found for the specified criteria",
                    "data": None,
                    "format": format,
                    "export_metadata": self._get_export_metadata(user_id, 0, start_date, end_date)
                }
            
            # Export based on format
            if format == "json":
                exported_data = self._export_to_json(sessions)
            else:  # csv
                exported_data = self._export_to_csv(sessions)
                
            metadata = self._get_export_metadata(user_id, len(sessions), start_date, end_date)
            
            return {
                "success": True,
                "data": exported_data,
                "format": format,
                "export_metadata": metadata
            }
            
        except (ValidationError, DatabaseError):
            raise
        except Exception as e:
            logger.exception("Unexpected error during export")
            raise DatabaseError(
                "Failed to export workout data",
                f"Internal error: {str(e)}"
            )
        finally:
            session.close()

    def _export_to_json(self, sessions: List[WorkoutSession]) -> Dict[str, Any]:
        """Export sessions to JSON format"""
        export_data = {
            "export_info": {
                "format": "json",
                "exported_at": datetime.now().isoformat(),
                "total_sessions": len(sessions)
            },
            "sessions": []
        }
        
        for session in sessions:
            session_data = {
                "session_id": session.session_id,
                "date": session.date.isoformat(),
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "duration_minutes": session.duration_minutes,
                "status": session.status.value,
                "body_weight_kg": session.body_weight_kg,
                "energy_level": session.energy_level,
                "audio_count": session.audio_count,
                "notes": session.notes,
                "created_at": session.created_at.isoformat(),
                "resistance_exercises": [],
                "aerobic_exercises": []
            }
            
            # Add resistance exercises
            for workout_ex in session.exercises:
                ex_data = {
                    "exercise_name": workout_ex.exercise.name,
                    "muscle_group": workout_ex.exercise.muscle_group,
                    "equipment": workout_ex.exercise.equipment,
                    "order_in_workout": workout_ex.order_in_workout,
                    "sets": workout_ex.sets,
                    "reps": workout_ex.reps,
                    "weights_kg": workout_ex.weights_kg,
                    "rest_seconds": workout_ex.rest_seconds,
                    "perceived_difficulty": workout_ex.perceived_difficulty,
                    "notes": workout_ex.notes
                }
                session_data["resistance_exercises"].append(ex_data)
            
            # Add aerobic exercises
            for aerobic_ex in session.aerobics:
                ex_data = {
                    "exercise_name": aerobic_ex.exercise.name,
                    "duration_minutes": aerobic_ex.duration_minutes,
                    "distance_km": aerobic_ex.distance_km,
                    "average_heart_rate": aerobic_ex.average_heart_rate,
                    "calories_burned": aerobic_ex.calories_burned,
                    "intensity_level": aerobic_ex.intensity_level,
                    "notes": aerobic_ex.notes
                }
                session_data["aerobic_exercises"].append(ex_data)
            
            export_data["sessions"].append(session_data)
        
        return export_data

    def _export_to_csv(self, sessions: List[WorkoutSession]) -> str:
        """Export sessions to CSV format"""
        output = StringIO()
        
        # CSV headers for workout sessions
        headers = [
            "session_id", "date", "start_time", "end_time", "duration_minutes",
            "status", "body_weight_kg", "energy_level", "audio_count",
            "exercise_type", "exercise_name", "muscle_group", "equipment",
            "sets", "reps", "weights_kg", "rest_seconds", "perceived_difficulty",
            "duration_minutes_aerobic", "distance_km", "intensity_level",
            "exercise_notes", "session_notes"
        ]
        
        writer = csv.writer(output)
        writer.writerow(headers)
        
        for session in sessions:
            base_row = [
                session.session_id,
                session.date.isoformat(),
                session.start_time.isoformat() if session.start_time else "",
                session.end_time.isoformat() if session.end_time else "",
                session.duration_minutes or "",
                session.status.value,
                session.body_weight_kg or "",
                session.energy_level or "",
                session.audio_count or 0,
            ]
            
            # Add resistance exercises
            if session.exercises:
                for workout_ex in session.exercises:
                    row = base_row + [
                        "resistance",
                        workout_ex.exercise.name,
                        workout_ex.exercise.muscle_group or "",
                        workout_ex.exercise.equipment or "",
                        workout_ex.sets or "",
                        json.dumps(workout_ex.reps) if workout_ex.reps else "",
                        json.dumps(workout_ex.weights_kg) if workout_ex.weights_kg else "",
                        workout_ex.rest_seconds or "",
                        workout_ex.perceived_difficulty or "",
                        "",  # duration_minutes_aerobic
                        "",  # distance_km
                        "",  # intensity_level
                        workout_ex.notes or "",
                        session.notes or ""
                    ]
                    writer.writerow(row)
            
            # Add aerobic exercises
            if session.aerobics:
                for aerobic_ex in session.aerobics:
                    row = base_row + [
                        "aerobic",
                        aerobic_ex.exercise.name,
                        aerobic_ex.exercise.muscle_group or "",
                        aerobic_ex.exercise.equipment or "",
                        "",  # sets
                        "",  # reps
                        "",  # weights_kg
                        "",  # rest_seconds
                        "",  # perceived_difficulty
                        aerobic_ex.duration_minutes or "",
                        aerobic_ex.distance_km or "",
                        aerobic_ex.intensity_level or "",
                        aerobic_ex.notes or "",
                        session.notes or ""
                    ]
                    writer.writerow(row)
            
            # If session has no exercises, still add the session row
            if not session.exercises and not session.aerobics:
                row = base_row + ["", "", "", "", "", "", "", "", "", "", "", "", "", session.notes or ""]
                writer.writerow(row)
        
        return output.getvalue()

    def _get_export_metadata(
        self, 
        user_id: str, 
        session_count: int,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> Dict[str, Any]:
        """Generate export metadata"""
        return {
            "user_id": user_id,
            "exported_at": datetime.now().isoformat(),
            "total_sessions": session_count,
            "date_range": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None
            }
        }

    def get_export_summary(self, user_id: str) -> Dict[str, Any]:
        """Get summary of available data for export
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with export summary statistics
        """
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        session = self.db.get_session()
        
        try:
            sessions = session.query(WorkoutSession).filter_by(user_id=user_id).all()
            
            if not sessions:
                return {
                    "total_sessions": 0,
                    "date_range": None,
                    "status_breakdown": {},
                    "exercise_counts": {"resistance": 0, "aerobic": 0}
                }
            
            # Calculate statistics
            dates = [s.date for s in sessions if s.date]
            status_counts = {}
            total_resistance = 0
            total_aerobic = 0
            
            for s in sessions:
                status = s.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                total_resistance += len(s.exercises)
                total_aerobic += len(s.aerobics)
            
            return {
                "total_sessions": len(sessions),
                "date_range": {
                    "earliest": min(dates).isoformat() if dates else None,
                    "latest": max(dates).isoformat() if dates else None
                },
                "status_breakdown": status_counts,
                "exercise_counts": {
                    "resistance": total_resistance,
                    "aerobic": total_aerobic
                }
            }
            
        except Exception as e:
            logger.exception("Error getting export summary")
            raise DatabaseError(
                "Failed to get export summary",
                f"Internal error: {str(e)}"
            )
        finally:
            session.close()