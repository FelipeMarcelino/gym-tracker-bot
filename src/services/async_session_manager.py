"""Async session manager for workout sessions"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from config.logging_config import get_logger
from config.settings import settings
from database.async_connection import get_async_session_context
from database.models import SessionStatus, WorkoutSession
from services.exceptions import DatabaseError, ErrorCode, ValidationError

logger = get_logger(__name__)


class AsyncSessionManager:
    """Async manager for workout sessions with optimized database operations"""

    def __init__(self):
        self._user_locks = {}
        self._lock_creation_lock = asyncio.Lock()

    async def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        if user_id not in self._user_locks:
            async with self._lock_creation_lock:
                if user_id not in self._user_locks:
                    self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    async def get_or_create_session(
        self, user_id: Union[str, int]
    ) -> Tuple[WorkoutSession, bool]:
        """Get existing active session or create a new one (async)

        Args:
            user_id: User ID

        Returns:
            Tuple of (WorkoutSession, is_new_session)

        Raises:
            ValidationError: If user_id is invalid
            DatabaseError: If database operation fails

        """
        original_user_id = user_id
        if user_id is None:
            normalized_user_id = ''
        else:
            normalized_user_id = str(user_id).strip()

        if not normalized_user_id:
            raise ValidationError(
                message='User ID is required',
                field='user_id',
                value=original_user_id,
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                user_message='User ID cannot be empty',
            )

        # Clean up stale sessions before checking for active ones
        await self.cleanup_stale_sessions()

        user_lock = await self._get_user_lock(normalized_user_id)

        async with user_lock:
            async with get_async_session_context() as session:
                # Look for active session
                now = datetime.now()
                timeout_threshold = now - timedelta(
                    hours=settings.SESSION_TIMEOUT_HOURS
                )

                # Find the most recent session for this user
                stmt = (
                    select(WorkoutSession)
                    .where(WorkoutSession.user_id == normalized_user_id)
                    .order_by(
                        WorkoutSession.date.desc(),
                        WorkoutSession.start_time.desc(),
                    )
                    .limit(1)
                )
                result = await session.execute(stmt)
                last_session = result.scalar_one_or_none()

                # Check if we can reuse the last session
                if last_session and self._is_session_active(
                    last_session, timeout_threshold
                ):
                    logger.info(
                        f'Reusing active session {last_session.session_id} for user {normalized_user_id}'
                    )
                    return last_session, False

                # Create new session
                new_session = WorkoutSession(
                    user_id=normalized_user_id,
                    date=now.date(),
                    start_time=now.time(),
                    status=SessionStatus.ATIVA,
                    audio_count=0,
                )

                session.add(new_session)
                await session.commit()
                await session.refresh(new_session)

                logger.info(
                    f'Created new session {new_session.session_id} for user {normalized_user_id}'
                )
                return new_session, True

    def _is_session_active(
        self, session: WorkoutSession, timeout_threshold: datetime
    ) -> bool:
        """Check if a session is still active based on timeout"""
        if session.status == SessionStatus.FINALIZADA:
            return False

        session_datetime = datetime.combine(session.date, session.start_time)
        return session_datetime >= timeout_threshold

    async def update_session_metadata(
        self,
        session_id: int,
        transcription: str = None,
        processing_time: float = None,
        model_used: str = None,
        **kwargs,
    ) -> bool:
        """Update session metadata efficiently (async)

        Args:
            session_id: Session ID
            transcription: Latest transcription text
            processing_time: Processing time for this operation
            model_used: Model used for processing
            **kwargs: Additional metadata fields

        Returns:
            True if successful

        Raises:
            DatabaseError: If database operation fails

        """
        if not session_id or session_id <= 0:
            return False

        try:
            async with get_async_session_context() as session:
                # Build update values
                update_values = {}

                if transcription:
                    update_values['original_transcription'] = transcription

                if processing_time is not None:
                    update_values['processing_time_seconds'] = processing_time

                if model_used:
                    update_values['llm_model_used'] = model_used

                # Add any additional fields
                for key, value in kwargs.items():
                    if hasattr(WorkoutSession, key):
                        update_values[key] = value

                if not update_values:
                    return True  # Nothing to update

                # Perform update
                stmt = (
                    update(WorkoutSession)
                    .where(WorkoutSession.session_id == session_id)
                    .values(**update_values)
                )
                result = await session.execute(stmt)
                await session.commit()

                success = result.rowcount > 0
                if success:
                    logger.debug(f'Updated metadata for session {session_id}')

                return success

        except SQLAlchemyError as e:
            logger.exception(
                f'Error updating session metadata for session {session_id}'
            )
            raise DatabaseError(
                message=f'Failed to update session {session_id} metadata',
                operation='update_session_metadata',
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message='Failed to update session information',
                cause=e,
            )

    async def get_active_sessions_count(self) -> int:
        """Get count of currently active sessions (async)

        Returns:
            Number of active sessions

        """
        try:
            async with get_async_session_context() as session:
                from sqlalchemy import func

                now = datetime.now()
                timeout_threshold = now - timedelta(
                    hours=settings.SESSION_TIMEOUT_HOURS
                )

                # Count sessions that are either:
                # 1. Explicitly marked as ATIVA, OR
                # 2. Not explicitly finished AND within timeout window
                stmt = select(func.count(WorkoutSession.session_id)).where(
                    (WorkoutSession.status == SessionStatus.ATIVA)
                    & (WorkoutSession.last_update > timeout_threshold),
                )

                result = await session.execute(stmt)
                return result.scalar() or 0

        except SQLAlchemyError:
            logger.exception('Error counting active sessions')
            return 0  # Return 0 on error rather than raising

    async def cleanup_stale_sessions(self) -> int:
        """Mark stale sessions as finished (async)

        Returns:
            Number of sessions cleaned up

        """
        try:
            async with get_async_session_context() as session:
                now = datetime.now()
                timeout_threshold = now - timedelta(
                    hours=settings.SESSION_TIMEOUT_HOURS
                )

                # First, find stale sessions to calculate their durations
                find_stmt = select(WorkoutSession).where(
                    (WorkoutSession.status == SessionStatus.ATIVA)
                    & (WorkoutSession.last_update < timeout_threshold),
                )

                result = await session.execute(find_stmt)
                stale_sessions = result.scalars().all()

                if not stale_sessions:
                    return 0

                # Update each session with calculated duration
                cleaned_count = 0
                for stale_session in stale_sessions:
                    # Calculate duration from start_time to timeout_threshold
                    start_datetime = datetime.combine(
                        stale_session.date, stale_session.start_time
                    )
                    # Use timeout_threshold as end time (when session should have ended)
                    duration_minutes = int(
                        (timeout_threshold - start_datetime).total_seconds()
                        // 60
                    )

                    # Ensure duration is not negative
                    duration_minutes = max(0, duration_minutes)

                    # Update the session
                    stale_session.status = SessionStatus.FINALIZADA
                    stale_session.end_time = timeout_threshold.time()
                    stale_session.duration_minutes = duration_minutes

                    session.add(stale_session)
                    cleaned_count += 1

                await session.commit()

                if cleaned_count > 0:
                    logger.info(f'Cleaned up {cleaned_count} stale sessions')

                return cleaned_count

        except SQLAlchemyError as e:
            logger.exception('Error cleaning up stale sessions')
            raise DatabaseError(
                message='Failed to cleanup stale sessions',
                operation='cleanup_stale_sessions',
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message='Failed to cleanup old sessions',
                cause=e,
            )

    async def get_session_by_id(
        self, session_id: int, user_id: str = None
    ) -> Optional[WorkoutSession]:
        """Get a specific session by ID with optional user validation (async)

        Args:
            session_id: Session ID
            user_id: Optional user ID for access control

        Returns:
            WorkoutSession if found, None otherwise

        """
        try:
            async with get_async_session_context() as session:
                stmt = select(WorkoutSession).where(
                    WorkoutSession.session_id == session_id
                )

                if user_id:
                    stmt = stmt.where(WorkoutSession.user_id == user_id)

                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.exception(f'Error getting session {session_id}')
            raise DatabaseError(
                message=f'Failed to get session {session_id}',
                operation='get_session_by_id',
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message='Failed to retrieve session',
                cause=e,
            )

    async def get_user_session_history(
        self,
        user_id: str,
        limit: int = 10,
        include_active: bool = True,
    ) -> list[WorkoutSession]:
        """Get user's session history (async)

        Args:
            user_id: User ID
            limit: Maximum number of sessions to return
            include_active: Whether to include active sessions

        Returns:
            List of WorkoutSession objects

        """
        try:
            async with get_async_session_context() as session:
                stmt = (
                    select(WorkoutSession)
                    .where(WorkoutSession.user_id == user_id)
                    .order_by(
                        WorkoutSession.date.desc(),
                        WorkoutSession.start_time.desc(),
                    )
                    .limit(limit)
                )

                if not include_active:
                    stmt = stmt.where(
                        WorkoutSession.status == SessionStatus.FINALIZADA
                    )

                result = await session.execute(stmt)
                return list(result.scalars().all())

        except SQLAlchemyError as e:
            logger.exception(
                f'Error getting session history for user {user_id}'
            )
            raise DatabaseError(
                message=f'Failed to get session history for user {user_id}',
                operation='get_user_session_history',
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message='Failed to retrieve session history',
                cause=e,
            )

    async def batch_finish_sessions(self, session_ids: list[int]) -> int:
        """Batch finish multiple sessions (async)

        Args:
            session_ids: List of session IDs to finish

        Returns:
            Number of sessions successfully finished

        """
        if not session_ids:
            return 0

        try:
            async with get_async_session_context() as session:
                end_time = datetime.now().time()

                stmt = (
                    update(WorkoutSession)
                    .where(
                        WorkoutSession.session_id.in_(session_ids),
                        WorkoutSession.status == SessionStatus.ATIVA,
                    )
                    .values(
                        status=SessionStatus.FINALIZADA,
                        end_time=end_time,
                    )
                )

                result = await session.execute(stmt)
                await session.commit()

                finished_count = result.rowcount
                if finished_count > 0:
                    logger.info(f'Batch finished {finished_count} sessions')

                return finished_count

        except SQLAlchemyError as e:
            logger.exception(f'Error batch finishing sessions: {session_ids}')
            raise DatabaseError(
                message='Failed to batch finish sessions',
                operation='batch_finish_sessions',
                error_code=ErrorCode.TRANSACTION_FAILED,
                user_message='Failed to finish sessions',
                cause=e,
            )
