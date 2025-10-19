"""Metrics collection middleware for performance monitoring"""

import time
import functools
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

from config.logging_config import get_logger
from services.async_health_service import health_service

logger = get_logger(__name__)


def track_command_metrics(command_name: str = None):
    """Decorator to track command execution metrics
    
    Args:
        command_name: Optional name for the command (auto-detected if not provided)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
            # Determine command name
            cmd_name = command_name or getattr(func, "__name__", "unknown_command")
            
            # Start timing
            start_time = time.time()
            is_error = False
            
            try:
                # Execute the command
                result = await func(update, context, *args, **kwargs)
                return result
                
            except Exception as e:
                is_error = True
                logger.exception(f"Error in command {cmd_name}")
                raise
                
            finally:
                # Calculate response time
                response_time_ms = (time.time() - start_time) * 1000
                
                # Record metrics
                health_service.record_command(response_time_ms, is_error)
                
                # Log performance metrics
                logger.debug(f"Command {cmd_name} completed in {response_time_ms:.2f}ms (error: {is_error})")
        
        return wrapper
    return decorator


def track_audio_metrics(operation_name: str = None):
    """Decorator to track audio processing metrics
    
    Args:
        operation_name: Optional name for the operation (auto-detected if not provided)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
            # Determine operation name
            op_name = operation_name or getattr(func, "__name__", "unknown_audio_operation")
            
            # Start timing
            start_time = time.time()
            is_error = False
            
            try:
                # Execute the audio processing
                result = await func(update, context, *args, **kwargs)
                return result
                
            except Exception as e:
                is_error = True
                logger.exception(f"Error in audio operation {op_name}")
                raise
                
            finally:
                # Calculate processing time
                processing_time_ms = (time.time() - start_time) * 1000
                
                # Record metrics
                health_service.record_audio_processing(processing_time_ms, is_error)
                
                # Log performance metrics
                logger.debug(f"Audio operation {op_name} completed in {processing_time_ms:.2f}ms (error: {is_error})")
        
        return wrapper
    return decorator


