"""Database backup service with automated scheduling"""

import os
import shutil
import sqlite3
import asyncio
import aiosqlite
import aiofiles
import aiofiles.os
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
        self.is_running = False
        self.scheduler_task = None
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)
        
        logger.info(f"Backup service initialized: {self.backup_dir}")
        logger.info(f"Database path: {self.database_path}")
        logger.info(f"Max backups: {self.max_backups}")
        logger.info(f"Backup frequency: every {self.backup_frequency_hours} hours")
    
    async def create_backup(self, backup_name: str = None) -> str:
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
            if not await aiofiles.os.path.exists(self.database_path):
                raise BackupError(
                    f"Source database does not exist: {self.database_path}",
                    error_code=ErrorCode.FILE_NOT_FOUND
                )
            
            logger.info(f"Creating backup: {backup_name}")
            
            # Use aiosqlite for async backup
            async with aiosqlite.connect(self.database_path) as source_conn:
                async with aiosqlite.connect(str(backup_path)) as backup_conn:
                    # Perform the backup using SQL commands
                    await source_conn.execute("BEGIN IMMEDIATE;")
                    try:
                        # Copy all tables
                        await self._copy_database_async(source_conn, backup_conn)
                        logger.info(f"Backup created successfully: {backup_path}")
                        
                        # Verify backup integrity
                        if await self._verify_backup_async(str(backup_path)):
                            logger.info(f"Backup verified successfully: {backup_name}")
                            return str(backup_path)
                        else:
                            # Remove corrupted backup
                            await aiofiles.os.remove(str(backup_path))
                            raise BackupError(
                                f"Backup verification failed: {backup_name}",
                                error_code=ErrorCode.BACKUP_VERIFICATION_FAILED
                            )
                    finally:
                        await source_conn.execute("COMMIT;")
                
        except BackupError:
            raise
        except Exception as e:
            logger.exception(f"Backup creation failed: {backup_name}")
            raise BackupError(
                f"Failed to create backup: {str(e)}",
                error_code=ErrorCode.BACKUP_FAILED,
                cause=e
            )
    
    async def _copy_database_async(self, source_conn: aiosqlite.Connection, backup_conn: aiosqlite.Connection):
        """Copy all tables from source to backup database"""
        # Get all table names
        cursor = await source_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = await cursor.fetchall()
        await cursor.close()
        
        for (table_name,) in tables:
            if table_name == 'sqlite_sequence':
                continue
                
            # Get table schema
            cursor = await source_conn.execute(f"SELECT sql FROM sqlite_master WHERE name='{table_name}'")
            schema = await cursor.fetchone()
            await cursor.close()
            
            if schema and schema[0]:
                # Create table in backup
                await backup_conn.execute(schema[0])
                
                # Copy data
                cursor = await source_conn.execute(f"SELECT * FROM {table_name}")
                rows = await cursor.fetchall()
                await cursor.close()
                
                if rows:
                    # Get column count for placeholders
                    cursor = await source_conn.execute(f"PRAGMA table_info({table_name})")
                    columns = await cursor.fetchall()
                    await cursor.close()
                    
                    placeholders = ','.join(['?' for _ in columns])
                    await backup_conn.executemany(
                        f"INSERT INTO {table_name} VALUES ({placeholders})", 
                        rows
                    )
        
        await backup_conn.commit()
    
    async def _verify_backup_async(self, backup_path: str) -> bool:
        """
        Verify backup integrity (async version)
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if backup is valid, False otherwise
        """
        try:
            async with aiosqlite.connect(backup_path) as conn:
                # Check if we can query basic tables
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = await cursor.fetchall()
                await cursor.close()
                
                # Verify we have expected tables
                table_names = {table[0] for table in tables}
                expected_tables = {'users', 'exercises', 'workout_sessions', 'workout_exercises'}
                
                if not expected_tables.issubset(table_names):
                    logger.warning(f"Backup missing expected tables: {expected_tables - table_names}")
                    return False
                
                # Verify we can query each table
                for table in expected_tables:
                    cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                    result = await cursor.fetchone()
                    await cursor.close()
                    count = result[0] if result else 0
                    logger.debug(f"Backup verification - {table}: {count} records")
                
                return True
                
        except Exception as e:
            logger.exception(f"Backup verification failed: {backup_path}")
            return False
    
    def _verify_backup(self, backup_path: str) -> bool:
        """
        Verify backup integrity (sync version for compatibility)
        
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
    
    async def restore_backup(self, backup_path: str, confirm: bool = False) -> bool:
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
            if not await aiofiles.os.path.exists(backup_path):
                raise BackupError(
                    f"Backup file not found: {backup_path}",
                    error_code=ErrorCode.FILE_NOT_FOUND
                )
            
            # Verify backup before restoring
            if not await self._verify_backup_async(backup_path):
                raise BackupError(
                    f"Backup verification failed: {backup_path}",
                    error_code=ErrorCode.BACKUP_VERIFICATION_FAILED
                )
            
            logger.warning(f"Starting database restore from: {backup_path}")
            
            # Create a backup of current database before restore
            current_backup = await self.create_backup(f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            logger.info(f"Current database backed up to: {current_backup}")
            
            # Perform restore using async file operations
            async with aiofiles.open(backup_path, 'rb') as src:
                async with aiofiles.open(self.database_path, 'wb') as dst:
                    await dst.write(await src.read())
            
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
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups
        
        Returns:
            List of backup information dictionaries
        """
        try:
            backups = []
            
            # Use asyncio.to_thread for file operations that don't have async versions
            backup_files = await asyncio.to_thread(lambda: list(self.backup_dir.glob("*.db")))
            
            for backup_file in backup_files:
                try:
                    stat = await asyncio.to_thread(backup_file.stat)
                    size_mb = stat.st_size / (1024 * 1024)
                    
                    backup_info = {
                        "name": backup_file.name,
                        "path": str(backup_file),
                        "created": datetime.fromtimestamp(stat.st_ctime),
                        "size_mb": round(size_mb, 2),
                        "verified": await self._verify_backup_async(str(backup_file))
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
    
    async def cleanup_old_backups(self):
        """Remove old backups beyond max_backups limit"""
        try:
            backups = await self.list_backups()
            
            if len(backups) <= self.max_backups:
                logger.debug(f"Backup cleanup not needed: {len(backups)}/{self.max_backups}")
                return
            
            # Remove oldest backups
            backups_to_remove = backups[self.max_backups:]
            
            for backup in backups_to_remove:
                try:
                    await aiofiles.os.remove(backup["path"])
                    logger.info(f"Removed old backup: {backup['name']}")
                except Exception as e:
                    logger.warning(f"Failed to remove backup {backup['name']}: {e}")
            
            logger.info(f"Backup cleanup completed: removed {len(backups_to_remove)} old backups")
            
        except Exception as e:
            logger.exception("Backup cleanup failed")
            # Don't raise exception for cleanup failures
    
    async def get_backup_stats(self) -> Dict[str, Any]:
        """
        Get backup statistics
        
        Returns:
            Dictionary with backup statistics
        """
        try:
            # Check if backup directory exists
            if not await asyncio.to_thread(self.backup_dir.exists):
                return {"error": f"Backup directory does not exist: {self.backup_dir}"}
            
            backups = await self.list_backups()
            
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
        
        self.is_running = True
        # Create asyncio task for the scheduler
        self.scheduler_task = asyncio.create_task(self._run_async_scheduler())
        
        logger.info(f"Automated backups started: every {self.backup_frequency_hours} hours")
    
    def stop_automated_backups(self):
        """Stop automated backup scheduler"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if hasattr(self, 'scheduler_task'):
            self.scheduler_task.cancel()
        
        logger.info("Automated backups stopped")
    
    async def _scheduled_backup(self):
        """Perform scheduled backup"""
        try:
            logger.info("Starting scheduled backup")
            backup_path = await self.create_backup()
            await self.cleanup_old_backups()
            logger.info(f"Scheduled backup completed: {backup_path}")
            
        except Exception as e:
            logger.exception("Scheduled backup failed")
    
    async def _run_async_scheduler(self):
        """Run the async backup scheduler"""
        next_backup_time = datetime.now() + timedelta(hours=self.backup_frequency_hours)
        logger.info(f"Next backup scheduled for: {next_backup_time}")
        
        while self.is_running:
            try:
                current_time = datetime.now()
                
                if current_time >= next_backup_time:
                    await self._scheduled_backup()
                    next_backup_time = current_time + timedelta(hours=self.backup_frequency_hours)
                    logger.info(f"Next backup scheduled for: {next_backup_time}")
                
                # Check every 5 minutes
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                logger.info("Backup scheduler cancelled")
                break
            except Exception as e:
                logger.exception("Backup scheduler error")
                await asyncio.sleep(300)  # Wait 5 minutes on error


# Global backup service instance
backup_service = BackupService()