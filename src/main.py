import asyncio
from typing import NoReturn

from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Import centralized logging FIRST
from config.logging_config import get_logger, log_system_info

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
from bot.backup_commands import (
    backup_create, backup_list, backup_stats, backup_restore, 
    backup_cleanup, backup_auto_start, backup_auto_stop
)
from config.settings import settings
from services.container import initialize_all_services
from services.async_container import initialize_async_services, shutdown_async_services
from services.shutdown_service import shutdown_service
from services.backup_service import backup_service

logger = get_logger(__name__)


def main() -> NoReturn:
    """Função principal - inicializa e roda o bot"""
    # Log system info for debugging
    log_system_info()
    
    logger.info("🚀 Iniciando bot...")
    
    # Initialize services early to catch configuration errors
    logger.info("🔧 Inicializando serviços...")
    try:
        # Initialize remaining sync services (audio, llm, export, analytics)
        initialize_all_services()
        
        # Initialize async services (user, workout, session)
        asyncio.get_event_loop().run_until_complete(initialize_async_services())
        
        logger.info("✅ Todos os serviços inicializados com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar serviços: {e}")
        raise

    # Criar aplicação
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # ===== ADICIONAR HANDLERS =====

    # Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("status", status_command))  # ← NOVO
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

    # Mensagens de voz (ANTES de text, para ter prioridade)
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Mensagens de texto (mas não comandos)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text,
    ))

    # Comandos desconhecidos (SEMPRE POR ÚLTIMO)
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    # ===== SETUP GRACEFUL SHUTDOWN =====
    logger.info("🔧 Setting up graceful shutdown...")
    
    # Setup signal handlers for graceful shutdown
    shutdown_service.setup_signal_handlers()
    
    # Register bot-specific shutdown handlers
    def stop_telegram_bot():
        """Stop the Telegram bot gracefully"""
        try:
            logger.info("Stopping Telegram bot...")
            application.stop()
            logger.info("✅ Telegram bot stopped")
        except Exception as e:
            logger.exception(f"Error stopping Telegram bot: {e}")
    
    def start_automated_backups():
        """Start automated backups if not already running"""
        try:
            if not backup_service.is_running:
                logger.info("Starting automated backups...")
                backup_service.start_automated_backups()
                logger.info("✅ Automated backups started")
            else:
                logger.info("Automated backups already running")
        except Exception as e:
            logger.exception(f"Error starting automated backups: {e}")
    
    def shutdown_async_services_handler():
        """Shutdown async services gracefully"""
        try:
            logger.info("Shutting down async services...")
            asyncio.get_event_loop().run_until_complete(shutdown_async_services())
            logger.info("✅ Async services shutdown")
        except Exception as e:
            logger.exception(f"Error shutting down async services: {e}")
    
    # Register shutdown handlers
    shutdown_service.register_shutdown_handler(stop_telegram_bot, "Stop Telegram bot")
    shutdown_service.register_shutdown_handler(shutdown_async_services_handler, "Shutdown async services")
    
    # Start automated backups
    start_automated_backups()

    # ===== INICIAR BOT =====
    logger.info("\n✅ Bot rodando! Aguardando mensagens...")
    logger.info("💡 Envie uma mensagem para o bot no Telegram")
    logger.info("🛑 Pressione Ctrl+C para parar gracefully\n")

    # Rodar bot (polling = fica checando por mensagens)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  KeyboardInterrupt received - graceful shutdown already handled by signal")
        logger.info("👋 Bot encerrado pelo usuário")
    except Exception as e:
        logger.error(f"\n❌ Erro ao iniciar bot: {e}")
        # Try to perform emergency shutdown
        try:
            shutdown_service.initiate_shutdown()
        except Exception as shutdown_error:
            logger.exception(f"Failed to perform emergency shutdown: {shutdown_error}")
        raise
