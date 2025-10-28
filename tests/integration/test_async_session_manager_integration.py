"""Integration tests for AsyncSessionManager

These tests use real database connections to test complete workflows,
session lifecycle management, and database consistency.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from services.async_session_manager import AsyncSessionManager
from services.exceptions import ValidationError, DatabaseError, ErrorCode
from database.models import SessionStatus, WorkoutSession


class TestSessionManagerIntegration:
    """Integration tests using real database connections"""
    
    @pytest.fixture
    def session_manager(self):
        return AsyncSessionManager()

    @pytest.fixture
    async def cleanup_sessions(self):
        """Clean up test sessions after each test"""
        yield
        # Cleanup any test sessions
        manager = AsyncSessionManager()
        try:
            await manager.cleanup_stale_sessions()
        except Exception:
            pass  # Cleanup is best effort


class TestSessionLifecycleIntegration(TestSessionManagerIntegration):
    """Test complete session lifecycle workflows"""
    
    @pytest.mark.asyncio
    async def test_session_creation_and_retrieval(self, session_manager, cleanup_sessions):
        """Test creating a session and retrieving it"""
        user_id = "test_lifecycle_user"
        
        # Create session
        session, is_new = await session_manager.get_or_create_session(user_id)
        
        assert session is not None
        assert isinstance(session, WorkoutSession)
        assert is_new is True
        assert session.user_id == user_id
        assert session.status == SessionStatus.ATIVA
        assert session.audio_count == 0
        
        # Retrieve the same session
        retrieved_session = await session_manager.get_session_by_id(session.session_id, user_id)
        assert retrieved_session is not None
        assert retrieved_session.session_id == session.session_id
        assert retrieved_session.user_id == user_id

    @pytest.mark.asyncio
    async def test_session_reuse_within_timeout(self, session_manager, cleanup_sessions):
        """Test that sessions are reused within timeout window"""
        user_id = "test_reuse_user"
        
        # Create first session
        session1, is_new1 = await session_manager.get_or_create_session(user_id)
        assert is_new1 is True
        
        # Request session again immediately (should reuse)
        session2, is_new2 = await session_manager.get_or_create_session(user_id)
        assert is_new2 is False
        assert session1.session_id == session2.session_id

    @pytest.mark.asyncio
    async def test_session_metadata_update_workflow(self, session_manager, cleanup_sessions):
        """Test updating session metadata"""
        user_id = "test_metadata_user"
        
        # Create session
        session, _ = await session_manager.get_or_create_session(user_id)
        
        # Update metadata
        success = await session_manager.update_session_metadata(
            session.session_id,
            transcription="Test transcription",
            processing_time=1.5,
            model_used="gpt-4"
        )
        
        assert success is True
        
        # Verify update
        updated_session = await session_manager.get_session_by_id(session.session_id)
        assert updated_session.original_transcription == "Test transcription"
        assert updated_session.processing_time_seconds == 1.5
        assert updated_session.llm_model_used == "gpt-4"

    @pytest.mark.asyncio
    async def test_session_history_retrieval(self, session_manager, cleanup_sessions):
        """Test retrieving user session history"""
        user_id = "test_history_user"
        
        # Create multiple sessions by finishing and creating new ones
        sessions = []
        for i in range(3):
            session, _ = await session_manager.get_or_create_session(user_id)
            sessions.append(session)
            
            # Finish the session to allow creating a new one
            await session_manager.batch_finish_sessions([session.session_id])
        
        # Get session history
        history = await session_manager.get_user_session_history(user_id, limit=5)
        
        assert len(history) >= 3
        assert all(s.user_id == user_id for s in history)
        
        # Test including only finished sessions
        finished_history = await session_manager.get_user_session_history(
            user_id, 
            limit=5, 
            include_active=False
        )
        assert len(finished_history) >= 3
        assert all(s.status == SessionStatus.FINALIZADA for s in finished_history)


class TestMultiUserSessionScenarios(TestSessionManagerIntegration):
    """Test multi-user session scenarios"""
    
    @pytest.mark.asyncio
    async def test_concurrent_user_sessions(self, session_manager, cleanup_sessions):
        """Test multiple users creating sessions concurrently"""
        user_ids = [f"concurrent_user_{i}" for i in range(5)]
        
        # Create sessions for all users concurrently
        tasks = [session_manager.get_or_create_session(uid) for uid in user_ids]
        results = await asyncio.gather(*tasks)
        
        # Verify each user got their own session
        sessions = [result[0] for result in results]
        is_new_flags = [result[1] for result in results]
        
        assert all(is_new for is_new in is_new_flags)
        assert len(set(s.session_id for s in sessions)) == 5  # All unique sessions
        
        # Verify user isolation
        for i, session in enumerate(sessions):
            assert session.user_id == user_ids[i]

    @pytest.mark.asyncio
    async def test_user_session_isolation(self, session_manager, cleanup_sessions):
        """Test that users cannot access each other's sessions"""
        user1_id = "isolation_user_1"
        user2_id = "isolation_user_2"
        
        # Create sessions for both users
        session1, _ = await session_manager.get_or_create_session(user1_id)
        session2, _ = await session_manager.get_or_create_session(user2_id)
        
        # User1 should not be able to access user2's session
        result = await session_manager.get_session_by_id(session2.session_id, user1_id)
        assert result is None
        
        # User2 should not be able to access user1's session
        result = await session_manager.get_session_by_id(session1.session_id, user2_id)
        assert result is None
        
        # But they should access their own sessions
        result1 = await session_manager.get_session_by_id(session1.session_id, user1_id)
        assert result1 is not None
        assert result1.session_id == session1.session_id
        
        result2 = await session_manager.get_session_by_id(session2.session_id, user2_id)
        assert result2 is not None
        assert result2.session_id == session2.session_id

    @pytest.mark.asyncio
    async def test_batch_operations_across_users(self, session_manager, cleanup_sessions):
        """Test batch operations across multiple users"""
        user_ids = [f"batch_user_{i}" for i in range(3)]
        
        # Create sessions for all users
        session_ids = []
        for user_id in user_ids:
            session, _ = await session_manager.get_or_create_session(user_id)
            session_ids.append(session.session_id)
        
        # Batch finish all sessions
        finished_count = await session_manager.batch_finish_sessions(session_ids)
        assert finished_count == 3
        
        # Verify all sessions are finished
        for session_id in session_ids:
            session = await session_manager.get_session_by_id(session_id)
            assert session.status == SessionStatus.FINALIZADA
            assert session.end_time is not None


class TestSessionTimeoutAndCleanup(TestSessionManagerIntegration):
    """Test session timeout and cleanup scenarios"""
    
    @pytest.mark.asyncio
    async def test_stale_session_cleanup(self, session_manager, cleanup_sessions):
        """Test cleaning up stale sessions"""
        user_id = "test_cleanup_user"
        
        # Create a session
        session, _ = await session_manager.get_or_create_session(user_id)
        
        # Manually mark it as old by updating the database
        from database.async_connection import get_async_session_context
        from sqlalchemy import update
        
        old_time = datetime.now() - timedelta(hours=5)
        
        async with get_async_session_context() as db_session:
            stmt = update(WorkoutSession).where(
                WorkoutSession.session_id == session.session_id
            ).values(
                date=old_time.date(),
                start_time=old_time.time(),
                last_update=old_time
            )
            await db_session.execute(stmt)
            await db_session.commit()
        
        # Run cleanup
        cleaned_count = await session_manager.cleanup_stale_sessions()
        assert cleaned_count >= 1
        
        # Verify session is now finished
        updated_session = await session_manager.get_session_by_id(session.session_id)
        assert updated_session.status == SessionStatus.FINALIZADA
        assert updated_session.end_time is not None
        assert updated_session.duration_minutes is not None
        assert updated_session.duration_minutes >= 0

    @pytest.mark.asyncio
    async def test_active_session_count_accuracy(self, session_manager, cleanup_sessions):
        """Test active session counting accuracy"""
        user_ids = [f"count_user_{i}" for i in range(3)]
        
        # Get initial count
        initial_count = await session_manager.get_active_sessions_count()
        
        # Create sessions
        session_ids = []
        for user_id in user_ids:
            session, _ = await session_manager.get_or_create_session(user_id)
            session_ids.append(session.session_id)
        
        # Count should increase
        new_count = await session_manager.get_active_sessions_count()
        assert new_count >= initial_count + 3
        
        # Finish some sessions
        await session_manager.batch_finish_sessions(session_ids[:2])
        
        # Count should decrease
        final_count = await session_manager.get_active_sessions_count()
        assert final_count <= new_count - 2

    @pytest.mark.asyncio
    async def test_session_timeout_edge_cases(self, session_manager, cleanup_sessions):
        """Test session timeout edge cases"""
        user_id = "timeout_edge_user"
        
        # Create session
        session, _ = await session_manager.get_or_create_session(user_id)
        
        # Update session to be right at the timeout boundary
        from database.async_connection import get_async_session_context
        from sqlalchemy import update
        from config.settings import settings
        
        boundary_time = datetime.now() - timedelta(hours=settings.SESSION_TIMEOUT_HOURS)
        
        async with get_async_session_context() as db_session:
            stmt = update(WorkoutSession).where(
                WorkoutSession.session_id == session.session_id
            ).values(
                date=boundary_time.date(),
                start_time=boundary_time.time(),
                last_update=boundary_time
            )
            await db_session.execute(stmt)
            await db_session.commit()
        
        # Try to get session again - should create new one due to timeout
        new_session, is_new = await session_manager.get_or_create_session(user_id)
        assert is_new is True
        assert new_session.session_id != session.session_id


class TestSessionValidationEdgeCases(TestSessionManagerIntegration):
    """Test session validation and edge cases"""
    
    @pytest.mark.asyncio
    async def test_invalid_user_id_validation(self, session_manager, cleanup_sessions):
        """Test validation with invalid user IDs"""
        invalid_user_ids = [None, "", "   ", "\t\n"]
        
        for invalid_id in invalid_user_ids:
            with pytest.raises(ValidationError) as exc_info:
                await session_manager.get_or_create_session(invalid_id)
            
            assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD

    @pytest.mark.asyncio
    async def test_nonexistent_session_operations(self, session_manager, cleanup_sessions):
        """Test operations on nonexistent sessions"""
        nonexistent_id = 999999
        
        # Get nonexistent session
        result = await session_manager.get_session_by_id(nonexistent_id)
        assert result is None
        
        # Update nonexistent session
        success = await session_manager.update_session_metadata(nonexistent_id, transcription="test")
        assert success is False
        
        # Batch finish including nonexistent session
        finished_count = await session_manager.batch_finish_sessions([nonexistent_id])
        assert finished_count == 0

    @pytest.mark.asyncio
    async def test_session_metadata_edge_cases(self, session_manager, cleanup_sessions):
        """Test session metadata with edge cases"""
        user_id = "metadata_edge_user"
        
        # Create session
        session, _ = await session_manager.get_or_create_session(user_id)
        
        # Test with various metadata combinations
        edge_cases = [
            {"transcription": ""},  # Empty transcription
            {"processing_time": 0.0},  # Zero processing time
            {"model_used": ""},  # Empty model
            {"transcription": "Very long transcription " * 100},  # Long transcription
            {"processing_time": 999.9},  # Large processing time
            {},  # No metadata
        ]
        
        for metadata in edge_cases:
            success = await session_manager.update_session_metadata(session.session_id, **metadata)
            assert success in [True, False]  # Should handle gracefully

    @pytest.mark.asyncio
    async def test_session_history_edge_cases(self, session_manager, cleanup_sessions):
        """Test session history with edge cases"""
        user_id = "history_edge_user"
        
        # Test with no sessions
        history = await session_manager.get_user_session_history("nonexistent_user")
        assert history == []
        
        # Create one session
        session, _ = await session_manager.get_or_create_session(user_id)
        
        # Test various limit values
        limit_cases = [0, 1, 100]
        for limit in limit_cases:
            history = await session_manager.get_user_session_history(user_id, limit=limit)
            assert isinstance(history, list)
            if limit == 0:
                assert len(history) == 0
            else:
                assert len(history) <= limit


class TestConcurrentOperationsIntegration(TestSessionManagerIntegration):
    """Test concurrent operations with real database"""
    
    @pytest.mark.asyncio
    async def test_concurrent_session_creation_same_user(self, session_manager, cleanup_sessions):
        """Test concurrent session creation for same user"""
        user_id = "concurrent_same_user"
        
        # Create multiple concurrent requests
        tasks = [
            session_manager.get_or_create_session(user_id),
            session_manager.get_or_create_session(user_id),
            session_manager.get_or_create_session(user_id),
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Should get same session for all requests (due to locking)
        sessions = [result[0] for result in results]
        is_new_flags = [result[1] for result in results]
        
        # First one should be new, others should be reused
        assert sum(is_new_flags) == 1
        assert all(s.session_id == sessions[0].session_id for s in sessions)

    @pytest.mark.asyncio
    async def test_concurrent_metadata_updates(self, session_manager, cleanup_sessions):
        """Test concurrent metadata updates"""
        user_id = "concurrent_metadata_user"
        
        # Create session
        session, _ = await session_manager.get_or_create_session(user_id)
        
        # Concurrent metadata updates
        tasks = [
            session_manager.update_session_metadata(session.session_id, transcription=f"text_{i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All updates should complete successfully
        assert all(result in [True, False] for result in results)
        
        # Final session should have some valid metadata
        final_session = await session_manager.get_session_by_id(session.session_id)
        assert final_session.original_transcription is not None

    @pytest.mark.asyncio
    async def test_concurrent_cleanup_operations(self, session_manager, cleanup_sessions):
        """Test concurrent cleanup operations"""
        # Create some sessions first
        user_ids = [f"cleanup_concurrent_user_{i}" for i in range(3)]
        for user_id in user_ids:
            await session_manager.get_or_create_session(user_id)
        
        # Run concurrent cleanup operations
        tasks = [
            session_manager.cleanup_stale_sessions(),
            session_manager.get_active_sessions_count(),
            session_manager.cleanup_stale_sessions(),
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Should complete without errors
        assert len(results) == 3
        assert all(isinstance(r, int) for r in results)


class TestDatabaseConsistencyIntegration(TestSessionManagerIntegration):
    """Test database consistency and integrity"""
    
    @pytest.mark.asyncio
    async def test_session_data_consistency(self, session_manager, cleanup_sessions):
        """Test session data remains consistent across operations"""
        user_id = "consistency_user"
        
        # Create session
        session, _ = await session_manager.get_or_create_session(user_id)
        original_session_id = session.session_id
        original_user_id = session.user_id
        original_date = session.date
        
        # Update metadata
        await session_manager.update_session_metadata(
            session.session_id,
            transcription="Test consistency"
        )
        
        # Retrieve and verify consistency
        updated_session = await session_manager.get_session_by_id(session.session_id)
        assert updated_session.session_id == original_session_id
        assert updated_session.user_id == original_user_id
        assert updated_session.date == original_date
        assert updated_session.original_transcription == "Test consistency"

    @pytest.mark.asyncio
    async def test_batch_operation_atomicity(self, session_manager, cleanup_sessions):
        """Test batch operations maintain data integrity"""
        user_ids = [f"atomic_user_{i}" for i in range(3)]
        
        # Create sessions
        session_ids = []
        for user_id in user_ids:
            session, _ = await session_manager.get_or_create_session(user_id)
            session_ids.append(session.session_id)
        
        # Batch finish with mix of valid and invalid IDs
        mixed_ids = session_ids + [999999, 999998]  # Add nonexistent IDs
        finished_count = await session_manager.batch_finish_sessions(mixed_ids)
        
        # Should finish only the valid sessions
        assert finished_count == 3
        
        # Verify only valid sessions were affected
        for session_id in session_ids:
            session = await session_manager.get_session_by_id(session_id)
            assert session.status == SessionStatus.FINALIZADA

    @pytest.mark.asyncio
    async def test_session_state_transitions(self, session_manager, cleanup_sessions):
        """Test valid session state transitions"""
        user_id = "state_transition_user"
        
        # Create session (ATIVA)
        session, _ = await session_manager.get_or_create_session(user_id)
        assert session.status == SessionStatus.ATIVA
        
        # Finish session (ATIVA -> FINALIZADA)
        finished_count = await session_manager.batch_finish_sessions([session.session_id])
        assert finished_count == 1
        
        # Verify transition
        finished_session = await session_manager.get_session_by_id(session.session_id)
        assert finished_session.status == SessionStatus.FINALIZADA
        assert finished_session.end_time is not None
        
        # Try to finish again (should not affect count)
        finished_again = await session_manager.batch_finish_sessions([session.session_id])
        assert finished_again == 0  # Already finished