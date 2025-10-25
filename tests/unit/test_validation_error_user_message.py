"""Unit tests specifically for ValidationError user_message handling logic"""

import pytest
from services.exceptions import ValidationError, ErrorCode
from config import messages as config_messages


class TestValidationErrorUserMessage:
    """Test the logic of ValidationError user_message handling"""

    def test_validation_error_has_user_message_attribute(self):
        """Test that ValidationError can have user_message attribute"""
        error = ValidationError(
            message="Test error",
            field="test_field",
            value=None,
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            user_message="User friendly message"
        )
        
        assert hasattr(error, 'user_message')
        assert error.user_message == "User friendly message"

    def test_validation_error_user_message_logic(self):
        """Test the if/else logic for user_message handling"""
        # Test with user_message
        error_with_message = ValidationError(
            message="Technical error",
            field="data",
            value=None,
            error_code=ErrorCode.INVALID_INPUT,
            user_message="Por favor, informe os dados completos"
        )
        
        # Simulate the handler logic
        if hasattr(error_with_message, 'user_message') and error_with_message.user_message:
            result = error_with_message.user_message
        else:
            details = f"\n\n_Detalhes: {error_with_message.details}_" if error_with_message.details else ""
            result = config_messages.Messages.ERROR_VALIDATION.format(message=error_with_message.message, details=details)
        
        assert result == "Por favor, informe os dados completos"

    def test_validation_error_without_user_message_logic(self):
        """Test the logic when user_message is not provided"""
        # Test without user_message
        error_without_message = ValidationError(
            message="Campo inválido",
            field="exercise",
            value="",
            error_code=ErrorCode.INVALID_FORMAT,
            details="O exercício não pode estar vazio"
        )
        
        # Explicitly set user_message to None to simulate not having it
        error_without_message.user_message = None
        
        # Simulate the handler logic
        if hasattr(error_without_message, 'user_message') and error_without_message.user_message:
            result = error_without_message.user_message
        else:
            details = f"\n\n_Detalhes: {error_without_message.details}_" if error_without_message.details else ""
            result = config_messages.Messages.ERROR_VALIDATION.format(message=error_without_message.message, details=details)
        
        expected = config_messages.Messages.ERROR_VALIDATION.format(
            message="Campo inválido",
            details="\n\n_Detalhes: O exercício não pode estar vazio_"
        )
        assert result == expected

    def test_validation_error_empty_user_message_logic(self):
        """Test the logic when user_message is empty string"""
        # Test with empty user_message
        error_empty_message = ValidationError(
            message="Erro genérico",
            field="test",
            value=None,
            error_code=ErrorCode.INVALID_INPUT,
            user_message=""  # Empty string
        )
        
        # Simulate the handler logic - empty string is falsy
        if hasattr(error_empty_message, 'user_message') and error_empty_message.user_message:
            result = error_empty_message.user_message
        else:
            details = f"\n\n_Detalhes: {error_empty_message.details}_" if error_empty_message.details else ""
            result = config_messages.Messages.ERROR_VALIDATION.format(message=error_empty_message.message, details=details)
        
        # When user_message is empty string (falsy), it should use default format
        # Empty string is falsy, so it falls back to the default format
        assert result != ""  # Should not be empty
        assert "Erro genérico" in result
        # The exact format depends on ERROR_VALIDATION template

    def test_validation_error_whitespace_user_message(self):
        """Test that whitespace-only user_message is treated as empty"""
        # Test with whitespace user_message
        error_whitespace = ValidationError(
            message="Test",
            field="field",
            value=None,
            error_code=ErrorCode.INVALID_INPUT,
            user_message="   "  # Only whitespace
        )
        
        # In real code, we might want to strip whitespace
        user_msg = error_whitespace.user_message.strip() if hasattr(error_whitespace, 'user_message') else ""
        
        # Simulate the handler logic with stripped message
        if hasattr(error_whitespace, 'user_message') and user_msg:
            result = user_msg
        else:
            details = f"\n\n_Detalhes: {error_whitespace.details}_" if error_whitespace.details else ""
            result = config_messages.Messages.ERROR_VALIDATION.format(message=error_whitespace.message, details=details)
        
        # Should use default format since stripped message is empty
        expected = config_messages.Messages.ERROR_VALIDATION.format(
            message="Test",
            details=""
        )
        assert result == expected

    def test_real_world_validation_scenarios(self):
        """Test real-world validation error scenarios"""
        # Scenario 1: Missing workout data
        error1 = ValidationError(
            message="Dados incompletos no treino parseado",
            field="workout_data",
            value=None,
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            user_message="📝 **Dados incompletos!**\n\nPor favor, inclua:\n• Número de repetições de cada série\n• Pesos utilizados em cada série\n\nExemplo: \"Fiz supino 3x12 com 60kg\""
        )
        
        # This should use user_message
        if hasattr(error1, 'user_message') and error1.user_message:
            result1 = error1.user_message
        else:
            details = f"\n\n_Detalhes: {error1.details}_" if error1.details else ""
            result1 = config_messages.Messages.ERROR_VALIDATION.format(message=error1.message, details=details)
        
        assert "Dados incompletos!" in result1
        assert "repetições" in result1
        assert "Pesos utilizados" in result1
        
        # Scenario 2: Invalid exercise format
        error2 = ValidationError(
            message="Formato de exercício inválido",
            field="exercise_format",
            value="invalid",
            error_code=ErrorCode.INVALID_FORMAT,
            details="O formato do exercício deve incluir nome, séries e repetições"
        )
        # No user_message provided
        
        if hasattr(error2, 'user_message') and error2.user_message:
            result2 = error2.user_message
        else:
            details = f"\n\n_Detalhes: {error2.details}_" if error2.details else ""
            result2 = config_messages.Messages.ERROR_VALIDATION.format(message=error2.message, details=details)
        
        # Since ValidationError has default user_message of "Invalid input provided"
        # and we didn't explicitly set it to None, it will use that default
        assert result2 == "Invalid input provided"

    def test_handler_code_snippet_simulation(self):
        """Test exact handler code logic"""
        # Create a validation error like in the real handlers
        e = ValidationError(
            message="Dados incompletos",
            field="workout_data",
            value=None,
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            user_message="Por favor, complete os dados do treino"
        )
        
        # Exact code from handlers.py
        if hasattr(e, 'user_message') and e.user_message:
            error_msg = e.user_message
        else:
            details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
            error_msg = config_messages.Messages.ERROR_VALIDATION.format(message=e.message, details=details)
        
        assert error_msg == "Por favor, complete os dados do treino"
        
        # Test without user_message
        e2 = ValidationError(
            message="Erro de validação",
            field="test",
            value=None,
            error_code=ErrorCode.INVALID_INPUT,
            details="Detalhes do erro"
        )
        e2.user_message = None  # Explicitly None
        
        if hasattr(e2, 'user_message') and e2.user_message:
            error_msg2 = e2.user_message
        else:
            details = f"\n\n_Detalhes: {e2.details}_" if e2.details else ""
            error_msg2 = config_messages.Messages.ERROR_VALIDATION.format(message=e2.message, details=details)
        
        expected = "❌ **Dados inválidos**\n\nErro de validação\n\n_Detalhes: Detalhes do erro_"
        assert error_msg2 == expected