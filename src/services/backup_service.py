"""Database backup service with automated scheduling"""

import os
import shutil
import sqlite3
import asyncio
import schedule
import threading
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from config.logging_config import get_logger
from config.settings import settings
from services.exceptions import BackupError, ErrorCode, GymTrackerError

logger = get_logger(__name__)


class BackupService:
    """Service for automated database backups"""
    
    def __init__(self, 
                 backup_dir: str = None,
                 max_backups: int = 30,
                 backup_frequency_hours: int = 6):
        """
        Initialize backup service
        
        Args:
            backup_dir: Directory to store backups (default: ./backups)
            max_backups: Maximum number of backups to keep
            backup_frequency_hours: How often to create backups (in hours)
        """
        self.backup_dir = Path(backup_dir or "./backups")
        self.max_backups = max_backups
        self.backup_frequency_hours = backup_frequency_hours
        self.database_path = settings.DATABASE_URL.replace("sqlite:///", "")
        self.scheduler_thread = None
        self.is_running = False
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)
        
        logger.info(f"Backup service initialized: {self.backup_dir}")
        logger.info(f"Database path: {self.database_path}")
        logger.info(f"Max backups: {self.max_backups}")
        logger.info(f"Backup frequency: every {self.backup_frequency_hours} hours")
    
    def create_backup(self, backup_name: str = None) -> str:
        """
        Create a backup of the database
        
        Args:
            backup_name: Optional custom name for backup
            
        Returns:
            Path to created backup file
            
        Raises:
            BackupError: If backup creation fails
        """
        try:
            # Generate backup filename
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"gym_tracker_backup_{timestamp}.db"
            
            backup_path = self.backup_dir / backup_name
            
            # Check if source database exists
            if not os.path.exists(self.database_path):
                raise BackupError(
                    f"Source database not found: {self.database_path}",
                    error_code=ErrorCode.FILE_NOT_FOUND
                )
            
            logger.info(f"Creating backup: {backup_name}")
            
            # Use SQLite's backup API for safe backup
            source_conn = sqlite3.connect(self.database_path)
            try:
                backup_conn = sqlite3.connect(str(backup_path))
                try:
                    # Perform the backup
                    source_conn.backup(backup_conn)
                    logger.info(f"Backup created successfully: {backup_path}")
                    
                    # Verify backup integrity
                    if self._verify_backup(str(backup_path)):
                        logger.info(f"Backup verified successfully: {backup_name}")
                        return str(backup_path)
                    else:
                        # Remove corrupted backup
                        backup_path.unlink(missing_ok=True)
                        raise BackupError(
                            f"Backup verification failed: {backup_name}",
                            error_code=ErrorCode.BACKUP_VERIFICATION_FAILED
                        )
                        
                finally:
                    backup_conn.close()
            finally:
                source_conn.close()
                
        except BackupError:
            raise
        except Exception as e:
            logger.exception(f"Backup creation failed: {backup_name}")
            raise BackupError(
                f"Failed to create backup: {str(e)}",
                error_code=ErrorCode.BACKUP_FAILED,
                cause=e
            )
    
    def _verify_backup(self, backup_path: str) -> bool:
        """
        Verify backup integrity
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if backup is valid, False otherwise
        """
        try:
            conn = sqlite3.connect(backup_path)
            try:
                # Check if we can query basic tables
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                # Verify we have expected tables
                table_names = {table[0] for table in tables}
                expected_tables = {'users', 'exercises', 'workout_sessions', 'workout_exercises'}
                
                if not expected_tables.issubset(table_names):
                    logger.warning(f"Backup missing expected tables: {expected_tables - table_names}")
                    return False
                
                # Verify we can query each table
                for table in expected_tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    logger.debug(f"Backup verification - {table}: {count} records")
                
                return True
                
            finally:
                conn.close()
                
        except Exception as e:
            logger.exception(f"Backup verification failed: {backup_path}")
            return False
    
    def restore_backup(self, backup_path: str, confirm: bool = False) -> bool:
        """
        Restore database from backup
        
        Args:
            backup_path: Path to backup file
            confirm: Must be True to proceed (safety measure)
            
        Returns:
            True if restore successful
            
        Raises:
            BackupError: If restore fails
        """
        if not confirm:
            raise BackupError(
                "Restore operation requires explicit confirmation",
                error_code=ErrorCode.INVALID_INPUT
            )
        
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                raise BackupError(
                    f"Backup file not found: {backup_path}",
                    error_code=ErrorCode.FILE_NOT_FOUND
                )
            
            # Verify backup before restoring
            if not self._verify_backup(backup_path):
                raise BackupError(
                    f"Backup verification failed: {backup_path}",
                    error_code=ErrorCode.BACKUP_VERIFICATION_FAILED
                )
            
            logger.warning(f"Starting database restore from: {backup_path}")
            
            # Create a backup of current database before restore
            current_backup = self.create_backup(f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            logger.info(f"Current database backed up to: {current_backup}")
            
            # Perform restore
            shutil.copy2(backup_path, self.database_path)
            logger.info(f"Database restored from: {backup_path}")
            
            return True
            
        except BackupError:
            raise
        except Exception as e:
            logger.exception(f"Database restore failed: {backup_path}")
            raise BackupError(
                f"Failed to restore database: {str(e)}",
                error_code=ErrorCode.RESTORE_FAILED,
                cause=e
            )
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups
        
        Returns:
            List of backup information dictionaries
        """
        try:
            backups = []
            
            for backup_file in self.backup_dir.glob("*.db"):
                try:
                    stat = backup_file.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    
                    backup_info = {
                        "name": backup_file.name,
                        "path": str(backup_file),
                        "created": datetime.fromtimestamp(stat.st_ctime),
                        "size_mb": round(size_mb, 2),
                        "verified": self._verify_backup(str(backup_file))
                    }
                    backups.append(backup_info)
                    
                except Exception as e:
                    logger.warning(f"Error reading backup info: {backup_file.name} - {e}")
                    continue
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x["created"], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.exception("Error listing backups")
            raise BackupError(
                f"Failed to list backups: {str(e)}",
                error_code=ErrorCode.FILE_OPERATION_ERROR,
                cause=e
            )
    
    def cleanup_old_backups(self):
        """Remove old backups beyond max_backups limit"""
        try:
            backups = self.list_backups()
            
            if len(backups) <= self.max_backups:
                logger.debug(f"Backup cleanup not needed: {len(backups)}/{self.max_backups}")
                return
            
            # Remove oldest backups
            backups_to_remove = backups[self.max_backups:]
            
            for backup in backups_to_remove:
                try:
                    backup_path = Path(backup["path"])
                    backup_path.unlink()
                    logger.info(f"Removed old backup: {backup['name']}")
                except Exception as e:
                    logger.warning(f"Failed to remove backup {backup['name']}: {e}")
            
            logger.info(f"Backup cleanup completed: removed {len(backups_to_remove)} old backups")
            
        except Exception as e:
            logger.exception("Backup cleanup failed")
            # Don't raise exception for cleanup failures
    
    def get_backup_stats(self) -> Dict[str, Any]:
        """
        Get backup statistics
        
        Returns:
            Dictionary with backup statistics
        """
        try:
            backups = self.list_backups()
            
            if not backups:
                return {
                    "total_backups": 0,
                    "total_size_mb": 0,
                    "oldest_backup": None,
                    "newest_backup": None,
                    "verified_backups": 0
                }
            
            total_size = sum(backup["size_mb"] for backup in backups)
            verified_count = sum(1 for backup in backups if backup["verified"])
            
            return {
                "total_backups": len(backups),
                "total_size_mb": round(total_size, 2),
                "oldest_backup": backups[-1]["created"] if backups else None,
                "newest_backup": backups[0]["created"] if backups else None,
                "verified_backups": verified_count,
                "backup_directory": str(self.backup_dir)
            }
            
        except Exception as e:
            logger.exception("Error getting backup stats")
            return {"error": str(e)}
    
    def start_automated_backups(self):
        """Start automated backup scheduler"""
        if self.is_running:
            logger.warning("Automated backups already running")
            return
        
        # Schedule backups
        schedule.every(self.backup_frequency_hours).hours.do(self._scheduled_backup)
        
        # Start scheduler thread
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info(f"Automated backups started: every {self.backup_frequency_hours} hours")
    
    def stop_automated_backups(self):
        """Stop automated backup scheduler"""
        if not self.is_running:
            return
        
        self.is_running = False
        schedule.clear()
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("Automated backups stopped")
    
    def _scheduled_backup(self):
        """Perform scheduled backup"""
        try:
            logger.info("Starting scheduled backup")
            backup_path = self.create_backup()
            self.cleanup_old_backups()
            logger.info(f"Scheduled backup completed: {backup_path}")
            
        except Exception as e:
            logger.exception("Scheduled backup failed")
    
    def _run_scheduler(self):
        """Run the backup scheduler"""
        while self.is_running:
            try:
                schedule.run_pending()
                threading.Event().wait(60)  # Check every minute
            except Exception as e:
                logger.exception("Backup scheduler error")
                threading.Event().wait(300)  # Wait 5 minutes on error


# Global backup service instance
backup_service = BackupService()