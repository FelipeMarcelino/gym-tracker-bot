"""Fixed unit tests for validation middleware that match actual APIs"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from bot.validation_middleware import (
    TextValidator, NumberValidator, AudioValidator,
    ValidationSchema, ValidationMiddleware, validate_input
)
from services.exceptions import ValidationError


class TestValidators:
    """Test individual validator classes with correct APIs"""
    
    def test_text_validator_valid(self):
        """Test text validator with valid input"""
        validator = TextValidator(min_length=5, max_length=20, allow_empty=False)
        
        # Valid text
        result = validator.validate("Hello world")
        assert result["is_valid"] is True
        assert result["value"] == "Hello world"
        assert result["error"] is None
        
        # Edge cases
        result = validator.validate("12345")  # Exactly min length
        assert result["is_valid"] is True
        assert result["value"] == "12345"
    
    def test_text_validator_invalid(self):
        """Test text validator with invalid input"""
        validator = TextValidator(min_length=5, max_length=20, allow_empty=False)
        
        # Too short
        result = validator.validate("Hi")
        assert result["is_valid"] is False
        assert "too short" in result["error"]
        
        # Too long
        result = validator.validate("A" * 25)
        assert result["is_valid"] is False
        assert "too long" in result["error"]
        
        # Empty when not allowed
        result = validator.validate("")
        assert result["is_valid"] is False
        assert "cannot be empty" in result["error"]
    
    def test_text_validator_optional(self):
        """Test text validator with optional field"""
        validator = TextValidator(min_length=5, max_length=20, allow_empty=True)
        
        # Empty should be allowed
        result = validator.validate("")
        assert result["is_valid"] is True
        assert result["value"] == ""
    
    def test_number_validator_valid(self):
        """Test number validator with valid input"""
        validator = NumberValidator(min_value=0, max_value=100)
        
        # Valid numbers
        result = validator.validate(50)
        assert result["is_valid"] is True
        assert result["value"] == 50
        
        result = validator.validate(0)  # Min boundary
        assert result["is_valid"] is True
        assert result["value"] == 0
        
        result = validator.validate(100)  # Max boundary
        assert result["is_valid"] is True
        assert result["value"] == 100
        
        # String numbers
        result = validator.validate("50")
        assert result["is_valid"] is True
        assert result["value"] == 50
    
    def test_number_validator_invalid(self):
        """Test number validator with invalid input"""
        validator = NumberValidator(min_value=0, max_value=100)
        
        # Out of range
        result = validator.validate(-1)
        assert result["is_valid"] is False
        assert "below minimum" in result["error"]
        
        result = validator.validate(101)
        assert result["is_valid"] is False
        assert "above maximum" in result["error"]
        
        # Invalid string
        result = validator.validate("not a number")
        assert result["is_valid"] is False
        assert "valid number" in result["error"]
    
    def test_audio_validator_valid(self):
        """Test audio validator with valid input"""
        validator = AudioValidator(max_duration=300)
        
        # Mock valid audio
        mock_audio = Mock()
        mock_audio.file_size = 1024 * 1024  # 1MB
        mock_audio.duration = 120  # 2 minutes
        
        result = validator.validate(mock_audio)
        assert result["is_valid"] is True
        assert result["value"] == mock_audio
    
    def test_audio_validator_invalid(self):
        """Test audio validator with invalid input"""
        validator = AudioValidator(max_duration=300, max_size_mb=10)  # Set smaller max size for test
        
        # Too large
        mock_large_audio = Mock()
        mock_large_audio.file_size = 25 * 1024 * 1024  # 25MB
        mock_large_audio.duration = 120
        
        result = validator.validate(mock_large_audio)
        assert result["is_valid"] is False
        assert "too large" in result["error"]


class TestValidationSchema:
    """Test validation schema functionality"""
    
    def test_schema_creation(self):
        """Test creating validation schemas"""
        schema = ValidationSchema(
            text_validator=TextValidator(min_length=1, max_length=100),
            user_required=True,
            message_required=True
        )
        
        assert schema.text_validator is not None
        assert schema.user_required is True
        assert schema.message_required is True
    
    @pytest.mark.asyncio
    async def test_schema_validation_success(self, mock_telegram_update, mock_telegram_context):
        """Test successful schema validation"""
        schema = ValidationSchema(
            text_validator=TextValidator(min_length=2, max_length=50, allow_empty=False),
            user_required=True,
            message_required=True
        )
        
        # Mock valid update
        mock_telegram_update.message.text = "Valid message"
        mock_telegram_update.effective_user.id = 12345
        
        result = await ValidationMiddleware.validate_update(mock_telegram_update, schema)
        
        assert result["is_valid"] is True
        assert "text" in result["data"]["message"]
        assert "user" in result["data"]
    
    @pytest.mark.asyncio
    async def test_schema_validation_failure(self, mock_telegram_update, mock_telegram_context):
        """Test schema validation with errors"""
        schema = ValidationSchema(
            text_validator=TextValidator(min_length=10, max_length=50, allow_empty=False),
            user_required=True,
            message_required=True
        )
        
        # Invalid data (message too short)
        mock_telegram_update.message.text = "Hi"
        mock_telegram_update.effective_user.id = 12345
        
        result = await ValidationMiddleware.validate_update(mock_telegram_update, schema)
        
        assert result["is_valid"] is False
        assert "errors" in result


class TestValidationMiddleware:
    """Test validation middleware functionality"""
    
    @pytest.mark.asyncio
    async def test_validate_update_success(self, mock_telegram_update):
        """Test successful update validation"""
        schema = ValidationSchema(
            text_validator=TextValidator(min_length=1, max_length=100, allow_empty=False),
            user_required=True
        )
        
        mock_telegram_update.message.text = "Test message"
        mock_telegram_update.effective_user.id = 12345
        
        result = await ValidationMiddleware.validate_update(mock_telegram_update, schema)
        
        assert result["is_valid"] is True
        assert result["data"]["message"]["text"] == "Test message"
        assert result["data"]["user"]["id"] == 12345
    
    @pytest.mark.asyncio
    async def test_validate_update_missing_user(self, mock_telegram_update):
        """Test validation with missing required user"""
        schema = ValidationSchema(user_required=True)
        
        mock_telegram_update.effective_user = None
        
        result = await ValidationMiddleware.validate_update(mock_telegram_update, schema)
        
        assert result["is_valid"] is False
        assert "errors" in result


class TestValidationDecorator:
    """Test the validation decorator"""
    
    @pytest.mark.asyncio
    async def test_validation_decorator_success(self, mock_telegram_update, mock_telegram_context):
        """Test validation decorator with valid data"""
        schema = ValidationSchema(
            text_validator=TextValidator(min_length=1, max_length=100, allow_empty=False)
        )
        
        @validate_input(schema)
        async def test_handler(update, context, validated_data=None):
            return validated_data
        
        # Mock valid update
        mock_telegram_update.message.text = "Valid message"
        mock_telegram_update.effective_user.id = 12345
        
        result = await test_handler(mock_telegram_update, mock_telegram_context)
        
        # Result should contain validated data
        assert result is not None
        assert "message" in result
        assert result["message"]["text"] == "Valid message"
    
    @pytest.mark.asyncio
    async def test_validation_decorator_failure(self, mock_telegram_update, mock_telegram_context):
        """Test validation decorator with invalid data"""
        schema = ValidationSchema(
            text_validator=TextValidator(min_length=10, max_length=100, allow_empty=False)
        )
        
        @validate_input(schema)
        async def test_handler(update, context, validated_data=None):
            return validated_data
        
        # Mock invalid update (message too short)
        mock_telegram_update.message.text = "Hi"
        mock_telegram_update.effective_user.id = 12345
        
        # Should handle validation error gracefully
        result = await test_handler(mock_telegram_update, mock_telegram_context)
        
        # Should have sent error message
        mock_telegram_update.message.reply_text.assert_called_once()


class TestValidationErrorHandling:
    """Test validation error handling and reporting"""
    
    def test_validation_error_creation(self):
        """Test validation error creation"""
        error = ValidationError("Test error", details={"field": "error message"})
        
        # ValidationError should contain the error code
        assert "Test error" in str(error)
    
    def test_validation_error_without_details(self):
        """Test validation error without detailed field errors"""
        error = ValidationError("Simple validation error")
        
        assert "Simple validation error" in str(error)


class TestValidationEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_validator_with_none_values(self):
        """Test validators handling None values"""
        # Non-empty validator
        validator = TextValidator(allow_empty=False)
        result = validator.validate(None)
        assert result["is_valid"] is False
        
        # Empty-allowed validator
        validator = TextValidator(allow_empty=True)
        result = validator.validate(None)
        assert result["is_valid"] is True
    
    def test_validator_with_empty_string(self):
        """Test validators handling empty strings"""
        validator = TextValidator(min_length=5, allow_empty=True)
        
        # Empty string should be allowed if allow_empty=True
        result = validator.validate("")
        assert result["is_valid"] is True
        assert result["value"] == ""
        
        # But should fail min_length if not empty
        result = validator.validate("Hi")  # Too short
        assert result["is_valid"] is False
        assert "too short" in result["error"]
    
    def test_number_validator_edge_values(self):
        """Test number validator with edge values"""
        validator = NumberValidator(min_value=0, max_value=100)
        
        # Boundary values
        result = validator.validate(0)
        assert result["is_valid"] is True
        assert result["value"] == 0
        
        result = validator.validate(100)
        assert result["is_valid"] is True
        assert result["value"] == 100
        
        # Float precision
        result = validator.validate(99.999)
        assert result["is_valid"] is True
        assert result["value"] == 99.999


class TestValidationIntegration:
    """Test validation integration with other components"""
    
    @pytest.mark.asyncio
    async def test_validation_with_real_telegram_data(self):
        """Test validation with realistic Telegram data structure"""
        # Create a realistic update mock
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "John"
        update.effective_user.username = "john_doe"
        
        update.message = Mock()
        update.message.text = "This is a valid message"
        update.message.chat = Mock()
        update.message.chat.id = 67890
        
        schema = ValidationSchema(
            text_validator=TextValidator(min_length=5, max_length=200, allow_empty=False),
            user_required=True,
            message_required=True
        )
        
        result = await ValidationMiddleware.validate_update(update, schema)
        
        assert result["is_valid"] is True
        assert result["data"]["message"]["text"] == "This is a valid message"
        assert result["data"]["user"]["id"] == 12345
        assert result["data"]["user"]["first_name"] == "John"
    
    def test_validation_performance(self):
        """Test validation performance with many operations"""
        validator = TextValidator(min_length=1, max_length=1000, allow_empty=False)
        
        # Test many validations
        import time
        start_time = time.time()
        
        for i in range(1000):
            result = validator.validate(f"Test message {i}")
            assert result["is_valid"] is True
        
        duration = time.time() - start_time
        
        # Should complete quickly (under 1 second for 1000 validations)
        assert duration < 1.0