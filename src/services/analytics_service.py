"""Analytics service for workout statistics and progress tracking"""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from sqlalchemy.orm import joinedload
from sqlalchemy import func, desc

from database.connection import db
from database.models import WorkoutSession, WorkoutExercise, AerobicExercise, Exercise, SessionStatus
from services.exceptions import ValidationError, DatabaseError

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for generating workout analytics and statistics"""

    def __init__(self):
        self.db = db

    def get_workout_analytics(
        self, 
        user_id: str,
        days: int = 30,
        include_active: bool = True
    ) -> Dict[str, Any]:
        """Get comprehensive workout analytics for a user
        
        Args:
            user_id: User ID
            days: Number of days to look back (default: 30)
            include_active: Whether to include active sessions
            
        Returns:
            Dict with comprehensive analytics
        """
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")
            
        if days <= 0:
            raise ValidationError("Days must be positive")

        session = self.db.get_session()
        
        try:
            # Calculate date range
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Build base query
            query = (
                session.query(WorkoutSession)
                .options(
                    joinedload(WorkoutSession.exercises).joinedload("exercise"),
                    joinedload(WorkoutSession.aerobics).joinedload("exercise")
                )
                .filter_by(user_id=user_id)
                .filter(WorkoutSession.date >= start_date)
                .filter(WorkoutSession.date <= end_date)
            )
            
            if not include_active:
                query = query.filter(WorkoutSession.status == SessionStatus.FINALIZADA)
                
            sessions = query.order_by(desc(WorkoutSession.date)).all()
            
            if not sessions:
                return self._empty_analytics(days, start_date, end_date)
            
            # Calculate all analytics
            analytics = {
                "period": {
                    "days": days,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "total_sessions": len(sessions)
                },
                "session_stats": self._calculate_session_stats(sessions),
                "exercise_stats": self._calculate_exercise_stats(sessions),
                "progress_trends": self._calculate_progress_trends(sessions),
                "muscle_group_distribution": self._calculate_muscle_group_distribution(sessions),
                "workout_frequency": self._calculate_workout_frequency(sessions, days),
                "personal_records": self._calculate_personal_records(sessions),
                "weekly_breakdown": self._calculate_weekly_breakdown(sessions, start_date)
            }
            
            return analytics
            
        except (ValidationError, DatabaseError):
            raise
        except Exception as e:
            logger.exception("Error calculating workout analytics")
            raise DatabaseError(
                "Failed to calculate workout analytics",
                f"Internal error: {str(e)}"
            )
        finally:
            session.close()

    def get_exercise_progress(
        self, 
        user_id: str, 
        exercise_name: str,
        days: int = 90
    ) -> Dict[str, Any]:
        """Get detailed progress for a specific exercise
        
        Args:
            user_id: User ID
            exercise_name: Name of the exercise
            days: Number of days to look back
            
        Returns:
            Dict with exercise-specific progress data
        """
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")
            
        if not exercise_name or not exercise_name.strip():
            raise ValidationError("Exercise name is required")

        session = self.db.get_session()
        
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Find exercise entries
            exercise_entries = (
                session.query(WorkoutExercise)
                .join(WorkoutSession)
                .join(Exercise)
                .filter(WorkoutSession.user_id == user_id)
                .filter(Exercise.name.ilike(f"%{exercise_name.lower()}%"))
                .filter(WorkoutSession.date >= start_date)
                .filter(WorkoutSession.date <= end_date)
                .order_by(desc(WorkoutSession.date))
                .all()
            )
            
            if not exercise_entries:
                return {
                    "exercise_name": exercise_name,
                    "found": False,
                    "message": f"No data found for exercise '{exercise_name}' in the last {days} days"
                }
            
            progress_data = []
            max_weight = 0
            max_volume = 0
            total_sessions = len(exercise_entries)
            
            for entry in exercise_entries:
                # Calculate session metrics
                weights = entry.weights_kg or []
                reps = entry.reps or []
                
                if weights and reps:
                    session_max_weight = max(weights) if weights else 0
                    session_volume = sum(w * r for w, r in zip(weights, reps) if w and r)
                    
                    max_weight = max(max_weight, session_max_weight)
                    max_volume = max(max_volume, session_volume)
                    
                    progress_data.append({
                        "date": entry.session.date.isoformat(),
                        "sets": entry.sets,
                        "reps": reps,
                        "weights_kg": weights,
                        "max_weight": session_max_weight,
                        "total_volume": session_volume,
                        "perceived_difficulty": entry.perceived_difficulty,
                        "rest_seconds": entry.rest_seconds
                    })
            
            # Calculate trends
            if len(progress_data) >= 2:
                first_session = progress_data[-1]  # Oldest
                last_session = progress_data[0]    # Newest
                
                weight_change = last_session["max_weight"] - first_session["max_weight"]
                volume_change = last_session["total_volume"] - first_session["total_volume"]
            else:
                weight_change = 0
                volume_change = 0
            
            return {
                "exercise_name": exercise_entries[0].exercise.name,
                "found": True,
                "period": {
                    "days": days,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "summary": {
                    "total_sessions": total_sessions,
                    "max_weight_ever": max_weight,
                    "max_volume_ever": max_volume,
                    "weight_progression": weight_change,
                    "volume_progression": volume_change
                },
                "progress_history": progress_data
            }
            
        except (ValidationError, DatabaseError):
            raise
        except Exception as e:
            logger.exception("Error calculating exercise progress")
            raise DatabaseError(
                "Failed to calculate exercise progress",
                f"Internal error: {str(e)}"
            )
        finally:
            session.close()

    def _empty_analytics(self, days: int, start_date: date, end_date: date) -> Dict[str, Any]:
        """Return empty analytics structure"""
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_sessions": 0
            },
            "message": f"No workout data found in the last {days} days"
        }

    def _calculate_session_stats(self, sessions: List[WorkoutSession]) -> Dict[str, Any]:
        """Calculate session-level statistics"""
        total_sessions = len(sessions)
        finished_sessions = sum(1 for s in sessions if s.status == SessionStatus.FINALIZADA)
        
        # Average duration for finished sessions
        durations = [s.duration_minutes for s in sessions if s.duration_minutes]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Audio counts
        audio_counts = [s.audio_count for s in sessions if s.audio_count]
        avg_audios = sum(audio_counts) / len(audio_counts) if audio_counts else 0
        
        # Energy levels
        energy_levels = [s.energy_level for s in sessions if s.energy_level]
        avg_energy = sum(energy_levels) / len(energy_levels) if energy_levels else 0
        
        return {
            "total_sessions": total_sessions,
            "finished_sessions": finished_sessions,
            "completion_rate": (finished_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            "average_duration_minutes": round(avg_duration, 1),
            "average_audios_per_session": round(avg_audios, 1),
            "average_energy_level": round(avg_energy, 1)
        }

    def _calculate_exercise_stats(self, sessions: List[WorkoutSession]) -> Dict[str, Any]:
        """Calculate exercise-level statistics"""
        resistance_exercises = []
        aerobic_exercises = []
        
        for session in sessions:
            resistance_exercises.extend(session.exercises)
            aerobic_exercises.extend(session.aerobics)
        
        # Resistance exercise stats
        resistance_stats = self._analyze_resistance_exercises(resistance_exercises)
        
        # Aerobic exercise stats
        aerobic_stats = self._analyze_aerobic_exercises(aerobic_exercises)
        
        return {
            "resistance": resistance_stats,
            "aerobic": aerobic_stats,
            "total_exercises": len(resistance_exercises) + len(aerobic_exercises)
        }

    def _analyze_resistance_exercises(self, exercises: List[WorkoutExercise]) -> Dict[str, Any]:
        """Analyze resistance exercises"""
        if not exercises:
            return {"total_exercises": 0}
        
        # Group by exercise name
        exercise_counts = defaultdict(int)
        total_volume = 0
        total_sets = 0
        difficulties = []
        
        for ex in exercises:
            exercise_counts[ex.exercise.name] += 1
            total_sets += ex.sets or 0
            
            if ex.perceived_difficulty:
                difficulties.append(ex.perceived_difficulty)
            
            # Calculate volume
            if ex.weights_kg and ex.reps:
                weights = ex.weights_kg
                reps = ex.reps
                for w, r in zip(weights, reps):
                    if w and r:
                        total_volume += w * r
        
        # Most trained exercises
        most_trained = sorted(exercise_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_exercises": len(exercises),
            "unique_exercises": len(exercise_counts),
            "total_sets": total_sets,
            "total_volume_kg": round(total_volume, 1),
            "average_difficulty": round(sum(difficulties) / len(difficulties), 1) if difficulties else 0,
            "most_trained": [{"name": name, "count": count} for name, count in most_trained]
        }

    def _analyze_aerobic_exercises(self, exercises: List[AerobicExercise]) -> Dict[str, Any]:
        """Analyze aerobic exercises"""
        if not exercises:
            return {"total_exercises": 0}
        
        exercise_counts = defaultdict(int)
        total_duration = 0
        total_distance = 0
        
        for ex in exercises:
            exercise_counts[ex.exercise.name] += 1
            
            if ex.duration_minutes:
                total_duration += ex.duration_minutes
            if ex.distance_km:
                total_distance += ex.distance_km
        
        most_trained = sorted(exercise_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_exercises": len(exercises),
            "unique_exercises": len(exercise_counts),
            "total_duration_minutes": round(total_duration, 1),
            "total_distance_km": round(total_distance, 1),
            "most_trained": [{"name": name, "count": count} for name, count in most_trained]
        }

    def _calculate_muscle_group_distribution(self, sessions: List[WorkoutSession]) -> Dict[str, Any]:
        """Calculate muscle group distribution"""
        muscle_group_counts = defaultdict(int)
        
        for session in sessions:
            for ex in session.exercises:
                if ex.exercise.muscle_group:
                    muscle_group_counts[ex.exercise.muscle_group] += 1
        
        total = sum(muscle_group_counts.values())
        
        if total == 0:
            return {"distribution": {}}
        
        distribution = {
            muscle: {
                "count": count,
                "percentage": round(count / total * 100, 1)
            }
            for muscle, count in muscle_group_counts.items()
        }
        
        return {
            "distribution": distribution,
            "most_trained_muscle": max(muscle_group_counts.items(), key=lambda x: x[1])[0] if muscle_group_counts else None
        }

    def _calculate_workout_frequency(self, sessions: List[WorkoutSession], days: int) -> Dict[str, Any]:
        """Calculate workout frequency metrics"""
        if not sessions:
            return {"frequency_per_week": 0}
        
        # Group sessions by date
        dates = set(session.date for session in sessions)
        unique_days = len(dates)
        
        # Calculate frequency
        frequency_per_week = (unique_days / days) * 7 if days > 0 else 0
        
        # Find longest streak
        sorted_dates = sorted(dates)
        current_streak = 1
        max_streak = 1
        
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days <= 2:  # Allow 1 day gap
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        return {
            "frequency_per_week": round(frequency_per_week, 1),
            "unique_workout_days": unique_days,
            "longest_streak_days": max_streak,
            "consistency_score": round((unique_days / days) * 100, 1) if days > 0 else 0
        }

    def _calculate_progress_trends(self, sessions: List[WorkoutSession]) -> Dict[str, Any]:
        """Calculate progress trends over time"""
        if len(sessions) < 2:
            return {"trend": "insufficient_data"}
        
        # Sort by date
        sorted_sessions = sorted(sessions, key=lambda s: s.date)
        
        # Calculate metrics over time
        weekly_volumes = defaultdict(float)
        weekly_sets = defaultdict(int)
        
        for session in sorted_sessions:
            # Get week number
            week_key = session.date.strftime("%Y-W%U")
            
            for ex in session.exercises:
                weekly_sets[week_key] += ex.sets or 0
                
                if ex.weights_kg and ex.reps:
                    weights = ex.weights_kg
                    reps = ex.reps
                    for w, r in zip(weights, reps):
                        if w and r:
                            weekly_volumes[week_key] += w * r
        
        if len(weekly_volumes) < 2:
            return {"trend": "insufficient_data"}
        
        # Calculate trend
        weeks = sorted(weekly_volumes.keys())
        first_week_volume = weekly_volumes[weeks[0]]
        last_week_volume = weekly_volumes[weeks[-1]]
        
        volume_change = last_week_volume - first_week_volume
        volume_change_percent = (volume_change / first_week_volume * 100) if first_week_volume > 0 else 0
        
        return {
            "trend": "improving" if volume_change > 0 else "declining" if volume_change < 0 else "stable",
            "volume_change_kg": round(volume_change, 1),
            "volume_change_percent": round(volume_change_percent, 1),
            "weekly_data": dict(weekly_volumes)
        }

    def _calculate_personal_records(self, sessions: List[WorkoutSession]) -> Dict[str, Any]:
        """Calculate personal records"""
        exercise_records = {}
        
        for session in sessions:
            for ex in session.exercises:
                exercise_name = ex.exercise.name
                
                if exercise_name not in exercise_records:
                    exercise_records[exercise_name] = {
                        "max_weight": 0,
                        "max_volume": 0,
                        "max_reps": 0,
                        "max_weight_date": None,
                        "max_volume_date": None,
                        "max_reps_date": None
                    }
                
                # Check for new records
                if ex.weights_kg:
                    max_weight = max(ex.weights_kg)
                    if max_weight > exercise_records[exercise_name]["max_weight"]:
                        exercise_records[exercise_name]["max_weight"] = max_weight
                        exercise_records[exercise_name]["max_weight_date"] = session.date.isoformat()
                
                if ex.reps:
                    max_reps = max(ex.reps)
                    if max_reps > exercise_records[exercise_name]["max_reps"]:
                        exercise_records[exercise_name]["max_reps"] = max_reps
                        exercise_records[exercise_name]["max_reps_date"] = session.date.isoformat()
                
                if ex.weights_kg and ex.reps:
                    volume = sum(w * r for w, r in zip(ex.weights_kg, ex.reps) if w and r)
                    if volume > exercise_records[exercise_name]["max_volume"]:
                        exercise_records[exercise_name]["max_volume"] = volume
                        exercise_records[exercise_name]["max_volume_date"] = session.date.isoformat()
        
        return {"exercise_records": exercise_records}

    def _calculate_weekly_breakdown(self, sessions: List[WorkoutSession], start_date: date) -> Dict[str, Any]:
        """Calculate weekly breakdown of workouts"""
        weekly_stats = defaultdict(lambda: {
            "sessions": 0,
            "total_exercises": 0,
            "total_volume": 0
        })
        
        for session in sessions:
            week_key = session.date.strftime("%Y-W%U")
            weekly_stats[week_key]["sessions"] += 1
            weekly_stats[week_key]["total_exercises"] += len(session.exercises) + len(session.aerobics)
            
            # Calculate volume
            for ex in session.exercises:
                if ex.weights_kg and ex.reps:
                    volume = sum(w * r for w, r in zip(ex.weights_kg, ex.reps) if w and r)
                    weekly_stats[week_key]["total_volume"] += volume
        
        return {"weekly_breakdown": dict(weekly_stats)}