"""Centralized logging configuration for the Gym Tracker Bot

This module provides a unified logging setup that:
- Logs INFO+ to console with colored output
- Logs DEBUG+ to rotating file with detailed format
- Configures all loggers consistently across the application
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Color codes for console output
class LogColors:
    """ANSI color codes for terminal output"""

    RESET = '\033[0m'
    BOLD = '\033[1m'

    # Log level colors
    DEBUG = '\033[36m'      # Cyan
    INFO = '\033[32m'       # Green
    WARNING = '\033[33m'    # Yellow
    ERROR = '\033[31m'      # Red
    CRITICAL = '\033[35m'   # Magenta


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to console output"""

    COLORS = {
        logging.DEBUG: LogColors.DEBUG,
        logging.INFO: LogColors.INFO,
        logging.WARNING: LogColors.WARNING,
        logging.ERROR: LogColors.ERROR,
        logging.CRITICAL: LogColors.CRITICAL,
    }

    def format(self, record):
        # Add color to the log level
        if record.levelno in self.COLORS:
            record.levelname = f'{self.COLORS[record.levelno]}{record.levelname}{LogColors.RESET}'

        # Format the message
        formatted = super().format(record)

        return formatted


def setup_logging(
    console_level: str = 'INFO',
    file_level: str = 'DEBUG',
    log_dir: str = 'logs',
    log_filename: str = 'gym_tracker_bot.log',
    max_file_size_mb: int = 10,
    backup_count: int = 5,
    enable_colors: bool = True,
    include_timestamp: bool = True,
) -> None:
    """Configure centralized logging for the application

    Args:
        console_level: Log level for console output (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file_level: Log level for file output (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        log_filename: Name of the main log file
        max_file_size_mb: Maximum size of each log file in MB before rotation
        backup_count: Number of backup files to keep
        enable_colors: Whether to enable colored output in console
        include_timestamp: Whether to include timestamp in log filename
    """

    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    # Generate timestamped filename if requested
    if include_timestamp:
        # Get current timestamp for filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Split filename and extension
        if '.' in log_filename:
            name_part, ext_part = log_filename.rsplit('.', 1)
            timestamped_filename = f'{name_part}_{timestamp}.{ext_part}'
        else:
            timestamped_filename = f'{log_filename}_{timestamp}'
    else:
        timestamped_filename = log_filename

    # Convert string levels to logging constants
    console_level_int = getattr(logging, console_level.upper(), logging.INFO)
    file_level_int = getattr(logging, file_level.upper(), logging.DEBUG)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set to most verbose level

    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # === CONSOLE HANDLER ===
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level_int)

    # Console format - clean and readable
    if (
        enable_colors and sys.stdout.isatty()
    ):  # Only use colors if terminal supports it
        console_format = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        console_formatter = ColoredFormatter(
            fmt=console_format, datefmt='%H:%M:%S'
        )
    else:
        console_format = (
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        )
        console_formatter = logging.Formatter(
            fmt=console_format, datefmt='%H:%M:%S'
        )

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # === FILE HANDLER (with rotation) ===
    log_file_path = log_path / timestamped_filename
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=max_file_size_mb * 1024 * 1024,  # Convert MB to bytes
        backupCount=backup_count,
        encoding='utf-8',
    )
    file_handler.setLevel(file_level_int)

    # File format - detailed with full context
    file_format = (
        '%(asctime)s | %(levelname)-8s | %(name)-30s | '
        '%(funcName)-20s:%(lineno)-4d | %(message)s'
    )
    file_formatter = logging.Formatter(
        fmt=file_format, datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # === CONFIGURE THIRD-PARTY LOGGERS ===
    # Reduce verbosity of external libraries

    # Telegram bot library
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    # SQLAlchemy
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

    # HTTP libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)

    # === LOG STARTUP MESSAGE ===
    logger = logging.getLogger(__name__)
    logger.info('=' * 60)
    logger.info('🤖 GYM TRACKER BOT - LOGGING INITIALIZED')
    logger.info('=' * 60)
    logger.info(f'📊 Console Level: {console_level.upper()}')
    logger.info(f'📁 File Level: {file_level.upper()}')
    logger.info(f'📂 Log Directory: {log_path.absolute()}')
    logger.info(f'📄 Log File: {timestamped_filename}')
    if include_timestamp:
        logger.info(f'⏰ Timestamped Filename: {timestamped_filename}')
    logger.info(f'🔄 Max File Size: {max_file_size_mb}MB')
    logger.info(f'📚 Backup Count: {backup_count}')
    logger.info(f'🎨 Colors Enabled: {enable_colors and sys.stdout.isatty()}')
    logger.info('=' * 60)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module

    Args:
        name: Usually __name__ from the calling module

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def get_session_id() -> str:
    """Generate a unique session identifier for this execution

    Returns:
        Session ID in format: YYYYMMDD_HHMMSS
    """
    return datetime.now().strftime('%Y%m%d_%H%M%S')


def setup_session_logging(session_id: Optional[str] = None) -> str:
    """Setup logging with a specific session identifier

    Args:
        session_id: Optional session ID, if not provided, one will be generated

    Returns:
        The session ID used for logging
    """
    if session_id is None:
        session_id = get_session_id()

    # Create a session-specific log filename
    session_filename = f'gym_tracker_bot_session_{session_id}.log'

    setup_logging(
        console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
        file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG'),
        log_dir=os.getenv('LOG_DIR', 'logs'),
        log_filename=session_filename,
        max_file_size_mb=int(os.getenv('LOG_MAX_FILE_SIZE_MB', '10')),
        backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5')),
        enable_colors=os.getenv('LOG_ENABLE_COLORS', 'true').lower()
        in ('true', '1', 'yes'),
        include_timestamp=False,  # Already included in session filename
    )

    return session_id


def log_system_info() -> None:
    """Log system information for debugging purposes"""
    logger = get_logger(__name__)

    logger.debug('🖥️  SYSTEM INFORMATION')
    logger.debug(f'   Python Version: {sys.version}')
    logger.debug(f'   Platform: {sys.platform}')
    logger.debug(f'   Working Directory: {os.getcwd()}')
    logger.debug(f'   Process ID: {os.getpid()}')
    logger.debug(f'   Timestamp: {datetime.now().isoformat()}')


def list_log_files(log_dir: str = 'logs') -> list[dict]:
    """List all log files in the log directory with metadata

    Args:
        log_dir: Directory to search for log files

    Returns:
        List of dictionaries containing log file information
    """
    log_files = []
    log_path = Path(log_dir)

    if not log_path.exists():
        return log_files

    for log_file in log_path.glob('*.log*'):
        if log_file.is_file():
            stat = log_file.stat()
            log_files.append(
                {
                    'filename': log_file.name,
                    'path': str(log_file),
                    'size_bytes': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(stat.st_ctime),
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'is_timestamped': '_20' in log_file.name,
                    'is_session': '_session_' in log_file.name,
                    'is_backup': '.log.' in log_file.name,
                }
            )

    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x['modified'], reverse=True)
    return log_files


def print_log_files_summary(log_dir: str = 'logs') -> None:
    """Print a formatted summary of all log files"""
    log_files = list_log_files(log_dir)

    if not log_files:
        print(f'📁 No log files found in {log_dir}/')
        return

    print(f'📁 Log Files in {log_dir}/ ({len(log_files)} files)')
    print('=' * 80)

    total_size = 0
    session_files = 0
    timestamped_files = 0
    backup_files = 0

    for log_file in log_files:
        # Icons based on file type
        icon = '📄'
        if log_file['is_session']:
            icon = '🎯'
            session_files += 1
        elif log_file['is_backup']:
            icon = '🔄'
            backup_files += 1
        elif log_file['is_timestamped']:
            icon = '⏰'
            timestamped_files += 1

        # Format file size
        if log_file['size_mb'] >= 1:
            size_str = f"{log_file['size_mb']}MB"
        else:
            size_str = f"{log_file['size_bytes']}B"

        # Format modification time
        mod_time = log_file['modified'].strftime('%Y-%m-%d %H:%M:%S')

        print(f"{icon} {log_file['filename']:<50} {size_str:>8} {mod_time}")
        total_size += log_file['size_bytes']

    print('=' * 80)
    print(f'📊 Summary:')
    print(f'   • Total files: {len(log_files)}')
    print(f'   • Total size: {round(total_size / (1024 * 1024), 2)}MB')
    print(f'   • Session files: {session_files}')
    print(f'   • Timestamped files: {timestamped_files}')
    print(f'   • Backup files: {backup_files}')


def cleanup_old_logs(log_dir: str = 'logs', days_to_keep: int = 30) -> int:
    """Clean up log files older than specified days

    Args:
        log_dir: Directory containing log files
        days_to_keep: Number of days of logs to keep

    Returns:
        Number of files deleted
    """
    log_files = list_log_files(log_dir)
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)

    deleted_count = 0
    logger = get_logger(__name__)

    for log_file in log_files:
        if log_file['modified'] < cutoff_date:
            try:
                Path(log_file['path']).unlink()
                logger.info(f"Deleted old log file: {log_file['filename']}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {log_file['filename']}: {e}")

    if deleted_count > 0:
        logger.info(f'Cleaned up {deleted_count} old log files')

    return deleted_count


def setup_default_logging() -> None:
    """Setup logging with default configuration from environment variables"""
    setup_logging(
        console_level=os.getenv('LOG_CONSOLE_LEVEL', 'INFO'),
        file_level=os.getenv('LOG_FILE_LEVEL', 'DEBUG'),
        log_dir=os.getenv('LOG_DIR', 'logs'),
        log_filename=os.getenv('LOG_FILENAME', 'gym_tracker_bot.log'),
        max_file_size_mb=int(os.getenv('LOG_MAX_FILE_SIZE_MB', '10')),
        backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5')),
        enable_colors=os.getenv('LOG_ENABLE_COLORS', 'true').lower()
        in ('true', '1', 'yes'),
        include_timestamp=os.getenv('LOG_INCLUDE_TIMESTAMP', 'true').lower()
        in ('true', '1', 'yes'),
    )


# Auto-configure logging when module is imported
# This ensures logging is ready as soon as any module imports this
if not logging.getLogger().handlers:
    setup_default_logging()
