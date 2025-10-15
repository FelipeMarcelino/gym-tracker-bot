"""Validation utility functions"""

import html
import re
from typing import Any, Dict

from config.settings import settings


class ValidationUtils:
    """Utility functions for input validation and sanitization"""
    
    # Regex patterns
    SAFE_TEXT_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?áéíóúâêîôûàèìòùãõçÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ]*$')
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitize text by removing dangerous characters
        
        Args:
            text: Text to be sanitized
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
            
        # Remove control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Escape HTML entities
        text = html.escape(text, quote=False)
        
        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def validate_user_id(user_id: Any) -> Dict[str, Any]:
        """Validate Telegram user ID
        
        Args:
            user_id: ID to be validated
            
        Returns:
            Dict with is_valid, validated_id, and error_message
        """
        try:
            # Convert to int for validation
            int_id = int(user_id)
            
            # Telegram IDs are positive
            if int_id <= 0:
                return {
                    "is_valid": False,
                    "validated_id": None,
                    "error_message": "User ID must be positive"
                }
            
            # Telegram IDs are less than 2^53
            if int_id >= 2**53:
                return {
                    "is_valid": False,
                    "validated_id": None,
                    "error_message": "User ID too large"
                }
            
            return {
                "is_valid": True,
                "validated_id": int_id,
                "error_message": None
            }
            
        except (ValueError, TypeError):
            return {
                "is_valid": False,
                "validated_id": None,
                "error_message": "User ID must be a number"
            }
    
    @staticmethod
    def validate_audio_file(voice) -> Dict[str, Any]:
        """Validate Telegram audio file
        
        Args:
            voice: Telegram voice object
            
        Returns:
            Dict with is_valid, file_info, and error_message
        """
        if not voice:
            return {
                "is_valid": False,
                "file_info": None,
                "error_message": "Audio file not found"
            }
        
        # Check duration
        if voice.duration > settings.MAX_AUDIO_DURATION_SECONDS:
            return {
                "is_valid": False,
                "file_info": None,
                "error_message": f"Audio too long (maximum {settings.MAX_AUDIO_DURATION_SECONDS//60} minutes)"
            }
        
        # Check file size
        max_size = settings.MAX_VOICE_FILE_SIZE_MB * 1024 * 1024
        if voice.file_size > max_size:
            return {
                "is_valid": False,
                "file_info": None,
                "error_message": f"File too large (maximum {settings.MAX_VOICE_FILE_SIZE_MB}MB)"
            }
        
        return {
            "is_valid": True,
            "file_info": {
                "duration": voice.duration,
                "file_size": voice.file_size,
                "file_id": voice.file_id
            },
            "error_message": None
        }


# Backward compatibility aliases
InputValidator = ValidationUtils