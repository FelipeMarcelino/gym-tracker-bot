import enum
from datetime import datetime

from sqlalchemy import JSON, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class ExerciseType(enum.Enum):
    RESISTENCIA = "resistencia"
    AEROBICO = "aerobico"

class SessionStatus(enum.Enum):
    """Status da sessão de treino"""

    ATIVA = "ativa"
    FINALIZADA = "finalizada"
    ABANDONADA = "abandonada"  # Passou 3h sem finalizar

class WorkoutSession(Base):
    """Sessão de treino"""

    __tablename__ = "workout_sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    date = Column(Date, default=datetime.now)
    start_time = Column(Time)  # Primeiro áudio da sessão
    end_time = Column(Time)    # Último áudio da sessão (atualizado automaticamente)
    body_weight_kg = Column(Float)
    energy_level = Column(Integer)  # 1-10
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    duration_minutes = Column(Integer)

    # ===== DADOS DA IA =====
    original_transcription = Column(Text)      # AGORA: Acumula todas as transcrições
    llm_model_used = Column(String(50))
    processing_time_seconds = Column(Float)

    # ===== NOVO: Controle de sessão =====
    status = Column(Enum(SessionStatus), default=SessionStatus.ATIVA)  # ← NOVO
    last_update = Column(DateTime, default=datetime.now, onupdate=datetime.now)  # ← NOVO
    audio_count = Column(Integer, default=0)   # ← NOVO: Quantos áudios nesta sessão

    # Relacionamentos
    exercises = relationship("WorkoutExercise", back_populates="session", cascade="all, delete-orphan")
    aerobics = relationship("AerobicExercise", back_populates="session", cascade="all, delete-orphan")

class Exercise(Base):
    """Catálogo de exercícios"""

    __tablename__ = "exercises"

    exercise_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(Enum(ExerciseType), nullable=False)
    muscle_group = Column(String(50))
    equipment = Column(String(50))
    description = Column(Text)

class WorkoutExercise(Base):
    """Exercícios de resistência executados"""

    __tablename__ = "workout_exercises"

    workout_exercise_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.session_id", ondelete="CASCADE"))
    exercise_id = Column(Integer, ForeignKey("exercises.exercise_id"))
    order_in_workout = Column(Integer)
    sets = Column(Integer)
    reps = Column(JSON)  # Array: [12, 10, 8]
    weights_kg = Column(JSON)
    rest_seconds = Column(Integer)
    perceived_difficulty = Column(Integer)  # RPE 1-10
    notes = Column(Text)

    # Relacionamentos
    session = relationship("WorkoutSession", back_populates="exercises")
    exercise = relationship("Exercise")

class AerobicExercise(Base):
    """Exercícios aeróbicos"""

    __tablename__ = "aerobic_exercises"

    aerobic_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("workout_sessions.session_id", ondelete="CASCADE"))
    exercise_id = Column(Integer, ForeignKey("exercises.exercise_id"))
    duration_minutes = Column(Float)
    distance_km = Column(Float)
    average_heart_rate = Column(Integer)
    calories_burned = Column(Integer)
    intensity_level = Column(String(20))  # low, moderate, high, hiit
    notes = Column(Text)

    # Relacionamentos
    session = relationship("WorkoutSession", back_populates="aerobics")
    exercise = relationship("Exercise")
