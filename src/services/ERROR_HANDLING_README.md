# Enhanced Error Handling System

This document explains the comprehensive error handling system implemented in the Gym Tracker Bot.

## Overview

The error handling system provides:
- **Standardized error codes** for different failure types
- **Rich context information** for debugging
- **User-friendly messages** separate from technical details
- **Centralized error handling** across all bot operations
- **Structured logging** with error details

## Error Code Categories

| Range | Category | Description |
|-------|----------|-------------|
| 1000-1099 | General | Unknown, configuration, internal errors |
| 1100-1199 | Authentication | Unauthorized, access denied, credentials |
| 1200-1299 | Validation | Invalid input, missing fields, format errors |
| 1300-1399 | Database | Connection, query, constraint failures |
| 1400-1499 | Session | Session management errors |
| 1500-1599 | Audio Processing | Transcription, format, quality issues |
| 1600-1699 | LLM Processing | Parsing, service, rate limit errors |
| 1700-1799 | External Services | API errors, network issues |
| 1800-1899 | Export/Import | Data format, file operation errors |
| 1900-1999 | Rate Limiting | Request limits, throttling |

## Exception Classes

### Base Exception
```python
class GymTrackerError(Exception):
    def __init__(
        self, 
        message: str,                    # Technical message for logs
        details: str = None,             # Additional technical details
        error_code: ErrorCode = None,    # Standardized error code
        user_message: str = None,        # User-friendly message
        context: Dict[str, Any] = None,  # Additional context data
        cause: Exception = None          # Original exception
    ):
```

### Specific Exceptions

#### ValidationError
```python
ValidationError(
    message="Invalid exercise name",
    field="exercise_name",
    value="",
    error_code=ErrorCode.MISSING_REQUIRED_FIELD,
    user_message="Please provide a valid exercise name"
)
```

#### DatabaseError
```python
DatabaseError(
    message="User lookup failed",
    operation="get_user_by_id",
    error_code=ErrorCode.DATABASE_QUERY_FAILED,
    user_message="Database operation failed"
)
```

#### LLMParsingError
```python
LLMParsingError(
    message="Invalid JSON response",
    model="llama3.1:8b",
    response='{"invalid": json}',
    error_code=ErrorCode.LLM_INVALID_RESPONSE,
    user_message="AI couldn't understand your workout description"
)
```

#### ServiceUnavailableError
```python
ServiceUnavailableError(
    message="Groq API rate limit exceeded",
    service="Groq API",
    retry_after=30,
    error_code=ErrorCode.LLM_RATE_LIMIT_EXCEEDED,
    user_message="Too many requests. Please wait 30 seconds."
)
```

#### AudioProcessingError
```python
AudioProcessingError(
    message="Transcription failed",
    stage="whisper_processing",
    duration=45.5,
    error_code=ErrorCode.AUDIO_TRANSCRIPTION_FAILED,
    user_message="Could not process audio. Please try with clearer audio."
)
```

## Using the Error Handler

### Decorator Approach (Recommended)
```python
from services.error_handler import error_handler

@error_handler("processing voice message")
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Your handler code here
    # Any exception will be automatically caught and handled
    pass
```

### Context Manager Approach
```python
from services.error_handler import ErrorContext

async def my_operation(update, context):
    async with ErrorContext(update, context, "performing operation"):
        # Your code here
        # Exceptions are automatically handled
        pass
```

### Manual Error Handling
```python
from services.error_handler import ErrorHandler

async def my_handler(update, context):
    try:
        # Your code here
        pass
    except Exception as e:
        await ErrorHandler.handle_error(e, update, context, "my operation")
```

### Quick Helper Functions
```python
from services.error_handler import (
    handle_validation_error,
    handle_database_error,
    handle_service_error
)

# Quick validation error
await handle_validation_error(
    update, 
    "Invalid input", 
    field="exercise_name", 
    value=""
)

# Quick database error
try:
    # database operation
    pass
except Exception as e:
    await handle_database_error(update, "user_lookup", e)

# Quick service error
try:
    # API call
    pass
except Exception as e:
    await handle_service_error(update, "Groq API", e)
```

## Error Context and Logging

### Rich Context
Each exception can include rich context for debugging:
```python
error = ValidationError(
    message="Invalid workout data",
    field="exercise_name",
    value="",
    context={
        "user_id": "12345",
        "session_id": "67890",
        "additional_info": "custom data"
    }
)
```

### Structured Logging
Errors are automatically logged with structured data:
```json
{
    "error_code": 1201,
    "error_name": "MISSING_REQUIRED_FIELD", 
    "message": "Invalid workout data",
    "user_message": "Please provide a valid exercise name",
    "context": {
        "field": "exercise_name",
        "value": "",
        "user_id": "12345"
    },
    "operation": "processing voice message",
    "stack_trace": "..."
}
```

## Exception Conversion Utilities

### Database Exception Conversion
```python
from services.exceptions import handle_database_exception

try:
    # SQLAlchemy operation
    pass
except Exception as e:
    gym_error = handle_database_exception(e, "user_creation")
    raise gym_error
```

### Service Exception Conversion
```python
from services.exceptions import handle_service_exception

try:
    # HTTP request
    pass
except Exception as e:
    gym_error = handle_service_exception(e, "Groq API")
    raise gym_error
```

## User Message Mapping

The error handler automatically maps technical errors to user-friendly messages:

| Exception Type | User Message Template |
|----------------|----------------------|
| ValidationError | "Invalid input provided" + details |
| AudioProcessingError | "Audio processing failed" + retry advice |
| LLMParsingError | "Failed to understand workout description" |
| ServiceUnavailableError | "External service temporarily unavailable" |
| DatabaseError | "Database operation failed" |
| AuthenticationError | "Access denied" |
| RateLimitError | "Too many requests, please try again later" |

## Best Practices

### 1. Use Specific Exceptions
```python
# Good
raise ValidationError(
    message="Exercise name cannot be empty",
    field="exercise_name",
    error_code=ErrorCode.MISSING_REQUIRED_FIELD
)

# Bad
raise Exception("Invalid input")
```

### 2. Provide User-Friendly Messages
```python
# Good
raise LLMParsingError(
    message="JSON parsing failed",
    user_message="The AI couldn't understand your workout. Try describing it more clearly."
)

# Bad
raise LLMParsingError("json.loads() failed")
```

### 3. Include Rich Context
```python
# Good
raise AudioProcessingError(
    message="Transcription failed",
    stage="whisper_api",
    duration=120.5,
    context={"file_size": 2048576, "format": "ogg"}
)

# Bad
raise AudioProcessingError("Audio failed")
```

### 4. Use Appropriate Error Codes
```python
# Good - Specific error code
raise ValidationError(
    message="Weight must be positive",
    error_code=ErrorCode.VALUE_OUT_OF_RANGE
)

# Bad - Generic error code
raise ValidationError(
    message="Weight must be positive",
    error_code=ErrorCode.INVALID_INPUT
)
```

### 5. Chain Exceptions
```python
# Good - Preserve original exception
try:
    external_api_call()
except requests.RequestException as e:
    raise ServiceUnavailableError(
        message="API call failed",
        service="External API",
        cause=e  # Preserve original exception
    )
```

## Error Monitoring

### Log Analysis
All errors are logged with structured data for easy analysis:
```bash
# Find all rate limit errors
grep "RATE_LIMIT_EXCEEDED" logs/gym_tracker_bot.log

# Find all user validation errors
grep "1200\|1201\|1202\|1203" logs/gym_tracker_bot.log
```

### Future Monitoring Integration
The system is designed to integrate with monitoring services:
```python
# TODO: Implement in ErrorHandler._report_to_monitoring()
# - Sentry for error tracking
# - DataDog for metrics
# - Custom alerting systems
```

## Testing Error Handling

### Unit Tests
```python
def test_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        # Code that should raise ValidationError
        pass
    
    error = exc_info.value
    assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD
    assert "exercise_name" in error.context
```

### Integration Tests
```python
async def test_error_handler_integration():
    # Mock update and context
    update = Mock()
    context = Mock()
    
    # Test that error handler processes exceptions correctly
    await ErrorHandler.handle_error(
        ValidationError("test"), 
        update, 
        context, 
        "test_operation"
    )
    
    # Assert error message was sent to user
    update.message.reply_text.assert_called_once()
```

## Migration Guide

### From Old Error Handling
```python
# Old approach
try:
    # operation
    pass
except Exception as e:
    logger.error(f"Error: {e}")
    await update.message.reply_text("An error occurred")

# New approach
@error_handler("operation_name")
async def my_handler(update, context):
    # operation
    # All errors automatically handled with rich context and user messages
    pass
```

This enhanced error handling system provides robust, user-friendly, and debuggable error management throughout the application.