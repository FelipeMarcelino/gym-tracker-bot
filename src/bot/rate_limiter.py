"""Rate limiting middleware to prevent spam and abuse"""

import logging
import time
from collections import defaultdict, deque
from collections.abc import Awaitable
from functools import wraps
from typing import Any, Callable, Deque, Dict, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings
from config.messages import messages

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter using sliding window approach"""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        """Args:
        max_requests: Maximum number of requests allowed in window
        window_seconds: Time window in seconds

        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # user_id -> deque of timestamps
        self.user_requests: Dict[int, Deque[float]] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> Tuple[bool, int]:
        """Check if user is allowed to make a request
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Tuple of (is_allowed, remaining_requests)

        """
        now = time.time()
        user_queue = self.user_requests[user_id]

        # Remove expired requests (outside the window)
        while user_queue and user_queue[0] <= now - self.window_seconds:
            user_queue.popleft()

        # Check if under limit
        if len(user_queue) < self.max_requests:
            user_queue.append(now)
            remaining = self.max_requests - len(user_queue)
            return True, remaining
        return False, 0

    def get_reset_time(self, user_id: int) -> int:
        """Get seconds until rate limit resets for user"""
        user_queue = self.user_requests[user_id]
        if not user_queue:
            return 0

        oldest_request = user_queue[0]
        reset_time = oldest_request + self.window_seconds - time.time()
        return max(0, int(reset_time))

    def check_status(self, user_id: int) -> Tuple[bool, int]:
        """Check rate limit status WITHOUT modifying state

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        now = time.time()
        user_queue = self.user_requests[user_id]

        # Count valid requests (within the window)
        valid_requests = sum(1 for timestamp in user_queue if timestamp > now - self.window_seconds)

        if valid_requests < self.max_requests:
            remaining = self.max_requests - valid_requests
            return True, remaining
        return False, 0

    def cleanup_inactive_users(self, max_inactive_seconds: int = 3600) -> int:
        """Remove inactive users from memory to prevent memory leak

        Args:
            max_inactive_seconds: Remove users inactive for this many seconds (default: 1 hour)

        Returns:
            Number of users cleaned up
        """
        now = time.time()
        users_to_remove = []

        for user_id, user_queue in self.user_requests.items():
            # Remove expired requests first
            while user_queue and user_queue[0] <= now - self.window_seconds:
                user_queue.popleft()

            # If no requests remain or last request is too old, mark for removal
            if not user_queue or user_queue[-1] <= now - max_inactive_seconds:
                users_to_remove.append(user_id)

        for user_id in users_to_remove:
            del self.user_requests[user_id]

        return len(users_to_remove)


# Global rate limiters with configurable limits
_general_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_GENERAL_REQUESTS, 
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
)
_voice_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_VOICE_REQUESTS, 
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
)
_command_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_COMMAND_REQUESTS, 
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
)


def rate_limit_general(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]:
    """Rate limiter for general requests (20/min)"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        user_id = update.effective_user.id
        is_allowed, remaining = _general_limiter.is_allowed(user_id)

        if not is_allowed:
            reset_time = _general_limiter.get_reset_time(user_id)
            message = messages.RATE_LIMIT_GENERAL.format(
                reset_time=reset_time,
                max_requests=_general_limiter.max_requests,
                window_seconds=_general_limiter.window_seconds
            )
            await update.message.reply_text(message)
            logger.warning(f"Rate limit geral: Usuário {user_id} bloqueado por {reset_time}s")
            return None

        # Add rate limit headers to context for monitoring
        context.user_data["rate_limit_remaining"] = remaining

        return await func(update, context)

    return wrapper


def rate_limit_voice(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]:
    """Rate limiter for voice messages (5/min)"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        user_id = update.effective_user.id
        is_allowed, remaining = _voice_limiter.is_allowed(user_id)

        if not is_allowed:
            reset_time = _voice_limiter.get_reset_time(user_id)
            message = messages.RATE_LIMIT_VOICE.format(
                reset_time=reset_time,
                max_requests=_voice_limiter.max_requests,
                window_seconds=_voice_limiter.window_seconds
            )
            await update.message.reply_text(message)
            logger.warning(f"Rate limit de voz: Usuário {user_id} bloqueado por {reset_time}s")
            return None

        context.user_data["voice_limit_remaining"] = remaining

        return await func(update, context)

    return wrapper


def rate_limit_commands(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]:
    """Rate limiter for commands (30/min)"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        user_id = update.effective_user.id
        is_allowed, remaining = _command_limiter.is_allowed(user_id)

        if not is_allowed:
            reset_time = _command_limiter.get_reset_time(user_id)
            message = messages.RATE_LIMIT_COMMANDS.format(
                reset_time=reset_time,
                max_requests=_command_limiter.max_requests,
                window_seconds=_command_limiter.window_seconds
            )
            await update.message.reply_text(message)
            logger.warning(f"Rate limit de comandos: Usuário {user_id} bloqueado por {reset_time}s")
            return None

        context.user_data["command_limit_remaining"] = remaining

        return await func(update, context)

    return wrapper


def get_rate_limit_status(user_id: int) -> Dict[str, Any]:
    """Get current rate limit status for a user"""
    # Use check_status() instead of is_allowed() to avoid modifying state
    general_allowed, general_remaining = _general_limiter.check_status(user_id)
    voice_allowed, voice_remaining = _voice_limiter.check_status(user_id)
    commands_allowed, commands_remaining = _command_limiter.check_status(user_id)

    return {
        "general": {
            "allowed": general_allowed,
            "remaining": general_remaining,
            "reset_time": _general_limiter.get_reset_time(user_id),
            "limit": _general_limiter.max_requests,
            "window": _general_limiter.window_seconds,
        },
        "voice": {
            "allowed": voice_allowed,
            "remaining": voice_remaining,
            "reset_time": _voice_limiter.get_reset_time(user_id),
            "limit": _voice_limiter.max_requests,
            "window": _voice_limiter.window_seconds,
        },
        "commands": {
            "allowed": commands_allowed,
            "remaining": commands_remaining,
            "reset_time": _command_limiter.get_reset_time(user_id),
            "limit": _command_limiter.max_requests,
            "window": _command_limiter.window_seconds,
        },
    }


def clear_rate_limits(user_id: int) -> None:
    """Clear rate limits for a user (admin function)"""
    _general_limiter.user_requests.pop(user_id, None)
    _voice_limiter.user_requests.pop(user_id, None)
    _command_limiter.user_requests.pop(user_id, None)


def get_rate_limiter_stats() -> Dict[str, Any]:
    """Get overall rate limiter statistics"""
    return {
        "active_users": {
            "general": len(_general_limiter.user_requests),
            "voice": len(_voice_limiter.user_requests),
            "commands": len(_command_limiter.user_requests),
        },
        "limits": {
            "general": {"requests": _general_limiter.max_requests, "window": _general_limiter.window_seconds},
            "voice": {"requests": _voice_limiter.max_requests, "window": _voice_limiter.window_seconds},
            "commands": {"requests": _command_limiter.max_requests, "window": _command_limiter.window_seconds},
        },
    }


def cleanup_all_inactive_users(max_inactive_seconds: int = 3600) -> Dict[str, int]:
    """Clean up inactive users from all rate limiters to prevent memory leaks

    Args:
        max_inactive_seconds: Remove users inactive for this many seconds (default: 1 hour)

    Returns:
        Dictionary with cleanup counts per limiter
    """
    general_cleaned = _general_limiter.cleanup_inactive_users(max_inactive_seconds)
    voice_cleaned = _voice_limiter.cleanup_inactive_users(max_inactive_seconds)
    commands_cleaned = _command_limiter.cleanup_inactive_users(max_inactive_seconds)

    total_cleaned = general_cleaned + voice_cleaned + commands_cleaned

    if total_cleaned > 0:
        logger.info(
            f"Cleaned up {total_cleaned} inactive users from rate limiters "
            f"(general: {general_cleaned}, voice: {voice_cleaned}, commands: {commands_cleaned})"
        )

    return {
        "general": general_cleaned,
        "voice": voice_cleaned,
        "commands": commands_cleaned,
        "total": total_cleaned,
    }

