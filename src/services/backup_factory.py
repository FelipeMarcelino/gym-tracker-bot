"""Factory for backup services based on database type"""

from typing import Union
from config.settings import settings
from services.async_backup_service import BackupService
from services.postgres_backup_service import PostgreSQLBackupService
from config.logging_config import get_logger

logger = get_logger(__name__)


class BackupFactory:
    """Factory to create appropriate backup service based on database type"""

    @staticmethod
    def create_backup_service() -> Union[
        BackupService, PostgreSQLBackupService
    ]:
        """Create the appropriate backup service based on DATABASE_URL"""
        database_url = settings.DATABASE_URL

        if database_url.startswith('sqlite'):
            logger.info('Using SQLite backup service')
            return BackupService()
        elif database_url.startswith(('postgresql', 'postgres')):
            logger.info('Using PostgreSQL backup service')
            return PostgreSQLBackupService()
        else:
            logger.warning(
                f'Unknown database type, defaulting to SQLite backup: {database_url}'
            )
            return BackupService()

    @staticmethod
    def is_postgresql() -> bool:
        """Check if current database is PostgreSQL"""
        database_url = settings.DATABASE_URL
        return database_url.startswith(('postgresql', 'postgres'))

    @staticmethod
    def is_sqlite() -> bool:
        """Check if current database is SQLite"""
        database_url = settings.DATABASE_URL
        return database_url.startswith('sqlite')


# Global backup service instance
backup_service = BackupFactory.create_backup_service()
