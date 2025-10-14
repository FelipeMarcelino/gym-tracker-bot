"""Centralized error handling for the gym tracker bot

This module provides a unified way to handle exceptions across all bot handlers,
ensuring consistent error messages, logging, and user experience.
"""

from typing import Dict, Any, Optional, Tuple
from telegram import Update
from telegram.ext import ContextTypes

from config.logging_config import get_logger
from config.messages import messages
from services.exceptions import (
    GymTrackerError, 
    ValidationError, 
    DatabaseError, 
    AudioProcessingError,
    LLMParsingError, 
    ServiceUnavailableError, 
    AuthenticationError,
    RateLimitError,
    SessionError,
    ExportError,
    ErrorCode
)

logger = get_logger(__name__)


class ErrorHandler:
    """Centralized error handler for bot operations"""
    
    @staticmethod
    async def handle_error(
        error: Exception,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        operation: str = "unknown"
    ) -> None:
        """Handle any exception and send appropriate response to user
        
        Args:
            error: The exception that occurred
            update: Telegram update object
            context: Telegram context object
            operation: Description of the operation that failed
        """
        
        # Convert to GymTrackerError if needed
        gym_error = ErrorHandler._ensure_gym_tracker_error(error, operation)
        
        # Log the error with full context
        ErrorHandler._log_error(gym_error, update, operation)
        
        # Send user-friendly message
        await ErrorHandler._send_user_message(gym_error, update)
        
        # Report to monitoring (if implemented)
        ErrorHandler._report_to_monitoring(gym_error, update, operation)
    
    @staticmethod
    def _ensure_gym_tracker_error(error: Exception, operation: str) -> GymTrackerError:
        """Convert any exception to a GymTrackerError"""
        
        if isinstance(error, GymTrackerError):
            return error
        
        # Handle specific known exception types
        if isinstance(error, ValueError):
            return ValidationError(
                message=f"Invalid value in {operation}",
                details=str(error),
                error_code=ErrorCode.INVALID_INPUT,
                cause=error
            )
        
        elif isinstance(error, FileNotFoundError):
            return ValidationError(
                message=f"Required file not found in {operation}",
                details=str(error),
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                cause=error
            )
        
        elif isinstance(error, PermissionError):
            return AuthenticationError(
                message=f"Permission denied in {operation}",
                details=str(error),
                error_code=ErrorCode.ACCESS_DENIED,
                cause=error
            )
        
        elif isinstance(error, TimeoutError):
            return ServiceUnavailableError(
                message=f"Timeout in {operation}",
                details=str(error),
                error_code=ErrorCode.SERVICE_TIMEOUT,
                cause=error
            )
        
        else:
            # Generic unknown error
            return GymTrackerError(
                message=f"Unexpected error in {operation}",
                details=str(error),
                error_code=ErrorCode.INTERNAL_ERROR,
                user_message="An unexpected error occurred. Please try again.",
                cause=error
            )
    
    @staticmethod
    def _log_error(error: GymTrackerError, update: Update, operation: str) -> None:
        """Log error with appropriate level and context"""
        
        # Prepare context for logging
        user_info = {}
        if update and update.effective_user:
            user_info = {
                "user_id": update.effective_user.id,
                "username": update.effective_user.username,
                "first_name": update.effective_user.first_name
            }
        
        log_context = {
            "operation": operation,
            "user": user_info,
            "error_details": error.to_dict()
        }
        
        # Choose appropriate log level based on error type
        if error.error_code.value < 1200:  # General/Auth errors
            logger.error(f"Operation failed: {error}", extra=log_context)
        elif error.error_code.value < 1300:  # Validation errors
            logger.warning(f"Validation failed: {error}", extra=log_context)
        elif error.error_code.value < 1600:  # Database/Session errors
            logger.error(f"System error: {error}", extra=log_context)
        elif error.error_code.value < 1800:  # External service errors
            logger.warning(f"External service error: {error}", extra=log_context)
        else:  # Other errors
            logger.error(f"Unexpected error: {error}", extra=log_context)
    
    @staticmethod
    async def _send_user_message(error: GymTrackerError, update: Update) -> None:
        """Send appropriate error message to user"""
        
        if not update or not update.message:
            return
        
        # Get user-friendly message based on error type
        user_message = ErrorHandler._get_user_message(error)
        
        try:
            await update.message.reply_text(user_message, parse_mode="Markdown")
        except Exception as e:
            # Fallback if message sending fails
            logger.error(f"Failed to send error message to user: {e}")
            try:
                await update.message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
            except:
                pass  # Give up if even basic message fails
    
    @staticmethod
    def _get_user_message(error: GymTrackerError) -> str:
        """Generate user-friendly error message"""
        
        # Map error codes to specific message templates
        if isinstance(error, ValidationError):
            return messages.ERROR_VALIDATION.format(
                message=error.user_message,
                details=f"\n\n**Details:** {error.details}" if error.details else ""
            )
        
        elif isinstance(error, AudioProcessingError):
            rate_limit_note = ""
            if error.error_code == ErrorCode.LLM_RATE_LIMIT_EXCEEDED:
                rate_limit_note = "\n\n💡 _Try again in a few seconds_"
            
            return messages.ERROR_AUDIO_PROCESSING.format(
                message=error.user_message,
                rate_limit_note=rate_limit_note
            )
        
        elif isinstance(error, LLMParsingError):
            return messages.ERROR_LLM_PARSING.format(message=error.user_message)
        
        elif isinstance(error, ServiceUnavailableError):
            details = ""
            if error.context.get('retry_after'):
                details = f"\n\n**Retry after:** {error.context['retry_after']} seconds"
            
            return messages.ERROR_SERVICE_UNAVAILABLE.format(
                message=error.user_message,
                details=details
            )
        
        elif isinstance(error, DatabaseError):
            return messages.ERROR_DATABASE.format(message=error.user_message)
        
        elif isinstance(error, AuthenticationError):
            user_id = error.context.get('user_id', 'unknown')
            return messages.ACCESS_DENIED.format(user_id=user_id)
        
        elif isinstance(error, RateLimitError):
            reset_time = error.context.get('reset_time', 0)
            limit_type = error.context.get('limit_type', 'general')
            
            if limit_type == 'voice':
                return messages.RATE_LIMIT_VOICE.format(
                    reset_time=reset_time,
                    max_requests=5,  # Default values
                    window_seconds=60
                )
            elif limit_type == 'commands':
                return messages.RATE_LIMIT_COMMANDS.format(
                    reset_time=reset_time,
                    max_requests=30,
                    window_seconds=60
                )
            else:
                return messages.RATE_LIMIT_GENERAL.format(
                    reset_time=reset_time,
                    max_requests=20,
                    window_seconds=60
                )
        
        else:
            # Generic error message
            return messages.ERROR_UNEXPECTED.format(error_message=error.user_message)
    
    @staticmethod
    def _report_to_monitoring(error: GymTrackerError, update: Update, operation: str) -> None:
        """Report error to monitoring systems (placeholder for future implementation)"""
        # TODO: Implement monitoring integration (e.g., Sentry, DataDog, etc.)
        pass


class ErrorContext:
    """Context manager for handling errors in bot operations"""
    
    def __init__(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE, 
        operation: str
    ):
        self.update = update
        self.context = context
        self.operation = operation
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            await ErrorHandler.handle_error(exc_val, self.update, self.context, self.operation)
            return True  # Suppress the exception
        return False


def error_handler(operation: str):
    """Decorator for automatic error handling in bot handlers
    
    Usage:
        @error_handler("processing voice message")
        async def handle_voice(update, context):
            # Your handler code here
            pass
    """
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                return await func(update, context, *args, **kwargs)
            except Exception as e:
                await ErrorHandler.handle_error(e, update, context, operation)
        
        return wrapper
    return decorator


# Convenience functions for common error scenarios
async def handle_validation_error(
    update: Update, 
    message: str, 
    field: Optional[str] = None,
    value: Optional[Any] = None
) -> None:
    """Quick helper for validation errors"""
    error = ValidationError(message=message, field=field, value=value)
    await ErrorHandler.handle_error(error, update, None, "validation")


async def handle_database_error(
    update: Update, 
    operation: str, 
    original_error: Exception
) -> None:
    """Quick helper for database errors"""
    from services.exceptions import handle_database_exception
    
    error = handle_database_exception(original_error, operation)
    await ErrorHandler.handle_error(error, update, None, operation)


async def handle_service_error(
    update: Update, 
    service: str, 
    original_error: Exception
) -> None:
    """Quick helper for external service errors"""
    from services.exceptions import handle_service_exception
    
    error = handle_service_exception(original_error, service)
    await ErrorHandler.handle_error(error, update, None, f"{service} operation")