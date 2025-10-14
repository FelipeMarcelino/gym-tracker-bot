"""Serviço para gerenciar sessões de treino e exercícios
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from config.settings import settings
from database.connection import db
from database.models import AerobicExercise, Exercise, ExerciseType, SessionStatus, WorkoutExercise, WorkoutSession
from services.exceptions import DatabaseError, ValidationError
from services.exercise_knowledge import infer_equipment, infer_muscle_group
from services.stats_service import SessionStatsCalculator

logger = get_logger(__name__)


class WorkoutService:
    """Serviço para gerenciar salvamento e finalização de treinos"""

    def __init__(self) -> None:
        self.db = db

    # =========================================================================
    # MÉTODOS PÚBLICOS - Operações Principais
    # =========================================================================

    def add_exercises_to_session_batch(
        self,
        session_id: int,
        parsed_data: Dict[str, Any],
        user_id: str,
    ) -> bool:
        """Versão otimizada que faz todas as operações em uma única transação
        
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
            # ===== TRANSAÇÃO ÚNICA OTIMIZADA =====
            with session.begin():
                # 1. Buscar sessão
                workout_session = session.query(WorkoutSession).filter_by(
                    session_id=session_id,
                ).first()

                if not workout_session:
                    raise ValidationError(f"Sessão {session_id} não encontrada")

                if workout_session.user_id != user_id:
                    raise ValidationError("Usuário não autorizado para esta sessão")

                # 2. Atualizar dados da sessão
                self._update_session_data_batch(workout_session, parsed_data)

                # 3. Contar exercícios existentes
                existing_resistance = len(workout_session.exercises)

                # 4. Processar exercícios de resistência em batch
                resistance_exercises = parsed_data.get("resistance_exercises", [])
                if resistance_exercises:
                    self._process_resistance_exercises_batch(
                        session, session_id, resistance_exercises, existing_resistance
                    )

                # 5. Processar exercícios aeróbicos em batch
                aerobic_exercises = parsed_data.get("aerobic_exercises", [])
                if aerobic_exercises:
                    self._process_aerobic_exercises_batch(
                        session, session_id, aerobic_exercises
                    )

                # Commit automático pelo context manager

            resistance_count = len(resistance_exercises)
            aerobic_count = len(aerobic_exercises)

            logger.info(f"BATCH: Adicionado à sessão #{session_id}: {resistance_count} resistência, {aerobic_count} aeróbico")
            return True

        except (ValidationError, DatabaseError):
            raise
        except SQLAlchemyError as e:
            logger.exception("Erro de banco de dados ao adicionar exercícios (batch)")
            raise DatabaseError(
                "Erro ao salvar exercícios no banco de dados",
                f"Erro SQLAlchemy: {e!s}",
            )
        except Exception as e:
            logger.exception("Erro inesperado ao adicionar exercícios (batch)")
            raise DatabaseError(
                "Erro inesperado ao adicionar exercícios",
                f"Erro interno: {e!s}",
            )
        finally:
            session.close()

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
                    average_heart_rate=ex_data.get("average_heart_rate"),
                    calories_burned=ex_data.get("calories_burned"),
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
                f"Erro SQLAlchemy: {e!s}",
            )
        except Exception as e:
            session.rollback()
            logger.exception("Erro inesperado ao adicionar exercícios")
            raise DatabaseError(
                "Erro inesperado ao adicionar exercícios",
                f"Erro interno: {e!s}",
            )
        finally:
            session.close()

    def _validate_and_process_weights(self, ex_data: Dict[str, Any], exercise_idx: int) -> Optional[List[float]]:
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

            logger.info(f"Sessão #{session_id} finalizada com duração de {workout_session.duration_minutes}min")

            return {
                "success": True,
                "session_id": session_id,
                "duration_minutes": workout_session.duration_minutes,
                "stats": stats,
            }

        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao finalizar sessão {session_id}: {e}")
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
                f"Erro SQLAlchemy: {e!s}",
            )
        except Exception as e:
            logger.exception("Erro inesperado ao buscar última sessão")
            raise DatabaseError(
                "Erro inesperado ao buscar última sessão",
                f"Erro interno: {e!s}",
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
                f"Erro SQLAlchemy: {e!s}",
            )
        except Exception as e:
            logger.exception("Erro inesperado ao buscar resumo da sessão")
            raise DatabaseError(
                "Erro inesperado ao buscar resumo da sessão",
                f"Erro interno: {e!s}",
            )
        finally:
            session.close()

    def get_user_session_status(self, user_id: str) -> Dict[str, Any]:
        """Busca status detalhado da sessão de um usuário com queries otimizadas
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Dict com status da sessão ou None se não houver sessões
            
        Raises:
            ValidationError: Se user_id é inválido
            DatabaseError: Se operação no banco falhar

        """
        if not user_id or not user_id.strip():
            raise ValidationError("ID do usuário é obrigatório")

        session = self.db.get_session()

        try:
            # Query otimizada com eager loading dos relacionamentos
            from sqlalchemy.orm import joinedload

            last_session = (
                session.query(WorkoutSession)
                .options(
                    joinedload(WorkoutSession.exercises),
                    joinedload(WorkoutSession.aerobics),
                )
                .filter_by(user_id=user_id)
                .order_by(WorkoutSession.last_update.desc())
                .first()
            )

            if not last_session:
                return {
                    "has_session": False,
                    "message": "Você ainda não tem nenhuma sessão registrada.\nEnvie um áudio para começar!",
                }

            # Calcular tempo desde última atualização
            time_since = datetime.now() - last_session.last_update
            hours_passed = time_since.total_seconds() / 3600
            minutes_passed = int(hours_passed * 60)

            # Determinar se está ativa
            is_active = last_session.status

            # Contar exercícios (já carregados via joinedload)
            resistance_count = len(last_session.exercises)
            aerobic_count = len(last_session.aerobics)

            return {
                "has_session": True,
                "session": last_session,
                "is_active": is_active,
                "hours_passed": hours_passed,
                "minutes_passed": minutes_passed,
                "resistance_count": resistance_count,
                "aerobic_count": aerobic_count,
                "timeout_hours": settings.SESSION_TIMEOUT_HOURS,
            }

        except (ValidationError, DatabaseError):
            raise
        except SQLAlchemyError as e:
            logger.exception("Erro de banco ao buscar status da sessão")
            raise DatabaseError(
                "Erro ao buscar status da sessão",
                f"Erro SQLAlchemy: {e!s}",
            )
        except Exception as e:
            logger.exception("Erro inesperado ao buscar status da sessão")
            raise DatabaseError(
                "Erro inesperado ao buscar status da sessão",
                f"Erro interno: {e!s}",
            )
        finally:
            session.close()

    def check_and_mark_abandoned_sessions(self, user_id: str) -> None:
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
                logger.warning(f"Sessão #{ws.session_id} marcada como abandonada")

            if abandoned:
                session.commit()

        except Exception as e:
            session.rollback()
            logger.error(f"Erro ao marcar sessões abandonadas: {e}")
        finally:
            session.close()

    # =========================================================================
    # MÉTODOS PRIVADOS - Auxiliares
    # =========================================================================

    def _update_session_data_batch(self, workout_session: WorkoutSession, parsed_data: Dict[str, Any]) -> None:
        """Atualiza dados da sessão em batch"""
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

    def _process_resistance_exercises_batch(
        self, 
        session: Session, 
        session_id: int, 
        resistance_exercises: List[Dict[str, Any]], 
        existing_resistance: int
    ) -> None:
        """Processa exercícios de resistência em batch"""
        # Cache para exercícios já criados nesta transação
        exercise_cache = {}
        
        for idx, ex_data in enumerate(resistance_exercises):
            if not isinstance(ex_data, dict):
                raise ValidationError(f"Exercício de resistência {idx} deve ser um objeto")

            if "name" not in ex_data or not ex_data["name"].strip():
                raise ValidationError(f"Nome do exercício é obrigatório (exercício {idx})")

            # Usar cache para evitar queries repetidas
            exercise_name = ex_data["name"].lower().strip()
            if exercise_name in exercise_cache:
                exercise = exercise_cache[exercise_name]
            else:
                exercise = self._get_or_create_exercise_batch(
                    session=session,
                    name=ex_data["name"],
                    type=ExerciseType.RESISTENCIA,
                )
                exercise_cache[exercise_name] = exercise

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

    def _process_aerobic_exercises_batch(
        self, 
        session: Session, 
        session_id: int, 
        aerobic_exercises: List[Dict[str, Any]]
    ) -> None:
        """Processa exercícios aeróbicos em batch"""
        exercise_cache = {}
        
        for idx, ex_data in enumerate(aerobic_exercises):
            if not isinstance(ex_data, dict):
                raise ValidationError(f"Exercício aeróbico {idx} deve ser um objeto")

            if "name" not in ex_data or not ex_data["name"].strip():
                raise ValidationError(f"Nome do exercício aeróbico é obrigatório (exercício {idx})")

            # Usar cache para evitar queries repetidas
            exercise_name = ex_data["name"].lower().strip()
            if exercise_name in exercise_cache:
                exercise = exercise_cache[exercise_name]
            else:
                exercise = self._get_or_create_exercise_batch(
                    session=session,
                    name=ex_data["name"],
                    type=ExerciseType.AEROBICO,
                )
                exercise_cache[exercise_name] = exercise

            aerobic_exercise = AerobicExercise(
                session_id=session_id,
                exercise_id=exercise.exercise_id,
                duration_minutes=ex_data.get("duration_minutes"),
                distance_km=ex_data.get("distance_km"),
                average_heart_rate=ex_data.get("average_heart_rate"),
                calories_burned=ex_data.get("calories_burned"),
                intensity_level=ex_data.get("intensity_level"),
                notes=ex_data.get("notes"),
            )
            session.add(aerobic_exercise)

    def _get_or_create_exercise_batch(
        self,
        session: Session,
        name: str,
        type: ExerciseType,
    ) -> Exercise:
        """Versão otimizada para batch - reutiliza a sessão existente"""
        name_lower = name.lower().strip()

        # Buscar se já existe na sessão atual
        exercise = session.query(Exercise).filter_by(name=name_lower).first()

        if not exercise:
            # Inferir muscle_group e equipment automaticamente
            exercise_type_str = "aerobico" if type == ExerciseType.AEROBICO else "resistencia"
            muscle_group = infer_muscle_group(name_lower, exercise_type_str)
            equipment = infer_equipment(name_lower, exercise_type_str)

            exercise = Exercise(
                name=name_lower,
                type=type,
                muscle_group=muscle_group,
                equipment=equipment,
            )
            session.add(exercise)
            session.flush()  # Para obter o ID sem commit

            logger.debug(f"BATCH: Novo exercício: {name_lower} (Músculo: {muscle_group}, Equipamento: {equipment})")

        return exercise

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
            exercise_type_str = "aerobico" if type == ExerciseType.AEROBICO else "resistencia"
            muscle_group = infer_muscle_group(name_lower, exercise_type_str)
            equipment = infer_equipment(name_lower, exercise_type_str)

            exercise = Exercise(
                name=name_lower,
                type=type,
                muscle_group=muscle_group,
                equipment=equipment,
            )
            session.add(exercise)
            session.flush()

            logger.info(f"Novo exercício criado: {name_lower} (Músculo: {muscle_group}, Equipamento: {equipment})")

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


# Service instantiation moved to container.py
# This module only defines the service class
