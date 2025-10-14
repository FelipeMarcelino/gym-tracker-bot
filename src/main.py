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
from config.settings import settings
from services.container import initialize_all_services

logger = get_logger(__name__)


def main() -> NoReturn:
    """Função principal - inicializa e roda o bot"""
    # Log system info for debugging
    log_system_info()
    
    logger.info("🚀 Iniciando bot...")
    
    # Initialize all services early to catch configuration errors
    logger.info("🔧 Inicializando serviços...")
    try:
        initialize_all_services()
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

    # Mensagens de voz (ANTES de text, para ter prioridade)
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Mensagens de texto (mas não comandos)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text,
    ))

    # Comandos desconhecidos (SEMPRE POR ÚLTIMO)
    application.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    # ===== INICIAR BOT =====
    logger.info("\n✅ Bot rodando! Aguardando mensagens...")
    logger.info("💡 Envie uma mensagem para o bot no Telegram")
    logger.info("🛑 Pressione Ctrl+C para parar\n")

    # Rodar bot (polling = fica checando por mensagens)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n\n👋 Bot encerrado pelo usuário")
    except Exception as e:
        logger.error(f"\n❌ Erro ao iniciar bot: {e}")
