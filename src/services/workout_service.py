from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from database.connection import db
from database.models import AerobicExercise, Exercise, ExerciseType, WorkoutExercise, WorkoutSession


class WorkoutService:
    """Serviço para gerenciar salvamento de treinos"""

    def __init__(self):
        self.db = db

    def add_exercises_to_session(
        self,
        session_id: int,
        parsed_data: Dict[str, Any],
        user_id: str,
    ) -> bool:
        """Adiciona exercícios a uma sessão EXISTENTE
        
        Returns:
            True se sucesso, False se erro

        """
        session = self.db.get_session()

        try:
            # Buscar sessão
            workout_session = session.query(WorkoutSession).filter_by(
                session_id=session_id,
            ).first()

            if not workout_session:
                print(f"❌ Sessão {session_id} não encontrada")
                return False

            # Atualizar dados da sessão (se fornecidos)
            if parsed_data.get("body_weight_kg") and not workout_session.body_weight_kg:
                workout_session.body_weight_kg = parsed_data.get("body_weight_kg")

            if parsed_data.get("energy_level") and not workout_session.energy_level:
                workout_session.energy_level = parsed_data.get("energy_level")

            if parsed_data.get("notes"):
                if workout_session.notes:
                    workout_session.notes += f"\n{parsed_data.get('notes')}"
                else:
                    workout_session.notes = parsed_data.get("notes")

            # Contar exercícios já existentes (para order_in_workout)
            existing_resistance = len(workout_session.exercises)
            existing_aerobic = len(workout_session.aerobics)

            # Adicionar exercícios de RESISTÊNCIA
            for idx, ex_data in enumerate(parsed_data.get("resistance_exercises", [])):
                exercise = self._get_or_create_exercise(
                    session=session,
                    name=ex_data["name"],
                    type=ExerciseType.RESISTENCIA,
                )

                workout_exercise = WorkoutExercise(
                    session_id=session_id,
                    exercise_id=exercise.exercise_id,
                    order_in_workout=existing_resistance + idx + 1,  # Continua numeração
                    sets=ex_data.get("sets"),
                    reps=ex_data.get("reps"),
                    weight_kg=ex_data.get("weight_kg"),
                    notes=ex_data.get("notes"),
                )
                session.add(workout_exercise)

            # Adicionar exercícios AERÓBICOS
            for idx, ex_data in enumerate(parsed_data.get("aerobic_exercises", [])):
                exercise = self._get_or_create_exercise(
                    session=session,
                    name=ex_data["name"],
                    type=ExerciseType.AEROBICO,
                )

                aerobic_exercise = AerobicExercise(
                    session_id=session_id,
                    exercise_id=exercise.exercise_id,
                    duration_minutes=ex_data.get("duration_minutes"),
                    distance_km=ex_data.get("distance_km"),
                    intensity_level=ex_data.get("intensity_level"),
                    notes=ex_data.get("notes"),
                )
                session.add(aerobic_exercise)

            # Commit
            session.commit()

            resistance_count = len(parsed_data.get("resistance_exercises", []))
            aerobic_count = len(parsed_data.get("aerobic_exercises", []))

            print(f"✅ Adicionado à sessão #{session_id}: {resistance_count} resistência, {aerobic_count} aeróbico")
            return True

        except Exception as e:
            session.rollback()
            print(f"❌ Erro ao adicionar exercícios: {e}")
            return False
        finally:
            session.close()

    def _get_or_create_exercise(
        self,
        session: Session,
        name: str,
        type: ExerciseType,
    ) -> Exercise:
        """Busca exercício ou cria se não existir"""
        name_lower = name.lower().strip()

        exercise = session.query(Exercise).filter_by(name=name_lower).first()

        if not exercise:
            exercise = Exercise(
                name=name_lower,
                type=type,
            )
            session.add(exercise)
            session.flush()

        return exercise

    def get_session_summary(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Retorna resumo de uma sessão"""
        session = self.db.get_session()

        try:
            workout_session = session.query(WorkoutSession).filter_by(
                session_id=session_id,
            ).first()

            if not workout_session:
                return None

            # Contar exercícios
            resistance_count = len(workout_session.exercises)
            aerobic_count = len(workout_session.aerobics)

            # Calcular duração
            if workout_session.start_time and workout_session.end_time:
                duration = workout_session.end_time - workout_session.start_time
                duration_minutes = int(duration.total_seconds() / 60)
            else:
                duration_minutes = 0

            return {
                "session_id": session_id,
                "date": workout_session.date,
                "audio_count": workout_session.audio_count,
                "resistance_count": resistance_count,
                "aerobic_count": aerobic_count,
                "duration_minutes": duration_minutes,
                "exercises": workout_session.exercises,
                "aerobics": workout_session.aerobics,
            }

        finally:
            session.close()

# Instância global
_workout_service = None

def get_workout_service() -> WorkoutService:
    """Retorna instância única do serviço de workout"""
    global _workout_service
    if _workout_service is None:
        _workout_service = WorkoutService()
    return _workout_service
