"""Custom exceptions for gym tracker services

This module provides a comprehensive exception hierarchy for the gym tracker application.
All exceptions include error codes, user-friendly messages, and detailed error information.
"""

from enum import Enum
from typing import Any, Dict, Optional
import traceback

from models.service_models import ErrorContext


class ErrorCode(Enum):
    """Standardized error codes for different types of failures"""

    # General errors (1000-1099)
    UNKNOWN_ERROR = 1000
    CONFIGURATION_ERROR = 1001
    INTERNAL_ERROR = 1002

    # Authentication/Authorization errors (1100-1199)
    UNAUTHORIZED = 1100
    ACCESS_DENIED = 1101
    INVALID_CREDENTIALS = 1102
    TOKEN_EXPIRED = 1103

    # Validation errors (1200-1299)
    INVALID_INPUT = 1200
    MISSING_REQUIRED_FIELD = 1201
    INVALID_FORMAT = 1202
    VALUE_OUT_OF_RANGE = 1203
    INVALID_FILE_TYPE = 1204
    FILE_TOO_LARGE = 1205

    # Database errors (1300-1399)
    DATABASE_CONNECTION_FAILED = 1300
    DATABASE_QUERY_FAILED = 1301
    RECORD_NOT_FOUND = 1302
    DUPLICATE_RECORD = 1303
    CONSTRAINT_VIOLATION = 1304
    TRANSACTION_FAILED = 1305

    # Session errors (1400-1499)
    SESSION_NOT_FOUND = 1400
    SESSION_EXPIRED = 1401
    SESSION_ALREADY_ACTIVE = 1402
    SESSION_CREATION_FAILED = 1403

    # Audio processing errors (1500-1599)
    AUDIO_DOWNLOAD_FAILED = 1500
    AUDIO_TRANSCRIPTION_FAILED = 1501
    AUDIO_FORMAT_UNSUPPORTED = 1502
    AUDIO_TOO_LONG = 1503
    AUDIO_QUALITY_POOR = 1504

    # LLM processing errors (1600-1699)
    LLM_PARSING_FAILED = 1600
    LLM_SERVICE_UNAVAILABLE = 1601
    LLM_RATE_LIMIT_EXCEEDED = 1602
    LLM_INVALID_RESPONSE = 1603
    LLM_TIMEOUT = 1604

    # External service errors (1700-1799)
    TELEGRAM_API_ERROR = 1700
    GROQ_API_ERROR = 1701
    WHISPER_API_ERROR = 1702
    NETWORK_ERROR = 1703
    SERVICE_TIMEOUT = 1704

    # Export/Import errors (1800-1899)
    EXPORT_FAILED = 1800
    IMPORT_FAILED = 1801
    UNSUPPORTED_FORMAT = 1802

    # Rate limiting errors (1900-1999)
    RATE_LIMIT_EXCEEDED = 1900
    TOO_MANY_REQUESTS = 1901

    # Backup/Restore errors (2000-2099)
    BACKUP_FAILED = 2000
    RESTORE_FAILED = 2001
    BACKUP_NOT_FOUND = 2002
    BACKUP_VERIFICATION_FAILED = 2003

    # File operation errors (2100-2199)
    FILE_NOT_FOUND = 2100
    FILE_OPERATION_ERROR = 2101
    PERMISSION_DENIED = 2102


class GymTrackerError(Exception):
    """Base exception for gym tracker application

    Provides structured error information including error codes,
    user-friendly messages, and detailed technical information.
    """

    def __init__(
        self,
        message: str,
        details: Optional[str] = None,
        error_code: Optional[ErrorCode] = None,
        user_message: Optional[str] = None,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
    ):
        self.message = message
        self.details = details
        self.error_code = error_code or ErrorCode.UNKNOWN_ERROR
        self.user_message = user_message or message
        self.context = context or ErrorContext()
        self.cause = cause

        # Capture stack trace for debugging
        self.stack_trace = traceback.format_exc() if cause else None

        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization"""
        return {
            'error_code': self.error_code.value,
            'error_name': self.error_code.name,
            'message': self.message,
            'user_message': self.user_message,
            'details': self.details,
            'context': self.context.to_dict(),
            'cause': str(self.cause) if self.cause else None,
            'stack_trace': self.stack_trace,
        }

    def __str__(self) -> str:
        """String representation for logging"""
        base_msg = f'[{self.error_code.value}] {self.message}'
        if self.details:
            if isinstance(self.details, dict):
                # Format dict details nicely
                details_str = ', '.join(
                    f'{k}: {v}' for k, v in self.details.items()
                )
                return f'{base_msg} ({details_str})'
            else:
                return f'{base_msg} ({self.details})'
        return base_msg


# =============================================================================
# SPECIFIC EXCEPTION CLASSES
# =============================================================================


class ValidationError(GymTrackerError):
    """Raised when input validation fails"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs,
    ):
        # Build ErrorContext from parameters
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if field:
                context_dict['field'] = field
            if value is not None:
                context_dict['value'] = str(value)
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.INVALID_INPUT),
            user_message=kwargs.get('user_message', 'Invalid input provided'),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class DatabaseError(GymTrackerError):
    """Raised when database operations fail"""

    def __init__(
        self, message: str, operation: Optional[str] = None, **kwargs
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if operation:
                context_dict['operation'] = operation
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get(
                'error_code', ErrorCode.DATABASE_QUERY_FAILED
            ),
            user_message=kwargs.get(
                'user_message', 'Database operation failed'
            ),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class SessionError(GymTrackerError):
    """Raised when session management fails"""

    def __init__(
        self, message: str, session_id: Optional[str] = None, **kwargs
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if session_id:
                context_dict['session_id'] = session_id
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.SESSION_NOT_FOUND),
            user_message=kwargs.get(
                'user_message', 'Session operation failed'
            ),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class AudioProcessingError(GymTrackerError):
    """Raised when audio processing fails"""

    def __init__(
        self,
        message: str,
        stage: Optional[str] = None,
        duration: Optional[float] = None,
        **kwargs,
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if stage:
                context_dict['stage'] = stage
            if duration:
                context_dict['duration'] = duration
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get(
                'error_code', ErrorCode.AUDIO_TRANSCRIPTION_FAILED
            ),
            user_message=kwargs.get('user_message', 'Audio processing failed'),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class LLMParsingError(GymTrackerError):
    """Raised when LLM parsing fails"""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        response: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if model:
                context_dict['model'] = model
            if response:
                # Truncate response for context
                context_dict['response_preview'] = (
                    response[:200] + '...' if len(response) > 200 else response
                )
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.LLM_PARSING_FAILED),
            user_message=kwargs.get(
                'user_message', 'Failed to understand workout description'
            ),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class ServiceUnavailableError(GymTrackerError):
    """Raised when external services are unavailable"""

    def __init__(
        self,
        message: str,
        service: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if service:
                context_dict['service'] = service
            if retry_after:
                context_dict['retry_after'] = retry_after
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.SERVICE_TIMEOUT),
            user_message=kwargs.get(
                'user_message', 'External service temporarily unavailable'
            ),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class AuthenticationError(GymTrackerError):
    """Raised when authentication/authorization fails"""

    def __init__(self, message: str, user_id: Optional[str] = None, **kwargs):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if user_id:
                context_dict['user_id'] = user_id
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.UNAUTHORIZED),
            user_message=kwargs.get('user_message', 'Access denied'),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class RateLimitError(GymTrackerError):
    """Raised when rate limits are exceeded"""

    def __init__(
        self,
        message: str,
        limit_type: Optional[str] = None,
        reset_time: Optional[int] = None,
        **kwargs,
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if limit_type:
                context_dict['limit_type'] = limit_type
            if reset_time:
                context_dict['reset_time'] = reset_time
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.RATE_LIMIT_EXCEEDED),
            user_message=kwargs.get(
                'user_message', 'Too many requests, please try again later'
            ),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class ExportError(GymTrackerError):
    """Raised when data export/import fails"""

    def __init__(
        self, message: str, format_type: Optional[str] = None, **kwargs
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if format_type:
                context_dict['format'] = format_type
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.EXPORT_FAILED),
            user_message=kwargs.get('user_message', 'Export operation failed'),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


class BackupError(GymTrackerError):
    """Raised when backup/restore operations fail"""

    def __init__(
        self,
        message: str,
        backup_path: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        context = kwargs.get('context')
        if not isinstance(context, ErrorContext):
            context_dict = context if isinstance(context, dict) else {}
            if backup_path:
                context_dict['backup_path'] = backup_path
            if operation:
                context_dict['operation'] = operation
            context = ErrorContext(**context_dict)

        super().__init__(
            message=message,
            error_code=kwargs.get('error_code', ErrorCode.BACKUP_FAILED),
            user_message=kwargs.get('user_message', 'Backup operation failed'),
            context=context,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ['error_code', 'user_message', 'context']
            },
        )


# =============================================================================
# EXCEPTION UTILITIES
# =============================================================================


def handle_database_exception(
    e: Exception, operation: str = 'unknown'
) -> DatabaseError:
    """Convert generic database exceptions to DatabaseError"""
    from sqlalchemy.exc import (
        SQLAlchemyError,
        IntegrityError,
        OperationalError,
    )

    if isinstance(e, IntegrityError):
        return DatabaseError(
            message=f'Database constraint violation during {operation}',
            operation=operation,
            error_code=ErrorCode.CONSTRAINT_VIOLATION,
            cause=e,
        )
    elif isinstance(e, OperationalError):
        return DatabaseError(
            message=f'Database connection failed during {operation}',
            operation=operation,
            error_code=ErrorCode.DATABASE_CONNECTION_FAILED,
            cause=e,
        )
    elif isinstance(e, SQLAlchemyError):
        return DatabaseError(
            message=f'Database error during {operation}',
            operation=operation,
            cause=e,
        )
    else:
        return DatabaseError(
            message=f'Unexpected database error during {operation}',
            operation=operation,
            cause=e,
        )


def handle_service_exception(
    e: Exception, service: str = 'unknown'
) -> ServiceUnavailableError:
    """Convert generic service exceptions to ServiceUnavailableError"""
    import requests

    if isinstance(e, requests.exceptions.Timeout):
        return ServiceUnavailableError(
            message=f'{service} service timeout',
            service=service,
            error_code=ErrorCode.SERVICE_TIMEOUT,
            cause=e,
        )
    elif isinstance(e, requests.exceptions.ConnectionError):
        return ServiceUnavailableError(
            message=f'{service} service connection failed',
            service=service,
            error_code=ErrorCode.NETWORK_ERROR,
            cause=e,
        )
    elif isinstance(e, requests.exceptions.HTTPError):
        status_code = getattr(e.response, 'status_code', None)
        if status_code == 429:
            return ServiceUnavailableError(
                message=f'{service} rate limit exceeded',
                service=service,
                error_code=ErrorCode.LLM_RATE_LIMIT_EXCEEDED,
                cause=e,
            )
        else:
            return ServiceUnavailableError(
                message=f'{service} HTTP error: {status_code}',
                service=service,
                cause=e,
            )
    else:
        return ServiceUnavailableError(
            message=f'{service} service error', service=service, cause=e
        )
