# Centralized Logging Configuration

This document explains how to use the centralized logging system in the Gym Tracker Bot.

## Overview

The logging system provides:
- **Console output**: INFO level and above with colored output
- **File output**: DEBUG level and above with detailed format including function names and line numbers
- **Rotating log files**: Automatic file rotation when size limit is reached
- **Configurable levels**: Environment variable configuration support

## Basic Usage

### In any module:

```python
from config.logging_config import get_logger

logger = get_logger(__name__)

# Use the logger
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error")

# Exception logging with traceback
try:
    # some code
    pass
except Exception as e:
    logger.exception("An error occurred")
```

## Log Levels

| Level    | Console | File | Description |
|----------|---------|------|-------------|
| DEBUG    | ❌      | ✅   | Detailed diagnostic information |
| INFO     | ✅      | ✅   | General information messages |
| WARNING  | ✅      | ✅   | Warning messages |
| ERROR    | ✅      | ✅   | Error messages |
| CRITICAL | ✅      | ✅   | Critical error messages |

## Configuration

### Environment Variables

You can configure logging behavior using environment variables:

```bash
# Console log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_CONSOLE_LEVEL=INFO

# File log level
LOG_FILE_LEVEL=DEBUG

# Log directory
LOG_DIR=logs

# Log filename (base name - timestamp will be added if enabled)
LOG_FILENAME=gym_tracker_bot.log

# Maximum file size before rotation (MB)
LOG_MAX_FILE_SIZE_MB=10

# Number of backup files to keep
LOG_BACKUP_COUNT=5

# Enable colored console output (true/false)
LOG_ENABLE_COLORS=true

# Include timestamp in log filename (true/false)
LOG_INCLUDE_TIMESTAMP=true
```

### Programmatic Configuration

```python
from config.logging_config import setup_logging, setup_session_logging

# Standard logging with timestamps
setup_logging(
    console_level="INFO",
    file_level="DEBUG",
    log_dir="logs",
    log_filename="app.log",
    max_file_size_mb=20,
    backup_count=10,
    enable_colors=True,
    include_timestamp=True
)

# Session-specific logging (automatically timestamped)
session_id = setup_session_logging()
print(f"Logging to session: {session_id}")
```

## Log Format

### Console Format
```
HH:MM:SS | LEVEL | module.name | message
```

Example:
```
14:30:45 | INFO | bot.handlers | User 12345 sent voice message
```

### File Format
```
YYYY-MM-DD HH:MM:SS | LEVEL | module.name | function_name:line | message
```

Example:
```
2025-10-14 14:30:45 | INFO | bot.handlers | handle_voice:547 | User 12345 sent voice message
```

## Log Files

- **Location**: `logs/` directory (configurable)
- **Timestamped files**: `gym_tracker_bot_20251014_143022.log` (when `LOG_INCLUDE_TIMESTAMP=true`)
- **Standard files**: `gym_tracker_bot.log` (when `LOG_INCLUDE_TIMESTAMP=false`)
- **Session files**: `gym_tracker_bot_session_20251014_143022.log` (when using `setup_session_logging()`)
- **Rotation**: When file reaches 10MB (configurable)
- **Backups**: Keeps 5 backup files (configurable)
- **Naming**: `filename.log.1`, `filename.log.2`, etc.

### Timestamp Formats

- **Date format**: `YYYYMMDD` (e.g., `20251014`)
- **Time format**: `HHMMSS` (e.g., `143022`)
- **Combined**: `YYYYMMDD_HHMMSS` (e.g., `20251014_143022`)

### File Naming Examples

```
# With timestamps enabled (default)
gym_tracker_bot_20251014_143022.log
gym_tracker_bot_20251014_143022.log.1
gym_tracker_bot_20251014_143022.log.2

# Session-specific logging
gym_tracker_bot_session_20251014_143022.log
gym_tracker_bot_session_20251014_143022.log.1

# Without timestamps
gym_tracker_bot.log
gym_tracker_bot.log.1
gym_tracker_bot.log.2
```

## Examples

### Basic Logging
```python
from config.logging_config import get_logger

logger = get_logger(__name__)

logger.info("Application started")
logger.debug(f"Processing user {user_id}")
logger.warning(f"Rate limit exceeded for user {user_id}")
logger.error(f"Failed to process audio: {error}")
```

### Exception Logging
```python
try:
    result = process_workout(data)
    logger.info(f"Workout processed successfully: {result}")
except ValidationError as e:
    logger.error(f"Validation failed: {e}")
except Exception as e:
    logger.exception("Unexpected error occurred")
```

### Structured Logging
```python
# Good practices for consistent logging
logger.info(f"Audio received from {user_name} (ID: {user_id}) - Duration: {duration}s")
logger.debug(f"Parsed {len(exercises)} exercises from transcription")
logger.warning(f"User {user_id} exceeded rate limit: {attempts} attempts")
```

### Session-Based Logging
```python
from config.logging_config import setup_session_logging, get_session_id

# Automatic session ID generation
session_id = setup_session_logging()
logger = get_logger(__name__)
logger.info(f"Started new session: {session_id}")

# Manual session ID
custom_session = "maintenance_20251014"
setup_session_logging(custom_session)
logger.info("Running maintenance tasks")

# Get current session ID
current_session = get_session_id()
logger.info(f"Current session: {current_session}")
```

## Migration from Print Statements

### Before (print statements):
```python
print(f"✅ Processing complete in {time:.2f}s")
print(f"❌ Error: {error}")
```

### After (centralized logging):
```python
logger.info(f"Processing complete in {time:.2f}s")
logger.error(f"Error: {error}")
```

## Third-Party Library Logs

The system automatically configures third-party library log levels to reduce noise:

- **Telegram libraries**: WARNING level
- **SQLAlchemy**: WARNING level  
- **HTTP libraries**: WARNING level

## Best Practices

1. **Use appropriate log levels**:
   - `DEBUG`: Detailed diagnostic information
   - `INFO`: Normal application flow
   - `WARNING`: Unexpected but recoverable situations
   - `ERROR`: Error conditions that don't stop the application
   - `CRITICAL`: Serious errors that may stop the application

2. **Include context in messages**:
   ```python
   # Good
   logger.info(f"User {user_id} completed workout session {session_id}")
   
   # Bad
   logger.info("Workout completed")
   ```

3. **Use structured formatting**:
   ```python
   logger.info(f"Audio processing: user={user_id}, duration={duration}s, size={size}KB")
   ```

4. **Avoid sensitive information**:
   ```python
   # Good
   logger.info(f"User {user_id} authenticated")
   
   # Bad
   logger.info(f"User logged in with token: {secret_token}")
   ```

## Troubleshooting

### Log files not being created
- Check if the `logs/` directory exists and is writable
- Verify file permissions
- Check disk space

### Console output missing colors
- Ensure `LOG_ENABLE_COLORS=true` in environment
- Verify terminal supports ANSI colors
- Check if output is being redirected

### Too many/few log messages
- Adjust `LOG_CONSOLE_LEVEL` and `LOG_FILE_LEVEL`
- Check third-party library log levels
- Review log level usage in code

### Log files growing too large
- Reduce `LOG_MAX_FILE_SIZE_MB`
- Increase rotation frequency
- Review DEBUG level usage

## Log File Management

### Listing Log Files
```python
from config.logging_config import list_log_files, print_log_files_summary

# Get list of log files with metadata
log_files = list_log_files("logs")
for log_file in log_files:
    print(f"{log_file['filename']} - {log_file['size_mb']}MB")

# Print formatted summary
print_log_files_summary("logs")
```

### Cleaning Up Old Logs
```python
from config.logging_config import cleanup_old_logs

# Clean up logs older than 30 days
deleted_count = cleanup_old_logs("logs", days_to_keep=30)
print(f"Deleted {deleted_count} old log files")
```

### Log File Types
- **📄 Standard**: `gym_tracker_bot.log` - Regular log files
- **⏰ Timestamped**: `gym_tracker_bot_20251014_143022.log` - Files with timestamps
- **🎯 Session**: `gym_tracker_bot_session_20251014_143022.log` - Session-specific logs
- **🔄 Backup**: `gym_tracker_bot.log.1` - Rotated backup files