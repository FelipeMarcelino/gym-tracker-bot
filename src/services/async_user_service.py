"""Async user service for improved database performance"""

from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError

from config.logging_config import get_logger
from database.async_connection import get_async_session_context
from database.models import User
from services.exceptions import DatabaseError, ValidationError, ErrorCode

logger = get_logger(__name__)


class AsyncUserService:
    """Async service for managing users with improved performance"""

    async def is_user_authorized(self, user_id: str) -> bool:
        """Check if a user is authorized to use the bot (async)

        Args:
            user_id: Telegram user ID

        Returns:
            True if authorized, False otherwise
        """
        try:
            async with get_async_session_context() as session:
                stmt = select(User).where(User.user_id == user_id, User.is_active == True)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                return user is not None

        except SQLAlchemyError as e:
            logger.exception("Error checking user authorization")
            # Deny access on database error for security
            return False

    async def is_user_admin(self, user_id: str) -> bool:
        """Check if a user is an administrator (async)

        Args:
            user_id: Telegram user ID

        Returns:
            True if user is admin, False otherwise
        """
        try:
            async with get_async_session_context() as session:
                stmt = select(User).where(
                    User.user_id == user_id,
                    User.is_active == True,
                    User.is_admin == True,
                )
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
                return user is not None

        except SQLAlchemyError as e:
            logger.exception("Error checking admin status")
            return False

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID (async)

        Args:
            user_id: Telegram user ID

        Returns:
            User object if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with get_async_session_context() as session:
                stmt = select(User).where(User.user_id == user_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()

        except SQLAlchemyError as e:
            logger.exception(f"Error getting user {user_id}")
            raise DatabaseError(
                message=f"Failed to get user {user_id}",
                operation="get_user",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to retrieve user information",
                cause=e,
            )

    async def add_user(
        self,
        user_id: str,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        is_admin: bool = False,
        created_by: str = None,
    ) -> User:
        """Add a new user to the system (async)

        Args:
            user_id: Telegram user ID
            first_name: User's first name
            last_name: User's last name
            username: User's username
            is_admin: Whether user should be admin
            created_by: Admin user ID who created this user

        Returns:
            Created User object

        Raises:
            ValidationError: If user data is invalid
            DatabaseError: If database operation fails
        """
        if not user_id or not user_id.strip():
            raise ValidationError(
                message="User ID is required",
                field="user_id",
                value=user_id,
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
                user_message="User ID cannot be empty",
            )

        try:
            async with get_async_session_context() as session:
                # Check if user already exists
                existing_stmt = select(User).where(User.user_id == user_id)
                existing_result = await session.execute(existing_stmt)
                existing_user = existing_result.scalar_one_or_none()

                if existing_user:
                    raise ValidationError(
                        message=f"User {user_id} already exists",
                        field="user_id",
                        value=user_id,
                        error_code=ErrorCode.DUPLICATE_RECORD,
                        user_message="User already exists",
                    )

                # Create new user
                new_user = User(
                    user_id=user_id,
                    first_name=first_name,
                    last_name=last_name,
                    username=username,
                    is_admin=is_admin,
                    is_active=True,
                    created_by=created_by,
                )

                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)

                logger.info(f"User {user_id} added successfully (admin: {is_admin})")
                return new_user

        except ValidationError:
            raise
        except SQLAlchemyError as e:
            logger.exception(f"Error adding user {user_id}")
            raise DatabaseError(
                message=f"Failed to add user {user_id}",
                operation="add_user",
                error_code=ErrorCode.CONSTRAINT_VIOLATION,
                user_message="Failed to create user",
                cause=e,
            )

    async def update_user(
        self,
        user_id: str,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        is_admin: bool = None,
    ) -> Optional[User]:
        """Update user information (async)

        Args:
            user_id: Telegram user ID
            first_name: New first name
            last_name: New last name
            username: New username
            is_admin: New admin status

        Returns:
            Updated User object if found, None otherwise

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with get_async_session_context() as session:
                # Build update values
                update_values = {}
                if first_name is not None:
                    update_values["first_name"] = first_name
                if last_name is not None:
                    update_values["last_name"] = last_name
                if username is not None:
                    update_values["username"] = username
                if is_admin is not None:
                    update_values["is_admin"] = is_admin

                if not update_values:
                    # No updates, just return current user
                    return await self.get_user(user_id)

                # Update user
                stmt = update(User).where(User.user_id == user_id).values(**update_values)
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount == 0:
                    return None

                # Return updated user
                return await self.get_user(user_id)

        except SQLAlchemyError as e:
            logger.exception(f"Error updating user {user_id}")
            raise DatabaseError(
                message=f"Failed to update user {user_id}",
                operation="update_user",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to update user information",
                cause=e,
            )

    async def remove_user(self, user_id: str) -> bool:
        """Remove (deactivate) a user from the system (async)

        Args:
            user_id: Telegram user ID

        Returns:
            True if user was removed, False if not found

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with get_async_session_context() as session:
                stmt = update(User).where(User.user_id == user_id).values(is_active=False)
                result = await session.execute(stmt)
                await session.commit()

                success = result.rowcount > 0
                if success:
                    logger.info(f"User {user_id} removed (deactivated)")

                return success

        except SQLAlchemyError as e:
            logger.exception(f"Error removing user {user_id}")
            raise DatabaseError(
                message=f"Failed to remove user {user_id}",
                operation="remove_user",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to remove user",
                cause=e,
            )

    async def list_users(self, include_inactive: bool = False) -> List[User]:
        """List all users in the system (async)

        Args:
            include_inactive: Whether to include inactive users

        Returns:
            List of User objects

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with get_async_session_context() as session:
                stmt = select(User).order_by(User.is_admin.desc(), User.first_name)

                if not include_inactive:
                    stmt = stmt.where(User.is_active == True)

                result = await session.execute(stmt)
                return list(result.scalars().all())

        except SQLAlchemyError as e:
            logger.exception("Error listing users")
            raise DatabaseError(
                message="Failed to list users",
                operation="list_users",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to retrieve user list",
                cause=e,
            )

    async def get_user_count(self, active_only: bool = True) -> int:
        """Get total number of users (async)

        Args:
            active_only: Count only active users

        Returns:
            Number of users

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with get_async_session_context() as session:
                from sqlalchemy import func

                stmt = select(func.count(User.user_id))

                if active_only:
                    stmt = stmt.where(User.is_active == True)

                result = await session.execute(stmt)
                return result.scalar() or 0

        except SQLAlchemyError as e:
            logger.exception("Error counting users")
            raise DatabaseError(
                message="Failed to count users",
                operation="get_user_count",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to get user statistics",
                cause=e,
            )

    async def batch_update_user_info(self, user_updates: List[dict]) -> int:
        """Batch update multiple users (async)

        Args:
            user_updates: List of dicts with user_id and update fields

        Returns:
            Number of users updated

        Raises:
            DatabaseError: If database operation fails
        """
        if not user_updates:
            return 0

        try:
            async with get_async_session_context() as session:
                updated_count = 0

                for user_update in user_updates:
                    user_id = user_update.pop("user_id", None)
                    if not user_id:
                        continue

                    stmt = update(User).where(User.user_id == user_id).values(**user_update)
                    result = await session.execute(stmt)
                    if result.rowcount > 0:
                        updated_count += 1

                await session.commit()
                logger.info(f"Batch updated {updated_count} users")
                return updated_count

        except SQLAlchemyError as e:
            logger.exception("Error in batch user update")
            raise DatabaseError(
                message="Failed to batch update users",
                operation="batch_update_user_info",
                error_code=ErrorCode.DATABASE_QUERY_FAILED,
                user_message="Failed to update user information",
                cause=e,
            )
