"""Unit tests for validation middleware"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from bot.validation_middleware import (
    TextValidator, NumberValidator, AudioValidator,
    ValidationSchema, CommonSchemas, validate_input
)
from services.exceptions import ValidationError


class TestValidators:
    """Test individual validator classes"""
    
    def test_text_validator_valid(self):
        """Test text validator with valid input"""
        validator = TextValidator(min_length=5, max_length=20, required=True)
        
        # Valid text
        result = validator.validate("Hello world")
        assert result == "Hello world"
        
        # Edge cases
        assert validator.validate("12345") == "12345"  # Exactly min length
        assert validator.validate("A" * 20) == "A" * 20  # Exactly max length
    
    def test_text_validator_invalid(self):
        """Test text validator with invalid input"""
        validator = TextValidator(min_length=5, max_length=20, required=True)
        
        # Too short
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("Hi")
        assert "too short" in str(exc_info.value)
        
        # Too long
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("A" * 25)
        assert "too long" in str(exc_info.value)
        
        # Empty when required
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("")
        assert "required" in str(exc_info.value)
    
    def test_text_validator_optional(self):
        """Test text validator with optional field"""
        validator = TextValidator(min_length=5, max_length=20, required=False)
        
        # Empty should be allowed
        result = validator.validate("")
        assert result == ""
        
        # None should be allowed
        result = validator.validate(None)
        assert result is None
    
    def test_number_validator_valid(self):
        """Test number validator with valid input"""
        validator = NumberValidator(min_value=0, max_value=100, required=True)
        
        # Valid numbers
        assert validator.validate(50) == 50
        assert validator.validate(0) == 0  # Min boundary
        assert validator.validate(100) == 100  # Max boundary
        assert validator.validate(50.5) == 50.5  # Float
        
        # String numbers
        assert validator.validate("50") == 50
        assert validator.validate("50.5") == 50.5
    
    def test_number_validator_invalid(self):
        """Test number validator with invalid input"""
        validator = NumberValidator(min_value=0, max_value=100, required=True)
        
        # Out of range
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(-1)
        assert "below minimum" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(101)
        assert "above maximum" in str(exc_info.value)
        
        # Invalid string
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("not a number")
        assert "valid number" in str(exc_info.value)
    
    def test_audio_validator_valid(self, mock_audio_file):
        """Test audio validator with valid input"""
        validator = AudioValidator(max_duration=300, required=True)
        
        # Mock valid audio
        mock_audio = Mock()
        mock_audio.file_size = 1024 * 1024  # 1MB
        mock_audio.duration = 120  # 2 minutes
        
        result = validator.validate(mock_audio)
        assert result == mock_audio
    
    def test_audio_validator_invalid(self):
        """Test audio validator with invalid input"""
        validator = AudioValidator(max_duration=300, required=True)
        
        # Missing when required
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(None)
        assert "required" in str(exc_info.value)
        
        # Too large
        mock_large_audio = Mock()
        mock_large_audio.file_size = 25 * 1024 * 1024  # 25MB
        mock_large_audio.duration = 120
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(mock_large_audio)
        assert "too large" in str(exc_info.value)
        
        # Too long
        mock_long_audio = Mock()
        mock_long_audio.file_size = 1024 * 1024  # 1MB
        mock_long_audio.duration = 400  # Too long
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(mock_long_audio)
        assert "too long" in str(exc_info.value)


class TestValidationSchema:
    """Test validation schema functionality"""
    
    def test_schema_creation(self):
        """Test creating validation schemas"""
        schema = ValidationSchema()
        schema.add_field("text", TextValidator(min_length=1, max_length=100))
        schema.add_field("number", NumberValidator(min_value=0, max_value=10))
        
        assert "text" in schema.fields
        assert "number" in schema.fields
        assert len(schema.fields) == 2
    
    def test_schema_validation_success(self):
        """Test successful schema validation"""
        schema = ValidationSchema()
        schema.add_field("name", TextValidator(min_length=2, max_length=50))
        schema.add_field("age", NumberValidator(min_value=0, max_value=150))
        
        data = {"name": "John", "age": 25}
        result = schema.validate(data)
        
        assert result["name"] == "John"
        assert result["age"] == 25
    
    def test_schema_validation_failure(self):
        """Test schema validation with errors"""
        schema = ValidationSchema()
        schema.add_field("name", TextValidator(min_length=2, max_length=50))
        schema.add_field("age", NumberValidator(min_value=0, max_value=150))
        
        # Invalid data
        data = {"name": "X", "age": -5}  # Name too short, age negative
        
        with pytest.raises(ValidationError) as exc_info:
            schema.validate(data)
        
        error = exc_info.value
        assert "name" in error.details
        assert "age" in error.details
    
    def test_schema_with_missing_fields(self):
        """Test schema validation with missing fields"""
        schema = ValidationSchema()
        schema.add_field("required_field", TextValidator(required=True))
        schema.add_field("optional_field", TextValidator(required=False))
        
        # Missing required field
        data = {"optional_field": "present"}
        
        with pytest.raises(ValidationError) as exc_info:
            schema.validate(data)
        assert "required_field" in str(exc_info.value)


class TestCommonSchemas:
    """Test pre-built common schemas"""
    
    def test_text_message_schema(self):
        """Test text message schema"""
        schema = CommonSchemas.text_message(min_length=5, max_length=100)
        
        # Valid message
        data = {"text": "Hello world", "user": {"id": 12345}}
        result = schema.validate(data)
        assert result["text"] == "Hello world"
        assert result["user"]["id"] == 12345
        
        # Invalid message
        data = {"text": "Hi", "user": {"id": 12345}}  # Too short
        with pytest.raises(ValidationError):
            schema.validate(data)
    
    def test_admin_command_schema(self):
        """Test admin command schema"""
        schema = CommonSchemas.admin_command()
        
        # Valid admin data
        data = {"user": {"id": 12345}, "args": ["arg1", "arg2"]}
        result = schema.validate(data)
        assert result["user"]["id"] == 12345
        assert result["args"] == ["arg1", "arg2"]
    
    def test_audio_message_schema(self):
        """Test audio message schema"""
        schema = CommonSchemas.audio_message(max_duration=300)
        
        # Mock valid audio data
        mock_audio = Mock()
        mock_audio.file_size = 1024 * 1024
        mock_audio.duration = 120
        
        data = {"audio": mock_audio, "user": {"id": 12345}}
        result = schema.validate(data)
        assert result["audio"] == mock_audio
        assert result["user"]["id"] == 12345


class TestValidationDecorator:
    """Test the validation decorator"""
    
    @pytest.mark.asyncio
    async def test_validation_decorator_success(self, mock_telegram_update, mock_telegram_context):
        """Test validation decorator with valid data"""
        schema = CommonSchemas.text_message(min_length=1, max_length=100)
        
        @validate_input(schema)
        async def test_handler(update, context, validated_data=None):
            return validated_data
        
        # Mock valid update
        mock_telegram_update.message.text = "Valid message"
        
        result = await test_handler(mock_telegram_update, mock_telegram_context)
        
        assert result is not None
        assert result["text"] == "Valid message"
        assert result["user"]["id"] == 12345
    
    @pytest.mark.asyncio
    async def test_validation_decorator_failure(self, mock_telegram_update, mock_telegram_context):
        """Test validation decorator with invalid data"""
        schema = CommonSchemas.text_message(min_length=10, max_length=100)
        
        @validate_input(schema)
        async def test_handler(update, context, validated_data=None):
            return validated_data
        
        # Mock invalid update (message too short)
        mock_telegram_update.message.text = "Hi"
        
        # Should handle validation error gracefully
        result = await test_handler(mock_telegram_update, mock_telegram_context)
        
        # Should have sent error message
        mock_telegram_update.message.reply_text.assert_called_once()
        error_message = mock_telegram_update.message.reply_text.call_args[0][0]
        assert "validation error" in error_message.lower() or "invalid" in error_message.lower()
    
    @pytest.mark.asyncio
    async def test_validation_decorator_with_function_args(self, mock_telegram_update, mock_telegram_context):
        """Test validation decorator preserves function arguments"""
        schema = CommonSchemas.text_message(min_length=1, max_length=100)
        
        @validate_input(schema)
        async def test_handler(update, context, extra_arg=None, validated_data=None):
            return {"validated": validated_data, "extra": extra_arg}
        
        mock_telegram_update.message.text = "Valid message"
        
        result = await test_handler(
            mock_telegram_update, 
            mock_telegram_context, 
            extra_arg="test_value"
        )
        
        assert result["validated"]["text"] == "Valid message"
        assert result["extra"] == "test_value"


class TestValidationErrorHandling:
    """Test validation error handling and reporting"""
    
    def test_validation_error_with_details(self):
        """Test validation error with detailed field errors"""
        details = {
            "name": "Name is required",
            "age": "Age must be positive"
        }
        
        error = ValidationError("Multiple validation errors", details=details)
        
        assert error.details == details
        assert "name" in str(error)
        assert "age" in str(error)
    
    def test_validation_error_without_details(self):
        """Test validation error without detailed field errors"""
        error = ValidationError("Simple validation error")
        
        assert error.details is None
        assert "Simple validation error" in str(error)
    
    def test_validation_error_formatting(self):
        """Test validation error message formatting"""
        details = {
            "field1": "Error message 1",
            "field2": "Error message 2"
        }
        
        error = ValidationError("Validation failed", details=details)
        error_str = str(error)
        
        # Should contain main message and field details
        assert "Validation failed" in error_str
        assert "field1" in error_str
        assert "field2" in error_str
        assert "Error message 1" in error_str
        assert "Error message 2" in error_str


class TestValidationEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_validator_with_none_values(self):
        """Test validators handling None values"""
        # Required validator
        required_validator = TextValidator(required=True)
        with pytest.raises(ValidationError):
            required_validator.validate(None)
        
        # Optional validator
        optional_validator = TextValidator(required=False)
        result = optional_validator.validate(None)
        assert result is None
    
    def test_validator_with_empty_string(self):
        """Test validators handling empty strings"""
        validator = TextValidator(min_length=5, required=False)
        
        # Empty string should be allowed if not required
        result = validator.validate("")
        assert result == ""
        
        # But should fail min_length if not empty
        with pytest.raises(ValidationError):
            validator.validate("Hi")  # Too short
    
    def test_number_validator_edge_values(self):
        """Test number validator with edge values"""
        validator = NumberValidator(min_value=0, max_value=100)
        
        # Boundary values
        assert validator.validate(0) == 0
        assert validator.validate(100) == 100
        
        # Float precision
        assert validator.validate(99.999) == 99.999
        assert validator.validate(0.001) == 0.001
    
    def test_schema_with_nested_data(self):
        """Test schema validation with nested data structures"""
        schema = ValidationSchema()
        # This is a simple test - real nested validation would be more complex
        schema.add_field("user_id", NumberValidator(min_value=1, required=True))
        
        data = {"user_id": 12345, "extra": {"nested": "data"}}
        result = schema.validate(data)
        
        assert result["user_id"] == 12345
        # Extra fields should be preserved
        assert result["extra"]["nested"] == "data"