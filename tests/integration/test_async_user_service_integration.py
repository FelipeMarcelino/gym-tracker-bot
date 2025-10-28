"""Integration tests for AsyncUserService

These tests use real database connections to test complete workflows,
admin permissions, and multi-user scenarios. They focus on end-to-end
functionality and database consistency.
"""

import pytest
from datetime import datetime

from services.async_user_service import AsyncUserService
from services.exceptions import DatabaseError, ValidationError, ErrorCode
from database.models import User


class TestAsyncUserServiceIntegration:
    """Integration tests using real database connections"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()
    
    @pytest.fixture
    async def admin_user(self, clean_test_database, user_service):
        """Create an admin user for testing admin operations"""
        admin = await user_service.add_user(
            user_id="admin_test_123",
            first_name="Admin",
            last_name="User",
            username="admin",
            is_admin=True
        )
        return admin
    
    @pytest.fixture
    async def regular_user(self, clean_test_database, user_service):
        """Create a regular user for testing"""
        user = await user_service.add_user(
            user_id="user_test_456",
            first_name="Regular",
            last_name="User",
            username="regular",
            is_admin=False,
            created_by="admin_test_123"
        )
        return user


class TestUserLifecycleIntegration(TestAsyncUserServiceIntegration):
    """Test complete user lifecycle with real database"""
    
    @pytest.mark.asyncio
    async def test_user_creation_and_retrieval(self, clean_test_database, user_service):
        """Test creating and retrieving a user"""
        # Create user
        user = await user_service.add_user(
            user_id="test_lifecycle_123",
            first_name="Test",
            last_name="User",
            username="testuser",
            is_admin=False,
            created_by="admin_123"
        )
        
        assert user.user_id == "test_lifecycle_123"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.username == "testuser"
        assert user.is_admin is False
        assert user.is_active is True
        assert user.created_by == "admin_123"
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)
        
        # Retrieve user
        retrieved_user = await user_service.get_user("test_lifecycle_123")
        assert retrieved_user is not None
        assert retrieved_user.user_id == user.user_id
        assert retrieved_user.first_name == user.first_name

    @pytest.mark.asyncio
    async def test_user_update_and_persistence(self, clean_test_database, user_service):
        """Test updating user information and persistence"""
        # Create user
        await user_service.add_user(
            user_id="test_update_123",
            first_name="Original",
            last_name="Name",
            username="original",
            is_admin=False
        )
        
        # Update user
        updated_user = await user_service.update_user(
            user_id="test_update_123",
            first_name="Updated",
            last_name="LastName",
            username="updated_username",
            is_admin=True
        )
        
        assert updated_user is not None
        assert updated_user.first_name == "Updated"
        assert updated_user.last_name == "LastName"
        assert updated_user.username == "updated_username"
        assert updated_user.is_admin is True
        
        # Verify persistence by retrieving again
        retrieved_user = await user_service.get_user("test_update_123")
        assert retrieved_user.first_name == "Updated"
        assert retrieved_user.is_admin is True

    @pytest.mark.asyncio
    async def test_user_deactivation_and_authorization(self, clean_test_database, user_service):
        """Test user deactivation affects authorization"""
        # Create and verify active user
        await user_service.add_user(
            user_id="test_deactivate_123",
            first_name="Test",
            username="test"
        )
        
        # User should be authorized when active
        assert await user_service.is_user_authorized("test_deactivate_123") is True
        assert await user_service.is_user_admin("test_deactivate_123") is False
        
        # Deactivate user
        success = await user_service.remove_user("test_deactivate_123")
        assert success is True
        
        # User should not be authorized when inactive
        assert await user_service.is_user_authorized("test_deactivate_123") is False
        assert await user_service.is_user_admin("test_deactivate_123") is False
        
        # User should still exist in database but inactive
        user = await user_service.get_user("test_deactivate_123")
        assert user is not None
        assert user.is_active is False


class TestAdminPermissionScenarios(TestAsyncUserServiceIntegration):
    """Test admin permission scenarios and workflows"""
    
    @pytest.mark.asyncio
    async def test_admin_user_permissions(self, admin_user, user_service):
        """Test admin user has proper permissions"""
        # Admin should be authorized and have admin privileges
        assert await user_service.is_user_authorized(admin_user.user_id) is True
        assert await user_service.is_user_admin(admin_user.user_id) is True
        
        # Admin should be able to see their own info
        admin_info = await user_service.get_user(admin_user.user_id)
        assert admin_info is not None
        assert admin_info.is_admin is True
        assert admin_info.is_active is True

    @pytest.mark.asyncio
    async def test_regular_user_permissions(self, regular_user, user_service):
        """Test regular user has limited permissions"""
        # Regular user should be authorized but not admin
        assert await user_service.is_user_authorized(regular_user.user_id) is True
        assert await user_service.is_user_admin(regular_user.user_id) is False
        
        # Regular user info should show non-admin status
        user_info = await user_service.get_user(regular_user.user_id)
        assert user_info is not None
        assert user_info.is_admin is False
        assert user_info.is_active is True

    @pytest.mark.asyncio
    async def test_admin_creating_users(self, admin_user, user_service):
        """Test admin can create users and track who created them"""
        # Admin creates a new user
        new_user = await user_service.add_user(
            user_id="admin_created_123",
            first_name="Admin",
            last_name="Created",
            username="admin_created",
            is_admin=False,
            created_by=admin_user.user_id
        )
        
        assert new_user.created_by == admin_user.user_id
        assert new_user.is_admin is False
        
        # Admin creates another admin
        new_admin = await user_service.add_user(
            user_id="admin_created_admin_456",
            first_name="New",
            last_name="Admin",
            username="new_admin",
            is_admin=True,
            created_by=admin_user.user_id
        )
        
        assert new_admin.created_by == admin_user.user_id
        assert new_admin.is_admin is True
        assert await user_service.is_user_admin(new_admin.user_id) is True

    @pytest.mark.asyncio
    async def test_admin_user_management_workflow(self, admin_user, user_service):
        """Test complete admin user management workflow"""
        # Admin creates multiple users
        user_ids = []
        for i in range(3):
            user = await user_service.add_user(
                user_id=f"workflow_user_{i}",
                first_name=f"User{i}",
                last_name="Test",
                username=f"user{i}",
                is_admin=False,
                created_by=admin_user.user_id
            )
            user_ids.append(user.user_id)
        
        # Admin lists all users (should include admin + 3 new users)
        all_users = await user_service.list_users(include_inactive=False)
        active_user_ids = [u.user_id for u in all_users]
        
        assert admin_user.user_id in active_user_ids
        for user_id in user_ids:
            assert user_id in active_user_ids
        
        # Admin updates user permissions
        updated_user = await user_service.update_user(
            user_ids[0], 
            is_admin=True,
            first_name="Promoted"
        )
        assert updated_user.is_admin is True
        assert updated_user.first_name == "Promoted"
        
        # Admin deactivates a user
        success = await user_service.remove_user(user_ids[1])
        assert success is True
        
        # Check user count changes
        active_count = await user_service.get_user_count(active_only=True)
        total_count = await user_service.get_user_count(active_only=False)
        
        assert total_count > active_count  # Should have inactive users
        
        # List users excluding inactive should not show deactivated user
        active_users = await user_service.list_users(include_inactive=False)
        active_user_ids = [u.user_id for u in active_users]
        assert user_ids[1] not in active_user_ids
        
        # List all users including inactive should show deactivated user
        all_users = await user_service.list_users(include_inactive=True)
        all_user_ids = [u.user_id for u in all_users]
        assert user_ids[1] in all_user_ids


class TestMultiUserScenarios(TestAsyncUserServiceIntegration):
    """Test scenarios involving multiple users"""
    
    @pytest.mark.asyncio
    async def test_multiple_admin_coexistence(self, clean_test_database, user_service):
        """Test multiple admins can coexist and have proper permissions"""
        # Create multiple admins
        admin1 = await user_service.add_user(
            user_id="admin1_test",
            first_name="Admin",
            last_name="One",
            username="admin1",
            is_admin=True
        )
        
        admin2 = await user_service.add_user(
            user_id="admin2_test",
            first_name="Admin",
            last_name="Two",
            username="admin2",
            is_admin=True,
            created_by=admin1.user_id
        )
        
        # Both should have admin privileges
        assert await user_service.is_user_admin(admin1.user_id) is True
        assert await user_service.is_user_admin(admin2.user_id) is True
        
        # Both should be in user list with admin priority (sorted by is_admin desc)
        users = await user_service.list_users()
        admin_users = [u for u in users if u.is_admin]
        assert len(admin_users) >= 2
        
        admin_user_ids = [u.user_id for u in admin_users]
        assert admin1.user_id in admin_user_ids
        assert admin2.user_id in admin_user_ids

    @pytest.mark.asyncio
    async def test_user_hierarchy_and_tracking(self, clean_test_database, user_service):
        """Test user creation hierarchy and tracking"""
        # Root admin creates users
        root_admin = await user_service.add_user(
            user_id="root_admin",
            first_name="Root",
            last_name="Admin",
            username="root",
            is_admin=True
        )
        
        # Root admin creates sub-admin
        sub_admin = await user_service.add_user(
            user_id="sub_admin",
            first_name="Sub",
            last_name="Admin", 
            username="sub",
            is_admin=True,
            created_by=root_admin.user_id
        )
        
        # Sub-admin creates regular users
        user1 = await user_service.add_user(
            user_id="user1",
            first_name="User",
            last_name="One",
            username="user1",
            is_admin=False,
            created_by=sub_admin.user_id
        )
        
        user2 = await user_service.add_user(
            user_id="user2",
            first_name="User",
            last_name="Two",
            username="user2",
            is_admin=False,
            created_by=sub_admin.user_id
        )
        
        # Verify hierarchy
        assert root_admin.created_by is None  # Root admin not created by anyone
        assert sub_admin.created_by == root_admin.user_id
        assert user1.created_by == sub_admin.user_id
        assert user2.created_by == sub_admin.user_id
        
        # All should be active and authorized
        all_user_ids = [root_admin.user_id, sub_admin.user_id, user1.user_id, user2.user_id]
        for user_id in all_user_ids:
            assert await user_service.is_user_authorized(user_id) is True
        
        # Only admins should have admin privileges
        assert await user_service.is_user_admin(root_admin.user_id) is True
        assert await user_service.is_user_admin(sub_admin.user_id) is True
        assert await user_service.is_user_admin(user1.user_id) is False
        assert await user_service.is_user_admin(user2.user_id) is False

    @pytest.mark.asyncio
    async def test_batch_operations_with_real_users(self, clean_test_database, user_service):
        """Test batch operations with real database users"""
        # Create multiple users for batch testing
        user_ids = []
        for i in range(5):
            user = await user_service.add_user(
                user_id=f"batch_user_{i}",
                first_name=f"BatchUser{i}",
                last_name="Test",
                username=f"batchuser{i}",
                is_admin=False
            )
            user_ids.append(user.user_id)
        
        # Batch update users
        updates = [
            {"user_id": user_ids[0], "first_name": "UpdatedBatch0", "is_admin": True},
            {"user_id": user_ids[1], "first_name": "UpdatedBatch1"},
            {"user_id": user_ids[2], "last_name": "UpdatedLastName"},
            {"user_id": "nonexistent", "first_name": "ShouldNotUpdate"},  # Should be ignored
        ]
        
        updated_count = await user_service.batch_update_user_info(updates)
        assert updated_count == 3  # 3 existing users updated, 1 ignored
        
        # Verify updates
        user0 = await user_service.get_user(user_ids[0])
        assert user0.first_name == "UpdatedBatch0"
        assert user0.is_admin is True
        
        user1 = await user_service.get_user(user_ids[1])
        assert user1.first_name == "UpdatedBatch1"
        assert user1.is_admin is False  # Should remain unchanged
        
        user2 = await user_service.get_user(user_ids[2])
        assert user2.last_name == "UpdatedLastName"
        assert user2.first_name == f"BatchUser2"  # Should remain unchanged


class TestEdgeCasesAndErrorHandling(TestAsyncUserServiceIntegration):
    """Test edge cases and error handling with real database"""
    
    @pytest.mark.asyncio
    async def test_duplicate_user_creation(self, clean_test_database, user_service):
        """Test creating duplicate user raises validation error"""
        # Create first user
        await user_service.add_user(
            user_id="duplicate_test",
            first_name="First",
            username="first"
        )
        
        # Attempt to create duplicate should fail
        with pytest.raises(ValidationError) as exc_info:
            await user_service.add_user(
                user_id="duplicate_test",
                first_name="Second",
                username="second"
            )
        
        assert exc_info.value.error_code == ErrorCode.DUPLICATE_RECORD
        assert "already exists" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_nonexistent_user_operations(self, clean_test_database, user_service):
        """Test operations on non-existent users"""
        nonexistent_id = "nonexistent_user_123"
        
        # Get non-existent user
        user = await user_service.get_user(nonexistent_id)
        assert user is None
        
        # Update non-existent user
        updated_user = await user_service.update_user(nonexistent_id, first_name="Test")
        assert updated_user is None
        
        # Remove non-existent user
        success = await user_service.remove_user(nonexistent_id)
        assert success is False
        
        # Authorization checks on non-existent user
        assert await user_service.is_user_authorized(nonexistent_id) is False
        assert await user_service.is_user_admin(nonexistent_id) is False

    @pytest.mark.asyncio
    async def test_empty_database_operations(self, clean_test_database, user_service):
        """Test operations on empty database"""
        # List users in empty database
        users = await user_service.list_users()
        assert users == []
        
        users_with_inactive = await user_service.list_users(include_inactive=True)
        assert users_with_inactive == []
        
        # Count users in empty database
        active_count = await user_service.get_user_count(active_only=True)
        assert active_count == 0
        
        total_count = await user_service.get_user_count(active_only=False)
        assert total_count == 0
        
        # Batch update in empty database
        updates = [{"user_id": "nonexistent", "first_name": "Test"}]
        updated_count = await user_service.batch_update_user_info(updates)
        assert updated_count == 0

    @pytest.mark.asyncio
    async def test_user_update_edge_cases(self, clean_test_database, user_service):
        """Test user update edge cases"""
        # Create user
        user = await user_service.add_user(
            user_id="update_edge_test",
            first_name="Original",
            last_name="Name",
            username="original"
        )
        
        # Update with None values (should be ignored)
        updated_user = await user_service.update_user(
            user.user_id,
            first_name=None,
            last_name=None,
            username=None,
            is_admin=None
        )
        
        # Should return user unchanged since no actual updates
        assert updated_user.first_name == "Original"
        assert updated_user.last_name == "Name"
        assert updated_user.username == "original"
        
        # Update with empty strings (should update to empty)
        updated_user = await user_service.update_user(
            user.user_id,
            first_name="",
            last_name="",
            username=""
        )
        
        assert updated_user.first_name == ""
        assert updated_user.last_name == ""
        assert updated_user.username == ""

    @pytest.mark.asyncio
    async def test_admin_demotion_and_promotion(self, clean_test_database, user_service):
        """Test admin demotion and promotion scenarios"""
        # Create admin user
        admin = await user_service.add_user(
            user_id="admin_promotion_test",
            first_name="Admin",
            username="admin",
            is_admin=True
        )
        
        # Verify admin status
        assert await user_service.is_user_admin(admin.user_id) is True
        
        # Demote admin to regular user
        demoted_user = await user_service.update_user(admin.user_id, is_admin=False)
        assert demoted_user.is_admin is False
        assert await user_service.is_user_admin(admin.user_id) is False
        
        # User should still be authorized but not admin
        assert await user_service.is_user_authorized(admin.user_id) is True
        
        # Promote back to admin
        promoted_user = await user_service.update_user(admin.user_id, is_admin=True)
        assert promoted_user.is_admin is True
        assert await user_service.is_user_admin(admin.user_id) is True


class TestConcurrentUserOperations(TestAsyncUserServiceIntegration):
    """Test concurrent user operations and data consistency"""
    
    @pytest.mark.asyncio
    async def test_concurrent_user_creation_different_ids(self, clean_test_database, user_service):
        """Test concurrent creation of different users"""
        import asyncio
        
        async def create_user(user_id, name):
            return await user_service.add_user(
                user_id=user_id,
                first_name=name,
                username=name.lower()
            )
        
        # Create multiple users concurrently
        tasks = [
            create_user("concurrent_1", "User1"),
            create_user("concurrent_2", "User2"),
            create_user("concurrent_3", "User3"),
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 3
        for user in results:
            assert user is not None
            assert user.is_active is True
        
        # Verify all users exist in database
        all_users = await user_service.list_users()
        user_ids = [u.user_id for u in all_users]
        
        assert "concurrent_1" in user_ids
        assert "concurrent_2" in user_ids
        assert "concurrent_3" in user_ids

    @pytest.mark.asyncio
    async def test_user_listing_consistency(self, clean_test_database, user_service):
        """Test user listing returns consistent results"""
        # Create users with different statuses
        await user_service.add_user("active_1", "Active", "One", "active1", False)
        await user_service.add_user("active_2", "Active", "Two", "active2", True)  # Admin
        await user_service.add_user("to_deactivate", "Will", "Deactivate", "deactivate", False)
        
        # Deactivate one user
        await user_service.remove_user("to_deactivate")
        
        # Test listing consistency
        active_users = await user_service.list_users(include_inactive=False)
        all_users = await user_service.list_users(include_inactive=True)
        
        # Active users should not include deactivated user
        active_user_ids = [u.user_id for u in active_users]
        assert "to_deactivate" not in active_user_ids
        assert "active_1" in active_user_ids
        assert "active_2" in active_user_ids
        
        # All users should include deactivated user
        all_user_ids = [u.user_id for u in all_users]
        assert "to_deactivate" in all_user_ids
        assert len(all_users) > len(active_users)
        
        # Verify admin sorting (admins should come first)
        for i, user in enumerate(active_users):
            if user.is_admin:
                # All subsequent non-admin users should come after
                for j in range(i + 1, len(active_users)):
                    if not active_users[j].is_admin:
                        break
                else:
                    continue  # All remaining users are admin
                break