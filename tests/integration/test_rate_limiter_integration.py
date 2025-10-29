"""Integration tests for bot rate limiter

These tests focus on complete workflows, real-world scenarios,
and integration between all rate limiter components.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from bot.rate_limiter import (
    rate_limit_general,
    rate_limit_voice,
    rate_limit_commands,
    get_rate_limiter_stats,
    cleanup_all_inactive_users,
    _general_limiter,
    _voice_limiter,
    _command_limiter,
)
from models.service_models import (
    RateLimiterStats,
    CleanupResult,
)


class TestRateLimiterIntegration:
    """Integration tests for complete rate limiter workflows"""
    
    @pytest.fixture(autouse=True)
    def setup_clean_rate_limiters(self):
        """Clean up rate limiter state before each test"""
        # Clear all user requests from global rate limiters
        _general_limiter.user_requests.clear()
        _voice_limiter.user_requests.clear()
        _command_limiter.user_requests.clear()
        yield
        # Cleanup after test as well
        _general_limiter.user_requests.clear()
        _voice_limiter.user_requests.clear()
        _command_limiter.user_requests.clear()
    
    @pytest.mark.asyncio
    async def test_end_to_end_rate_limiting_with_real_telegram_updates(self):
        """Test complete rate limiting flow with realistic Telegram update objects"""
        # Create realistic Telegram update and context objects
        mock_update = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.user_data = {}
        
        # Create a simple test function to decorate
        call_count = 0
        @rate_limit_general
        async def test_handler(update, context):
            nonlocal call_count
            call_count += 1
            return f"handler_called_{call_count}"
        
        # Test successful calls within limit (assuming default limit is 20)
        for i in range(1, 6):  # Make 5 calls
            result = await test_handler(mock_update, mock_context)
            assert result == f"handler_called_{i}"
            assert mock_context.user_data["rate_limit_remaining"] == 20 - i
        
        # Verify no rate limit messages were sent
        assert mock_update.message.reply_text.call_count == 0
        
        # Test that different users have independent limits
        mock_update2 = MagicMock()
        mock_update2.effective_user.id = 67890
        mock_update2.message.reply_text = AsyncMock()
        mock_context2 = MagicMock()
        mock_context2.user_data = {}
        
        result2 = await test_handler(mock_update2, mock_context2)
        assert result2 == "handler_called_6"  # Function still works for different user
        assert mock_context2.user_data["rate_limit_remaining"] == 19  # Fresh limit for new user

    @pytest.mark.asyncio
    async def test_multiple_decorator_types_integration(self):
        """Test integration between different types of rate limiters (voice, commands, general)"""
        mock_user = MagicMock()
        mock_user.id = 12345
        
        # Create different update objects for different types
        voice_update = MagicMock()
        voice_update.effective_user = mock_user
        voice_update.message.reply_text = AsyncMock()
        
        command_update = MagicMock()
        command_update.effective_user = mock_user
        command_update.message.reply_text = AsyncMock()
        
        general_update = MagicMock()
        general_update.effective_user = mock_user
        general_update.message.reply_text = AsyncMock()
        
        # Create contexts
        voice_context = MagicMock()
        voice_context.user_data = {}
        command_context = MagicMock()
        command_context.user_data = {}
        general_context = MagicMock()
        general_context.user_data = {}
        
        # Create test handlers for each type
        voice_calls = []
        command_calls = []
        general_calls = []
        
        @rate_limit_voice
        async def voice_handler(update, context):
            voice_calls.append(len(voice_calls) + 1)
            return "voice_success"
        
        @rate_limit_commands
        async def command_handler(update, context):
            command_calls.append(len(command_calls) + 1)
            return "command_success"
        
        @rate_limit_general
        async def general_handler(update, context):
            general_calls.append(len(general_calls) + 1)
            return "general_success"
        
        # Test that each rate limiter works independently
        # Make voice calls (should use voice limits)
        result1 = await voice_handler(voice_update, voice_context)
        assert result1 == "voice_success"
        assert len(voice_calls) == 1
        
        # Make command calls (should use command limits, independent of voice)
        result2 = await command_handler(command_update, command_context)
        assert result2 == "command_success"
        assert len(command_calls) == 1
        
        # Make general calls (should use general limits, independent of both)
        result3 = await general_handler(general_update, general_context)
        assert result3 == "general_success"
        assert len(general_calls) == 1
        
        # Verify each context has appropriate rate limit info
        assert "voice_limit_remaining" in voice_context.user_data
        assert "command_limit_remaining" in command_context.user_data
        assert "rate_limit_remaining" in general_context.user_data
        
        # Verify the limits are different (voice < commands < general typically)
        voice_remaining = voice_context.user_data["voice_limit_remaining"]
        command_remaining = command_context.user_data["command_limit_remaining"]
        general_remaining = general_context.user_data["rate_limit_remaining"]
        
        # These should be different values based on different rate limits
        assert voice_remaining != command_remaining or command_remaining != general_remaining

    @pytest.mark.asyncio
    @patch('bot.rate_limiter.time.time')
    async def test_rate_limiter_cleanup_integration_with_time_progression(self, mock_time):
        """Test rate limiter cleanup integration in realistic time-based scenarios"""
        # Setup multiple users making requests at different times
        users = [12345, 67890, 11111, 22222, 33333]
        
        # Simulate requests over time
        mock_time.return_value = 0.0
        
        @rate_limit_voice
        async def voice_handler(update, context):
            return "voice_processed"
        
        @rate_limit_commands
        async def command_handler(update, context):
            return "command_processed"
        
        # Time 0: Users 1, 2, 3 make voice requests
        for user_id in users[:3]:
            update = MagicMock()
            update.effective_user.id = user_id
            update.message.reply_text = AsyncMock()
            context = MagicMock()
            context.user_data = {}
            
            result = await voice_handler(update, context)
            assert result == "voice_processed"
        
        # Time 1800 (30 minutes): Users 2, 4, 5 make command requests
        mock_time.return_value = 1800.0
        for user_id in [users[1], users[3], users[4]]:
            update = MagicMock()
            update.effective_user.id = user_id
            update.message.reply_text = AsyncMock()
            context = MagicMock()
            context.user_data = {}
            
            result = await command_handler(update, context)
            assert result == "command_processed"
        
        # Time 3600 (1 hour): User 5 makes another voice request
        mock_time.return_value = 3600.0
        update = MagicMock()
        update.effective_user.id = users[4]
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.user_data = {}
        
        result = await voice_handler(update, context)
        assert result == "voice_processed"
        
        # Check stats before cleanup
        stats_before = get_rate_limiter_stats()
        total_users_before = (stats_before.active_users.voice + 
                             stats_before.active_users.commands + 
                             stats_before.active_users.general)
        
        # Time 7200 (2 hours): Perform cleanup of users inactive for 1 hour
        mock_time.return_value = 7200.0
        cleanup_result = cleanup_all_inactive_users(max_inactive_seconds=3600)
        
        # Verify cleanup occurred
        assert cleanup_result.total > 0
        assert isinstance(cleanup_result, CleanupResult)
        
        # Check stats after cleanup
        stats_after = get_rate_limiter_stats()
        total_users_after = (stats_after.active_users.voice + 
                            stats_after.active_users.commands + 
                            stats_after.active_users.general)
        
        # Should have fewer active users after cleanup
        assert total_users_after < total_users_before
        
        # User 5 should still be active (made request at time 3600, cleanup at 7200 with 1 hour threshold)
        # Users 1 and 3 should be cleaned up (last activity at time 0, more than 1 hour ago)
        # User 2 should be cleaned up (last activity at time 1800, more than 1 hour ago)
        # User 4 should be cleaned up (last activity at time 1800, more than 1 hour ago)
        
        # New request from active user should still work
        update_new = MagicMock()
        update_new.effective_user.id = users[4]  # User 5
        update_new.message.reply_text = AsyncMock()
        context_new = MagicMock()
        context_new.user_data = {}
        
        result_new = await voice_handler(update_new, context_new)
        assert result_new == "voice_processed"

    @pytest.mark.asyncio
    async def test_rate_limiter_error_handling_and_recovery_integration(self):
        """Test rate limiter behavior during error conditions and recovery scenarios"""
        user_id = 12345
        
        # Setup mock update and context
        mock_update = MagicMock()
        mock_update.effective_user.id = user_id
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = MagicMock()
        mock_context.user_data = {}
        
        # Create a handler that sometimes fails
        call_attempts = []
        
        @rate_limit_commands
        async def unstable_handler(update, context):
            attempt = len(call_attempts) + 1
            call_attempts.append(attempt)
            
            if attempt == 3:  # Fail on third attempt
                raise Exception("Simulated handler failure")
            
            return f"success_{attempt}"
        
        # Test successful calls and one failure
        # First call - should succeed
        result1 = await unstable_handler(mock_update, mock_context)
        assert result1 == "success_1"
        assert mock_context.user_data["command_limit_remaining"] == 29  # Assuming 30 command limit
        
        # Second call - should succeed
        result2 = await unstable_handler(mock_update, mock_context)
        assert result2 == "success_2"
        assert mock_context.user_data["command_limit_remaining"] == 28
        
        # Third call - will fail in handler, but rate limit should still be consumed
        with pytest.raises(Exception, match="Simulated handler failure"):
            await unstable_handler(mock_update, mock_context)
        
        # Rate limit should still be decremented even when handler fails
        assert mock_context.user_data["command_limit_remaining"] == 27
        
        # Fourth call - should succeed (handler works again)
        result4 = await unstable_handler(mock_update, mock_context)
        assert result4 == "success_4"
        assert mock_context.user_data["command_limit_remaining"] == 26
        
        # Test rate limit blocking behavior
        # Exhaust remaining requests (26 more calls)
        for i in range(5, 31):  # calls 5 through 30
            result = await unstable_handler(mock_update, mock_context)
            assert result == f"success_{i}"
        
        # 31st call should be blocked by rate limiter
        mock_update.message.reply_text.reset_mock()  # Clear previous calls
        
        with patch('bot.rate_limiter.messages') as mock_messages:
            mock_messages.RATE_LIMIT_COMMANDS.format.return_value = "Rate limited!"
            
            result_blocked = await unstable_handler(mock_update, mock_context)
        
        # Should be blocked
        assert result_blocked is None
        mock_update.message.reply_text.assert_called_once_with("Rate limited!")
        
        # Verify handler wasn't called (call_attempts should still be 30)
        assert len(call_attempts) == 30
        
        # Test recovery after time passes (mock time progression)
        with patch('bot.rate_limiter.time.time') as mock_time:
            # Simulate time progression to reset rate limit
            mock_time.return_value = 3700.0  # 1+ hour later
            
            # Clear the rate limits to simulate window expiration
            from bot.rate_limiter import _command_limiter
            _command_limiter.user_requests[user_id].clear()
            
            # Reset context for clean state
            mock_context.user_data = {}
            
            # Should work again after rate limit reset
            result_recovered = await unstable_handler(mock_update, mock_context)
            assert result_recovered == "success_31"
            assert mock_context.user_data["command_limit_remaining"] == 29

    @pytest.mark.asyncio
    async def test_rate_limiter_performance_under_load_integration(self):
        """Test rate limiter performance and behavior under high load conditions"""
        # Create many users and concurrent requests to test performance
        num_users = 50
        requests_per_user = 10
        
        @rate_limit_general
        async def load_test_handler(update, context):
            # Simulate some processing time
            await asyncio.sleep(0.001)  # 1ms processing time
            return f"processed_user_{update.effective_user.id}"
        
        # Prepare requests for all users
        requests = []
        for user_id in range(1000, 1000 + num_users):
            for request_num in range(requests_per_user):
                mock_update = MagicMock()
                mock_update.effective_user.id = user_id
                mock_update.message.reply_text = AsyncMock()
                
                mock_context = MagicMock()
                mock_context.user_data = {}
                
                requests.append((mock_update, mock_context, user_id))
        
        # Execute all requests concurrently
        start_time = time.time()
        
        async def make_request(update, context, expected_user_id):
            try:
                result = await load_test_handler(update, context)
                return {
                    'success': True,
                    'result': result,
                    'user_id': expected_user_id,
                    'rate_limit_remaining': context.user_data.get('rate_limit_remaining')
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e),
                    'user_id': expected_user_id
                }
        
        # Use asyncio.gather for concurrent execution
        tasks = [make_request(update, context, user_id) for update, context, user_id in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        execution_time = time.time() - start_time
        
        # Analyze results
        successful_requests = [r for r in results if isinstance(r, dict) and r.get('success', False)]
        failed_requests = [r for r in results if not (isinstance(r, dict) and r.get('success', False))]
        rate_limited_requests = [r for r in results if isinstance(r, dict) and r.get('result') is None]
        
        # Verify performance metrics
        assert execution_time < 10.0  # Should complete within 10 seconds
        assert len(successful_requests) > 0  # Some requests should succeed
        
        # Verify rate limiting worked correctly - each user should have some successful requests
        # and potentially some rate limited requests
        user_results = {}
        for result in successful_requests:
            user_id = result['user_id']
            if user_id not in user_results:
                user_results[user_id] = []
            user_results[user_id].append(result)
        
        # Each user should have at least one successful request (within their rate limit)
        assert len(user_results) == num_users
        
        # Verify rate limit information is properly tracked
        for user_id, user_requests in user_results.items():
            for request_result in user_requests:
                assert 'rate_limit_remaining' in request_result
                assert isinstance(request_result['rate_limit_remaining'], int)
                assert request_result['rate_limit_remaining'] >= 0
        
        # Check rate limiter stats after load test
        stats = get_rate_limiter_stats()
        assert stats.active_users.general == num_users
        
        # Verify memory usage is reasonable (each user should have some requests tracked)
        from bot.rate_limiter import _general_limiter
        total_tracked_requests = sum(len(queue) for queue in _general_limiter.user_requests.values())
        assert total_tracked_requests > 0
        assert total_tracked_requests <= num_users * 20  # Shouldn't exceed max requests per user
        
        print(f"Load test completed: {len(successful_requests)} successful, "
              f"{len(failed_requests)} failed, {len(rate_limited_requests)} rate limited, "
              f"in {execution_time:.2f}s")

    @pytest.mark.asyncio
    @patch('bot.rate_limiter.time.time')
    async def test_complete_system_integration_all_components(self, mock_time):
        """Test complete integration of all rate limiter components working together"""
        # Test scenario: A complete workflow with multiple users, different request types,
        # time progression, cleanup, and monitoring
        
        mock_time.return_value = 0.0
        
        # Setup multiple users with different behavior patterns
        admin_user = 1001
        power_user = 1002
        regular_user = 1003
        inactive_user = 1004
        
        # Create handlers for different operations
        @rate_limit_commands
        async def admin_command(update, context):
            return f"admin_action_{update.effective_user.id}"
        
        @rate_limit_voice
        async def voice_processing(update, context):
            return f"voice_processed_{update.effective_user.id}"
        
        @rate_limit_general
        async def general_operation(update, context):
            return f"general_op_{update.effective_user.id}"
        
        # Helper function to create update/context pairs
        def create_request(user_id):
            update = MagicMock()
            update.effective_user.id = user_id
            update.message.reply_text = AsyncMock()
            context = MagicMock()
            context.user_data = {}
            return update, context
        
        # === Phase 1: Initial activity (Time 0) ===
        # Admin user makes commands
        for _ in range(5):
            update, context = create_request(admin_user)
            result = await admin_command(update, context)
            assert result == f"admin_action_{admin_user}"
        
        # Power user makes mixed requests
        for _ in range(3):
            update, context = create_request(power_user)
            await voice_processing(update, context)
            
            update, context = create_request(power_user)
            await general_operation(update, context)
        
        # Regular user makes few requests
        update, context = create_request(regular_user)
        await general_operation(update, context)
        
        # Inactive user makes one request
        update, context = create_request(inactive_user)
        await general_operation(update, context)
        
        # Check initial stats
        stats_initial = get_rate_limiter_stats()
        assert stats_initial.active_users.commands >= 1  # Admin user
        assert stats_initial.active_users.voice >= 1     # Power user
        assert stats_initial.active_users.general >= 3   # Power, regular, inactive users
        
        # === Phase 2: Time progression and continued activity (Time 1800 - 30 minutes) ===
        mock_time.return_value = 1800.0
        
        # Only admin and power users remain active
        for _ in range(3):
            update, context = create_request(admin_user)
            await admin_command(update, context)
            
            update, context = create_request(power_user)
            await voice_processing(update, context)
        
        # === Phase 3: Cleanup and monitoring (Time 3600 - 1 hour) ===
        mock_time.return_value = 3600.0
        
        # Perform cleanup - should remove users inactive for > 30 minutes
        cleanup_result = cleanup_all_inactive_users(max_inactive_seconds=1800)
        assert cleanup_result.total > 0  # Some users should be cleaned up
        
        # Check stats after cleanup
        stats_after_cleanup = get_rate_limiter_stats()
        total_after = (stats_after_cleanup.active_users.general + 
                      stats_after_cleanup.active_users.voice + 
                      stats_after_cleanup.active_users.commands)
        total_initial = (stats_initial.active_users.general + 
                        stats_initial.active_users.voice + 
                        stats_initial.active_users.commands)
        assert total_after < total_initial  # Should have fewer active users
        
        # === Phase 4: Rate limit testing ===
        # Test that active users still work after cleanup
        update, context = create_request(admin_user)
        result = await admin_command(update, context)
        assert result == f"admin_action_{admin_user}"
        
        # Test rate limiting by exhausting limits for a user
        test_user = 2000
        request_count = 0
        
        while request_count < 35:  # Exceed typical command limits
            update, context = create_request(test_user)
            
            with patch('bot.rate_limiter.messages') as mock_messages:
                mock_messages.RATE_LIMIT_COMMANDS.format.return_value = "Rate limited!"
                result = await admin_command(update, context)
            
            if result is None:  # Rate limited
                break
            request_count += 1
        
        # Should have hit rate limit before 35 requests
        assert request_count < 35
        assert request_count > 0  # But should have allowed some requests
        
        # === Phase 5: Recovery testing ===
        # Clear rate limits and test recovery
        from bot.rate_limiter import _command_limiter
        _command_limiter.user_requests[test_user].clear()
        
        update, context = create_request(test_user)
        result = await admin_command(update, context)
        assert result == f"admin_action_{test_user}"  # Should work again
        
        # === Final verification ===
        final_stats = get_rate_limiter_stats()
        assert isinstance(final_stats, RateLimiterStats)
        assert hasattr(final_stats, 'active_users')
        assert hasattr(final_stats, 'limits')
        
        # Verify configuration is still intact
        for limiter_type in ['general', 'voice', 'commands']:
            assert limiter_type in final_stats.limits
            assert final_stats.limits[limiter_type].requests > 0
            assert final_stats.limits[limiter_type].window > 0
        
        print(f"Complete integration test passed - "
              f"Cleanup removed {cleanup_result.total} users, "
              f"Rate limited after {request_count} requests")