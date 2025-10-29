"""Unit tests for bot rate limiter

These tests focus on business logic validation, rate limiting algorithms,
and decorator behavior without external dependencies.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from bot.rate_limiter import (
    RateLimiter,
    rate_limit_general,
    rate_limit_voice,
    rate_limit_commands,
    get_rate_limiter_stats,
    cleanup_all_inactive_users,
)
from models.service_models import (
    RateLimitCheckResult,
    RateLimiterStats,
    CleanupResult,
    ActiveUsersCount,
    RateLimitConfig,
)


class TestRateLimiterClass:
    """Test the core RateLimiter class functionality"""
    
    def test_rate_limiter_initialization(self):
        """Test RateLimiter class initializes correctly with default and custom parameters"""
        # Test default parameters
        limiter_default = RateLimiter()
        assert limiter_default.max_requests == 10
        assert limiter_default.window_seconds == 60
        assert isinstance(limiter_default.user_requests, dict)
        assert len(limiter_default.user_requests) == 0
        
        # Test custom parameters
        limiter_custom = RateLimiter(max_requests=5, window_seconds=30)
        assert limiter_custom.max_requests == 5
        assert limiter_custom.window_seconds == 30
        assert isinstance(limiter_custom.user_requests, dict)
        assert len(limiter_custom.user_requests) == 0

    def test_rate_limiter_allows_requests_within_limit(self):
        """Test that RateLimiter allows requests when under the limit"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        user_id = 12345
        
        # First request should be allowed
        result1 = limiter.is_allowed(user_id)
        assert result1.is_allowed is True
        assert result1.remaining_requests == 2  # 3 - 1 = 2 remaining
        
        # Second request should be allowed
        result2 = limiter.is_allowed(user_id)
        assert result2.is_allowed is True
        assert result2.remaining_requests == 1  # 3 - 2 = 1 remaining
        
        # Third request should be allowed
        result3 = limiter.is_allowed(user_id)
        assert result3.is_allowed is True
        assert result3.remaining_requests == 0  # 3 - 3 = 0 remaining
        
        # Verify user is tracked in the limiter
        assert user_id in limiter.user_requests
        assert len(limiter.user_requests[user_id]) == 3

    def test_rate_limiter_blocks_requests_over_limit(self):
        """Test that RateLimiter blocks requests when over the limit"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        user_id = 12345
        
        # Use up the limit
        result1 = limiter.is_allowed(user_id)
        assert result1.is_allowed is True
        assert result1.remaining_requests == 1
        
        result2 = limiter.is_allowed(user_id)
        assert result2.is_allowed is True
        assert result2.remaining_requests == 0
        
        # Next request should be blocked
        result3 = limiter.is_allowed(user_id)
        assert result3.is_allowed is False
        assert result3.remaining_requests == 0
        
        # Multiple blocked requests should continue to be blocked
        result4 = limiter.is_allowed(user_id)
        assert result4.is_allowed is False
        assert result4.remaining_requests == 0
        
        # Verify user queue doesn't grow beyond limit when blocked
        assert len(limiter.user_requests[user_id]) == 2  # Only the allowed requests

    @patch('bot.rate_limiter.time.time')
    def test_rate_limiter_sliding_window_behavior(self, mock_time):
        """Test that RateLimiter correctly implements sliding window with time progression"""
        limiter = RateLimiter(max_requests=2, window_seconds=10)
        user_id = 12345
        
        # Start at time 0
        mock_time.return_value = 0.0
        
        # Use up the limit
        result1 = limiter.is_allowed(user_id)
        assert result1.is_allowed is True
        assert result1.remaining_requests == 1
        
        result2 = limiter.is_allowed(user_id)
        assert result2.is_allowed is True
        assert result2.remaining_requests == 0
        
        # Should be blocked now
        result3 = limiter.is_allowed(user_id)
        assert result3.is_allowed is False
        
        # Move time forward by 5 seconds (still within window)
        mock_time.return_value = 5.0
        result4 = limiter.is_allowed(user_id)
        assert result4.is_allowed is False  # Still blocked
        
        # Move time forward by 11 seconds (outside window)
        mock_time.return_value = 11.0
        result5 = limiter.is_allowed(user_id)
        assert result5.is_allowed is True  # Should be allowed again
        assert result5.remaining_requests == 1  # Fresh window
        
        # Verify old requests were cleaned up
        assert len(limiter.user_requests[user_id]) == 1  # Only the new request

    @patch('bot.rate_limiter.time.time')
    def test_check_status_does_not_modify_state(self, mock_time):
        """Test that check_status method doesn't modify the rate limiter state"""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        user_id = 12345
        
        mock_time.return_value = 0.0
        
        # Make some requests to set up state
        limiter.is_allowed(user_id)
        limiter.is_allowed(user_id)
        
        # Check that we have 2 requests in queue and 1 remaining
        assert len(limiter.user_requests[user_id]) == 2
        
        # Use check_status multiple times
        status1 = limiter.check_status(user_id)
        assert status1.is_allowed is True
        assert status1.remaining_requests == 1
        
        status2 = limiter.check_status(user_id)
        assert status2.is_allowed is True
        assert status2.remaining_requests == 1
        
        # Verify state hasn't changed - still 2 requests in queue
        assert len(limiter.user_requests[user_id]) == 2
        
        # Verify that after check_status, is_allowed still works correctly
        result = limiter.is_allowed(user_id)
        assert result.is_allowed is True
        assert result.remaining_requests == 0
        assert len(limiter.user_requests[user_id]) == 3

    @patch('bot.rate_limiter.time.time')
    def test_get_reset_time_calculation(self, mock_time):
        """Test that get_reset_time correctly calculates when rate limit resets"""
        limiter = RateLimiter(max_requests=2, window_seconds=30)
        user_id = 12345
        
        # No requests made yet
        reset_time = limiter.get_reset_time(user_id)
        assert reset_time == 0
        
        # Make first request at time 0
        mock_time.return_value = 0.0
        limiter.is_allowed(user_id)
        
        # At time 10, reset should be in 20 seconds (30 - 10)
        mock_time.return_value = 10.0
        reset_time = limiter.get_reset_time(user_id)
        assert reset_time == 20
        
        # At time 25, reset should be in 5 seconds (30 - 25)
        mock_time.return_value = 25.0
        reset_time = limiter.get_reset_time(user_id)
        assert reset_time == 5
        
        # At time 30, reset should be 0 (window expired)
        mock_time.return_value = 30.0
        reset_time = limiter.get_reset_time(user_id)
        assert reset_time == 0
        
        # At time 35, reset should be 0 (past window)
        mock_time.return_value = 35.0
        reset_time = limiter.get_reset_time(user_id)
        assert reset_time == 0

    @patch('bot.rate_limiter.time.time')
    def test_cleanup_inactive_users(self, mock_time):
        """Test that cleanup_inactive_users removes old inactive users"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        
        # Create requests for multiple users at different times
        mock_time.return_value = 0.0
        limiter.is_allowed(12345)  # User 1 at time 0
        limiter.is_allowed(67890)  # User 2 at time 0
        
        mock_time.return_value = 1800.0  # 30 minutes later
        limiter.is_allowed(11111)  # User 3 at time 1800
        
        mock_time.return_value = 3600.0  # 1 hour later
        limiter.is_allowed(22222)  # User 4 at time 3600
        
        # Verify all users are tracked
        assert len(limiter.user_requests) == 4
        assert 12345 in limiter.user_requests
        assert 67890 in limiter.user_requests
        assert 11111 in limiter.user_requests
        assert 22222 in limiter.user_requests
        
        # Move to time 7200 (2 hours) and cleanup users inactive for 1 hour (3600s)
        mock_time.return_value = 7200.0
        cleaned_count = limiter.cleanup_inactive_users(max_inactive_seconds=3600)
        
        # Users 1 and 2 should be cleaned (inactive for > 1 hour)
        # User 3 should be cleaned (inactive for exactly 1 hour)
        # User 4 should remain (inactive for less than 1 hour)
        assert cleaned_count == 3
        assert len(limiter.user_requests) == 1
        assert 22222 in limiter.user_requests
        assert 12345 not in limiter.user_requests
        assert 67890 not in limiter.user_requests
        assert 11111 not in limiter.user_requests

    def test_multiple_users_independent_rate_limiting(self):
        """Test that rate limiting works independently for different users"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        user1 = 12345
        user2 = 67890
        user3 = 11111
        
        # User 1 uses up their limit
        result1_1 = limiter.is_allowed(user1)
        assert result1_1.is_allowed is True
        assert result1_1.remaining_requests == 1
        
        result1_2 = limiter.is_allowed(user1)
        assert result1_2.is_allowed is True
        assert result1_2.remaining_requests == 0
        
        result1_3 = limiter.is_allowed(user1)
        assert result1_3.is_allowed is False
        
        # User 2 should have fresh limits
        result2_1 = limiter.is_allowed(user2)
        assert result2_1.is_allowed is True
        assert result2_1.remaining_requests == 1
        
        result2_2 = limiter.is_allowed(user2)
        assert result2_2.is_allowed is True
        assert result2_2.remaining_requests == 0
        
        # User 3 should also have fresh limits
        result3_1 = limiter.is_allowed(user3)
        assert result3_1.is_allowed is True
        assert result3_1.remaining_requests == 1
        
        # Verify user 1 is still blocked while others can continue
        result1_4 = limiter.is_allowed(user1)
        assert result1_4.is_allowed is False
        
        result2_3 = limiter.is_allowed(user2)
        assert result2_3.is_allowed is False  # User 2 now at limit
        
        result3_2 = limiter.is_allowed(user3)
        assert result3_2.is_allowed is True
        assert result3_2.remaining_requests == 0
        
        # Verify all users are tracked independently
        assert len(limiter.user_requests) == 3
        assert len(limiter.user_requests[user1]) == 2
        assert len(limiter.user_requests[user2]) == 2
        assert len(limiter.user_requests[user3]) == 2

    def test_rate_limiter_edge_cases(self):
        """Test RateLimiter handles edge cases correctly"""
        # Test with zero max_requests
        limiter_zero = RateLimiter(max_requests=0, window_seconds=60)
        user_id = 12345
        
        # Should always block when max_requests is 0
        result = limiter_zero.is_allowed(user_id)
        assert result.is_allowed is False
        assert result.remaining_requests == 0
        
        # Test with very small window
        limiter_small_window = RateLimiter(max_requests=1, window_seconds=1)
        result1 = limiter_small_window.is_allowed(user_id)
        assert result1.is_allowed is True
        
        result2 = limiter_small_window.is_allowed(user_id)
        assert result2.is_allowed is False
        
        # Test check_status with non-existent user
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        status = limiter.check_status(99999)
        assert status.is_allowed is True
        assert status.remaining_requests == 5
        
        # Test get_reset_time with non-existent user
        reset_time = limiter.get_reset_time(99999)
        assert reset_time == 0
        
        # Test cleanup with no users
        cleaned = limiter.cleanup_inactive_users()
        assert cleaned == 0
        
        # Test cleanup with max_inactive_seconds = 0
        limiter.is_allowed(user_id)
        cleaned_zero = limiter.cleanup_inactive_users(max_inactive_seconds=0)
        assert cleaned_zero == 1  # Should clean all users immediately

    @patch('bot.rate_limiter.time.time')
    def test_rate_limiter_memory_management_and_performance(self, mock_time):
        """Test that RateLimiter properly manages memory and performs efficiently"""
        limiter = RateLimiter(max_requests=3, window_seconds=10)
        
        mock_time.return_value = 0.0
        
        # Create many users and requests to test memory management
        user_ids = range(1000, 1100)  # 100 users
        
        # All users make requests at time 0
        for user_id in user_ids:
            for _ in range(3):  # Each user makes 3 requests (hitting limit)
                limiter.is_allowed(user_id)
        
        # Verify all users are tracked
        assert len(limiter.user_requests) == 100
        
        # Verify each user has exactly 3 requests in their queue
        for user_id in user_ids:
            assert len(limiter.user_requests[user_id]) == 3
        
        # Move time forward beyond window (15 seconds)
        mock_time.return_value = 15.0
        
        # Make a request for one user to trigger cleanup of their expired requests
        result = limiter.is_allowed(1000)
        assert result.is_allowed is True
        assert len(limiter.user_requests[1000]) == 1  # Only the new request
        
        # Verify other users still have their old requests (not cleaned yet)
        assert len(limiter.user_requests[1001]) == 3
        
        # Test bulk cleanup
        cleaned = limiter.cleanup_inactive_users(max_inactive_seconds=5)
        
        # Should clean up 99 users (all except user 1000 who just made a request)
        assert cleaned == 99
        assert len(limiter.user_requests) == 1
        assert 1000 in limiter.user_requests
        
        # Test that cleanup doesn't affect active users
        mock_time.return_value = 20.0
        limiter.is_allowed(1000)  # Keep user 1000 active
        
        # Add new users
        limiter.is_allowed(2000)
        limiter.is_allowed(3000)
        
        # Cleanup should not remove recently active users
        cleaned_recent = limiter.cleanup_inactive_users(max_inactive_seconds=10)
        assert cleaned_recent == 0  # No users should be cleaned
        assert len(limiter.user_requests) == 3


class TestRateLimitDecorators:
    """Test the rate limit decorator functions"""
    
    @pytest.mark.asyncio
    @patch('bot.rate_limiter._general_limiter')
    async def test_rate_limit_general_decorator_allows_request(self, mock_limiter):
        """Test that rate_limit_general decorator allows requests within limit"""
        # Setup mock limiter to allow request
        mock_limiter.is_allowed.return_value = RateLimitCheckResult(
            is_allowed=True, 
            remaining_requests=5
        )
        
        # Create mock function to decorate
        mock_function = AsyncMock(return_value="success")
        decorated_function = rate_limit_general(mock_function)
        
        # Create mock update and context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_context = MagicMock()
        mock_context.user_data = {}
        
        # Call decorated function
        result = await decorated_function(mock_update, mock_context)
        
        # Verify limiter was called with correct user ID
        mock_limiter.is_allowed.assert_called_once_with(12345)
        
        # Verify original function was called
        mock_function.assert_called_once_with(mock_update, mock_context)
        
        # Verify result is returned
        assert result == "success"
        
        # Verify rate limit info is added to context
        assert mock_context.user_data["rate_limit_remaining"] == 5
        
        # Verify no rate limit message was sent
        assert not hasattr(mock_update.message, 'reply_text') or not mock_update.message.reply_text.called

    @pytest.mark.asyncio
    @patch('bot.rate_limiter._general_limiter')
    @patch('bot.rate_limiter.logger')
    async def test_rate_limit_general_decorator_blocks_request(self, mock_logger, mock_limiter):
        """Test that rate_limit_general decorator blocks requests over limit"""
        # Setup mock limiter to block request
        mock_limiter.is_allowed.return_value = RateLimitCheckResult(
            is_allowed=False, 
            remaining_requests=0
        )
        mock_limiter.get_reset_time.return_value = 45
        mock_limiter.max_requests = 20
        mock_limiter.window_seconds = 60
        
        # Create mock function to decorate
        mock_function = AsyncMock()
        decorated_function = rate_limit_general(mock_function)
        
        # Create mock update and context
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        
        # Mock the rate limit message
        with patch('bot.rate_limiter.messages') as mock_messages:
            mock_messages.RATE_LIMIT_GENERAL.format.return_value = "Rate limited! Wait 45 seconds."
            
            # Call decorated function
            result = await decorated_function(mock_update, mock_context)
        
        # Verify limiter was called
        mock_limiter.is_allowed.assert_called_once_with(12345)
        mock_limiter.get_reset_time.assert_called_once_with(12345)
        
        # Verify original function was NOT called
        mock_function.assert_not_called()
        
        # Verify result is None (blocked)
        assert result is None
        
        # Verify rate limit message was sent
        mock_update.message.reply_text.assert_called_once_with("Rate limited! Wait 45 seconds.")
        
        # Verify rate limit message was formatted correctly
        mock_messages.RATE_LIMIT_GENERAL.format.assert_called_once_with(
            reset_time=45,
            max_requests=20,
            window_seconds=60
        )
        
        # Verify warning was logged
        mock_logger.warning.assert_called_once_with("Rate limit geral: Usuário 12345 bloqueado por 45s")

    @pytest.mark.asyncio
    @patch('bot.rate_limiter._voice_limiter')
    @patch('bot.rate_limiter.logger')
    async def test_rate_limit_voice_decorator_blocks_request(self, mock_logger, mock_limiter):
        """Test that rate_limit_voice decorator blocks voice requests over limit"""
        # Setup mock limiter to block request
        mock_limiter.is_allowed.return_value = RateLimitCheckResult(
            is_allowed=False, 
            remaining_requests=0
        )
        mock_limiter.get_reset_time.return_value = 30
        mock_limiter.max_requests = 5
        mock_limiter.window_seconds = 60
        
        # Create mock function to decorate
        mock_function = AsyncMock()
        decorated_function = rate_limit_voice(mock_function)
        
        # Create mock update and context
        mock_update = MagicMock()
        mock_update.effective_user.id = 67890
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        
        # Mock the rate limit message
        with patch('bot.rate_limiter.messages') as mock_messages:
            mock_messages.RATE_LIMIT_VOICE.format.return_value = "Voice rate limited! Wait 30 seconds."
            
            # Call decorated function
            result = await decorated_function(mock_update, mock_context)
        
        # Verify limiter was called with correct user ID
        mock_limiter.is_allowed.assert_called_once_with(67890)
        mock_limiter.get_reset_time.assert_called_once_with(67890)
        
        # Verify original function was NOT called
        mock_function.assert_not_called()
        
        # Verify result is None (blocked)
        assert result is None
        
        # Verify voice rate limit message was sent
        mock_update.message.reply_text.assert_called_once_with("Voice rate limited! Wait 30 seconds.")
        
        # Verify message was formatted correctly
        mock_messages.RATE_LIMIT_VOICE.format.assert_called_once_with(
            reset_time=30,
            max_requests=5,
            window_seconds=60
        )
        
        # Verify specific voice warning was logged
        mock_logger.warning.assert_called_once_with("Rate limit de voz: Usuário 67890 bloqueado por 30s")

    @pytest.mark.asyncio
    @patch('bot.rate_limiter._command_limiter')
    async def test_rate_limit_commands_decorator_allows_request(self, mock_limiter):
        """Test that rate_limit_commands decorator allows command requests within limit"""
        # Setup mock limiter to allow request
        mock_limiter.is_allowed.return_value = RateLimitCheckResult(
            is_allowed=True, 
            remaining_requests=15
        )
        
        # Create mock function to decorate
        mock_function = AsyncMock(return_value="command_executed")
        decorated_function = rate_limit_commands(mock_function)
        
        # Create mock update and context
        mock_update = MagicMock()
        mock_update.effective_user.id = 11111
        mock_context = MagicMock()
        mock_context.user_data = {}
        
        # Call decorated function
        result = await decorated_function(mock_update, mock_context)
        
        # Verify command limiter was used
        mock_limiter.is_allowed.assert_called_once_with(11111)
        
        # Verify original function was called
        mock_function.assert_called_once_with(mock_update, mock_context)
        
        # Verify result is returned from original function
        assert result == "command_executed"
        
        # Verify command limit info is added to context
        assert mock_context.user_data["command_limit_remaining"] == 15
        
        # Verify get_reset_time was not called (since request was allowed)
        mock_limiter.get_reset_time.assert_not_called()


class TestUtilityFunctions:
    """Test utility functions for rate limiter management"""
    
    @patch('bot.rate_limiter._general_limiter')
    @patch('bot.rate_limiter._voice_limiter')
    @patch('bot.rate_limiter._command_limiter')
    def test_get_rate_limiter_stats(self, mock_command_limiter, mock_voice_limiter, mock_general_limiter):
        """Test that get_rate_limiter_stats returns correct statistics"""
        # Setup mock limiters with different user counts and configurations
        mock_general_limiter.user_requests = {12345: MagicMock(), 67890: MagicMock()}
        mock_general_limiter.max_requests = 20
        mock_general_limiter.window_seconds = 60
        
        mock_voice_limiter.user_requests = {12345: MagicMock(), 67890: MagicMock(), 11111: MagicMock()}
        mock_voice_limiter.max_requests = 5
        mock_voice_limiter.window_seconds = 60
        
        mock_command_limiter.user_requests = {12345: MagicMock()}
        mock_command_limiter.max_requests = 30
        mock_command_limiter.window_seconds = 60
        
        # Call the function
        stats = get_rate_limiter_stats()
        
        # Verify the structure and values
        assert isinstance(stats, RateLimiterStats)
        
        # Check active users count
        assert stats.active_users.general == 2
        assert stats.active_users.voice == 3
        assert stats.active_users.commands == 1
        
        # Check limits configuration
        assert stats.limits["general"].requests == 20
        assert stats.limits["general"].window == 60
        
        assert stats.limits["voice"].requests == 5
        assert stats.limits["voice"].window == 60
        
        assert stats.limits["commands"].requests == 30
        assert stats.limits["commands"].window == 60
        
        # Verify the returned object has all expected attributes
        assert hasattr(stats, 'active_users')
        assert hasattr(stats, 'limits')
        assert isinstance(stats.limits, dict)
        assert len(stats.limits) == 3

    @patch('bot.rate_limiter._general_limiter')
    @patch('bot.rate_limiter._voice_limiter')
    @patch('bot.rate_limiter._command_limiter')
    @patch('bot.rate_limiter.logger')
    def test_cleanup_all_inactive_users(self, mock_logger, mock_command_limiter, mock_voice_limiter, mock_general_limiter):
        """Test that cleanup_all_inactive_users cleans up all limiters and returns correct results"""
        # Setup mock limiters to return different cleanup counts
        mock_general_limiter.cleanup_inactive_users.return_value = 5
        mock_voice_limiter.cleanup_inactive_users.return_value = 3
        mock_command_limiter.cleanup_inactive_users.return_value = 2
        
        # Call cleanup with custom max_inactive_seconds
        max_inactive = 1800  # 30 minutes
        result = cleanup_all_inactive_users(max_inactive_seconds=max_inactive)
        
        # Verify all limiters were called with correct parameter
        mock_general_limiter.cleanup_inactive_users.assert_called_once_with(max_inactive)
        mock_voice_limiter.cleanup_inactive_users.assert_called_once_with(max_inactive)
        mock_command_limiter.cleanup_inactive_users.assert_called_once_with(max_inactive)
        
        # Verify the result structure and values
        assert isinstance(result, CleanupResult)
        assert result.general == 5
        assert result.voice == 3
        assert result.commands == 2
        assert result.total == 10  # 5 + 3 + 2
        
        # Verify logging occurred with correct message
        mock_logger.info.assert_called_once_with(
            "Cleaned up 10 inactive users from rate limiters "
            "(general: 5, voice: 3, commands: 2)"
        )
        
        # Test case with no cleanup needed
        mock_general_limiter.cleanup_inactive_users.return_value = 0
        mock_voice_limiter.cleanup_inactive_users.return_value = 0
        mock_command_limiter.cleanup_inactive_users.return_value = 0
        mock_logger.reset_mock()
        
        result_empty = cleanup_all_inactive_users()
        
        # Verify no logging when no cleanup occurred
        mock_logger.info.assert_not_called()
        assert result_empty.total == 0