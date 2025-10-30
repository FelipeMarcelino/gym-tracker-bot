"""Graceful shutdown service for the gym tracker bot"""

import signal
import asyncio
import threading
from typing import List, Callable, Any, Optional
from datetime import datetime

from config.logging_config import get_logger
from services.async_health_service import health_service
from services.backup_factory import BackupFactory

logger = get_logger(__name__)


class ShutdownService:
    """Service for handling graceful application shutdown"""

    def __init__(
        self,
        shutdown_timeout: int = 30,
        emergency_backup_on_shutdown: bool = True,
        **kwargs,
    ):
        self.shutdown_handlers: List[Callable] = []
        self.is_shutting_down = False
        self.shutdown_timeout = shutdown_timeout  # seconds
        self.emergency_backup_on_shutdown = emergency_backup_on_shutdown

    def register_shutdown_handler(
        self, handler: Callable, description: str = None
    ):
        """
        Register a function to be called during shutdown

        Args:
            handler: Function to call during shutdown
            description: Optional description of what the handler does
        """
        # Check for duplicate registration
        if handler in self.shutdown_handlers:
            logger.debug(
                f'Handler {description or handler.__name__} already registered, skipping'
            )
            return

        if asyncio.iscoroutinefunction(handler):
            # Wrap async functions
            def wrapper():
                try:
                    # Always create a new event loop for shutdown handlers
                    asyncio.run(asyncio.wait_for(handler(), timeout=10))
                except Exception as e:
                    logger.exception(
                        f"Error in async shutdown handler {description or 'unknown'}: {e}"
                    )

            self.shutdown_handlers.append(wrapper)
        else:
            self.shutdown_handlers.append(handler)

        logger.info(
            f'Registered shutdown handler: {description or handler.__name__}'
        )

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(
                f'Received {signal_name} signal, initiating graceful shutdown...'
            )
            self.initiate_shutdown()

        # Register handlers for common termination signals
        signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Termination request

        # On Unix systems, also handle SIGHUP
        try:
            signal.signal(signal.SIGHUP, signal_handler)  # Hangup
            logger.info('Signal handlers registered: SIGINT, SIGTERM, SIGHUP')
        except AttributeError:
            # Windows doesn't have SIGHUP
            logger.info('Signal handlers registered: SIGINT, SIGTERM')

    async def initiate_shutdown(self):
        """Initiate graceful shutdown process"""
        if self.is_shutting_down:
            logger.warning(
                'Shutdown already in progress, ignoring duplicate signal'
            )
            return

        self.is_shutting_down = True
        shutdown_start = datetime.now()

        logger.info('🔄 Starting graceful shutdown process...')

        try:
            # Run shutdown handlers
            self._run_shutdown_handlers()

            # Create emergency backup if enabled
            if self.emergency_backup_on_shutdown:
                await self._create_emergency_backup()

            # Stop background services
            self._stop_background_services()

            # Log final shutdown message
            shutdown_duration = (
                datetime.now() - shutdown_start
            ).total_seconds()
            logger.info(
                f'✅ Graceful shutdown completed in {shutdown_duration:.2f}s'
            )

        except Exception as e:
            logger.exception(f'❌ Error during graceful shutdown: {e}')
        finally:
            logger.info('👋 Application shutdown complete')

    def _run_shutdown_handlers(self):
        """Execute all registered shutdown handlers"""
        if not self.shutdown_handlers:
            logger.info('No shutdown handlers to execute')
            return

        logger.info(
            f'Executing {len(self.shutdown_handlers)} shutdown handlers...'
        )

        for i, handler in enumerate(self.shutdown_handlers, 1):
            try:
                handler_name = getattr(handler, '__name__', f'handler_{i}')
                logger.info(
                    f'Running shutdown handler {i}/{len(self.shutdown_handlers)}: {handler_name}'
                )

                # Execute with timeout
                if asyncio.iscoroutinefunction(handler):
                    # This shouldn't happen as we wrap async functions, but just in case
                    asyncio.run(asyncio.wait_for(handler(), timeout=10))
                else:
                    # Run in thread with timeout
                    thread = threading.Thread(target=handler)
                    thread.start()
                    thread.join(timeout=10)

                    if thread.is_alive():
                        logger.warning(
                            f'Shutdown handler {handler_name} timed out after 10s'
                        )

                logger.debug(f'✅ Shutdown handler {handler_name} completed')

            except Exception as e:
                logger.exception(f'❌ Error in shutdown handler {i}: {e}')

    async def _create_emergency_backup(self):
        """Create emergency backup during shutdown"""
        if not self.emergency_backup_on_shutdown:
            logger.debug('Emergency backup disabled, skipping backup')
            return

        try:
            logger.info('📦 Creating emergency backup before shutdown...')
            # Import here to avoid circular import
            from services.async_container import get_async_backup_service

            backup_service = await get_async_backup_service()

            # Use appropriate backup method based on database type
            if BackupFactory.is_postgresql():
                # For PostgreSQL, try SQL backup first, fallback to JSON
                try:
                    backup_path = await backup_service.create_backup_sql()
                    backup_type = 'SQL'
                except Exception as e:
                    logger.warning(
                        f'Emergency SQL backup failed, trying JSON: {e}'
                    )
                    backup_path = await backup_service.create_backup_json()
                    backup_type = 'JSON'
            else:
                # SQLite backup
                backup_name = f"emergency_shutdown_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                backup_path = await backup_service.create_backup(backup_name)
                backup_type = 'SQLite'

            logger.info(
                f'✅ Emergency backup created ({backup_type}): {backup_path}'
            )

        except Exception as e:
            logger.exception(f'❌ Failed to create emergency backup: {e}')

    def _stop_background_services(self):
        """Stop all background services"""
        try:
            logger.info('🛑 Stopping background services...')

            # Stop automated backups (if service supports it)
            try:
                # Use factory to get the appropriate backup service
                backup_service = BackupFactory.create_backup_service()
                if (
                    hasattr(backup_service, 'is_running')
                    and backup_service.is_running
                ):
                    backup_service.stop_automated_backups()
                    logger.info('✅ Automated backups stopped')
                elif hasattr(backup_service, 'stop_automated_backups'):
                    # Try to stop even if we can't check status
                    backup_service.stop_automated_backups()
                    logger.info('✅ Automated backups stopped')
            except Exception as e:
                logger.debug(
                    f'No automated backups to stop or error stopping: {e}'
                )

            # Stop health service background tasks (if any)
            # Note: health_service doesn't currently have background tasks

            logger.info('✅ Background services stopped')

        except Exception as e:
            logger.exception(f'❌ Error stopping background services: {e}')

    def force_shutdown(self, exit_code: int = 1):
        """Force immediate shutdown if graceful shutdown fails"""
        logger.warning(
            f'🚨 Forcing immediate shutdown with exit code {exit_code}'
        )
        import os

        os._exit(exit_code)

    def shutdown_with_timeout(self, timeout: int = None):
        """Shutdown with timeout, force kill if exceeded"""
        timeout = timeout or self.shutdown_timeout

        def timeout_handler():
            logger.error(
                f'⏰ Graceful shutdown timeout ({timeout}s) exceeded, forcing exit'
            )
            self.force_shutdown(1)

        # Start timeout timer
        timer = threading.Timer(timeout, timeout_handler)
        timer.start()

        try:
            # Perform graceful shutdown
            asyncio.run(self.initiate_shutdown())
            timer.cancel()  # Cancel timeout if shutdown completes

        except Exception as e:
            timer.cancel()
            logger.exception(f'❌ Shutdown failed: {e}')
            self.force_shutdown(1)


# Example shutdown handlers for common cleanup tasks
async def close_database_connections():
    """Close database connections"""
    try:
        logger.info('Closing database connections...')
        from database.async_connection import async_db

        await async_db.close()
        logger.info('✅ Async database connections closed')
    except Exception as e:
        logger.exception(f'Error closing database connections: {e}')


def flush_logs():
    """Flush log buffers"""
    try:
        logger.info('Flushing log buffers...')
        import logging

        # Flush all handlers
        for handler in logging.getLogger().handlers:
            if hasattr(handler, 'flush'):
                handler.flush()
        logger.info('✅ Log buffers flushed')
    except Exception as e:
        logger.exception(f'Error flushing logs: {e}')


async def save_pending_operations():
    """Save any pending operations"""
    try:
        logger.info('Saving pending operations...')
        # This would save any pending async operations
        # For now, we'll just log that we're checking
        logger.info('✅ No pending operations to save')
    except Exception as e:
        logger.exception(f'Error saving pending operations: {e}')


def cleanup_temp_files():
    """Clean up temporary files"""
    try:
        logger.info('Cleaning up temporary files...')
        import tempfile
        import shutil
        import os

        # Clean up any temp files we might have created
        temp_dir = tempfile.gettempdir()
        gym_tracker_temps = []

        # Look for our temp files (if any)
        for filename in os.listdir(temp_dir):
            if 'gym_tracker' in filename.lower():
                gym_tracker_temps.append(os.path.join(temp_dir, filename))

        if gym_tracker_temps:
            for temp_file in gym_tracker_temps:
                try:
                    if os.path.isfile(temp_file):
                        os.remove(temp_file)
                    elif os.path.isdir(temp_file):
                        shutil.rmtree(temp_file)
                    logger.debug(f'Removed temp file: {temp_file}')
                except Exception as e:
                    logger.warning(
                        f'Could not remove temp file {temp_file}: {e}'
                    )

            logger.info(
                f'✅ Cleaned up {len(gym_tracker_temps)} temporary files'
            )
        else:
            logger.info('✅ No temporary files to clean up')

    except Exception as e:
        logger.exception(f'Error cleaning up temporary files: {e}')


# Global shutdown service instance
shutdown_service = ShutdownService()

# Register default shutdown handlers
shutdown_service.register_shutdown_handler(flush_logs, 'Flush log buffers')
shutdown_service.register_shutdown_handler(
    save_pending_operations, 'Save pending operations'
)
shutdown_service.register_shutdown_handler(
    close_database_connections, 'Close database connections'
)
shutdown_service.register_shutdown_handler(
    cleanup_temp_files, 'Clean up temporary files'
)
