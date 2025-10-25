"""Rate limit cleanup service with automated scheduling"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


class RateLimitCleanupService:
    """Service for automated rate limit cleanup to prevent memory leaks"""

    def __init__(self):
        """Initialize rate limit cleanup service using settings"""
        self.cleanup_frequency_hours = settings.RATE_LIMIT_CLEANUP_FREQUENCY_HOURS
        self.max_inactive_seconds = settings.RATE_LIMIT_MAX_INACTIVE_SECONDS
        self.is_running = False
        self.scheduler_task = None
        self._stop_event = None

        logger.info("Rate limit cleanup service initialized")
        logger.info(f"Cleanup frequency: every {self.cleanup_frequency_hours} hour(s)")
        logger.info(f"Max inactive time: {self.max_inactive_seconds} seconds")

    def start_automated_cleanup(self):
        """Start automated cleanup scheduler"""
        if self.is_running:
            logger.warning("Automated rate limit cleanup already running")
            return

        self.is_running = True

        # Try to create asyncio task, but handle the case where no event loop exists
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self.scheduler_task = asyncio.create_task(self._run_async_scheduler())
            else:
                # Defer task creation until event loop is running
                self.scheduler_task = None
                logger.info("Event loop not running, cleanup scheduler will start when loop is available")
        except RuntimeError:
            # No event loop exists yet, defer task creation
            self.scheduler_task = None
            logger.info("No event loop exists, cleanup scheduler will start when loop is available")

        logger.info(f"Automated rate limit cleanup started: every {self.cleanup_frequency_hours} hour(s)")

    def stop_automated_cleanup(self):
        """Stop automated cleanup scheduler"""
        if not self.is_running:
            return

        self.is_running = False

        # Set the stop event to wake up the scheduler
        if hasattr(self, "_stop_event") and self._stop_event is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule the event to be set
                    loop.call_soon_threadsafe(self._stop_event.set)
            except RuntimeError:
                pass  # No event loop running

        if hasattr(self, "scheduler_task") and self.scheduler_task is not None:
            if not self.scheduler_task.cancelled():
                self.scheduler_task.cancel()
                logger.info("Cleanup scheduler task cancelled")

        logger.info("Automated rate limit cleanup stopped")

    async def stop_automated_cleanup_async(self):
        """Stop automated cleanup scheduler (async version)"""
        if not self.is_running:
            return

        self.is_running = False

        # Set the stop event to wake up the scheduler immediately
        if hasattr(self, "_stop_event"):
            self._stop_event.set()

        if hasattr(self, "scheduler_task") and self.scheduler_task is not None:
            if not self.scheduler_task.cancelled():
                self.scheduler_task.cancel()
                try:
                    await self.scheduler_task
                except asyncio.CancelledError:
                    pass  # Expected when cancelling
                logger.info("Cleanup scheduler task cancelled and awaited")

        logger.info("Automated rate limit cleanup stopped (async)")

    async def ensure_scheduler_running(self):
        """Ensure the async scheduler task is running (call after event loop starts)"""
        if self.is_running and self.scheduler_task is None:
            try:
                # Create stop event if not exists
                if self._stop_event is None:
                    self._stop_event = asyncio.Event()
                else:
                    # Reset the stop event for a fresh start
                    self._stop_event.clear()
                self.scheduler_task = asyncio.create_task(self._run_async_scheduler())
                logger.info("Cleanup scheduler task created and started")
                # Return immediately - don't await the task
                return
            except Exception as e:
                logger.error(f"Failed to start cleanup scheduler task: {e}")

    async def perform_cleanup(self) -> Dict[str, int]:
        """Perform rate limit cleanup

        Returns:
            Dictionary with cleanup statistics
        """
        try:
            # Import here to avoid circular import
            from bot.rate_limiter import cleanup_all_inactive_users

            logger.info("Starting scheduled rate limit cleanup")
            cleanup_stats = cleanup_all_inactive_users(self.max_inactive_seconds)

            if cleanup_stats.total > 0:
                logger.info(
                    f"Rate limit cleanup completed: {cleanup_stats.total} users removed "
                    f"(general: {cleanup_stats.general}, "
                    f"voice: {cleanup_stats.voice}, "
                    f"commands: {cleanup_stats.commands})"
                )
            else:
                logger.debug("Rate limit cleanup: no inactive users to remove")

            return cleanup_stats

        except Exception as e:
            logger.exception("Rate limit cleanup failed")
            return {
                "general": 0,
                "voice": 0,
                "commands": 0,
                "total": 0,
                "error": str(e),
            }

    async def _scheduled_cleanup(self):
        """Perform scheduled cleanup"""
        try:
            await self.perform_cleanup()
        except Exception:
            logger.exception("Scheduled rate limit cleanup failed")

    async def _run_async_scheduler(self):
        """Run the async cleanup scheduler"""
        next_cleanup_time = datetime.now() + timedelta(hours=self.cleanup_frequency_hours)
        logger.info(f"Next rate limit cleanup scheduled for: {next_cleanup_time}")

        while self.is_running:
            try:
                current_time = datetime.now()

                if current_time >= next_cleanup_time:
                    await self._scheduled_cleanup()
                    next_cleanup_time = current_time + timedelta(hours=self.cleanup_frequency_hours)
                    logger.info(f"Next rate limit cleanup scheduled for: {next_cleanup_time}")

                # Check every 5 seconds for faster shutdown response
                for _ in range(12):  # 12 * 5 = 60 seconds total
                    if not self.is_running:
                        return  # Exit immediately if stopped
                    await asyncio.sleep(5)

            except asyncio.CancelledError:
                logger.info("Cleanup scheduler cancelled")
                break
            except Exception:
                logger.exception("Cleanup scheduler error")
                await asyncio.sleep(60)  # Wait 1 minute on error

    def get_stats(self) -> Dict[str, Any]:
        """Get cleanup service statistics"""
        return {
            "is_running": self.is_running,
            "cleanup_frequency_hours": self.cleanup_frequency_hours,
            "max_inactive_seconds": self.max_inactive_seconds,
            "scheduler_active": self.scheduler_task is not None and not self.scheduler_task.done(),
        }


# Global cleanup service instance (used for sync startup in main.py)
rate_limit_cleanup_service = RateLimitCleanupService()
