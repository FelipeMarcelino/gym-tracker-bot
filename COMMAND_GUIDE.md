# 🤖 Gym Tracker Bot - Command Guide

## 🚀 How to Run the Bot

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python run_bot.py
# OR
python src/main.py
```

## 📱 Available Commands

### 👤 User Commands (All Users)
- `/start` - Initialize bot
- `/help` - Show help message with all commands
- `/status` - Check current workout session status
- `/stats [days]` - View workout statistics
- `/exercises` - List all exercises in database
- `/export [json|csv]` - Export workout data
- `/myid` - Get your Telegram user ID

### 🔧 Health & Monitoring Commands (Admin Only)

#### `/health`
**Quick system health check**
- Shows: Overall status, uptime, database connectivity
- Example output:
```
Status: healthy
Uptime: 150s
Database: healthy
CPU OK: True
Memory OK: True
```

#### `/healthfull`
**Comprehensive health analysis**
- Shows: Detailed system checks, all components status
- Includes: Database, async database, system resources, configuration, dependencies

#### `/metrics`
**Performance metrics overview**
- Shows: CPU/Memory/Disk usage, database performance, bot statistics
- Example output:
```
🖥️ System Metrics:
   CPU: 15.2%
   Memory: 67.1%
   Disk: 45.8%

💾 Database Metrics:
   Response Time: 12.34ms
   Total Users: 25
   Sessions Today: 8

🤖 Bot Metrics:
   Commands Processed: 1,245
   Error Rate: 0.8%
```

#### `/performance`
**Bot performance analysis**
- Shows: Response times, error rates, operation statistics
- Includes: Average processing time, success rates

### 💾 Backup Commands (Admin Only)

#### `/backup_create`
**Create manual backup**
- Creates timestamped backup file
- Verifies backup integrity
- Example: Creates `gym_tracker_backup_20241014_163920.db`

#### `/backup_list`
**List available backups**
- Shows all backup files with details
- Displays: filename, size, creation date, verification status

#### `/backup_stats`
**Backup statistics overview**
- Shows: total backups, total size, verification status
- Includes: newest/oldest backup dates, directory info

#### `/backup_cleanup`
**Remove old backups**
- Automatically removes backups beyond max limit (30 by default)
- Keeps most recent backups

#### `/backup_auto_start`
**Enable automated backups**
- Starts background scheduler
- Creates backups every 6 hours automatically
- Runs cleanup after each backup

#### `/backup_auto_stop`
**Disable automated backups**
- Stops background scheduler
- Manual backups still work

#### `/backup_restore <filename> confirm`
**⚠️ DANGEROUS: Restore from backup**
- **REPLACES current database completely**
- Requires explicit confirmation
- Creates backup of current data before restore

**Example:**
```
/backup_restore gym_tracker_backup_20241014_142431.db confirm
```

## 🎯 Recommended Workflow

### Daily Usage
1. `/health` - Check system status
2. `/backup_create` - Create backup before major operations
3. `/metrics` - Monitor performance

### Initial Setup
1. `/backup_auto_start` - Enable automatic backups
2. `/health` - Verify everything is working
3. `/backup_create` - Create initial manual backup

### Maintenance
1. `/backup_stats` - Check backup status
2. `/backup_cleanup` - Remove old backups if needed
3. `/healthfull` - Full system check
4. `/performance` - Analyze bot performance

### Emergency Recovery
1. `/backup_list` - Find recent backup
2. `/backup_restore <filename> confirm` - Restore if needed
3. `/health` - Verify system after restore

## 🔒 Security Notes

- **Admin Commands**: Only work for users with admin privileges
- **Backup Restore**: Extremely dangerous - backs up current data first
- **Confirmation Required**: Restore operations need explicit "confirm" parameter
- **Automatic Verification**: All backups are verified for integrity

## 📊 What Each Command Monitors

### Health Commands
- **System Resources**: CPU, memory, disk usage
- **Database**: Connection status, query performance
- **Dependencies**: Required libraries and versions
- **Configuration**: Critical settings validation

### Backup Commands
- **Data Safety**: Regular database backups
- **Storage Management**: Automatic cleanup of old backups
- **Integrity**: Verification of backup files
- **Automation**: Scheduled backup creation

## 🚨 Important Warnings

1. **Backup Restore**: 
   - REPLACES entire database
   - Cannot be undone
   - Always creates pre-restore backup

2. **Storage Space**: 
   - Backups consume disk space
   - Use `/backup_cleanup` regularly
   - Monitor with `/backup_stats`

3. **Admin Access**: 
   - All monitoring commands require admin privileges
   - Regular users cannot access these features

## 🛠️ Troubleshooting

### Command Not Working?
- Check if you have admin privileges
- Verify bot is running properly
- Check logs for error messages

### Backup Issues?
- Ensure disk space available
- Check backup directory permissions
- Verify database is not corrupted

### Health Check Failures?
- Check system resources
- Verify database connectivity
- Review configuration settings

## 📝 Example Command Session

```
Admin: /health
Bot: ✅ Status: healthy, Uptime: 3600s, Database: healthy

Admin: /backup_create  
Bot: ✅ Backup created: gym_tracker_backup_20241014_142431.db

Admin: /metrics
Bot: 📊 CPU: 12%, Memory: 45%, DB Response: 8ms

Admin: /backup_auto_start
Bot: ✅ Automated backups started: every 6 hours

Admin: /backup_stats
Bot: 📁 Total: 15 backups, Size: 2.4 MB, All verified
```