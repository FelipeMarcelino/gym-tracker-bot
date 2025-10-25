"""Unit tests for validation_utils.py"""

import html
from unittest.mock import Mock, patch

import pytest

from bot.validation_utils import ValidationUtils, InputValidator
from config.settings import settings


class TestValidationUtils:
    """Test cases for ValidationUtils class"""

    def test_class_backward_compatibility(self):
        """Test that InputValidator is an alias for ValidationUtils"""
        assert InputValidator is ValidationUtils

    # Test sanitize_text method
    def test_sanitize_text_empty_string(self):
        """Test sanitizing empty string"""
        assert ValidationUtils.sanitize_text("") == ""
        
    def test_sanitize_text_none(self):
        """Test sanitizing None value"""
        assert ValidationUtils.sanitize_text(None) == ""
    
    def test_sanitize_text_normal_text(self):
        """Test sanitizing normal text"""
        text = "Hello World! This is a test."
        assert ValidationUtils.sanitize_text(text) == text
    
    def test_sanitize_text_with_multiple_spaces(self):
        """Test sanitizing text with multiple spaces"""
        text = "Hello    World!   Test"
        expected = "Hello World! Test"
        assert ValidationUtils.sanitize_text(text) == expected
    
    def test_sanitize_text_with_control_characters(self):
        """Test sanitizing text with control characters"""
        text = "Hello\x00World\x01Test\x1f"
        expected = "HelloWorldTest"
        assert ValidationUtils.sanitize_text(text) == expected
    
    def test_sanitize_text_with_allowed_control_chars(self):
        """Test that newline and tab are preserved"""
        text = "Hello\nWorld\tTest"
        expected = "Hello World Test"  # They get normalized to spaces
        assert ValidationUtils.sanitize_text(text) == expected
    
    def test_sanitize_text_with_html_entities(self):
        """Test sanitizing text with HTML entities"""
        text = "<script>alert('XSS')</script>"
        expected = html.escape(text, quote=False)
        assert ValidationUtils.sanitize_text(text) == expected
    
    def test_sanitize_text_with_special_chars(self):
        """Test sanitizing text with special characters"""
        text = "Test & < > \" '"
        expected = "Test &amp; &lt; &gt; \" '"
        assert ValidationUtils.sanitize_text(text) == expected
    
    def test_sanitize_text_with_unicode(self):
        """Test sanitizing text with unicode characters"""
        text = "Olá! Ça va? 你好 🌍"
        expected = "Olá! Ça va? 你好 🌍"
        assert ValidationUtils.sanitize_text(text) == expected
    
    def test_sanitize_text_with_portuguese_chars(self):
        """Test sanitizing text with Portuguese characters"""
        text = "áéíóúâêîôûàèìòùãõçÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ"
        assert ValidationUtils.sanitize_text(text) == text
    
    def test_sanitize_text_strip_whitespace(self):
        """Test that leading and trailing whitespace is stripped"""
        text = "  Hello World  "
        expected = "Hello World"
        assert ValidationUtils.sanitize_text(text) == expected
    
    def test_sanitize_text_complex_scenario(self):
        """Test complex sanitization scenario"""
        text = "  <b>Hello</b>\x00\nWorld!   Multiple   spaces\t\ttest  "
        expected = "&lt;b&gt;Hello&lt;/b&gt; World! Multiple spaces test"
        assert ValidationUtils.sanitize_text(text) == expected

    # Test validate_user_id method
    def test_validate_user_id_valid_numeric_string(self):
        """Test validating valid numeric string user ID"""
        result = ValidationUtils.validate_user_id("12345")
        assert result["is_valid"] is True
        assert result["validated_id"] == "12345"
        assert result["error_message"] is None
    
    def test_validate_user_id_valid_integer(self):
        """Test validating integer user ID (gets converted to string)"""
        result = ValidationUtils.validate_user_id(12345)
        assert result["is_valid"] is True
        assert result["validated_id"] == "12345"
        assert result["error_message"] is None
    
    def test_validate_user_id_invalid_non_numeric(self):
        """Test validating non-numeric user ID"""
        result = ValidationUtils.validate_user_id("abc123")
        assert result["is_valid"] is False
        assert result["validated_id"] is None
        assert result["error_message"] == "User ID must be a sequence of digits"
    
    def test_validate_user_id_invalid_special_chars(self):
        """Test validating user ID with special characters"""
        result = ValidationUtils.validate_user_id("123!45")
        assert result["is_valid"] is False
        assert result["validated_id"] is None
        assert result["error_message"] == "User ID must be a sequence of digits"
    
    def test_validate_user_id_invalid_too_long(self):
        """Test validating user ID that is too long"""
        long_id = "1" * 21  # 21 digits
        result = ValidationUtils.validate_user_id(long_id)
        assert result["is_valid"] is False
        assert result["validated_id"] is None
        assert result["error_message"] == "User ID is too long"
    
    def test_validate_user_id_valid_max_length(self):
        """Test validating user ID at maximum length"""
        max_id = "1" * 20  # 20 digits
        result = ValidationUtils.validate_user_id(max_id)
        assert result["is_valid"] is True
        assert result["validated_id"] == max_id
        assert result["error_message"] is None
    
    def test_validate_user_id_empty_string(self):
        """Test validating empty string user ID"""
        result = ValidationUtils.validate_user_id("")
        assert result["is_valid"] is False
        assert result["validated_id"] is None
        assert result["error_message"] == "User ID must be a sequence of digits"
    
    def test_validate_user_id_negative_number(self):
        """Test validating negative number user ID"""
        result = ValidationUtils.validate_user_id(-12345)
        assert result["is_valid"] is False
        assert result["validated_id"] is None
        assert result["error_message"] == "User ID must be a sequence of digits"
    
    def test_validate_user_id_float(self):
        """Test validating float user ID"""
        result = ValidationUtils.validate_user_id(123.45)
        assert result["is_valid"] is False
        assert result["validated_id"] is None
        assert result["error_message"] == "User ID must be a sequence of digits"
    
    def test_validate_user_id_zero(self):
        """Test validating zero as user ID"""
        result = ValidationUtils.validate_user_id(0)
        assert result["is_valid"] is True
        assert result["validated_id"] == "0"
        assert result["error_message"] is None

    # Test validate_audio_file method
    def test_validate_audio_file_valid(self):
        """Test validating valid audio file"""
        voice = Mock()
        voice.duration = 60  # 1 minute
        voice.file_size = 1024 * 1024  # 1 MB
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is True
        assert result["file_info"]["duration"] == 60
        assert result["file_info"]["file_size"] == 1024 * 1024
        assert result["file_info"]["file_id"] == "test_file_id"
        assert result["error_message"] is None
    
    def test_validate_audio_file_none(self):
        """Test validating None audio file"""
        result = ValidationUtils.validate_audio_file(None)
        assert result["is_valid"] is False
        assert result["file_info"] is None
        assert result["error_message"] == "Audio file not found"
    
    def test_validate_audio_file_too_long(self):
        """Test validating audio file that is too long"""
        voice = Mock()
        voice.duration = settings.MAX_AUDIO_DURATION_SECONDS + 1
        voice.file_size = 1024 * 1024
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is False
        assert result["file_info"] is None
        assert result["error_message"] == f"Audio too long (maximum {settings.MAX_AUDIO_DURATION_SECONDS//60} minutes)"
    
    def test_validate_audio_file_max_duration(self):
        """Test validating audio file at maximum duration"""
        voice = Mock()
        voice.duration = settings.MAX_AUDIO_DURATION_SECONDS
        voice.file_size = 1024 * 1024
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is True
        assert result["error_message"] is None
    
    def test_validate_audio_file_too_large(self):
        """Test validating audio file that is too large"""
        voice = Mock()
        voice.duration = 60
        voice.file_size = (settings.MAX_VOICE_FILE_SIZE_MB * 1024 * 1024) + 1
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is False
        assert result["file_info"] is None
        assert result["error_message"] == f"File too large (maximum {settings.MAX_VOICE_FILE_SIZE_MB}MB)"
    
    def test_validate_audio_file_max_size(self):
        """Test validating audio file at maximum size"""
        voice = Mock()
        voice.duration = 60
        voice.file_size = settings.MAX_VOICE_FILE_SIZE_MB * 1024 * 1024
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is True
        assert result["error_message"] is None
    
    def test_validate_audio_file_zero_duration(self):
        """Test validating audio file with zero duration"""
        voice = Mock()
        voice.duration = 0
        voice.file_size = 1024
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is True
        assert result["file_info"]["duration"] == 0
        assert result["error_message"] is None
    
    def test_validate_audio_file_zero_size(self):
        """Test validating audio file with zero size"""
        voice = Mock()
        voice.duration = 60
        voice.file_size = 0
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is True
        assert result["file_info"]["file_size"] == 0
        assert result["error_message"] is None
    
    @patch('config.settings.settings.MAX_AUDIO_DURATION_SECONDS', 120)
    def test_validate_audio_file_custom_duration_limit(self):
        """Test validation with custom duration limit"""
        voice = Mock()
        voice.duration = 150  # 2.5 minutes
        voice.file_size = 1024 * 1024
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is False
        assert result["error_message"] == "Audio too long (maximum 2 minutes)"
    
    @patch('config.settings.settings.MAX_VOICE_FILE_SIZE_MB', 5)
    def test_validate_audio_file_custom_size_limit(self):
        """Test validation with custom size limit"""
        voice = Mock()
        voice.duration = 60
        voice.file_size = 6 * 1024 * 1024  # 6 MB
        voice.file_id = "test_file_id"
        
        result = ValidationUtils.validate_audio_file(voice)
        assert result["is_valid"] is False
        assert result["error_message"] == "File too large (maximum 5MB)"

    # Test SAFE_TEXT_PATTERN regex
    def test_safe_text_pattern_valid(self):
        """Test SAFE_TEXT_PATTERN with valid text"""
        pattern = ValidationUtils.SAFE_TEXT_PATTERN
        
        valid_texts = [
            "Hello World",
            "Test123",
            "test-with-dash",
            "test_with_underscore",
            "Test with spaces",
            "Test.,!?",
            "áéíóúâêîôûàèìòùãõç",
            "ÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ",
            ""
        ]
        
        for text in valid_texts:
            assert pattern.match(text) is not None, f"'{text}' should be valid"
    
    def test_safe_text_pattern_invalid(self):
        """Test SAFE_TEXT_PATTERN with invalid text"""
        pattern = ValidationUtils.SAFE_TEXT_PATTERN
        
        invalid_texts = [
            "<script>",
            "test@email",
            "test#hash",
            "test$dollar",
            "test%percent",
            "test&ampersand",
            "test*asterisk",
            "test+plus",
            "test=equals",
            "test[bracket",
            "test{brace",
            "test|pipe",
            "test\\backslash",
            "test/slash",
            "test:colon",
            "test;semicolon",
            'test"quote',
            "test'apostrophe",
            "test<less",
            "test>greater"
        ]
        
        for text in invalid_texts:
            assert pattern.match(text) is None, f"'{text}' should be invalid"

    def test_validate_audio_file_missing_attributes(self):
        """Test validating audio file with missing attributes"""
        # Test with object missing duration
        voice = Mock(spec=['file_size', 'file_id'])
        voice.file_size = 1024
        voice.file_id = "test_file_id"
        
        with pytest.raises(AttributeError):
            ValidationUtils.validate_audio_file(voice)
        
        # Test with object missing file_size
        voice = Mock(spec=['duration', 'file_id'])
        voice.duration = 60
        voice.file_id = "test_file_id"
        
        with pytest.raises(AttributeError):
            ValidationUtils.validate_audio_file(voice)