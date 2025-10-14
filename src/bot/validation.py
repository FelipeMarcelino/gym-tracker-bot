"""Input validation and sanitization utilities for bot handlers"""

import html
import re
from typing import Optional, Dict, Any

from config.settings import settings


class InputValidator:
    """Validates and sanitizes user inputs in bot handlers"""
    
    # Maximum lengths come from settings
    
    # Regex patterns
    SAFE_TEXT_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?áéíóúâêîôûàèìòùãõçÁÉÍÓÚÂÊÎÔÛÀÈÌÒÙÃÕÇ]*$')
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Sanitiza texto removendo caracteres perigosos
        
        Args:
            text: Texto a ser sanitizado
            
        Returns:
            Texto sanitizado
        """
        if not text:
            return ""
            
        # Remove caracteres de controle
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Escape HTML entities
        text = html.escape(text, quote=False)
        
        # Remover múltiplos espaços
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def validate_text_input(text: str, max_length: int = None) -> Dict[str, Any]:
        """Valida entrada de texto do usuário
        
        Args:
            text: Texto a ser validado
            max_length: Comprimento máximo (usa default se None)
            
        Returns:
            Dict com is_valid, sanitized_text, e error_message
        """
        if not text:
            return {
                "is_valid": False,
                "sanitized_text": "",
                "error_message": "Texto não pode estar vazio"
            }
        
        # Usar limite padrão se não especificado
        if max_length is None:
            max_length = settings.MAX_TEXT_LENGTH
            
        # Verificar comprimento
        if len(text) > max_length:
            return {
                "is_valid": False,
                "sanitized_text": "",
                "error_message": f"Texto muito longo (máximo {max_length} caracteres)"
            }
        
        # Sanitizar
        sanitized = InputValidator.sanitize_text(text)
        
        return {
            "is_valid": True,
            "sanitized_text": sanitized,
            "error_message": None
        }
    
    @staticmethod
    def validate_user_name(name: str) -> Dict[str, Any]:
        """Valida nome de usuário
        
        Args:
            name: Nome a ser validado
            
        Returns:
            Dict com is_valid, sanitized_name, e error_message
        """
        if not name:
            return {
                "is_valid": False,
                "sanitized_name": "",
                "error_message": "Nome não pode estar vazio"
            }
            
        # Verificar comprimento
        if len(name) > settings.MAX_NAME_LENGTH:
            return {
                "is_valid": False,
                "sanitized_name": "",
                "error_message": f"Nome muito longo (máximo {settings.MAX_NAME_LENGTH} caracteres)"
            }
        
        # Sanitizar
        sanitized = InputValidator.sanitize_text(name)
        
        # Verificar se contém apenas caracteres seguros
        if not InputValidator.SAFE_TEXT_PATTERN.match(sanitized):
            return {
                "is_valid": False,
                "sanitized_name": "",
                "error_message": "Nome contém caracteres não permitidos"
            }
        
        return {
            "is_valid": True,
            "sanitized_name": sanitized,
            "error_message": None
        }
    
    @staticmethod
    def validate_user_id(user_id: Any) -> Dict[str, Any]:
        """Valida ID de usuário do Telegram
        
        Args:
            user_id: ID a ser validado
            
        Returns:
            Dict com is_valid, validated_id, e error_message
        """
        try:
            # Converter para int para validar
            int_id = int(user_id)
            
            # IDs do Telegram são positivos
            if int_id <= 0:
                return {
                    "is_valid": False,
                    "validated_id": None,
                    "error_message": "ID de usuário deve ser positivo"
                }
            
            # IDs do Telegram são menores que 2^53
            if int_id >= 2**53:
                return {
                    "is_valid": False,
                    "validated_id": None,
                    "error_message": "ID de usuário muito grande"
                }
            
            return {
                "is_valid": True,
                "validated_id": str(int_id),
                "error_message": None
            }
            
        except (ValueError, TypeError):
            return {
                "is_valid": False,
                "validated_id": None,
                "error_message": "ID de usuário deve ser um número"
            }
    
    @staticmethod
    def validate_audio_file(voice) -> Dict[str, Any]:
        """Valida arquivo de áudio do Telegram
        
        Args:
            voice: Objeto voice do Telegram
            
        Returns:
            Dict com is_valid, file_info, e error_message
        """
        if not voice:
            return {
                "is_valid": False,
                "file_info": None,
                "error_message": "Arquivo de áudio não encontrado"
            }
        
        # Verificar duração
        if voice.duration > settings.MAX_AUDIO_DURATION_SECONDS:
            return {
                "is_valid": False,
                "file_info": None,
                "error_message": f"Áudio muito longo (máximo {settings.MAX_AUDIO_DURATION_SECONDS//60} minutos)"
            }
        
        # Verificar tamanho
        max_size = settings.MAX_VOICE_FILE_SIZE_MB * 1024 * 1024
        if voice.file_size > max_size:
            return {
                "is_valid": False,
                "file_info": None,
                "error_message": f"Arquivo muito grande (máximo {settings.MAX_VOICE_FILE_SIZE_MB}MB)"
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


def validate_and_sanitize_user_input(update) -> Dict[str, Any]:
    """Valida e sanitiza todos os inputs de um update do Telegram
    
    Args:
        update: Update object do Telegram
        
    Returns:
        Dict com dados validados e sanitizados
    """
    result = {
        "is_valid": True,
        "errors": [],
        "user": {},
        "message": {}
    }
    
    # Validar dados do usuário
    if update.effective_user:
        user = update.effective_user
        
        # Validar user ID
        user_id_validation = InputValidator.validate_user_id(user.id)
        if not user_id_validation["is_valid"]:
            result["is_valid"] = False
            result["errors"].append(f"User ID: {user_id_validation['error_message']}")
        else:
            result["user"]["id"] = user_id_validation["validated_id"]
        
        # Validar nome
        if user.first_name:
            name_validation = InputValidator.validate_user_name(user.first_name)
            if not name_validation["is_valid"]:
                result["errors"].append(f"Nome: {name_validation['error_message']}")
            else:
                result["user"]["first_name"] = name_validation["sanitized_name"]
        
        # Validar username (opcional)
        if user.username:
            username_validation = InputValidator.validate_user_name(user.username)
            if username_validation["is_valid"]:
                result["user"]["username"] = username_validation["sanitized_name"]
    
    # Validar dados da mensagem
    if update.message:
        message = update.message
        
        # Validar texto da mensagem
        if message.text:
            text_validation = InputValidator.validate_text_input(message.text)
            if not text_validation["is_valid"]:
                result["is_valid"] = False
                result["errors"].append(f"Texto: {text_validation['error_message']}")
            else:
                result["message"]["text"] = text_validation["sanitized_text"]
        
        # Validar arquivo de áudio
        if message.voice:
            audio_validation = InputValidator.validate_audio_file(message.voice)
            if not audio_validation["is_valid"]:
                result["is_valid"] = False
                result["errors"].append(f"Áudio: {audio_validation['error_message']}")
            else:
                result["message"]["voice"] = audio_validation["file_info"]
    
    return result