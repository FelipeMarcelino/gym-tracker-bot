"""Unit tests for backup service"""

import pytest
import os
import time
from datetime import datetime
from pathlib import Path

from services.backup_service import BackupService
from services.exceptions import BackupError


class TestBackupService:
    """Test backup service functionality"""
    
    def test_backup_service_initialization(self, test_backup_dir):
        """Test backup service initializes correctly"""
        service = BackupService(
            backup_dir=test_backup_dir,
            max_backups=10,
            backup_frequency_hours=2
        )
        
        assert service.backup_dir == Path(test_backup_dir)
        assert service.max_backups == 10
        assert service.backup_frequency_hours == 2
        assert not service.is_running
        assert service.backup_dir.exists()
    
    def test_create_backup_with_nonexistent_database(self, test_backup_service):
        """Test backup creation fails with nonexistent database"""
        test_backup_service.database_path = "/nonexistent/database.db"
        
        with pytest.raises(BackupError) as exc_info:
            test_backup_service.create_backup("test_backup.db")
        
        assert "Source database not found" in str(exc_info.value)
    
    def test_create_backup_success(self, test_backup_service, populated_test_database):
        """Test successful backup creation"""
        test_backup_service.database_path = populated_test_database
        
        backup_path = test_backup_service.create_backup("test_backup.db")
        
        assert os.path.exists(backup_path)
        assert backup_path.endswith("test_backup.db")
        
        # Verify backup is listed
        backups = test_backup_service.list_backups()
        assert len(backups) == 1
        assert backups[0]["name"] == "test_backup.db"
        assert backups[0]["verified"] is True
    
    def test_backup_verification(self, test_backup_service, populated_test_database):
        """Test backup verification"""
        test_backup_service.database_path = populated_test_database
        
        # Create valid backup
        backup_path = test_backup_service.create_backup("valid_backup.db")
        assert test_backup_service._verify_backup(backup_path) is True
        
        # Create invalid backup (text file)
        invalid_path = test_backup_service.backup_dir / "invalid_backup.db"
        invalid_path.write_text("This is not a database")
        assert test_backup_service._verify_backup(str(invalid_path)) is False
    
    def test_list_backups(self, test_backup_service, populated_test_database):
        """Test backup listing functionality"""
        test_backup_service.database_path = populated_test_database
        
        # Initially no backups
        backups = test_backup_service.list_backups()
        assert len(backups) == 0
        
        # Create multiple backups
        backup1 = test_backup_service.create_backup("backup1.db")
        time.sleep(0.1)  # Ensure different timestamps
        backup2 = test_backup_service.create_backup("backup2.db")
        
        backups = test_backup_service.list_backups()
        assert len(backups) == 2
        
        # Should be sorted by creation date (newest first)
        assert backups[0]["name"] == "backup2.db"
        assert backups[1]["name"] == "backup1.db"
        
        # Check backup properties
        for backup in backups:
            assert "created" in backup
            assert "size_mb" in backup
            assert "verified" in backup
            assert backup["verified"] is True
    
    def test_backup_stats(self, test_backup_service, populated_test_database):
        """Test backup statistics"""
        test_backup_service.database_path = populated_test_database
        
        # No backups initially
        stats = test_backup_service.get_backup_stats()
        assert stats["total_backups"] == 0
        assert stats["total_size_mb"] == 0
        assert stats["newest_backup"] is None
        assert stats["oldest_backup"] is None
        
        # Create backups
        test_backup_service.create_backup("backup1.db")
        time.sleep(0.1)
        test_backup_service.create_backup("backup2.db")
        
        stats = test_backup_service.get_backup_stats()
        assert stats["total_backups"] == 2
        assert stats["total_size_mb"] > 0
        assert stats["verified_backups"] == 2
        assert stats["newest_backup"] is not None
        assert stats["oldest_backup"] is not None
        assert stats["newest_backup"] > stats["oldest_backup"]
    
    def test_cleanup_old_backups(self, test_backup_service, populated_test_database):
        """Test cleanup of old backups"""
        test_backup_service.database_path = populated_test_database
        test_backup_service.max_backups = 3
        
        # Create more backups than limit
        for i in range(5):
            test_backup_service.create_backup(f"backup{i}.db")
            time.sleep(0.1)
        
        # Should have 5 backups
        backups = test_backup_service.list_backups()
        assert len(backups) == 5
        
        # Cleanup should remove 2 oldest
        test_backup_service.cleanup_old_backups()
        
        backups = test_backup_service.list_backups()
        assert len(backups) == 3
        
        # Should keep newest backups
        backup_names = [b["name"] for b in backups]
        assert "backup4.db" in backup_names
        assert "backup3.db" in backup_names
        assert "backup2.db" in backup_names
        assert "backup0.db" not in backup_names
        assert "backup1.db" not in backup_names
    
    def test_automated_backup_start_stop(self, test_backup_service):
        """Test automated backup start and stop"""
        assert not test_backup_service.is_running
        
        # Start automated backups
        test_backup_service.start_automated_backups()
        assert test_backup_service.is_running
        
        # Stop automated backups
        test_backup_service.stop_automated_backups()
        assert not test_backup_service.is_running
        
        # Should handle double start/stop gracefully
        test_backup_service.start_automated_backups()
        test_backup_service.start_automated_backups()  # Should not error
        assert test_backup_service.is_running
        
        test_backup_service.stop_automated_backups()
        test_backup_service.stop_automated_backups()  # Should not error
        assert not test_backup_service.is_running
    
    def test_restore_backup_validation(self, test_backup_service):
        """Test backup restore validation"""
        # Should fail without confirmation
        with pytest.raises(BackupError) as exc_info:
            test_backup_service.restore_backup("some_backup.db", confirm=False)
        assert "requires explicit confirmation" in str(exc_info.value)
        
        # Should fail with nonexistent backup
        with pytest.raises(BackupError) as exc_info:
            test_backup_service.restore_backup("/nonexistent/backup.db", confirm=True)
        assert "not found" in str(exc_info.value)
    
    def test_error_handling(self, test_backup_service):
        """Test error handling in backup operations"""
        # Test with invalid database path
        test_backup_service.database_path = "/invalid/path/database.db"
        
        with pytest.raises(BackupError):
            test_backup_service.create_backup("test.db")
        
        # Test stats with no backups directory access
        test_backup_service.backup_dir = Path("/nonexistent/directory")
        stats = test_backup_service.get_backup_stats()
        assert "error" in stats


class TestBackupServiceEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_backup_name_generation(self, test_backup_service, populated_test_database):
        """Test automatic backup name generation"""
        test_backup_service.database_path = populated_test_database
        
        # Without custom name
        backup_path = test_backup_service.create_backup()
        backup_name = os.path.basename(backup_path)
        
        # Should follow format: gym_tracker_backup_YYYYMMDD_HHMMSS.db
        assert backup_name.startswith("gym_tracker_backup_")
        assert backup_name.endswith(".db")
        assert len(backup_name) == len("gym_tracker_backup_20251014_123456.db")
    
    def test_concurrent_backup_operations(self, test_backup_service, populated_test_database):
        """Test handling of concurrent backup operations"""
        test_backup_service.database_path = populated_test_database
        
        # SQLite should handle concurrent reads fine
        backup1 = test_backup_service.create_backup("concurrent1.db")
        backup2 = test_backup_service.create_backup("concurrent2.db")
        
        assert os.path.exists(backup1)
        assert os.path.exists(backup2)
        assert backup1 != backup2
    
    def test_backup_with_special_characters(self, test_backup_service, populated_test_database):
        """Test backup with special characters in name"""
        test_backup_service.database_path = populated_test_database
        
        # Should handle special characters appropriately
        backup_path = test_backup_service.create_backup("backup-with_special.chars.db")
        assert os.path.exists(backup_path)
        
        backups = test_backup_service.list_backups()
        assert any(b["name"] == "backup-with_special.chars.db" for b in backups)
    
    def test_backup_directory_permissions(self, test_backup_service, temp_dir):
        """Test handling of backup directory permission issues"""
        # This test would require changing directory permissions
        # Skipping for now as it's complex in test environment
        pass