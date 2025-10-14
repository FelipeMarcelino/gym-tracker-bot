"""Rate limiting middleware to prevent spam and abuse"""

import time
from collections import defaultdict, deque
from collections.abc import Awaitable
from functools import wraps
from typing import Any, Callable, Deque, Dict, Tuple

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings
from config.messages import messages


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
            print(f"🚫 Rate limit: User {user_id} blocked for {reset_time}s")
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
            print(f"🚫 Voice rate limit: User {user_id} blocked for {reset_time}s")
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
            print(f"🚫 Command rate limit: User {user_id} blocked for {reset_time}s")
            return None

        context.user_data["command_limit_remaining"] = remaining

        return await func(update, context)

    return wrapper


def get_rate_limit_status(user_id: int) -> Dict[str, Any]:
    """Get current rate limit status for a user"""
    return {
        "general": {
            "allowed": _general_limiter.is_allowed(user_id)[0],
            "remaining": _general_limiter.is_allowed(user_id)[1],
            "reset_time": _general_limiter.get_reset_time(user_id),
            "limit": _general_limiter.max_requests,
            "window": _general_limiter.window_seconds,
        },
        "voice": {
            "allowed": _voice_limiter.is_allowed(user_id)[0],
            "remaining": _voice_limiter.is_allowed(user_id)[1],
            "reset_time": _voice_limiter.get_reset_time(user_id),
            "limit": _voice_limiter.max_requests,
            "window": _voice_limiter.window_seconds,
        },
        "commands": {
            "allowed": _command_limiter.is_allowed(user_id)[0],
            "remaining": _command_limiter.is_allowed(user_id)[1],
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

