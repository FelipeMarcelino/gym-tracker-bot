"""Unit tests for backup commands"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime

# Import the module under test
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from services.exceptions import BackupError


@pytest.fixture(scope="session", autouse=True)
def mock_admin_middleware():
    """Mock admin middleware at session level to bypass admin checks"""
    with patch('bot.middleware.admin_only', lambda func: func):
        yield


@pytest.fixture(scope="session", autouse=True) 
def mock_validation_middleware():
    """Mock validation middleware at session level"""
    def mock_validate_input(schema):
        def decorator(func):
            # Return a wrapper that calls the original function with validated_data
            async def wrapper(update, context, validated_data=None):
                # Extract text from update.message if validated_data is None
                if validated_data is None:
                    validated_data = {"text": getattr(update.message, 'text', '')}
                return await func(update, context, validated_data=validated_data)
            return wrapper
        return decorator
    
    with patch('bot.validation_middleware.validate_input', mock_validate_input):
        yield


class TestBackupCommands:
    """Test backup command handlers"""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update"""
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_user.first_name = "Test User"
        update.effective_chat = Mock()
        update.effective_chat.id = 67890
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        update.message.text = "/backup_create"
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Telegram context"""
        context = Mock()
        context.args = []
        return context

    @pytest.fixture
    def mock_backup_service(self):
        """Create a mock backup service"""
        service = AsyncMock()
        service.list_backups.return_value = [
            {
                "name": "test_backup.sql",
                "size_mb": 2.5,
                "type": "sql",
                "created": datetime(2023, 12, 25, 10, 30, 0),
                "verified": True
            }
        ]
        service.get_backup_stats.return_value = {
            "total_backups": 5,
            "total_size_mb": 15.2,
            "newest_backup": datetime(2023, 12, 25, 10, 30, 0),
            "oldest_backup": datetime(2023, 12, 20, 8, 15, 0),
            "verified_backups": 5,
            "backup_directory": "./backups"
        }
        service.create_backup_sql.return_value = "/path/to/backup.sql"
        service.create_backup_json.return_value = "/path/to/backup.json"
        service.create_backup.return_value = "/path/to/backup.db"
        service.restore_backup.return_value = True
        service.restore_from_sql.return_value = True
        service.cleanup_old_backups.return_value = None
        service.start_automated_backups.return_value = None
        service.stop_automated_backups.return_value = None
        service.is_running = False
        service.backup_frequency_hours = 6
        service.max_backups = 30
        service.backup_dir = "./backups"
        return service

    @pytest.mark.asyncio
    async def test_backup_create_postgresql_success(self, mock_update, mock_context, mock_backup_service):
        """Test successful PostgreSQL backup creation"""
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service), \
             patch('bot.backup_commands.BackupFactory.is_postgresql', return_value=True):
            
            from bot.backup_commands import backup_create
            await backup_create(mock_update, mock_context)
            
            # Verify backup service was called
            mock_backup_service.create_backup_sql.assert_called_once()
            mock_backup_service.list_backups.assert_called_once()
            
            # Verify user got success message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "✅ **Backup Created Successfully**" in call_args[0]
            assert "SQL" in call_args[0]

    @pytest.mark.asyncio 
    async def test_backup_create_postgresql_sql_fails_json_succeeds(self, mock_update, mock_context, mock_backup_service):
        """Test PostgreSQL backup creation when SQL fails but JSON succeeds"""
        mock_backup_service.create_backup_sql.side_effect = Exception("SQL backup failed")
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service), \
             patch('bot.backup_commands.BackupFactory.is_postgresql', return_value=True):
            
            from bot.backup_commands import backup_create
            await backup_create(mock_update, mock_context)
            
            # Verify both methods were attempted
            mock_backup_service.create_backup_sql.assert_called_once()
            mock_backup_service.create_backup_json.assert_called_once()
            
            # Verify user got success message with JSON type
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "✅ **Backup Created Successfully**" in call_args[0]
            assert "JSON" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_create_sqlite_success(self, mock_update, mock_context, mock_backup_service):
        """Test successful SQLite backup creation"""
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service), \
             patch('bot.backup_commands.BackupFactory.is_postgresql', return_value=False):
            
            from bot.backup_commands import backup_create
            await backup_create(mock_update, mock_context)
            
            # Verify backup service was called
            mock_backup_service.create_backup.assert_called_once()
            mock_backup_service.list_backups.assert_called_once()
            
            # Verify user got success message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "✅ **Backup Created Successfully**" in call_args[0]
            assert "SQLite" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_create_failure(self, mock_update, mock_context, mock_backup_service):
        """Test backup creation failure"""
        mock_backup_service.create_backup_sql.side_effect = BackupError("Backup failed")
        mock_backup_service.create_backup_json.side_effect = BackupError("JSON backup failed")
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service), \
             patch('bot.backup_commands.BackupFactory.is_postgresql', return_value=True):
            
            from bot.backup_commands import backup_create
            await backup_create(mock_update, mock_context)
            
            # Verify error message was sent
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "❌ Backup failed:" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_list_with_backups(self, mock_update, mock_context, mock_backup_service):
        """Test listing backups when backups exist"""
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_list
            await backup_list(mock_update, mock_context)
            
            # Verify backup service was called
            mock_backup_service.list_backups.assert_called_once()
            
            # Verify user got backup list
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "📁 **Available Backups**" in call_args[0]
            assert "test_backup.sql" in call_args[0]
            assert "2.5 MB" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_list_no_backups(self, mock_update, mock_context, mock_backup_service):
        """Test listing backups when no backups exist"""
        mock_backup_service.list_backups.return_value = []
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_list
            await backup_list(mock_update, mock_context)
            
            # Verify user got no backups message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "📁 No backups found" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_stats_success(self, mock_update, mock_context, mock_backup_service):
        """Test backup statistics display"""
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_stats
            await backup_stats(mock_update, mock_context)
            
            # Verify backup service was called
            mock_backup_service.get_backup_stats.assert_called_once()
            
            # Verify user got stats
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "📊 **Backup Statistics**" in call_args[0]
            assert "📁 **Total Backups:** 5" in call_args[0]
            assert "💾 **Total Size:** 15.2 MB" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_restore_success(self, mock_update, mock_context, mock_backup_service):
        """Test successful backup restoration"""
        # Set up test data for restore command
        mock_update.message.text = "/backup_restore test_backup.sql confirm"
        mock_backup_service.list_backups.return_value = [
            {
                "name": "test_backup.sql",
                "path": "/path/to/test_backup.sql",
                "size_mb": 2.5,
                "type": "sql",
                "created": datetime(2023, 12, 25, 10, 30, 0)
            }
        ]
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service), \
             patch('bot.backup_commands.BackupFactory.is_postgresql', return_value=False):
            
            from bot.backup_commands import backup_restore
            
            # Mock validated_data for the function call
            validated_data = {"text": "/backup_restore test_backup.sql confirm"}
            await backup_restore(mock_update, mock_context, validated_data=validated_data)
            
            # Verify restore was called
            mock_backup_service.restore_backup.assert_called_once_with("/path/to/test_backup.sql", confirm=True)
            
            # Verify success message was sent
            mock_update.message.reply_text.assert_called()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "✅ **Database Restored Successfully**" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_restore_without_confirmation(self, mock_update, mock_context, mock_backup_service):
        """Test backup restoration without confirmation"""
        mock_update.message.text = "/backup_restore test_backup.sql"
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_restore
            
            validated_data = {"text": "/backup_restore test_backup.sql"}
            await backup_restore(mock_update, mock_context, validated_data=validated_data)
            
            # Verify warning message about confirmation
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "⚠️ **DANGER: DATABASE RESTORE**" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_restore_postgresql_sql_file(self, mock_update, mock_context, mock_backup_service):
        """Test backup restoration for PostgreSQL SQL file"""
        mock_update.message.text = "/backup_restore test_backup.sql confirm"
        mock_backup_service.list_backups.return_value = [
            {
                "name": "test_backup.sql",
                "path": "/path/to/test_backup.sql",
                "size_mb": 2.5,
                "type": "sql",
                "created": datetime(2023, 12, 25, 10, 30, 0)
            }
        ]
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service), \
             patch('bot.backup_commands.BackupFactory.is_postgresql', return_value=True):
            
            from bot.backup_commands import backup_restore
            
            validated_data = {"text": "/backup_restore test_backup.sql confirm"}
            await backup_restore(mock_update, mock_context, validated_data=validated_data)
            
            # Verify SQL restore was called
            mock_backup_service.restore_from_sql.assert_called_once_with("/path/to/test_backup.sql", confirm=True)
            
            # Verify success message
            mock_update.message.reply_text.assert_called()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "✅ **Database Restored Successfully**" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_cleanup_success(self, mock_update, mock_context, mock_backup_service):
        """Test successful backup cleanup"""
        # Mock the get_backup_stats method to return consistent data before and after cleanup
        stats_calls = [
            {"total_backups": 5, "total_size_mb": 15.2},  # Before cleanup
            {"total_backups": 3, "total_size_mb": 10.5}   # After cleanup
        ]
        mock_backup_service.get_backup_stats.side_effect = stats_calls
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_cleanup
            await backup_cleanup(mock_update, mock_context)
            
            # Verify cleanup was called
            mock_backup_service.cleanup_old_backups.assert_called_once()
            
            # Verify success message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "🧹 **Backup Cleanup Complete**" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_auto_start_success(self, mock_update, mock_context, mock_backup_service):
        """Test starting automatic backups"""
        mock_backup_service.is_running = False
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_auto_start
            await backup_auto_start(mock_update, mock_context)
            
            # Verify automatic backups were started
            mock_backup_service.start_automated_backups.assert_called_once()
            
            # Verify success message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "✅ **Automated Backups Started**" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_auto_start_already_running(self, mock_update, mock_context, mock_backup_service):
        """Test starting automatic backups when already running"""
        mock_backup_service.is_running = True
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_auto_start
            await backup_auto_start(mock_update, mock_context)
            
            # Verify service wasn't called again
            mock_backup_service.start_automated_backups.assert_not_called()
            
            # Verify already running message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "🔄 Automated backups are already running" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_auto_stop_success(self, mock_update, mock_context, mock_backup_service):
        """Test stopping automatic backups"""
        mock_backup_service.is_running = True
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_auto_stop
            await backup_auto_stop(mock_update, mock_context)
            
            # Verify automatic backups were stopped
            mock_backup_service.stop_automated_backups.assert_called_once()
            
            # Verify success message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "⏹️ **Automated Backups Stopped**" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_auto_stop_not_running(self, mock_update, mock_context, mock_backup_service):
        """Test stopping automatic backups when not running"""
        mock_backup_service.is_running = False
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_auto_stop
            await backup_auto_stop(mock_update, mock_context)
            
            # Verify service wasn't called
            mock_backup_service.stop_automated_backups.assert_not_called()
            
            # Verify not running message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "⏹️ Automated backups are not running" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_auto_start_no_automation_support(self, mock_update, mock_context):
        """Test automatic backups not supported for service without automation"""
        # Create a mock service without automation methods
        mock_backup_service = AsyncMock()
        # Remove automation methods to simulate unsupported service
        del mock_backup_service.start_automated_backups
        del mock_backup_service.is_running
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_auto_start
            await backup_auto_start(mock_update, mock_context)
            
            # Verify not supported message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "❌ Automated backups not supported for this database type" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_auto_stop_no_automation_support(self, mock_update, mock_context):
        """Test automatic backup stop not supported for service without automation"""
        # Create a mock service that has is_running but no stop_automated_backups method
        mock_backup_service = AsyncMock()
        mock_backup_service.is_running = True  # Keep is_running so we pass the first check
        # Remove only the stop method to simulate partial automation support
        del mock_backup_service.stop_automated_backups
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_backup_service):
            
            from bot.backup_commands import backup_auto_stop
            await backup_auto_stop(mock_update, mock_context)
            
            # Verify not supported message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "❌ Automated backups not supported for this database type" in call_args[0]


class TestBackupCommandsErrorHandling:
    """Test error handling in backup commands"""

    @pytest.fixture
    def mock_update(self):
        """Create a mock Telegram update"""
        update = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 12345
        update.effective_chat = Mock()
        update.effective_chat.id = 67890
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create a mock Telegram context"""
        context = Mock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_backup_list_service_error(self, mock_update, mock_context):
        """Test backup list with service error"""
        mock_service = AsyncMock()
        mock_service.list_backups.side_effect = Exception("Service error")
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_service):
            
            from bot.backup_commands import backup_list
            await backup_list(mock_update, mock_context)
            
            # Verify error message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "❌ Failed to list backups" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_stats_service_error(self, mock_update, mock_context):
        """Test backup stats with service error"""
        mock_service = AsyncMock()
        mock_service.get_backup_stats.side_effect = Exception("Stats error")
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_service):
            
            from bot.backup_commands import backup_stats
            await backup_stats(mock_update, mock_context)
            
            # Verify error message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "❌ Failed to get backup statistics" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_cleanup_service_error(self, mock_update, mock_context):
        """Test backup cleanup with service error"""
        mock_service = AsyncMock()
        mock_service.cleanup_old_backups.side_effect = Exception("Cleanup error")
        
        with patch('bot.backup_commands.get_async_backup_service', return_value=mock_service):
            
            from bot.backup_commands import backup_cleanup
            await backup_cleanup(mock_update, mock_context)
            
            # Verify error message
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0]
            assert "❌ Failed to cleanup backups" in call_args[0]

    @pytest.mark.asyncio
    async def test_backup_restore_invalid_arguments(self, mock_update, mock_context):
        """Test backup restore with invalid arguments"""
        mock_update.message.text = "/backup_restore"
        
        from bot.backup_commands import backup_restore
        
        validated_data = {"text": "/backup_restore"}  # No backup filename provided
        await backup_restore(mock_update, mock_context, validated_data=validated_data)
        
        # Verify usage message
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "❌ Please specify backup filename:" in call_args[0]
        assert "/backup_restore" in call_args[0]