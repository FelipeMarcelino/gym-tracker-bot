import asyncio
import sys
from typing import NoReturn

from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Import centralized logging FIRST
from config.logging_config import get_logger, log_system_info

logger = get_logger(__name__)

from bot.backup_commands import (
    backup_auto_start,
    backup_auto_stop,
    backup_cleanup,
    backup_create,
    backup_list,
    backup_restore,
    backup_stats,
)

# Import handlers
from bot.handlers import (
    add_user_command,
    exercises_command,
    export_command,
    finish_command,
    handle_text,
    handle_unknown,
    handle_voice,
    help_command,
    info_command,
    list_users_command,
    myid_command,
    progress_command,
    remove_user_command,
    start,
    stats_command,
    status_command,
)
from bot.health_endpoints import health_command, health_full_command, metrics_command, performance_command
from config.settings import settings
from services.async_container import initialize_async_services, shutdown_async_services
from services.async_backup_service import backup_service
from services.container import initialize_all_services
from services.async_shutdown_service import shutdown_service


def setup_signal_handlers(app: Application):
    """Setup signal handlers for graceful shutdown"""
    
    # Add a shutdown callback to the application
    async def shutdown_callback(app):
        """Called when the application is shutting down"""
        logger.info("🛑 Application shutdown initiated...")
        
        try:
            # Stop backup service first
            from services.async_backup_service import backup_service
            await backup_service.stop_automated_backups_async()
            logger.info("✅ Backup service stopped")
            
            # Stop other async services
            await shutdown_async_services()
            logger.info("✅ Async services stopped")
            
            # Stop shutdown service
            await shutdown_service.initiate_shutdown()
            logger.info("✅ Shutdown service completed")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
    
    # Register the shutdown callback
    app.post_shutdown = shutdown_callback
    
    logger.info("📡 Shutdown callback registered")


def main() -> NoReturn:
    """Main function to initialize and run the bot"""
    # Log system info for debugging
    log_system_info()

    logger.info("🚀 Starting Gym Tracker Bot...")
    logger.info(f"🐍 Python version: {sys.version}")
    logger.info(f"📁 Working directory: {sys.path[0]}")

    # Check critical configuration
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not configured!")
        logger.error("Please set TELEGRAM_BOT_TOKEN in your .env file")
        sys.exit(1)

    # Initialize services
    logger.info("=" * 60)
    logger.info("🔧 INITIALIZING SERVICES")
    logger.info("=" * 60)

    try:
        # Initialize sync services
        logger.info("📦 [1/2] Initializing sync services...")
        initialize_all_services()
        logger.info("✅ Sync services initialized")

        # Initialize async services
        logger.info("🚀 [2/2] Initializing async services...")
        # Create a new event loop for initialization
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(initialize_async_services())
        logger.info("✅ Async services initialized")

    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("🤖 CREATING TELEGRAM BOT")
    logger.info("=" * 60)

    # Create Telegram application with proper timeout settings
    from telegram.request import HTTPXRequest
    
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=10.0
    )
    
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .request(request)
        .build()
    )

    # Setup signal handlers
    setup_signal_handlers(application)

    # ===== ADD HANDLERS =====
    logger.info("📝 Registering command handlers...")

    # ... (add handlers as before)
    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("finish", finish_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("progress", progress_command))
    application.add_handler(CommandHandler("exercises", exercises_command))

    # Admin commands
    application.add_handler(CommandHandler("adduser", add_user_command))
    application.add_handler(CommandHandler("removeuser", remove_user_command))
    application.add_handler(CommandHandler("listusers", list_users_command))

    # Health and monitoring commands (Admin only)
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("healthfull", health_full_command))
    application.add_handler(CommandHandler("metrics", metrics_command))
    application.add_handler(CommandHandler("performance", performance_command))

    # Backup commands (Admin only)
    application.add_handler(CommandHandler("backup_create", backup_create))
    application.add_handler(CommandHandler("backup_list", backup_list))
    application.add_handler(CommandHandler("backup_stats", backup_stats))
    application.add_handler(CommandHandler("backup_restore", backup_restore))
    application.add_handler(CommandHandler("backup_cleanup", backup_cleanup))
    application.add_handler(CommandHandler("backup_auto_start", backup_auto_start))
    application.add_handler(CommandHandler("backup_auto_stop", backup_auto_stop))

    # Message handlers
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown))


    logger.info("✅ All handlers registered")
    
    # Add post_init callback to start backup scheduler  
    async def post_init_callback(app):
        """Called after the application is initialized and event loop is running"""
        logger.info("🔄 Starting backup scheduler...")
        await backup_service.ensure_scheduler_running()
        logger.info("✅ Backup scheduler started")

    application.post_init = post_init_callback

    # Start automated backups (will defer scheduler until event loop runs)
    try:
        logger.info("💾 Starting automated backups...")
        backup_service.start_automated_backups()
        logger.info("✅ Automated backups started")
    except Exception as e:
        logger.warning(f"⚠️ Could not start automated backups: {e}")

    # ===== START BOT =====
    logger.info("=" * 60)
    logger.info("✅ BOT READY!")
    logger.info("💬 Send a message to your bot on Telegram")
    logger.info("🛑 Press Ctrl+C to stop gracefully")
    logger.info("=" * 60)

    # Run bot with default signal handling (SIGINT, SIGTERM)
    application.run_polling(allowed_updates=["message"])
    
    # Note: The backup scheduler will auto-start when the event loop begins


if __name__ == "__main__":
    main()