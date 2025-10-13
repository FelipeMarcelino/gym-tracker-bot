import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from database.connection import db
from database.models import SessionStatus, WorkoutSession
from services.exceptions import DatabaseError, SessionError, ValidationError

logger = logging.getLogger(__name__)


class SessionManager:
    """Gerencia lógica de sessões de treino"""

    # Tempo máximo entre áudios para considerar mesma sessão
    SESSION_TIMEOUT_HOURS = 3

    def __init__(self):
        self.db = db

    def get_or_create_session(self, user_id: str) -> tuple[WorkoutSession, bool]:
        """Retorna sessão ativa ou cria nova
        
        Args:
            user_id: ID do usuário
        
        Returns:
            (WorkoutSession, is_new)
            - WorkoutSession: sessão atual
            - is_new: True se criou nova, False se reusou existente
            
        Raises:
            ValidationError: Se user_id é inválido
            SessionError: Se falhar ao criar/gerenciar sessão
            DatabaseError: Se operação no banco falhar

        """
        if not user_id or not user_id.strip():
            raise ValidationError("ID do usuário é obrigatório")
            
        session = self.db.get_session()

        try:
            # Buscar última sessão
            last_session = session.query(WorkoutSession).filter_by(
                user_id=user_id,
            ).order_by(WorkoutSession.session_id.desc()).first()

            # ===== DECISÃO: CRIAR NOVA OU REUTILIZAR =====
            if self._should_create_new_session(last_session):
                # CRIAR NOVA SESSÃO
                new_session = WorkoutSession(
                    user_id=user_id,
                    date=datetime.now().date(),
                    start_time=datetime.now().time(),
                    last_update=datetime.now(),
                    status=SessionStatus.ATIVA,
                    audio_count=0,
                )
                session.add(new_session)
                session.commit()
                session.refresh(new_session)

                logger.info(f"Nova sessão #{new_session.session_id} criada para usuário {user_id}")
                logger.info(f"Início: {new_session.start_time.strftime('%H:%M')}")

                return new_session, True  # is_new = True

            # REUTILIZAR SESSÃO EXISTENTE
            minutes_since = (datetime.now() - last_session.last_update).total_seconds() / 60
            logger.info(f"Reutilizando sessão #{last_session.session_id} (há {minutes_since:.0f} minutos)")

            return last_session, False  # is_new = False

        except (ValidationError, SessionError):
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro de banco ao gerenciar sessão")
            raise DatabaseError(
                "Erro ao gerenciar sessão no banco de dados",
                f"Erro SQLAlchemy: {str(e)}"
            )
        except Exception as e:
            session.rollback()
            logger.exception("Erro inesperado ao gerenciar sessão")
            raise SessionError(
                "Erro inesperado ao gerenciar sessão",
                f"Erro interno: {str(e)}"
            )
        finally:
            session.close()

    def _should_create_new_session(self, last_session: Optional[WorkoutSession]) -> bool:
        """Decide se deve criar uma nova sessão ou reutilizar a última
        
        Cria nova sessão se:
        - Não existe sessão anterior
        - Passou mais de 3 horas desde última atualização
        - Sessão anterior já foi finalizada
        
        Args:
            last_session: Última WorkoutSession ou None
            
        Returns:
            True se deve criar nova sessão

        """
        # Sem sessão anterior = criar nova
        if not last_session:
            logger.info("Primeira sessão deste usuário")
            return True

        # Sessão já finalizada = criar nova
        if last_session.status == SessionStatus.FINALIZADA:
            logger.info(f"Sessão #{last_session.session_id} já finalizada - criando nova")
            return True

        # Verificar timeout de 3 horas
        hours_since_last = (datetime.now() - last_session.last_update).total_seconds() / 3600

        if hours_since_last >= self.SESSION_TIMEOUT_HOURS:
            logger.info(f"Última sessão há {hours_since_last:.1f}h - criando nova")

            # Marcar sessão antiga como abandonada
            if last_session.status == SessionStatus.ATIVA:
                try:
                    self._mark_as_abandoned(last_session)
                except Exception as e:
                    logger.warning(f"Falha ao marcar sessão como abandonada: {e}")
                    # Continue anyway - não é crítico

            return True

        # Reutilizar sessão existente
        return False

    def _mark_as_abandoned(self, workout_session: WorkoutSession):
        """Marca uma sessão como abandonada
        
        Raises:
            DatabaseError: Se operação no banco falhar
        """
        session = self.db.get_session()

        try:
            workout_session.status = SessionStatus.ABANDONADA
            session.merge(workout_session)
            session.commit()
            logger.info(f"Sessão #{workout_session.session_id} marcada como abandonada")
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro de banco ao marcar sessão como abandonada")
            raise DatabaseError(
                "Erro ao marcar sessão como abandonada",
                f"Erro SQLAlchemy: {str(e)}"
            )
        except Exception as e:
            session.rollback()
            logger.exception("Erro inesperado ao marcar sessão como abandonada")
            raise DatabaseError(
                "Erro inesperado ao marcar sessão como abandonada",
                f"Erro interno: {str(e)}"
            )
        finally:
            session.close()


    def update_session_metadata(
        self,
        session_id: int,
        transcription: str,
        processing_time: float,
        model_used: str,
    ):
        """Atualiza metadados da sessão após processar áudio
        
        Args:
            session_id: ID da sessão
            transcription: Texto transcrito
            processing_time: Tempo de processamento
            model_used: Modelo LLM usado
            
        Raises:
            ValidationError: Se os parâmetros são inválidos
            DatabaseError: Se operação no banco falhar

        """
        if not session_id or session_id <= 0:
            raise ValidationError("ID da sessão inválido")
            
        if not transcription or not transcription.strip():
            raise ValidationError("Transcrição é obrigatória")
            
        if processing_time < 0:
            raise ValidationError("Tempo de processamento deve ser não-negativo")
            
        session = self.db.get_session()

        try:
            workout_session = session.query(WorkoutSession).filter_by(
                session_id=session_id,
            ).first()

            if not workout_session:
                raise ValidationError(f"Sessão {session_id} não encontrada")

            # Incrementar contador de áudios
            workout_session.audio_count += 1

            # Adicionar transcrição ao histórico
            if workout_session.original_transcription:
                workout_session.original_transcription += f"\n\n--- Áudio #{workout_session.audio_count} ---\n{transcription}"
            else:
                workout_session.original_transcription = f"--- Áudio #1 ---\n{transcription}"

            # Atualizar timestamp (updated_at é automático)
            session.commit()

            logger.info(f"Metadados atualizados: sessão #{session_id}, {workout_session.audio_count} áudios")

        except (ValidationError, DatabaseError):
            session.rollback()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.exception("Erro de banco ao atualizar metadados")
            raise DatabaseError(
                "Erro ao atualizar metadados da sessão",
                f"Erro SQLAlchemy: {str(e)}"
            )
        except Exception as e:
            session.rollback()
            logger.exception("Erro inesperado ao atualizar metadados")
            raise DatabaseError(
                "Erro inesperado ao atualizar metadados",
                f"Erro interno: {str(e)}"
            )
        finally:
            session.close()


# Singleton
_session_manager = None

def get_session_manager() -> SessionManager:
    """Retorna instância única do gerenciador de sessões"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
