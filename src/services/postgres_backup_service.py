"""PostgreSQL backup service for remote databases"""

import asyncio
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
import os

import aiofiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.logging_config import get_logger
from config.settings import settings
from database.async_connection import get_async_session_context
from database.models import (
    WorkoutSession,
    Exercise,
    User,
    WorkoutExercise,
    AerobicExercise,
)
from services.exceptions import BackupError, ErrorCode

logger = get_logger(__name__)


class PostgreSQLBackupService:
    """Backup service for PostgreSQL databases (local and remote)"""

    def __init__(self, backup_dir: str = None, max_backups: int = 30):
        self.backup_dir = Path(backup_dir or './backups')
        self.max_backups = max_backups
        self.database_url = settings.DATABASE_URL

        # Ensure backup directory exists
        self.backup_dir.mkdir(exist_ok=True)

        logger.info(
            f'PostgreSQL backup service initialized: {self.backup_dir}'
        )
        logger.info(f'Database URL: {self._safe_url()}')

    def _safe_serialize_datetime(self, dt_value) -> Optional[str]:
        """Safely serialize datetime/date/time objects to ISO format string"""
        if dt_value is None:
            return None
        if hasattr(dt_value, 'isoformat'):
            return dt_value.isoformat()
        return str(dt_value)

    def _safe_serialize_enum(self, enum_value) -> Optional[str]:
        """Safely serialize enum objects to string"""
        if enum_value is None:
            return None
        if hasattr(enum_value, 'value'):
            return enum_value.value
        return str(enum_value)

    def _safe_url(self) -> str:
        """Return database URL with password hidden"""
        if '@' in self.database_url:
            parts = self.database_url.split('@')
            prefix = parts[0].split('://')[0] + '://***:***@'
            return prefix + parts[1]
        return self.database_url

    async def create_backup_sql(self, backup_name: str = None) -> str:
        """Create SQL backup using pg_dump (requires pg_dump installed)"""
        try:
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'gym_tracker_backup_{timestamp}.sql'

            backup_path = self.backup_dir / backup_name

            # Check if pg_dump is available
            try:
                subprocess.run(
                    ['pg_dump', '--version'], capture_output=True, check=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise BackupError(
                    'pg_dump not found. Install PostgreSQL client tools.',
                    error_code=ErrorCode.FILE_NOT_FOUND,
                )

            logger.info(f'Creating SQL backup: {backup_name}')

            # Run pg_dump
            result = await asyncio.create_subprocess_exec(
                'pg_dump',
                self.database_url,
                '--verbose',
                '--no-password',  # Use connection string auth
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = (
                    stderr.decode() if stderr else 'Unknown pg_dump error'
                )
                raise BackupError(
                    f'pg_dump failed: {error_msg}',
                    error_code=ErrorCode.BACKUP_FAILED,
                )

            # Save backup to file
            async with aiofiles.open(backup_path, 'wb') as f:
                await f.write(stdout)

            logger.info(f'SQL backup created: {backup_path}')
            return str(backup_path)

        except BackupError:
            raise
        except Exception as e:
            logger.exception(f'SQL backup creation failed: {backup_name}')
            raise BackupError(
                f'Failed to create SQL backup: {str(e)}',
                error_code=ErrorCode.BACKUP_FAILED,
                cause=e,
            )

    async def create_backup_json(self, backup_name: str = None) -> str:
        """Create JSON backup by exporting all data"""
        try:
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'gym_tracker_backup_{timestamp}.json'

            backup_path = self.backup_dir / backup_name

            logger.info(f'Creating JSON backup: {backup_name}')

            backup_data = {
                'backup_info': {
                    'created_at': datetime.now().isoformat(),
                    'database_type': 'postgresql',
                    'backup_type': 'json_export',
                },
                'data': {},
            }

            async with get_async_session_context() as session:
                # Export Users
                users_result = await session.execute(
                    text('SELECT * FROM users')
                )
                users = []
                for row in users_result:
                    users.append(
                        {
                            'user_id': row.user_id,
                            'username': row.username,
                            'first_name': row.first_name,
                            'last_name': row.last_name,
                            'is_admin': row.is_admin,
                            'is_active': row.is_active,
                            'created_at': self._safe_serialize_datetime(
                                row.created_at
                            ),
                            'updated_at': self._safe_serialize_datetime(
                                row.updated_at
                            ),
                            'created_by': row.created_by,
                        }
                    )
                backup_data['data']['users'] = users

                # Export Exercises
                exercises_result = await session.execute(
                    text('SELECT * FROM exercises')
                )
                exercises = []
                for row in exercises_result:
                    exercises.append(
                        {
                            'exercise_id': row.exercise_id,
                            'name': row.name,
                            'type': self._safe_serialize_enum(row.type),
                            'muscle_group': row.muscle_group,
                            'equipment': row.equipment,
                            'description': row.description,
                        }
                    )
                backup_data['data']['exercises'] = exercises

                # Export Workout Sessions
                sessions_result = await session.execute(
                    text('SELECT * FROM workout_sessions')
                )
                sessions = []
                for row in sessions_result:
                    sessions.append(
                        {
                            'session_id': row.session_id,
                            'user_id': row.user_id,
                            'date': self._safe_serialize_datetime(row.date),
                            'start_time': self._safe_serialize_datetime(
                                row.start_time
                            ),
                            'end_time': self._safe_serialize_datetime(
                                row.end_time
                            ),
                            'body_weight_kg': row.body_weight_kg,
                            'energy_level': row.energy_level,
                            'notes': row.notes,
                            'created_at': self._safe_serialize_datetime(
                                row.created_at
                            ),
                            'duration_minutes': row.duration_minutes,
                            'original_transcription': row.original_transcription,
                            'llm_model_used': row.llm_model_used,
                            'processing_time_seconds': row.processing_time_seconds,
                            'status': self._safe_serialize_enum(row.status),
                            'last_update': self._safe_serialize_datetime(
                                row.last_update
                            ),
                            'audio_count': row.audio_count,
                        }
                    )
                backup_data['data']['workout_sessions'] = sessions

                # Export Workout Exercises
                we_result = await session.execute(
                    text('SELECT * FROM workout_exercises')
                )
                workout_exercises = []
                for row in we_result:
                    workout_exercises.append(
                        {
                            'workout_exercise_id': row.workout_exercise_id,
                            'session_id': row.session_id,
                            'exercise_id': row.exercise_id,
                            'order_in_workout': row.order_in_workout,
                            'sets': row.sets,
                            'reps': row.reps,
                            'weights_kg': row.weights_kg,
                            'rest_seconds': row.rest_seconds,
                            'perceived_difficulty': row.perceived_difficulty,
                            'notes': row.notes,
                        }
                    )
                backup_data['data']['workout_exercises'] = workout_exercises

                # Export Aerobic Exercises
                ae_result = await session.execute(
                    text('SELECT * FROM aerobic_exercises')
                )
                aerobic_exercises = []
                for row in ae_result:
                    aerobic_exercises.append(
                        {
                            'aerobic_id': row.aerobic_id,
                            'session_id': row.session_id,
                            'exercise_id': row.exercise_id,
                            'duration_minutes': row.duration_minutes,
                            'distance_km': row.distance_km,
                            'average_heart_rate': row.average_heart_rate,
                            'calories_burned': row.calories_burned,
                            'intensity_level': row.intensity_level,
                            'notes': row.notes,
                        }
                    )
                backup_data['data']['aerobic_exercises'] = aerobic_exercises

            # Save to JSON file
            async with aiofiles.open(backup_path, 'w', encoding='utf-8') as f:
                await f.write(
                    json.dumps(backup_data, indent=2, ensure_ascii=False)
                )

            logger.info(f'JSON backup created: {backup_path}')
            return str(backup_path)

        except Exception as e:
            logger.exception(f'JSON backup creation failed: {backup_name}')
            raise BackupError(
                f'Failed to create JSON backup: {str(e)}',
                error_code=ErrorCode.BACKUP_FAILED,
                cause=e,
            )

    async def restore_from_sql(
        self, backup_path: str, confirm: bool = False
    ) -> bool:
        """Restore from SQL backup using psql"""
        if not confirm:
            raise BackupError(
                'Restore operation requires explicit confirmation',
                error_code=ErrorCode.INVALID_INPUT,
            )

        try:
            if not os.path.exists(backup_path):
                raise BackupError(
                    f'Backup file not found: {backup_path}',
                    error_code=ErrorCode.FILE_NOT_FOUND,
                )

            # Check if psql is available
            try:
                subprocess.run(
                    ['psql', '--version'], capture_output=True, check=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise BackupError(
                    'psql not found. Install PostgreSQL client tools.',
                    error_code=ErrorCode.FILE_NOT_FOUND,
                )

            logger.warning(
                f'Starting database restore from SQL: {backup_path}'
            )

            # Run psql to restore
            with open(backup_path, 'r') as f:
                result = await asyncio.create_subprocess_exec(
                    'psql',
                    self.database_url,
                    '--quiet',
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await result.communicate(
                    input=f.read().encode()
                )

            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else 'Unknown psql error'
                raise BackupError(
                    f'psql restore failed: {error_msg}',
                    error_code=ErrorCode.RESTORE_FAILED,
                )

            logger.info(f'Database restored from SQL: {backup_path}')
            return True

        except BackupError:
            raise
        except Exception as e:
            logger.exception(f'SQL restore failed: {backup_path}')
            raise BackupError(
                f'Failed to restore from SQL: {str(e)}',
                error_code=ErrorCode.RESTORE_FAILED,
                cause=e,
            )

    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        try:
            backups = []

            backup_files = await asyncio.to_thread(
                lambda: list(self.backup_dir.glob('*.sql'))
                + list(self.backup_dir.glob('*.json'))
            )

            for backup_file in backup_files:
                try:
                    stat = await asyncio.to_thread(backup_file.stat)
                    size_mb = stat.st_size / (1024 * 1024)

                    backup_info = {
                        'name': backup_file.name,
                        'path': str(backup_file),
                        'type': 'sql'
                        if backup_file.suffix == '.sql'
                        else 'json',
                        'created': datetime.fromtimestamp(stat.st_ctime),
                        'size_mb': round(size_mb, 2),
                    }
                    backups.append(backup_info)

                except Exception as e:
                    logger.warning(
                        f'Error reading backup info: {backup_file.name} - {e}'
                    )
                    continue

            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x['created'], reverse=True)
            return backups

        except Exception as e:
            logger.exception('Error listing backups')
            raise BackupError(
                f'Failed to list backups: {str(e)}',
                error_code=ErrorCode.FILE_OPERATION_ERROR,
                cause=e,
            )

    async def cleanup_old_backups(self):
        """Remove old backups beyond max_backups limit"""
        try:
            backups = await self.list_backups()

            if len(backups) <= self.max_backups:
                logger.debug(
                    f'Backup cleanup not needed: {len(backups)}/{self.max_backups}'
                )
                return

            # Remove oldest backups
            backups_to_remove = backups[self.max_backups :]

            for backup in backups_to_remove:
                try:
                    await asyncio.to_thread(os.remove, backup['path'])
                    logger.info(f"Removed old backup: {backup['name']}")
                except Exception as e:
                    logger.warning(
                        f"Failed to remove backup {backup['name']}: {e}"
                    )

            logger.info(
                f'Backup cleanup completed: removed {len(backups_to_remove)} old backups'
            )

        except Exception:
            logger.exception('Backup cleanup failed')


# Global PostgreSQL backup service instance
postgres_backup_service = PostgreSQLBackupService()
