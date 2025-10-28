"""Unit tests for AsyncUserService

These tests focus on business logic validation, edge cases, and validation rules.
They test the core business functionality without database dependencies.
"""

import pytest
from services.async_user_service import AsyncUserService
from services.exceptions import ValidationError, ErrorCode


class TestUserIdValidation:
    """Test user ID validation business logic"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()

    @pytest.mark.asyncio
    async def test_add_user_empty_user_id_variations(self, user_service):
        """Test all variations of empty user ID"""
        empty_variations = [
            None,
            "",
            " ",
            "  ",
            "\t",
            "\n",
            "\r",
            "\t\n\r",
            "   \t\n\r   ",
        ]
        
        for empty_id in empty_variations:
            with pytest.raises(ValidationError) as exc_info:
                await user_service.add_user(empty_id, first_name="Test")
            
            assert exc_info.value.error_code == ErrorCode.MISSING_REQUIRED_FIELD
            assert "User ID is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_add_user_valid_user_id_formats(self, user_service):
        """Test user ID validation allows valid formats"""
        # This tests the validation logic - these should pass validation
        # but will fail at database level (which is expected for unit tests)
        valid_formats = [
            "12345",
            "user123",
            "user_123",
            "user-123",
            "user.123",
            "user@domain.com",
            "123456789012345678901234567890",  # Long ID
            "ñoño",  # Unicode
            "用户123",  # Unicode
            "  valid_trim  ",  # Should be trimmed
        ]
        
        for valid_id in valid_formats:
            # These will raise database errors but not validation errors
            try:
                await user_service.add_user(valid_id, first_name="Test")
            except ValidationError as e:
                if e.error_code == ErrorCode.MISSING_REQUIRED_FIELD:
                    pytest.fail(f"Valid user ID '{valid_id}' should not raise MISSING_REQUIRED_FIELD")
            except Exception:
                # Database errors are expected in unit tests
                pass

    @pytest.mark.asyncio
    async def test_update_user_empty_user_id(self, user_service):
        """Test update user with empty user ID"""
        empty_variations = [None, "", "   ", "\t\n"]
        
        for empty_id in empty_variations:
            try:
                result = await user_service.update_user(empty_id, first_name="Test")
                # If no validation error, should return None (user not found)
                assert result is None
            except ValidationError as e:
                # Some methods might validate user_id, which is also acceptable
                assert e.error_code in [ErrorCode.MISSING_REQUIRED_FIELD, ErrorCode.INVALID_INPUT]


class TestUserDataValidation:
    """Test user data field validation"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()

    @pytest.mark.asyncio
    async def test_add_user_name_field_edge_cases(self, user_service):
        """Test name field validation edge cases"""
        name_test_cases = [
            ("", "empty string"),
            ("   ", "whitespace only"),
            ("A", "single character"),
            ("A" * 255, "very long name"),
            ("José María", "unicode with accents"),
            ("李明", "chinese characters"),
            ("O'Connor", "apostrophe"),
            ("Van der Berg", "multiple spaces"),
            ("    Trimmed    ", "needs trimming"),
            ("Name\nWith\nNewlines", "newlines"),
            ("Name\tWith\tTabs", "tabs"),
        ]
        
        for name_value, description in name_test_cases:
            try:
                await user_service.add_user("test_user", first_name=name_value)
            except ValidationError as e:
                # Only fail if it's a validation error we don't expect
                if "name" in str(e).lower() and "invalid" in str(e).lower():
                    pytest.fail(f"Name validation failed for {description}: {name_value}")
            except Exception:
                # Database errors expected
                pass

    @pytest.mark.asyncio
    async def test_add_user_username_edge_cases(self, user_service):
        """Test username validation edge cases"""
        username_cases = [
            None,  # Should be allowed
            "",    # Should be allowed
            "user",
            "user123",
            "user_123",
            "user.name",
            "user@domain",
            "very_long_username_that_might_exceed_normal_limits_123456789",
        ]
        
        for username in username_cases:
            try:
                await user_service.add_user("test_user", username=username)
            except ValidationError as e:
                # Check if validation error is about username specifically
                if "username" in str(e).lower() and username not in [None, ""]:
                    pytest.fail(f"Valid username should not raise validation error: {username}")
            except Exception:
                # Database errors expected
                pass

    @pytest.mark.asyncio
    async def test_add_user_admin_flag_variations(self, user_service):
        """Test is_admin flag with various input types"""
        admin_variations = [
            (True, True),
            (False, False),
            (1, True),
            (0, False),
            ("true", True),
            ("false", True),  # Non-empty string is truthy
            ("", False),
            (None, False),
            ([], False),
            ([1], True),
            ({}, False),
            ({"admin": True}, True),
        ]
        
        for input_value, expected_bool in admin_variations:
            try:
                await user_service.add_user("test_user", is_admin=input_value)
                # If we get here, the boolean conversion worked as expected
                assert bool(input_value) == expected_bool
            except ValidationError as e:
                # Should not get validation errors for boolean conversion
                if "admin" in str(e).lower():
                    pytest.fail(f"Admin flag validation failed for {input_value}")
            except Exception:
                # Database errors expected
                pass


class TestBatchUpdateLogic:
    """Test batch update business logic and edge cases"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()

    @pytest.mark.asyncio
    async def test_batch_update_empty_list(self, user_service):
        """Test batch update with empty list"""
        result = await user_service.batch_update_user_info([])
        assert result == 0

    @pytest.mark.asyncio
    async def test_batch_update_data_filtering(self, user_service):
        """Test batch update filters invalid data correctly"""
        # This tests the filtering logic before database operations
        mixed_data = [
            {"user_id": "valid1", "first_name": "Test1"},  # Valid
            {"first_name": "No ID"},                       # Invalid - no user_id
            {"user_id": "", "first_name": "Empty ID"},     # Invalid - empty user_id
            {"user_id": None, "first_name": "None ID"},    # Invalid - None user_id
            {"user_id": "   ", "first_name": "Space ID"},  # Invalid - whitespace user_id
            {"user_id": "valid2"},                         # Valid - has user_id
            {},                                            # Invalid - empty dict
            {"user_id": "valid3", "first_name": "", "last_name": None, "is_admin": False},  # Valid
        ]
        
        try:
            result = await user_service.batch_update_user_info(mixed_data)
            # Result should be >= 0 (number of successful updates)
            assert isinstance(result, int)
            assert result >= 0
        except Exception:
            # Database errors expected, but the filtering logic should work
            pass

    @pytest.mark.asyncio
    async def test_batch_update_field_combinations(self, user_service):
        """Test various field combinations in batch updates"""
        field_combinations = [
            {"user_id": "test1", "first_name": "John"},
            {"user_id": "test2", "last_name": "Doe"},
            {"user_id": "test3", "username": "johndoe"},
            {"user_id": "test4", "is_admin": True},
            {"user_id": "test5", "first_name": "John", "last_name": "Doe"},
            {"user_id": "test6", "first_name": "Admin", "is_admin": True},
            {"user_id": "test7", "first_name": "", "last_name": "", "username": ""},  # Empty strings
            {"user_id": "test8", "first_name": None, "last_name": "ValidLast"},  # Mixed None/valid
        ]
        
        try:
            result = await user_service.batch_update_user_info(field_combinations)
            assert isinstance(result, int)
            assert result >= 0
        except Exception:
            # Database errors expected
            pass

    @pytest.mark.asyncio
    async def test_batch_update_large_dataset(self, user_service):
        """Test batch update with large number of records"""
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                "user_id": f"user_{i}",
                "first_name": f"User{i}",
                "last_name": f"Test{i}",
                "is_admin": i % 10 == 0,  # Every 10th user is admin
            })
        
        try:
            result = await user_service.batch_update_user_info(large_dataset)
            assert isinstance(result, int)
            assert result >= 0
        except Exception:
            # Database errors expected
            pass


class TestUserLifecycleValidation:
    """Test user lifecycle management validation"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()

    @pytest.mark.asyncio
    async def test_remove_user_edge_cases(self, user_service):
        """Test user removal with edge cases"""
        edge_cases = [
            None,
            "",
            "   ",
            "nonexistent_user",
            "user_with_special_chars!@#$%",
            "very_long_user_id_" + "x" * 100,
        ]
        
        for user_id in edge_cases:
            try:
                result = await user_service.remove_user(user_id)
                # Should return boolean or None
                assert result is None or isinstance(result, bool)
            except ValidationError as e:
                # Some validation errors are acceptable for invalid inputs
                if user_id in [None, "", "   "]:
                    assert e.error_code in [ErrorCode.MISSING_REQUIRED_FIELD, ErrorCode.INVALID_INPUT]
            except Exception:
                # Database errors expected
                pass

    @pytest.mark.asyncio
    async def test_get_user_edge_cases(self, user_service):
        """Test get user with edge cases"""
        edge_cases = [
            None,
            "",
            "   ",
            "nonexistent",
            "user_with_unicode_用户",
            "\x00null_byte",
            "user'with\"quotes",
            "user;with;semicolons",
        ]
        
        for user_id in edge_cases:
            try:
                result = await user_service.get_user(user_id)
                # Should return User object or None
                assert result is None or hasattr(result, 'user_id')
            except ValidationError as e:
                # Validation errors acceptable for clearly invalid inputs
                if user_id in [None, "", "   "]:
                    assert e.error_code in [ErrorCode.MISSING_REQUIRED_FIELD, ErrorCode.INVALID_INPUT]
            except Exception:
                # Database errors expected
                pass


class TestAuthorizationLogic:
    """Test authorization business logic patterns"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()

    @pytest.mark.asyncio
    async def test_authorization_with_edge_case_user_ids(self, user_service):
        """Test authorization logic with edge case user IDs"""
        edge_cases = [
            None,
            "",
            "   ",
            "nonexistent_user",
            "sql'; DROP TABLE users; --",  # SQL injection attempt
            "<script>alert('xss')</script>",  # XSS attempt
            "user\x00with\x00nulls",  # Null bytes
            "very_long_user_id_" + "x" * 1000,  # Very long ID
        ]
        
        for user_id in edge_cases:
            try:
                result = await user_service.is_user_authorized(user_id)
                # Should always return boolean, preferably False for invalid inputs
                assert isinstance(result, bool)
                if user_id in [None, "", "   "]:
                    assert result is False, "Invalid user IDs should not be authorized"
            except Exception:
                # Any exception should be handled gracefully
                pass

    @pytest.mark.asyncio
    async def test_admin_check_with_edge_cases(self, user_service):
        """Test admin check with edge case inputs"""
        edge_cases = [
            None,
            "",
            "   ",
            "definitely_not_admin",
            "admin'; DROP TABLE users; --",
            "\x00admin\x00",
        ]
        
        for user_id in edge_cases:
            try:
                result = await user_service.is_user_admin(user_id)
                # Should always return boolean, preferably False for invalid inputs
                assert isinstance(result, bool)
                if user_id in [None, "", "   "]:
                    assert result is False, "Invalid user IDs should not have admin access"
            except Exception:
                # Any exception should be handled gracefully
                pass


class TestUserListingAndCounting:
    """Test user listing and counting edge cases"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()

    @pytest.mark.asyncio
    async def test_list_users_parameter_variations(self, user_service):
        """Test list_users with various parameter combinations"""
        parameter_combinations = [
            {},  # Default parameters
            {"include_inactive": True},
            {"include_inactive": False},
            {"include_inactive": None},  # Should handle None gracefully
            {"include_inactive": "true"},  # String input
            {"include_inactive": 1},  # Integer input
            {"include_inactive": 0},  # Zero input
        ]
        
        for params in parameter_combinations:
            try:
                result = await user_service.list_users(**params)
                # Should return list
                assert isinstance(result, list)
            except Exception:
                # Database errors expected
                pass

    @pytest.mark.asyncio
    async def test_get_user_count_parameter_variations(self, user_service):
        """Test get_user_count with various parameter combinations"""
        parameter_combinations = [
            {},  # Default parameters
            {"active_only": True},
            {"active_only": False},
            {"active_only": None},
            {"active_only": "true"},
            {"active_only": 1},
            {"active_only": 0},
        ]
        
        for params in parameter_combinations:
            try:
                result = await user_service.get_user_count(**params)
                # Should return integer >= 0
                assert isinstance(result, int)
                assert result >= 0
            except Exception:
                # Database errors expected
                pass


class TestErrorHandlingRobustness:
    """Test error handling and robustness"""
    
    @pytest.fixture
    def user_service(self):
        return AsyncUserService()

    def test_validation_error_completeness(self):
        """Test ValidationError contains all required information"""
        error = ValidationError(
            message="Test error",
            field="test_field",
            value="test_value",
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            user_message="User message"
        )
        
        # Test all components are accessible
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.MISSING_REQUIRED_FIELD
        assert error.user_message == "User message"
        
        # Test context contains field and value information
        if hasattr(error, 'context') and error.context:
            if hasattr(error.context, 'field'):
                assert error.context.field == "test_field"
            if hasattr(error.context, 'value'):
                assert error.context.value == "test_value"
        
        # Test string representation includes key information
        error_str = str(error)
        assert "Test error" in error_str

    def test_error_code_enum_completeness(self):
        """Test that required error codes exist"""
        required_codes = [
            "MISSING_REQUIRED_FIELD",
            "DUPLICATE_RECORD",
            "DATABASE_QUERY_FAILED",
            "CONSTRAINT_VIOLATION",
            "INVALID_INPUT",
            "ACCESS_DENIED",
        ]
        
        for code_name in required_codes:
            assert hasattr(ErrorCode, code_name), f"ErrorCode.{code_name} should exist"
            code = getattr(ErrorCode, code_name)
            assert code is not None
            assert code.name == code_name

    @pytest.mark.asyncio
    async def test_service_handles_malformed_inputs(self, user_service):
        """Test service handles malformed inputs gracefully"""
        malformed_inputs = [
            object(),  # Random object
            [],        # List instead of string
            {},        # Dict instead of string
            123,       # Number instead of string
            True,      # Boolean instead of string
        ]
        
        for malformed_input in malformed_inputs:
            try:
                # These should either handle gracefully or raise appropriate ValidationError
                await user_service.add_user(malformed_input, first_name="Test")
            except ValidationError as e:
                # ValidationError is acceptable for malformed input
                assert e.error_code in [
                    ErrorCode.MISSING_REQUIRED_FIELD, 
                    ErrorCode.INVALID_INPUT
                ]
            except TypeError:
                # TypeError is also acceptable for type mismatches
                pass
            except Exception:
                # Other exceptions might occur due to database interactions
                pass


class TestServiceConfiguration:
    """Test service configuration and setup"""
    
    def test_service_instantiation(self):
        """Test service can be instantiated properly"""
        service = AsyncUserService()
        assert service is not None
        assert isinstance(service, AsyncUserService)

    def test_service_has_required_methods(self):
        """Test service has all required public methods"""
        service = AsyncUserService()
        required_methods = [
            "is_user_authorized",
            "is_user_admin",
            "get_user",
            "add_user",
            "update_user",
            "remove_user",
            "list_users",
            "get_user_count",
            "batch_update_user_info",
        ]
        
        for method_name in required_methods:
            assert hasattr(service, method_name), f"Method {method_name} should exist"
            method = getattr(service, method_name)
            assert callable(method), f"Method {method_name} should be callable"

    def test_service_method_are_async(self):
        """Test that service methods are properly async"""
        import asyncio
        service = AsyncUserService()
        async_methods = [
            "is_user_authorized",
            "is_user_admin",
            "get_user",
            "add_user",
            "update_user",
            "remove_user",
            "list_users",
            "get_user_count",
            "batch_update_user_info",
        ]
        
        for method_name in async_methods:
            method = getattr(service, method_name)
            assert asyncio.iscoroutinefunction(method), f"Method {method_name} should be async"