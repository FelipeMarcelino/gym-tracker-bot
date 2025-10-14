"""Metrics collection middleware for performance monitoring"""

import time
import functools
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes

from config.logging_config import get_logger
from services.health_service import health_service

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


class MetricsCollector:
    """Additional metrics collection for specific operations"""
    
    def __init__(self):
        self.operation_times = {}
        self.operation_counts = {}
        self.operation_errors = {}
    
    def start_operation(self, operation_name: str) -> str:
        """Start timing an operation"""
        operation_id = f"{operation_name}_{time.time()}"
        self.operation_times[operation_id] = time.time()
        return operation_id
    
    def end_operation(self, operation_id: str, is_error: bool = False):
        """End timing an operation"""
        if operation_id not in self.operation_times:
            return
        
        # Calculate duration
        duration = time.time() - self.operation_times[operation_id]
        
        # Extract operation name
        operation_name = "_".join(operation_id.split("_")[:-1])
        
        # Update counters
        self.operation_counts[operation_name] = self.operation_counts.get(operation_name, 0) + 1
        
        if is_error:
            self.operation_errors[operation_name] = self.operation_errors.get(operation_name, 0) + 1
        
        # Clean up
        del self.operation_times[operation_id]
        
        # Log metrics
        logger.debug(f"Operation {operation_name} completed in {duration*1000:.2f}ms (error: {is_error})")
    
    def get_operation_metrics(self) -> dict:
        """Get metrics for all tracked operations"""
        metrics = {}
        
        for operation_name, count in self.operation_counts.items():
            error_count = self.operation_errors.get(operation_name, 0)
            error_rate = (error_count / count * 100) if count > 0 else 0
            
            metrics[operation_name] = {
                "total_count": count,
                "error_count": error_count,
                "error_rate_percent": round(error_rate, 2),
                "success_rate_percent": round(100 - error_rate, 2)
            }
        
        return metrics


# Global metrics collector
metrics_collector = MetricsCollector()


def track_operation(operation_name: str):
    """Context manager for tracking custom operations"""
    class OperationTracker:
        def __init__(self, name: str):
            self.name = name
            self.operation_id = None
        
        def __enter__(self):
            self.operation_id = metrics_collector.start_operation(self.name)
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            is_error = exc_type is not None
            metrics_collector.end_operation(self.operation_id, is_error)
    
    return OperationTracker(operation_name)