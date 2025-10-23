import asyncio
import os
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
    ratelimit_cleanup_command,
    ratelimit_stats_command,
    remove_user_command,
    start,
    stats_command,
    status_command,
)
from bot.health_endpoints import health_command, health_full_command, metrics_command, performance_command
from config.settings import settings
from services.async_container import (
    initialize_async_services,
    shutdown_async_services,
)
from services.async_backup_service import backup_service
from services.rate_limit_cleanup_service import rate_limit_cleanup_service
from services.container import initialize_all_services
from services.async_shutdown_service import shutdown_service
from services.async_user_service import AsyncUserService


def setup_signal_handlers(app: Application):
    """Setup signal handlers for graceful shutdown"""
    
    # Add a shutdown callback to the application
    async def shutdown_callback(app):
        """Called when the application is shutting down"""
        logger.info("🛑 Application shutdown initiated...")

        try:
            # Stop backup service first
            await backup_service.stop_automated_backups_async()
            logger.info("✅ Backup service stopped")

            # Stop rate limit cleanup service
            await rate_limit_cleanup_service.stop_automated_cleanup_async()
            logger.info("✅ Rate limit cleanup service stopped")

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


async def initialize_admin_user() -> None:
    """Initialize the first admin user from environment variables

    This function runs during bot startup to ensure the first admin user
    is created in the database if it doesn't exist yet.

    It checks:
    1. FIRST_ADMIN_USER_ID environment variable
    2. First user from AUTHORIZED_USER_IDS if FIRST_ADMIN_USER_ID is not set

    If the user doesn't exist, creates them as admin.
    If the user already exists, does nothing (preserves current state).
    """
    try:
        # Try to get admin user ID from environment
        admin_id = os.getenv("FIRST_ADMIN_USER_ID")

        if not admin_id:
            # Try to get from authorized users list
            user_ids = settings.authorized_user_ids_list
            if user_ids:
                admin_id = str(user_ids[0])
            else:
                logger.info("⚠️  No admin user configured in FIRST_ADMIN_USER_ID or AUTHORIZED_USER_IDS")
                return

        admin_id = admin_id.strip()
        logger.info(f"🔧 Checking admin user initialization for ID: {admin_id}")

        # Initialize user service
        user_service = AsyncUserService()

        # Check if user already exists
        existing_user = await user_service.get_user(admin_id)

        if existing_user:
            # User already exists - do nothing
            if existing_user.is_admin:
                logger.info(f"✅ Admin user {admin_id} already exists and is admin")
            else:
                logger.info(f"✅ User {admin_id} already exists (not promoting to admin)")
            return

        # User doesn't exist - create as admin
        logger.info(f"🔧 Creating new admin user: {admin_id}")
        user = await user_service.add_user(
            user_id=admin_id,
            is_admin=True,
            created_by="system"  # Created by system initialization
        )

        logger.info(f"✅ Admin user created successfully!")
        logger.info(f"   ID: {user.user_id}")
        logger.info(f"   Admin: {user.is_admin}")
        logger.info(f"   Active: {user.is_active}")

    except Exception as e:
        logger.warning(f"⚠️  Could not initialize admin user: {e}")
        logger.warning("   You may need to run: python src/migrate_admin.py")


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

        # Initialize admin user
        logger.info("👤 Initializing admin user...")
        loop.run_until_complete(initialize_admin_user())
        logger.info("✅ Admin user initialization complete")

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
    application.add_handler(CommandHandler("ratelimit_cleanup", ratelimit_cleanup_command))
    application.add_handler(CommandHandler("ratelimit_stats", ratelimit_stats_command))

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
    
    # Add post_init callback to start schedulers
    async def post_init_callback(app):
        """Called after the application is initialized and event loop is running"""
        logger.info("🔄 Starting backup scheduler...")
        await backup_service.ensure_scheduler_running()
        logger.info("✅ Backup scheduler started")

        logger.info("🔄 Starting rate limit cleanup scheduler...")
        await rate_limit_cleanup_service.ensure_scheduler_running()
        logger.info("✅ Rate limit cleanup scheduler started")

    application.post_init = post_init_callback

    # Start automated backups (will defer scheduler until event loop runs)
    try:
        logger.info("💾 Starting automated backups...")
        backup_service.start_automated_backups()
        logger.info("✅ Automated backups started")
    except Exception as e:
        logger.warning(f"⚠️ Could not start automated backups: {e}")

    # Start automated rate limit cleanup (will defer scheduler until event loop runs)
    try:
        logger.info("🧹 Starting automated rate limit cleanup...")
        rate_limit_cleanup_service.start_automated_cleanup()
        logger.info("✅ Automated rate limit cleanup started")
    except Exception as e:
        logger.warning(f"⚠️ Could not start automated rate limit cleanup: {e}")

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
