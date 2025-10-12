from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from database.connection import db
from database.models import WorkoutSession

class SessionManager:
    """Gerencia lógica de sessões de treino"""
    
    # Tempo máximo entre áudios para considerar mesma sessão
    SESSION_TIMEOUT_HOURS = 3
    
    def __init__(self):
        self.db = db
    
    def get_or_create_session(self, user_id: str) -> tuple[WorkoutSession, bool]:
        """
        Retorna sessão ativa ou cria nova
        
        Returns:
            (WorkoutSession, is_new)
            - WorkoutSession: sessão atual
            - is_new: True se criou nova, False se reusou existente
        """
        session = self.db.get_session()
        
        try:
            # Buscar última sessão do usuário
            last_session = session.query(WorkoutSession).filter_by(
                user_id=user_id
            ).order_by(
                WorkoutSession.last_update.desc()
            ).first()
            
            # Se não tem sessão, criar nova
            if not last_session:
                new_session = self._create_new_session(session, user_id)
                return new_session, True
            
            # Calcular tempo desde última atualização
            time_since_last = datetime.now() - last_session.last_update
            hours_passed = time_since_last.total_seconds() / 3600
            
            # Se passou muito tempo, criar nova sessão
            if hours_passed > self.SESSION_TIMEOUT_HOURS:
                print(f"⏰ Passou {hours_passed:.1f}h desde último áudio - criando nova sessão")
                new_session = self._create_new_session(session, user_id)
                return new_session, True
            
            # Sessão ainda está ativa - reutilizar
            print(f"♻️  Reutilizando sessão #{last_session.session_id} (há {hours_passed*60:.0f} minutos)")
            return last_session, False
        
        finally:
            session.close()
    
    def _create_new_session(self, session: Session, user_id: str) -> WorkoutSession:
        """Cria uma nova sessão de treino"""
        new_session = WorkoutSession(
            user_id=user_id,
            date=datetime.now(),
            start_time=datetime.now(),
            last_update=datetime.now(),
            audio_count=0
        )
        
        session.add(new_session)
        session.commit()
        session.refresh(new_session)
        
        print(f"✨ Nova sessão criada: #{new_session.session_id}")
        return new_session
    
    def update_session_metadata(
        self,
        session_id: int,
        transcription: str,
        processing_time: float,
        model_used: str
    ):
        """Atualiza metadados da sessão após processar áudio"""
        session = self.db.get_session()
        
        try:
            workout_session = session.query(WorkoutSession).filter_by(
                session_id=session_id
            ).first()
            
            if not workout_session:
                return
            
            # Incrementar contador de áudios
            workout_session.audio_count += 1
            
            # Acumular transcrições (separadas por nova linha)
            if workout_session.original_transcription:
                workout_session.original_transcription += f"\n\n[Áudio {workout_session.audio_count}]\n{transcription}"
            else:
                workout_session.original_transcription = f"[Áudio 1]\n{transcription}"
            
            # Atualizar end_time (sempre o último áudio)
            workout_session.end_time = datetime.now()
            
            # Atualizar metadados
            workout_session.llm_model_used = model_used
            workout_session.processing_time_seconds = (
                workout_session.processing_time_seconds or 0
            ) + processing_time
            
            # last_update é atualizado automaticamente via onupdate
            
            session.commit()
            
        finally:
            session.close()

# Instância global
_session_manager = None

def get_session_manager() -> SessionManager:
    """Retorna instância única do SessionManager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
