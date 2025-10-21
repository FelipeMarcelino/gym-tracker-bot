"""Pydantic models for service responses and data structures

This module provides type-safe models for various services including:
- Rate limiting
- Error context
- Export services
- Session management
"""

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# RATE LIMITER MODELS
# =============================================================================

class RateLimitCheckResult(BaseModel):
    """Result of a rate limit check operation"""

    is_allowed: bool = Field(description="Whether the request is allowed")
    remaining_requests: int = Field(ge=0, description="Number of remaining requests in the window")
    reset_time: Optional[int] = Field(default=None, ge=0, description="Seconds until rate limit resets")

    model_config = {"frozen": True}  # Immutable result


class RateLimitInfo(BaseModel):
    """Information about a specific rate limit category"""

    allowed: bool = Field(description="Whether requests are currently allowed")
    remaining: int = Field(ge=0, description="Remaining requests in window")
    reset_time: int = Field(ge=0, description="Seconds until reset")
    limit: int = Field(gt=0, description="Maximum requests allowed")
    window: int = Field(gt=0, description="Time window in seconds")

    model_config = {"frozen": True}


class RateLimitStatus(BaseModel):
    """Complete rate limit status for a user across all categories"""

    general: RateLimitInfo = Field(description="General request rate limits")
    voice: RateLimitInfo = Field(description="Voice message rate limits")
    commands: RateLimitInfo = Field(description="Command rate limits")

    model_config = {"frozen": True}


class RateLimitConfig(BaseModel):
    """Configuration for a rate limit category"""

    requests: int = Field(gt=0, description="Maximum requests allowed")
    window: int = Field(gt=0, description="Time window in seconds")

    model_config = {"frozen": True}


class ActiveUsersCount(BaseModel):
    """Count of active users per rate limit category"""

    general: int = Field(ge=0, description="Active users in general rate limiter")
    voice: int = Field(ge=0, description="Active users in voice rate limiter")
    commands: int = Field(ge=0, description="Active users in commands rate limiter")

    model_config = {"frozen": True}


class RateLimiterStats(BaseModel):
    """Overall rate limiter statistics"""

    active_users: ActiveUsersCount = Field(description="Active user counts")
    limits: dict[str, RateLimitConfig] = Field(description="Rate limit configurations")

    model_config = {"frozen": True}


class CleanupResult(BaseModel):
    """Result of rate limiter cleanup operation"""

    general: int = Field(ge=0, description="Users cleaned from general limiter")
    voice: int = Field(ge=0, description="Users cleaned from voice limiter")
    commands: int = Field(ge=0, description="Users cleaned from commands limiter")
    total: int = Field(ge=0, description="Total users cleaned")

    @field_validator('total')
    @classmethod
    def validate_total(cls, v: int, info) -> int:
        """Ensure total equals sum of individual counts"""
        if info.data:
            expected = info.data.get('general', 0) + info.data.get('voice', 0) + info.data.get('commands', 0)
            if v != expected:
                raise ValueError(f"Total ({v}) must equal sum of individual counts ({expected})")
        return v

    model_config = {"frozen": True}


# =============================================================================
# ERROR CONTEXT MODELS
# =============================================================================

class ErrorContext(BaseModel):
    """Structured context for error information"""

    field: Optional[str] = Field(default=None, description="Field that caused the error")
    value: Optional[str] = Field(default=None, description="Value that was invalid")
    operation: Optional[str] = Field(default=None, description="Operation being performed")
    service: Optional[str] = Field(default=None, description="Service where error occurred")
    session_id: Optional[str] = Field(default=None, description="Session ID if applicable")
    user_id: Optional[str] = Field(default=None, description="User ID if applicable")
    retry_after: Optional[int] = Field(default=None, ge=0, description="Seconds to wait before retry")
    limit_type: Optional[str] = Field(default=None, description="Type of rate limit")
    reset_time: Optional[int] = Field(default=None, ge=0, description="Time until reset")
    model: Optional[str] = Field(default=None, description="Model name for LLM errors")
    response_preview: Optional[str] = Field(default=None, description="Preview of response that failed")
    stage: Optional[str] = Field(default=None, description="Processing stage")
    duration: Optional[float] = Field(default=None, ge=0, description="Duration in seconds")
    format: Optional[str] = Field(default=None, description="Data format")
    backup_path: Optional[str] = Field(default=None, description="Backup file path")

    # Allow arbitrary additional context fields
    model_config = {"extra": "allow"}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


# =============================================================================
# EXPORT SERVICE MODELS
# =============================================================================

class DateRange(BaseModel):
    """Date range for exports"""

    start: str = Field(description="Start date in DD/MM/YYYY format")
    end: str = Field(description="End date in DD/MM/YYYY format")

    @field_validator('start', 'end')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date format is DD/MM/YYYY"""
        try:
            datetime.strptime(v, "%d/%m/%Y")
        except ValueError:
            raise ValueError(f"Date must be in DD/MM/YYYY format, got: {v}")
        return v

    model_config = {"frozen": True}


class ExportSummary(BaseModel):
    """Summary statistics for exported workout data"""

    total_sessions: int = Field(ge=0, description="Total number of sessions")
    completed_sessions: int = Field(ge=0, description="Number of completed sessions")
    active_sessions: int = Field(ge=0, description="Number of active sessions")
    total_exercises: int = Field(ge=0, description="Total exercises across all sessions")
    resistance_exercises: int = Field(ge=0, description="Number of resistance exercises")
    aerobic_exercises: int = Field(ge=0, description="Number of aerobic exercises")
    total_duration_minutes: int = Field(ge=0, description="Total workout duration in minutes")
    date_range: Optional[DateRange] = Field(default=None, description="Date range of exported data")

    @field_validator('active_sessions')
    @classmethod
    def validate_active_sessions(cls, v: int, info) -> int:
        """Ensure active + completed = total"""
        if info.data:
            total = info.data.get('total_sessions', 0)
            completed = info.data.get('completed_sessions', 0)
            expected_active = total - completed
            if v != expected_active:
                raise ValueError(
                    f"Active sessions ({v}) must equal total ({total}) - completed ({completed})"
                )
        return v

    @field_validator('total_exercises')
    @classmethod
    def validate_total_exercises(cls, v: int, info) -> int:
        """Ensure total exercises = resistance + aerobic"""
        if info.data:
            resistance = info.data.get('resistance_exercises', 0)
            aerobic = info.data.get('aerobic_exercises', 0)
            expected_total = resistance + aerobic
            if v != expected_total:
                raise ValueError(
                    f"Total exercises ({v}) must equal resistance ({resistance}) + aerobic ({aerobic})"
                )
        return v

    model_config = {"frozen": True}


class ExportResult(BaseModel):
    """Result of a data export operation"""

    success: bool = Field(description="Whether export was successful")
    format: Literal["json", "csv"] = Field(description="Export format")
    data: str = Field(description="Exported data as string")
    summary: ExportSummary = Field(description="Summary statistics")
    export_date: str = Field(description="ISO format export timestamp")
    user_id: str = Field(description="User ID for the export")
    message: Optional[str] = Field(default=None, description="Error or info message")

    @field_validator('export_date')
    @classmethod
    def validate_iso_format(cls, v: str) -> str:
        """Ensure export_date is valid ISO format"""
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f"export_date must be ISO format, got: {v}")
        return v

    model_config = {"frozen": True}


class ExportPreview(BaseModel):
    """Preview/summary of data available for export"""

    total_sessions: int = Field(ge=0, description="Total sessions available")
    completed_sessions: int = Field(ge=0, description="Completed sessions")
    active_sessions: int = Field(ge=0, description="Active sessions")
    total_exercises: int = Field(ge=0, description="Total exercises")
    resistance_exercises: int = Field(ge=0, description="Resistance exercises")
    aerobic_exercises: int = Field(ge=0, description="Aerobic exercises")
    date_range: Optional[DateRange] = Field(default=None, description="Date range of data")
    estimated_size_mb: float = Field(ge=0, description="Estimated export size in MB")

    model_config = {"frozen": True}


# =============================================================================
# SESSION MANAGER MODELS
# =============================================================================
# Note: Session manager currently returns database models directly (WorkoutSession)
# rather than using Pydantic models. This could be a future enhancement if needed
# to separate the API layer from the database layer.
