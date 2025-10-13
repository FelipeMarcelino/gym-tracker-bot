"""Serviço para gerenciar sessões de treino e exercícios
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.connection import db
from database.models import AerobicExercise, Exercise, ExerciseType, SessionStatus, WorkoutExercise, WorkoutSession
from services.exercise_knowledge import infer_equipment, infer_muscle_group
from services.stats_service import SessionStatsCalculator
from services.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


class WorkoutService:
    """Serviço para gerenciar salvamento e finalização de treinos"""

    def __init__(self):
        self.db = db

    # =========================================================================
    # MÉTODOS PÚBLICOS - Operações Principais
    # =========================================================================


    def add_exercises_to_session(
        self,
        session_id: int,
        parsed_data: Dict[str, Any],
        user_id: str,
    ) -> bool:
        """Adiciona exercícios a uma sessão EXISTENTE
        
        Args:
            session_id: ID da sessão
            parsed_data: Dados parseados do LLM
            user_id: ID do usuário (para validação)
            
        Returns:
            True se sucesso
            
        Raises:
            ValidationError: Se os dados são inválidos
            DatabaseError: Se operação no banco falhar

        """
        if not session_id or session_id <= 0:
            raise ValidationError("ID da sessão inválido")
            
        if not user_id or not user_id.strip():
            raise ValidationError("ID do usuário é obrigatório")
            
        if not parsed_data or not isinstance(parsed_data, dict):
            raise ValidationError("Dados parseados inválidos")

        session = self.db.get_session()

        try:
            workout_session = session.query(WorkoutSession).filter_by(
                session_id=session_id,
            ).first()

            if not workout_session:
                raise ValidationError(f"Sessão {session_id} não encontrada")
                
            if workout_session.user_id != user_id:
                raise ValidationError("Usuário não autorizado para esta sessão")

            # Atualizar dados da sessão se fornecidos
            if parsed_data.get("body_weight_kg"):
                if not isinstance(parsed_data["body_weight_kg"], (int, float)) or parsed_data["body_weight_kg"] <= 0:
                    raise ValidationError("Peso corporal deve ser um número positivo")
                if not workout_session.body_weight_kg:
                    workout_session.body_weight_kg = parsed_data["body_weight_kg"]

            if parsed_data.get("energy_level"):
                energy = parsed_data["energy_level"]
                if not isinstance(energy, int) or energy < 1 or energy > 10:
                    raise ValidationError("Nível de energia deve ser um inteiro entre 1 e 10")
                if not workout_session.energy_level:
                    workout_session.energy_level = energy

            if parsed_data.get("notes"):
                notes = parsed_data["notes"]
                if not isinstance(notes, str):
                    raise ValidationError("Notas devem ser texto")
                if workout_session.notes:
                    workout_session.notes += f"\n{notes}"
                else:
                    workout_session.notes = notes

            # Contar exercícios já existentes
            existing_resistance = len(workout_session.exercises)

            # Adicionar exercícios de RESISTÊNCIA
            resistance_exercises = parsed_data.get("resistance_exercises", [])
            if resistance_exercises and not isinstance(resistance_exercises, list):
                raise ValidationError("resistance_exercises deve ser uma lista")
                
            for idx, ex_data in enumerate(resistance_exercises):
                if not isinstance(ex_data, dict):
                    raise ValidationError(f"Exercício de resistência {idx} deve ser um objeto")
                    
                if "name" not in ex_data or not ex_data["name"].strip():
                    raise ValidationError(f"Nome do exercício é obrigatório (exercício {idx})")

                exercise = self._get_or_create_exercise(
                    session=session,
                    name=ex_data["name"],
                    type=ExerciseType.RESISTENCIA,
                )

                # Validar e processar pesos
                weights_kg = self._validate_and_process_weights(ex_data, idx)

                # Validar repetições
                reps = ex_data.get("reps")
                if reps and not isinstance(reps, list):
                    raise ValidationError(f"Repetições devem ser uma lista (exercício {idx})")

                # Criar registro do exercício
                workout_exercise = WorkoutExercise(
                    session_id=session_id,
                    exercise_id=exercise.exercise_id,
                    order_in_workout=existing_resistance + idx + 1,
                    sets=ex_data.get("sets"),
                    reps=reps,
                    weights_kg=weights_kg,
                    rest_seconds=ex_data.get("rest_seconds"),
                    perceived_difficulty=ex_data.get("perceived_difficulty"),
                    notes=ex_data.get("notes"),
                )
                session.add(workout_exercise)

                logger.debug(f"Adicionado exercício: {ex_data['name']}")
                if ex_data.get("rest_seconds"):
                    logger.debug(f"   Descanso: {ex_data.get('rest_seconds')}s")
                if ex_data.get("perceived_difficulty"):
                    logger.debug(f"   RPE: {ex_data.get('perceived_difficulty')}/10")

            # Adicionar exercícios AERÓBICOS
            aerobic_exercises = parsed_data.get("aerobic_exercises", [])
            if aerobic_exercises and not isinstance(aerobic_exercises, list):
                raise ValidationError("aerobic_exercises deve ser uma lista")
                
            for idx, ex_data in enumerate(aerobic_exercises):
                if not isinstance(ex_data, dict):
                    raise ValidationError(f"Exercício aeróbico {idx} deve ser um objeto")
                    
                if "name" not in ex_data or not ex_data["name"].strip():
                    raise ValidationError(f"Nome do exercício aeróbico é obrigatório (exercício {idx})")

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
            session.refresh(workout_session)

            resistance_count = len(resistance_exercises)
            aerobic_count = len(aerobic_exercises)

            logger.info(f"Adicionado à sessão #{session_id}: {resistance_count} resistência, {aerobic_count} aeróbico")
            return True

        except (ValidationError, DatabaseError):
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro de banco de dados ao adicionar exercícios")
            raise DatabaseError(
                "Erro ao salvar exercícios no banco de dados",
                f"Erro SQLAlchemy: {str(e)}"
            )
        except Exception as e:
            session.rollback()
            logger.exception("Erro inesperado ao adicionar exercícios")
            raise DatabaseError(
                "Erro inesperado ao adicionar exercícios",
                f"Erro interno: {str(e)}"
            )
        finally:
            session.close()
            
    def _validate_and_process_weights(self, ex_data: Dict[str, Any], exercise_idx: int) -> Optional[list]:
        """Valida e processa pesos do exercício"""
        weights_kg = ex_data.get("weights_kg")
        
        if not weights_kg:
            # Compatibilidade com formato antigo
            single_weight = ex_data.get("weight_kg")
            if single_weight and ex_data.get("sets"):
                weights_kg = [single_weight] * ex_data.get("sets")
        
        if weights_kg:
            if not isinstance(weights_kg, list):
                raise ValidationError(f"Pesos devem ser uma lista (exercício {exercise_idx})")
                
            for i, weight in enumerate(weights_kg):
                if not isinstance(weight, (int, float)) or weight < 0:
                    raise ValidationError(f"Peso da série {i+1} deve ser um número não-negativo (exercício {exercise_idx})")
            
            # Validar que weights_kg tem o tamanho correto
            sets = ex_data.get("sets", 0)
            if len(weights_kg) != sets:
                logger.warning(f"Ajustando pesos: {len(weights_kg)} pesos mas {sets} séries")
                if len(weights_kg) < sets:
                    weights_kg.extend([weights_kg[-1]] * (sets - len(weights_kg)))
                else:
                    weights_kg = weights_kg[:sets]
                    
        return weights_kg

    def finish_session(self, session_id: int, user_id: str) -> Dict[str, Any]:
        """Finaliza uma sessão manualmente
        
        Args:
            session_id: ID da sessão
            user_id: ID do usuário (para validação)
            
        Returns:
            Dict com estatísticas da sessão ou erro

        """
        session = self.db.get_session()

        try:
            workout_session = session.query(WorkoutSession).filter_by(
                session_id=session_id,
                user_id=user_id,
            ).first()

            if not workout_session:
                return {"success": False, "error": "Sessão não encontrada"}

            if workout_session.status == SessionStatus.FINALIZADA:
                return {"success": False, "error": "Sessão já finalizada"}

            # Finalizar sessão
            workout_session.end_time = datetime.now().time()
            workout_session.status = SessionStatus.FINALIZADA

            # Calcular duração
            if workout_session.start_time and workout_session.end_time:
                start = datetime.combine(workout_session.date, workout_session.start_time)
                end = datetime.combine(workout_session.date, workout_session.end_time)
                duration = (end - start).total_seconds() / 60
                workout_session.duration_minutes = int(duration)

            # Calcular estatísticas
            stats = self._calculate_session_stats(workout_session)

            session.commit()

            print(f"✅ Sessão #{session_id} finalizada")
            print(f"   ⏰ Duração: {workout_session.duration_minutes}min")

            return {
                "success": True,
                "session_id": session_id,
                "duration_minutes": workout_session.duration_minutes,
                "stats": stats,
            }

        except Exception as e:
            session.rollback()
            print(f"❌ Erro ao finalizar sessão: {e}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def get_last_session(self, user_id: str) -> Optional[WorkoutSession]:
        """Busca a última sessão do usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            WorkoutSession ou None
            
        Raises:
            ValidationError: Se user_id é inválido
            DatabaseError: Se operação no banco falhar

        """
        if not user_id or not user_id.strip():
            raise ValidationError("ID do usuário é obrigatório")
            
        session = self.db.get_session()

        try:
            last_session = session.query(WorkoutSession).filter_by(
                user_id=user_id,
            ).order_by(WorkoutSession.session_id.desc()).first()

            return last_session
        except SQLAlchemyError as e:
            logger.exception("Erro de banco ao buscar última sessão")
            raise DatabaseError(
                "Erro ao buscar última sessão",
                f"Erro SQLAlchemy: {str(e)}"
            )
        except Exception as e:
            logger.exception("Erro inesperado ao buscar última sessão")
            raise DatabaseError(
                "Erro inesperado ao buscar última sessão",
                f"Erro interno: {str(e)}"
            )
        finally:
            session.close()
            
    def get_session_summary(self, session_id: int) -> Dict[str, Any]:
        """Busca resumo de uma sessão
        
        Args:
            session_id: ID da sessão
            
        Returns:
            Dict com resumo da sessão
            
        Raises:
            ValidationError: Se session_id é inválido
            DatabaseError: Se operação no banco falhar

        """
        if not session_id or session_id <= 0:
            raise ValidationError("ID da sessão inválido")
            
        session = self.db.get_session()

        try:
            workout_session = session.query(WorkoutSession).filter_by(
                session_id=session_id,
            ).first()

            if not workout_session:
                raise ValidationError(f"Sessão {session_id} não encontrada")

            # Contar exercícios
            resistance_count = len(workout_session.exercises)
            aerobic_count = len(workout_session.aerobics)

            return {
                "resistance_count": resistance_count,
                "aerobic_count": aerobic_count,
                "total_exercises": resistance_count + aerobic_count,
                "session_status": workout_session.status.value,
                "audio_count": workout_session.audio_count,
            }
            
        except (ValidationError, DatabaseError):
            raise
        except SQLAlchemyError as e:
            logger.exception("Erro de banco ao buscar resumo da sessão")
            raise DatabaseError(
                "Erro ao buscar resumo da sessão",
                f"Erro SQLAlchemy: {str(e)}"
            )
        except Exception as e:
            logger.exception("Erro inesperado ao buscar resumo da sessão")
            raise DatabaseError(
                "Erro inesperado ao buscar resumo da sessão",
                f"Erro interno: {str(e)}"
            )
        finally:
            session.close()

    def check_and_mark_abandoned_sessions(self, user_id: str):
        """Marca sessões ativas antigas como abandonadas
        (passou mais de 3h sem finalizar)
        
        Args:
            user_id: ID do usuário

        """
        session = self.db.get_session()

        try:
            cutoff_time = datetime.now() - timedelta(hours=3)

            abandoned = session.query(WorkoutSession).filter(
                WorkoutSession.user_id == user_id,
                WorkoutSession.status == SessionStatus.ATIVA,
                WorkoutSession.updated_at < cutoff_time,
            ).all()

            for ws in abandoned:
                ws.status = SessionStatus.ABANDONADA
                print(f"⚠️  Sessão #{ws.session_id} marcada como abandonada")

            if abandoned:
                session.commit()

        except Exception as e:
            session.rollback()
            print(f"❌ Erro ao marcar sessões abandonadas: {e}")
        finally:
            session.close()

    # =========================================================================
    # MÉTODOS PRIVADOS - Auxiliares
    # =========================================================================


    def _get_or_create_exercise(
        self,
        session: Session,
        name: str,
        type: ExerciseType,
    ) -> Exercise:
        """Busca exercício ou cria se não existir
        Com inferência automática de muscle_group e equipment
        
        Args:
            session: Sessão do SQLAlchemy
            name: Nome do exercício
            type: Tipo do exercício
            
        Returns:
            Exercise

        """
        name_lower = name.lower().strip()

        # Buscar se já existe
        exercise = session.query(Exercise).filter_by(name=name_lower).first()

        if not exercise:
            # Inferir muscle_group e equipment automaticamente
            muscle_group = infer_muscle_group(name_lower)
            equipment = infer_equipment(name_lower)

            exercise = Exercise(
                name=name_lower,
                type=type,
                muscle_group=muscle_group,
                equipment=equipment,
            )
            session.add(exercise)
            session.flush()

            print(f"   🆕 Novo exercício: {name_lower}")
            print(f"      💪 Músculo: {muscle_group}")
            print(f"      🏋️  Equipamento: {equipment}")

        return exercise

    def _calculate_session_stats(self, workout_session: WorkoutSession) -> Dict:
        """Calcula estatísticas da sessão de forma segura
        
        Args:
            workout_session: Sessão de treino
            
        Returns:
            Dict com estatísticas (valores padrão se dados incompletos)
            
        Raises:
            ValueError: Se workout_session for None

        """
        session_stats = SessionStatsCalculator.calculate_safe(workout_session)
        return session_stats.to_dict()


# Instância global
_workout_service = None

def get_workout_service() -> WorkoutService:
    """Retorna instância única do serviço de workout"""
    global _workout_service
    if _workout_service is None:
        _workout_service = WorkoutService()
    return _workout_service
