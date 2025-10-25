"""Pydantic models for workout data validation and LLM response parsing"""

from datetime import time, date
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class ResistanceExercise(BaseModel):
    """Model for resistance/strength training exercises"""

    name: str = Field(..., min_length=1, max_length=100, description="Exercise name")
    sets: int = Field(..., gt=0, le=20, description="Number of sets performed")
    reps: List[int] = Field(..., min_length=1, max_length=20, description="Repetitions per set")
    weights_kg: List[float] = Field(..., min_length=1, description="Weight used per set in kg")
    rest_seconds: Optional[int] = Field(None, ge=0, le=1800, description="Rest time between sets")
    perceived_difficulty: Optional[int] = Field(None, ge=1, le=10, description="RPE scale 1-10")
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")

    @field_validator("reps")
    @classmethod
    def validate_reps(cls, v):
        """Validate that all rep values are positive"""
        for rep in v:
            if rep <= 0:
                raise ValueError("All rep values must be positive")
        return v

    @field_validator("weights_kg")
    @classmethod
    def validate_weights(cls, v):
        """Validate that all weight values are positive"""
        for weight in v:
            if weight <= 0:
                raise ValueError("All weight values must be positive")
        return v

    @model_validator(mode="after")
    def validate_arrays_consistency(self):
        """Validate that reps and weights arrays are consistent with sets count"""
        if len(self.reps) != self.sets:
            raise ValueError(f"Number of rep values ({len(self.reps)}) must match sets count ({self.sets})")

        if len(self.weights_kg) != self.sets:
            raise ValueError(f"Number of weight values ({len(self.weights_kg)}) must match sets count ({self.sets})")

        return self


class AerobicExercise(BaseModel):
    """Model for aerobic/cardio exercises"""

    name: str = Field(..., min_length=1, max_length=100, description="Exercise name")
    duration_minutes: float = Field(..., gt=0, le=1440, description="Duration in minutes")
    distance_km: Optional[float] = Field(None, gt=0, description="Distance covered in kilometers")
    average_heart_rate: Optional[int] = Field(None, ge=40, le=220, description="Average heart rate")
    calories_burned: Optional[int] = Field(None, gt=0, le=10000, description="Estimated calories burned")
    intensity_level: Optional[Literal["low", "moderate", "high", "hiit"]] = Field(
        None, description="Exercise intensity"
    )
    notes: Optional[str] = Field(None, max_length=500, description="Additional notes")


class WorkoutData(BaseModel):
    """Complete workout session data model"""

    body_weight_kg: Optional[float] = Field(None, gt=0, le=500, description="Body weight in kg")
    energy_level: Optional[int] = Field(None, ge=1, le=10, description="Energy level 1-10")
    start_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="Start time HH:MM")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="End time HH:MM")
    resistance_exercises: List[ResistanceExercise] = Field(default_factory=list, description="Resistance exercises")
    aerobic_exercises: List[AerobicExercise] = Field(default_factory=list, description="Aerobic exercises")
    notes: Optional[str] = Field(None, max_length=1000, description="Session notes")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v):
        """Validate time format and range"""
        if v is None:
            return v

        try:
            hours, minutes = map(int, v.split(":"))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError("Invalid time range")
            return v
        except ValueError:
            raise ValueError("Time must be in HH:MM format")

    @model_validator(mode="after")
    def validate_workout_content(self):
        """Validate that workout has at least some content"""
        if not self.resistance_exercises and not self.aerobic_exercises:
            raise ValueError("Workout must contain at least one exercise")
        return self

    @model_validator(mode="after")
    def validate_time_sequence(self):
        """Validate that end_time is after start_time"""
        if self.start_time and self.end_time:
            start_h, start_m = map(int, self.start_time.split(":"))
            end_h, end_m = map(int, self.end_time.split(":"))

            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m

            # Handle case where workout spans midnight
            if end_minutes < start_minutes:
                end_minutes += 24 * 60  # Add 24 hours

            # Check for reasonable workout duration (max 6 hours)
            duration_minutes = end_minutes - start_minutes
            if duration_minutes > 360:
                raise ValueError("Workout duration cannot exceed 6 hours")

        return self


class LLMParseResult(BaseModel):
    """Result of LLM workout data parsing"""

    success: bool = Field(..., description="Whether parsing was successful")
    workout_data: Optional[WorkoutData] = Field(None, description="Parsed workout data")
    raw_text: str = Field(..., description="Original transcription text")
    parsing_notes: Optional[str] = Field(None, description="Notes about parsing process")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Parsing confidence score")
    errors: List[str] = Field(default_factory=list, description="List of parsing errors")

    @model_validator(mode="after")
    def validate_result_consistency(self):
        """Validate that success status matches data availability"""
        if self.success and self.workout_data is None:
            raise ValueError("Success=True requires workout_data to be present")

        if not self.success and not self.errors:
            raise ValueError("Success=False requires at least one error message")

        return self


# Helper models for specific use cases


class ExerciseSummary(BaseModel):
    """Summary of exercises in a workout"""

    total_resistance_exercises: int = Field(ge=0)
    total_aerobic_exercises: int = Field(ge=0)
    total_sets: int = Field(ge=0)
    estimated_duration_minutes: Optional[int] = Field(None, ge=0)
    muscle_groups: List[str] = Field(default_factory=list)


class WorkoutValidationError(BaseModel):
    """Detailed validation error information"""

    field: str = Field(..., description="Field that failed validation")
    error_type: str = Field(..., description="Type of validation error")
    message: str = Field(..., description="Human-readable error message")
    value: Optional[Any] = Field(None, description="Value that caused the error")
    exercise_index: Optional[int] = Field(None, description="Index of exercise if applicable")
