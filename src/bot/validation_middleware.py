"""Advanced input validation middleware for bot handlers

This module provides comprehensive validation decorators, schema validation,
and middleware for all bot operations with automatic error handling.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Dict, List, Optional, Union, Callable, Type
from telegram import Update
from telegram.ext import ContextTypes

from config.logging_config import get_logger
from config.settings import settings
from services.exceptions import ValidationError, ErrorCode
from services.error_handler import ErrorHandler
from bot.validation_utils import ValidationUtils

logger = get_logger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels"""
    STRICT = "strict"      # Reject any invalid input
    PERMISSIVE = "permissive"  # Try to sanitize and continue
    LENIENT = "lenient"    # Allow most inputs with basic sanitization


@dataclass
class ValidationRule:
    """Individual validation rule"""
    field: str
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    validator: Optional[Callable] = None
    error_message: Optional[str] = None


class BaseValidator(ABC):
    """Base class for input validators"""
    
    @abstractmethod
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate a value and return result dict"""
        pass


class TextValidator(BaseValidator):
    """Validator for text inputs"""
    
    def __init__(
        self, 
        min_length: int = 0,
        max_length: Optional[int] = None,
        pattern: Optional[str] = None,
        allow_empty: bool = False,
        strip_whitespace: bool = True,
        escape_html: bool = True
    ):
        self.min_length = min_length
        self.max_length = max_length or settings.MAX_TEXT_LENGTH
        self.pattern = re.compile(pattern) if pattern else None
        self.allow_empty = allow_empty
        self.strip_whitespace = strip_whitespace
        self.escape_html = escape_html
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate text input"""
        if value is None:
            value = ""
        
        # Convert to string
        text = str(value)
        
        # Strip whitespace if requested
        if self.strip_whitespace:
            text = text.strip()
        
        # Check empty
        if not text and not self.allow_empty:
            return {
                "is_valid": False,
                "value": text,
                "error": "Text cannot be empty",
                "error_code": ErrorCode.MISSING_REQUIRED_FIELD
            }
        
        # If empty and allowed, skip length checks
        if not text and self.allow_empty:
            return {
                "is_valid": True,
                "value": text,
                "error": None
            }
        
        # Check length
        if len(text) < self.min_length:
            return {
                "is_valid": False,
                "value": text,
                "error": f"Text too short (minimum {self.min_length} characters)",
                "error_code": ErrorCode.VALUE_OUT_OF_RANGE
            }
        
        if len(text) > self.max_length:
            return {
                "is_valid": False,
                "value": text,
                "error": f"Text too long (maximum {self.max_length} characters)",
                "error_code": ErrorCode.VALUE_OUT_OF_RANGE
            }
        
        # Sanitize text
        if self.escape_html:
            text = ValidationUtils.sanitize_text(text)
        
        # Check pattern
        if self.pattern and not self.pattern.match(text):
            return {
                "is_valid": False,
                "value": text,
                "error": "Text contains invalid characters",
                "error_code": ErrorCode.INVALID_FORMAT
            }
        
        return {
            "is_valid": True,
            "value": text,
            "error": None
        }


class NumberValidator(BaseValidator):
    """Validator for numeric inputs"""
    
    def __init__(
        self,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        integer_only: bool = False,
        positive_only: bool = False
    ):
        self.min_value = min_value
        self.max_value = max_value
        self.integer_only = integer_only
        self.positive_only = positive_only
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate numeric input"""
        try:
            if self.integer_only:
                num = int(value)
            else:
                num = float(value)
        except (ValueError, TypeError):
            return {
                "is_valid": False,
                "value": value,
                "error": f"Must be a valid {'number' if not self.integer_only else 'whole number'}",
                "error_code": ErrorCode.INVALID_FORMAT
            }
        
        # Check positive
        if self.positive_only and num <= 0:
            return {
                "is_valid": False,
                "value": num,
                "error": "Must be a positive number",
                "error_code": ErrorCode.VALUE_OUT_OF_RANGE
            }
        
        # Check range
        if self.min_value is not None and num < self.min_value:
            return {
                "is_valid": False,
                "value": num,
                "error": f"Number is below minimum value of {self.min_value}",
                "error_code": ErrorCode.VALUE_OUT_OF_RANGE
            }
        
        if self.max_value is not None and num > self.max_value:
            return {
                "is_valid": False,
                "value": num,
                "error": f"Number is above maximum value of {self.max_value}",
                "error_code": ErrorCode.VALUE_OUT_OF_RANGE
            }
        
        return {
            "is_valid": True,
            "value": num,
            "error": None
        }


class UserIdValidator(BaseValidator):
    """Validator for Telegram user IDs"""
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate Telegram user ID"""
        result = ValidationUtils.validate_user_id(value)
        # Ensure the validated ID is a string
        validated_id = str(result.get("validated_id")) if result.get("validated_id") is not None else None

        return {
            "is_valid": result["is_valid"],
            "value": validated_id,
            "error": result.get("error_message"),
            "error_code": ErrorCode.INVALID_INPUT if not result["is_valid"] else None
        }


class AudioValidator(BaseValidator):
    """Validator for audio files"""
    
    def __init__(
        self,
        max_duration: Optional[int] = None,
        max_size_mb: Optional[int] = None
    ):
        self.max_duration = max_duration or settings.MAX_AUDIO_DURATION_SECONDS
        self.max_size_mb = max_size_mb or settings.MAX_VOICE_FILE_SIZE_MB
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate audio file"""
        if not value:
            return {
                "is_valid": False,
                "value": None,
                "error": "Audio file is required",
                "error_code": ErrorCode.MISSING_REQUIRED_FIELD
            }
        
        # Check duration
        try:
            if hasattr(value, 'duration') and isinstance(value.duration, (int, float)) and value.duration > self.max_duration:
                return {
                    "is_valid": False,
                    "value": value,
                    "error": f"Audio too long (maximum {self.max_duration//60} minutes)",
                    "error_code": ErrorCode.AUDIO_TOO_LONG
                }
        except (TypeError, AttributeError):
            # Skip duration check if we can't get a valid duration
            pass
        
        # Check file size
        max_size_bytes = self.max_size_mb * 1024 * 1024
        try:
            if hasattr(value, 'file_size') and isinstance(value.file_size, (int, float)) and value.file_size > max_size_bytes:
                return {
                    "is_valid": False,
                    "value": value,
                    "error": f"Audio file too large (maximum {self.max_size_mb}MB)",
                    "error_code": ErrorCode.FILE_TOO_LARGE
                }
        except (TypeError, AttributeError):
            # Skip file size check if we can't get a valid file size
            pass
        
        return {
            "is_valid": True,
            "value": value,
            "error": None
        }


class CommandArgsValidator(BaseValidator):
    """Validator for command arguments"""
    
    def __init__(
        self,
        min_args: int = 0,
        max_args: Optional[int] = None,
        arg_validators: Optional[List[BaseValidator]] = None
    ):
        self.min_args = min_args
        self.max_args = max_args
        self.arg_validators = arg_validators or []
    
    def validate(self, value: Any, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate command arguments"""
        if not isinstance(value, list):
            args = str(value).split() if value else []
        else:
            args = value
        
        # Check argument count
        if len(args) < self.min_args:
            return {
                "is_valid": False,
                "value": args,
                "error": f"Not enough arguments (minimum {self.min_args})",
                "error_code": ErrorCode.MISSING_REQUIRED_FIELD
            }
        
        if self.max_args is not None and len(args) > self.max_args:
            return {
                "is_valid": False,
                "value": args,
                "error": f"Too many arguments (maximum {self.max_args})",
                "error_code": ErrorCode.INVALID_INPUT
            }
        
        # Validate individual arguments
        validated_args = []
        for i, arg in enumerate(args):
            if i < len(self.arg_validators):
                result = self.arg_validators[i].validate(arg, context)
                if not result["is_valid"]:
                    return {
                        "is_valid": False,
                        "value": args,
                        "error": f"Argument {i+1}: {result['error']}",
                        "error_code": result.get("error_code", ErrorCode.INVALID_INPUT)
                    }
                validated_args.append(result["value"])
            else:
                validated_args.append(arg)
        
        return {
            "is_valid": True,
            "value": validated_args,
            "error": None
        }


@dataclass
class ValidationSchema:
    """Schema for validating inputs"""
    user_required: bool = True
    message_required: bool = True
    text_validator: Optional[TextValidator] = None
    audio_validator: Optional[AudioValidator] = None
    command_args_validator: Optional[CommandArgsValidator] = None
    custom_validators: Optional[Dict[str, BaseValidator]] = None
    level: ValidationLevel = ValidationLevel.STRICT
    
    def __post_init__(self):
        """Initialize fields dict for dynamic validation"""
        if not hasattr(self, 'fields'):
            self.fields = {}
        if self.custom_validators is None:
            self.custom_validators = {}
    
    def add_field(self, name: str, validator: BaseValidator):
        """Add a field validator to the schema"""
        self.fields[name] = validator
        self.custom_validators[name] = validator
    
    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against the schema"""
        result = {}
        errors = {}
        
        # If we have defined fields, validate them
        if hasattr(self, 'fields') and self.fields:
            for field_name, validator in self.fields.items():
                if field_name in data:
                    validation_result = validator.validate(data[field_name])
                    if validation_result["is_valid"]:
                        result[field_name] = validation_result["value"]
                    else:
                        errors[field_name] = validation_result["error"]
                else:
                    # Check if field is required based on validator properties
                    if (hasattr(validator, 'allow_empty') and not getattr(validator, 'allow_empty', True)) or \
                       (not hasattr(validator, 'allow_empty') and hasattr(validator, 'min_length') and getattr(validator, 'min_length', 0) > 0):
                        errors[field_name] = f"{field_name} is required"
            
            # Copy non-validated fields
            for key, value in data.items():
                if key not in self.fields:
                    result[key] = value
        else:
            # For pre-defined schemas, validate according to the original schema design
            # This handles text_message, admin_command, etc. schemas from CommonSchemas
            if self.text_validator and 'text' in data:
                validation_result = self.text_validator.validate(data['text'])
                if validation_result["is_valid"]:
                    result['text'] = validation_result["value"]
                else:
                    errors['text'] = validation_result["error"]
            
            if self.audio_validator and 'audio' in data:
                validation_result = self.audio_validator.validate(data['audio'])
                if validation_result["is_valid"]:
                    result['audio'] = validation_result["value"]
                else:
                    errors['audio'] = validation_result["error"]
            
            # Copy remaining fields
            for key, value in data.items():
                if key not in ['text', 'audio'] or key not in result:
                    result[key] = value
        
        if errors:
            from services.exceptions import ValidationError
            error_message = f"Validation failed: {', '.join(f'{field}: {error}' for field, error in errors.items())}"
            raise ValidationError(error_message, details=errors)
        
        return result


class ValidationMiddleware:
    """Centralized validation middleware"""
    
    @staticmethod
    async def validate_update(
        update: Update,
        schema: ValidationSchema,
        context: ContextTypes.DEFAULT_TYPE = None
    ) -> Dict[str, Any]:
        """Validate an entire update against a schema"""
        
        result = {
            "is_valid": True,
            "errors": [],
            "data": {
                "user": {},
                "message": {},
                "custom": {}
            }
        }
        
        # Validate user
        if schema.user_required and not update.effective_user:
            result["is_valid"] = False
            result["errors"].append("User information is required")
            return result
        
        if update.effective_user:
            user_validation = ValidationMiddleware._validate_user(update.effective_user)
            if not user_validation["is_valid"]:
                result["is_valid"] = False
                result["errors"].extend(user_validation["errors"])
            else:
                result["data"]["user"] = user_validation["data"]
        
        # Validate message
        if schema.message_required and not update.message:
            result["is_valid"] = False
            result["errors"].append("Message is required")
            return result
        
        if update.message:
            message_validation = ValidationMiddleware._validate_message(
                update.message, schema
            )
            if not message_validation["is_valid"]:
                if schema.level == ValidationLevel.STRICT:
                    result["is_valid"] = False
                result["errors"].extend(message_validation["errors"])
            
            result["data"]["message"] = message_validation["data"]
        
        # Custom validations
        if schema.custom_validators:
            for field, validator in schema.custom_validators.items():
                value = getattr(update, field, None)
                validation_result = validator.validate(value, result["data"])
                if not validation_result["is_valid"]:
                    if schema.level == ValidationLevel.STRICT:
                        result["is_valid"] = False
                    result["errors"].append(f"{field}: {validation_result['error']}")
                else:
                    result["data"]["custom"][field] = validation_result["value"]
        
        return result
    
    @staticmethod
    def _validate_user(user) -> Dict[str, Any]:
        """Validate user information"""
        result = {"is_valid": True, "errors": [], "data": {}}
        
        # Validate user ID
        user_id_result = UserIdValidator().validate(user.id)
        if not user_id_result["is_valid"]:
            result["is_valid"] = False
            result["errors"].append(f"User ID: {user_id_result['error']}")
        else:
            result["data"]["id"] = user_id_result["value"]
        
        # Validate names
        if user.first_name:
            name_validator = TextValidator(max_length=settings.MAX_NAME_LENGTH)
            name_result = name_validator.validate(user.first_name)
            if name_result["is_valid"]:
                result["data"]["first_name"] = name_result["value"]
            else:
                result["errors"].append(f"First name: {name_result['error']}")
        
        if user.last_name:
            name_validator = TextValidator(max_length=settings.MAX_NAME_LENGTH)
            name_result = name_validator.validate(user.last_name)
            if name_result["is_valid"]:
                result["data"]["last_name"] = name_result["value"]
        
        if user.username:
            username_validator = TextValidator(
                max_length=settings.MAX_NAME_LENGTH,
                pattern=r'^[a-zA-Z0-9_]+$'
            )
            username_result = username_validator.validate(user.username)
            if username_result["is_valid"]:
                result["data"]["username"] = username_result["value"]
        
        return result
    
    @staticmethod
    def _validate_message(message, schema: ValidationSchema) -> Dict[str, Any]:
        """Validate message content"""
        result = {"is_valid": True, "errors": [], "data": {}}
        
        # Validate text
        if message.text and schema.text_validator:
            text_result = schema.text_validator.validate(message.text)
            if not text_result["is_valid"]:
                result["is_valid"] = False
                result["errors"].append(f"Text: {text_result['error']}")
            else:
                result["data"]["text"] = text_result["value"]
        elif message.text:
            # Default text validation
            default_validator = TextValidator()
            text_result = default_validator.validate(message.text)
            if text_result["is_valid"]:
                result["data"]["text"] = text_result["value"]
        
        # Validate audio
        if message.voice and schema.audio_validator:
            audio_result = schema.audio_validator.validate(message.voice)
            if not audio_result["is_valid"]:
                result["is_valid"] = False
                result["errors"].append(f"Audio: {audio_result['error']}")
            else:
                result["data"]["voice"] = audio_result["value"]
        elif message.voice:
            # Default audio validation
            default_validator = AudioValidator()
            audio_result = default_validator.validate(message.voice)
            if audio_result["is_valid"]:
                result["data"]["voice"] = audio_result["value"]
        
        # Validate command arguments
        if message.text and message.text.startswith('/') and schema.command_args_validator:
            # Extract command arguments
            args = message.text.split()[1:]  # Skip the command itself
            args_result = schema.command_args_validator.validate(args)
            if not args_result["is_valid"]:
                result["is_valid"] = False
                result["errors"].append(f"Arguments: {args_result['error']}")
            else:
                result["data"]["args"] = args_result["value"]
        
        return result


def validate_input(schema: ValidationSchema):
    """Decorator for input validation with schema
    
    Usage:
        @validate_input(ValidationSchema(
            text_validator=TextValidator(min_length=5),
            audio_validator=AudioValidator(max_duration=120)
        ))
        async def my_handler(update, context, validated_data):
            # validated_data contains sanitized input
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                # Validate input
                validation_result = await ValidationMiddleware.validate_update(
                    update, schema, context
                )
                
                if not validation_result["is_valid"]:
                    # Create validation error
                    error_messages = "; ".join(validation_result["errors"])
                    raise ValidationError(
                        message=f"Input validation failed: {error_messages}",
                        details=str(validation_result["errors"]),
                        error_code=ErrorCode.INVALID_INPUT,
                        user_message="Invalid input provided. Please check your message and try again.",
                        context={"validation_errors": validation_result["errors"]}
                    )
                
                # Add validated data to kwargs
                kwargs["validated_data"] = validation_result["data"]
                
                return await func(update, context, *args, **kwargs)
                
            except ValidationError as e:
                # Send user-friendly error message
                if update.message:
                    await update.message.reply_text(e.user_message)
                logger.warning(f"Validation error: {e}")
                return None
            except Exception as e:
                # Log unexpected errors
                logger.exception(f"Unexpected error in validation decorator: {e}")
                raise
        
        return wrapper
    return decorator


# Common validation schemas
class CommonSchemas:
    """Pre-defined validation schemas for common use cases"""
    
    @staticmethod
    def text_message(min_length: int = 1, max_length: Optional[int] = None) -> ValidationSchema:
        """Schema for text message handlers"""
        return ValidationSchema(
            text_validator=TextValidator(
                min_length=min_length,
                max_length=max_length or settings.MAX_TEXT_LENGTH
            ),
            audio_validator=None
        )
    
    @staticmethod
    def voice_message(max_duration: Optional[int] = None) -> ValidationSchema:
        """Schema for voice message handlers"""
        return ValidationSchema(
            text_validator=None,
            audio_validator=AudioValidator(
                max_duration=max_duration or settings.MAX_AUDIO_DURATION_SECONDS
            )
        )
    
    @staticmethod
    def command_with_args(min_args: int, max_args: Optional[int] = None) -> ValidationSchema:
        """Schema for command handlers that require arguments"""
        return ValidationSchema(
            command_args_validator=CommandArgsValidator(
                min_args=min_args,
                max_args=max_args
            )
        )
    
    @staticmethod
    def admin_command() -> ValidationSchema:
        """Schema for admin commands"""
        return ValidationSchema(
            user_required=True,
            message_required=True,
            level=ValidationLevel.STRICT
        )
    
    @staticmethod
    def flexible_input() -> ValidationSchema:
        """Schema for handlers that accept various input types"""
        return ValidationSchema(
            text_validator=TextValidator(allow_empty=True),
            audio_validator=AudioValidator(),
            level=ValidationLevel.PERMISSIVE
        )
    
    @staticmethod
    def audio_message(max_duration: Optional[int] = None) -> ValidationSchema:
        """Schema for audio message handlers"""
        return ValidationSchema(
            text_validator=None,
            audio_validator=AudioValidator(
                max_duration=max_duration or settings.MAX_AUDIO_DURATION_SECONDS
            )
        )