"""Admin commands for database backup management"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from config.logging_config import get_logger
from services.backup_service import backup_service
from services.exceptions import BackupError
from bot.middleware import admin_only
from bot.validation_middleware import validate_input, CommonSchemas

logger = get_logger(__name__)


@admin_only
async def backup_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a manual database backup"""
    try:
        # Create backup
        backup_path = backup_service.create_backup()
        
        # Get backup info
        backups = backup_service.list_backups()
        latest_backup = backups[0] if backups else None
        
        if latest_backup:
            message = (
                "✅ **Backup Created Successfully**\n\n"
                f"📁 **File:** {latest_backup['name']}\n"
                f"📊 **Size:** {latest_backup['size_mb']} MB\n"
                f"🕐 **Created:** {latest_backup['created'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"✔️ **Verified:** {'Yes' if latest_backup['verified'] else 'No'}"
            )
        else:
            message = f"✅ Backup created: {backup_path}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Manual backup created by admin {update.effective_user.id}")
        
    except BackupError as e:
        error_msg = f"❌ Backup failed: {e.user_message or str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(f"Manual backup failed: {e}")
        
    except Exception as e:
        await update.message.reply_text("❌ An unexpected error occurred during backup")
        logger.exception(f"Unexpected error in backup_create: {e}")


@admin_only
async def backup_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available backups"""
    try:
        backups = backup_service.list_backups()
        
        if not backups:
            await update.message.reply_text("📁 No backups found")
            return
        
        # Build backup list message
        message = "📁 **Available Backups**\n\n"
        
        for i, backup in enumerate(backups[:10], 1):  # Show latest 10
            status = "✔️" if backup["verified"] else "❌"
            message += (
                f"{i}. **{backup['name']}**\n"
                f"   📊 Size: {backup['size_mb']} MB\n"
                f"   🕐 Created: {backup['created'].strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"   {status} Verified\n\n"
            )
        
        if len(backups) > 10:
            message += f"... and {len(backups) - 10} more backups\n\n"
        
        # Add summary
        stats = backup_service.get_backup_stats()
        message += (
            f"📈 **Summary**\n"
            f"Total: {stats['total_backups']} backups\n"
            f"Size: {stats['total_size_mb']} MB\n"
            f"Verified: {stats['verified_backups']}/{stats['total_backups']}"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text("❌ Failed to list backups")
        logger.exception(f"Error listing backups: {e}")


@admin_only
async def backup_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show backup statistics"""
    try:
        stats = backup_service.get_backup_stats()
        
        if "error" in stats:
            await update.message.reply_text(f"❌ Error getting backup stats: {stats['error']}")
            return
        
        message = "📊 **Backup Statistics**\n\n"
        
        if stats["total_backups"] == 0:
            message += "No backups found"
        else:
            message += (
                f"📁 **Total Backups:** {stats['total_backups']}\n"
                f"💾 **Total Size:** {stats['total_size_mb']} MB\n"
                f"✔️ **Verified:** {stats['verified_backups']}/{stats['total_backups']}\n"
                f"📂 **Directory:** `{stats['backup_directory']}`\n\n"
            )
            
            if stats["newest_backup"]:
                message += f"🆕 **Newest:** {stats['newest_backup'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            if stats["oldest_backup"]:
                message += f"📅 **Oldest:** {stats['oldest_backup'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Add system info
        message += f"\n🔧 **Config:**\n"
        message += f"Max backups: {backup_service.max_backups}\n"
        message += f"Frequency: every {backup_service.backup_frequency_hours} hours\n"
        message += f"Auto-backup: {'Running' if backup_service.is_running else 'Stopped'}"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text("❌ Failed to get backup statistics")
        logger.exception(f"Error getting backup stats: {e}")


@admin_only
@validate_input(CommonSchemas.text_message(min_length=5))
async def backup_restore(update: Update, context: ContextTypes.DEFAULT_TYPE, validated_data=None):
    """Restore database from backup (DANGEROUS OPERATION)"""
    try:
        # Parse backup name from message
        text = validated_data["text"]
        parts = text.split()
        
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Please specify backup filename:\n"
                "`/backup_restore backup_filename.db`\n\n"
                "⚠️ **WARNING:** This will replace the current database!"
            )
            return
        
        backup_name = parts[1]
        
        # Safety confirmation check
        if len(parts) < 3 or parts[2].lower() != "confirm":
            await update.message.reply_text(
                f"⚠️ **DANGER: DATABASE RESTORE**\n\n"
                f"You are about to restore from: `{backup_name}`\n"
                f"This will **REPLACE** the current database!\n\n"
                f"To proceed, use:\n"
                f"`/backup_restore {backup_name} confirm`\n\n"
                f"⚠️ **This action cannot be undone!**"
            )
            return
        
        # Find backup file
        backups = backup_service.list_backups()
        backup_path = None
        
        for backup in backups:
            if backup["name"] == backup_name:
                backup_path = backup["path"]
                break
        
        if not backup_path:
            await update.message.reply_text(
                f"❌ Backup not found: `{backup_name}`\n\n"
                f"Use `/backup_list` to see available backups"
            )
            return
        
        # Perform restore
        await update.message.reply_text("🔄 Starting database restore...")
        
        success = backup_service.restore_backup(backup_path, confirm=True)
        
        if success:
            await update.message.reply_text(
                f"✅ **Database Restored Successfully**\n\n"
                f"Restored from: `{backup_name}`\n"
                f"⚠️ **Bot restart recommended**"
            )
            logger.warning(f"Database restored from {backup_name} by admin {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ Database restore failed")
        
    except BackupError as e:
        error_msg = f"❌ Restore failed: {e.user_message or str(e)}"
        await update.message.reply_text(error_msg)
        logger.error(f"Database restore failed: {e}")
        
    except Exception as e:
        await update.message.reply_text("❌ An unexpected error occurred during restore")
        logger.exception(f"Unexpected error in backup_restore: {e}")


@admin_only
async def backup_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clean up old backups"""
    try:
        # Get current backup count
        stats = backup_service.get_backup_stats()
        old_count = stats["total_backups"]
        
        # Perform cleanup
        backup_service.cleanup_old_backups()
        
        # Get new count
        new_stats = backup_service.get_backup_stats()
        new_count = new_stats["total_backups"]
        
        removed = old_count - new_count
        
        message = (
            f"🧹 **Backup Cleanup Complete**\n\n"
            f"Removed: {removed} old backups\n"
            f"Remaining: {new_count} backups\n"
            f"Total size: {new_stats['total_size_mb']} MB"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Backup cleanup performed by admin {update.effective_user.id}: removed {removed} backups")
        
    except Exception as e:
        await update.message.reply_text("❌ Failed to cleanup backups")
        logger.exception(f"Error during backup cleanup: {e}")


@admin_only
async def backup_auto_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start automated backups"""
    try:
        if backup_service.is_running:
            await update.message.reply_text("🔄 Automated backups are already running")
            return
        
        backup_service.start_automated_backups()
        
        message = (
            f"✅ **Automated Backups Started**\n\n"
            f"📅 Frequency: every {backup_service.backup_frequency_hours} hours\n"
            f"📁 Max backups: {backup_service.max_backups}\n"
            f"📂 Directory: `{backup_service.backup_dir}`"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Automated backups started by admin {update.effective_user.id}")
        
    except Exception as e:
        await update.message.reply_text("❌ Failed to start automated backups")
        logger.exception(f"Error starting automated backups: {e}")


@admin_only
async def backup_auto_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop automated backups"""
    try:
        if not backup_service.is_running:
            await update.message.reply_text("⏹️ Automated backups are not running")
            return
        
        backup_service.stop_automated_backups()
        
        await update.message.reply_text("⏹️ **Automated Backups Stopped**")
        logger.info(f"Automated backups stopped by admin {update.effective_user.id}")
        
    except Exception as e:
        await update.message.reply_text("❌ Failed to stop automated backups")
        logger.exception(f"Error stopping automated backups: {e}")


# Help text for backup commands
BACKUP_HELP = """
🔧 **Backup Management Commands** (Admin Only)

📁 **Basic Operations:**
• `/backup_create` - Create manual backup
• `/backup_list` - List available backups
• `/backup_stats` - Show backup statistics
• `/backup_cleanup` - Remove old backups

⚠️ **Danger Zone:**
• `/backup_restore <filename> confirm` - Restore from backup

🔄 **Automation:**
• `/backup_auto_start` - Start automated backups
• `/backup_auto_stop` - Stop automated backups

⚠️ **Important Notes:**
• Restore operations REPLACE the current database
• Always verify backups before restoring
• Automated backups run every 6 hours by default
• Maximum 30 backups are kept (configurable)
"""