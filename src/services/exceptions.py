"""Custom exceptions for gym tracker services"""


class GymTrackerError(Exception):
    """Base exception for gym tracker application"""
    
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class AudioProcessingError(GymTrackerError):
    """Raised when audio transcription fails"""
    pass


class LLMParsingError(GymTrackerError):
    """Raised when LLM parsing fails"""
    pass


class DatabaseError(GymTrackerError):
    """Raised when database operations fail"""
    pass


class SessionError(GymTrackerError):
    """Raised when session management fails"""
    pass


class ValidationError(GymTrackerError):
    """Raised when input validation fails"""
    pass


class ServiceUnavailableError(GymTrackerError):
    """Raised when external services are unavailable"""
    pass