"""PostgreSQL-compatible backup service tests"""

import pytest

from services.backup_factory import BackupFactory


# Skip all backup service unit tests when using PostgreSQL
# These tests are SQLite-specific and would need significant rewriting
pytestmark = pytest.mark.skipif(
    BackupFactory.is_postgresql(),
    reason="Backup service unit tests are SQLite-specific"
)


# This file exists to document that the backup service unit tests
# are intentionally skipped for PostgreSQL since they test SQLite-specific
# methods like create_backup(), restore_backup(), etc.
#
# The integration tests (test_service_integration.py) already cover
# PostgreSQL backup functionality using create_backup_sql() and 
# create_backup_json() methods.