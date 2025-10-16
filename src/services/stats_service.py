import logging
from dataclasses import dataclass
from typing import Dict, List

from database.models import WorkoutSession

logger = logging.getLogger(__name__)

@dataclass
class SessionStats:
    """Value Object para estatísticas de sessão"""

    total_exercises: int = 0
    resistance_exercises: int = 0
    aerobic_exercises: int = 0
    total_sets: int = 0
    total_volume_kg: float = 0.0
    muscle_groups: List[str] = None
    cardio_minutes: float = 0.0
    audio_count: int = 0

    def __post_init__(self):
        if self.muscle_groups is None:
            self.muscle_groups = []

    def to_dict(self) -> Dict:
        return {
            "total_exercises": self.total_exercises,
            "resistance_exercises": self.resistance_exercises,
            "aerobic_exercises": self.aerobic_exercises,
            "total_sets": self.total_sets,
            "total_volume_kg": self.total_volume_kg,
            "muscle_groups": self.muscle_groups,
            "cardio_minutes": self.cardio_minutes,
            "audio_count": self.audio_count,
        }


class SessionStatsCalculator:
    """Strategy Pattern para cálculo de estatísticas"""

    @staticmethod
    def calculate_safe(workout_session: WorkoutSession) -> SessionStats:
        """Template Method que coordena os cálculos"""
        if workout_session is None:
            logger.error("workout_session é None")
            return SessionStats()

        stats = SessionStats()

        # Cada método é responsável por sua própria validação
        resistance = SessionStatsCalculator._get_resistance_exercises(workout_session)
        aerobic = SessionStatsCalculator._get_aerobic_exercises(workout_session)

        stats.resistance_exercises = len(resistance)
        stats.aerobic_exercises = len(aerobic)
        stats.total_exercises = stats.resistance_exercises + stats.aerobic_exercises

        stats.total_sets = SessionStatsCalculator._calculate_total_sets(resistance)
        stats.total_volume_kg = SessionStatsCalculator._calculate_volume(resistance)
        stats.muscle_groups = SessionStatsCalculator._extract_muscle_groups(resistance)
        stats.cardio_minutes = SessionStatsCalculator._calculate_cardio_time(aerobic)
        stats.audio_count = getattr(workout_session, "audio_count", 0)

        return stats

    @staticmethod
    def _get_resistance_exercises(session: WorkoutSession) -> List:
        """Extrai exercícios de resistência de forma segura"""
        try:
            exercises = session.exercises
            return exercises if exercises is not None else []
        except AttributeError:
            logger.warning("session.exercises não existe")
            return []

    @staticmethod
    def _get_aerobic_exercises(session: WorkoutSession) -> List:
        """Extrai exercícios aeróbicos de forma segura"""
        try:
            exercises = session.aerobics
            return exercises if exercises is not None else []
        except AttributeError:
            logger.warning("session.aerobics não existe")
            return []

    @staticmethod
    def _calculate_total_sets(exercises: List) -> int:
        """Calcula total de séries"""
        try:
            return sum(
                ex.sets for ex in exercises
                if ex and hasattr(ex, "sets") and ex.sets is not None
            )
        except (TypeError, AttributeError) as e:
            logger.warning(f"Erro ao calcular sets: {e}")
            return 0

    @staticmethod
    def _calculate_volume(exercises: List) -> float:
        """Calcula volume total (reps × peso)"""
        try:
            total = 0.0
            for ex in exercises:
                if not ex:
                    continue
                reps = getattr(ex, "reps", None) or []
                weights = getattr(ex, "weights_kg", None) or []

                # Zip para garantir pares válidos
                total += sum(r * w for r, w in zip(reps, weights) if r and w)
            return total
        except (TypeError, AttributeError, ValueError) as e:
            logger.warning(f"Erro ao calcular volume: {e}")
            return 0.0

    @staticmethod
    def _extract_muscle_groups(exercises: List) -> List[str]:
        """Extrai grupos musculares únicos"""
        muscle_groups = set()
        for ex in exercises:
            try:
                # Acesso seguro a atributos aninhados
                if ex and hasattr(ex, "exercise") and ex.exercise:
                    muscle_group = getattr(ex.exercise, "muscle_group", None)
                    if muscle_group:
                        muscle_groups.add(muscle_group)
            except AttributeError as e:
                logger.debug(f"Exercício sem muscle_group válido: {e}")
                continue

        return list(muscle_groups)

    @staticmethod
    def _calculate_cardio_time(aerobic_exercises: List) -> float:
        """Calcula tempo total de cardio"""
        try:
            return sum(
                getattr(ex, "duration_minutes", 0) or 0
                for ex in aerobic_exercises
                if ex
            )
        except (TypeError, AttributeError) as e:
            logger.warning(f"Erro ao calcular cardio: {e}")
            return 0.0


