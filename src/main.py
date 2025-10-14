import logging
from typing import NoReturn

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.handlers import (
    export_command,
    finish_command,
    handle_text,
    handle_unknown,
    handle_voice,
    help_command,
    info_command,
    myid_command,
    progress_command,
    start,
    stats_command,
    status_command,
)
from config.settings import settings
from services.container import initialize_all_services

# Configurar logging para ver o que está acontecendo
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main() -> NoReturn:
    """Função principal - inicializa e roda o bot"""
    print("=" * 50)
    print("🤖 GYM TRACKER BOT")
    print("=" * 50)
    print("🚀 Iniciando bot...")
    print("=" * 50)
    
    # Initialize all services early to catch configuration errors
    print("🔧 Inicializando serviços...")
    try:
        initialize_all_services()
        print("✅ Todos os serviços inicializados com sucesso")
    except Exception as e:
        print(f"❌ Erro ao inicializar serviços: {e}")
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
    print("\n✅ Bot rodando! Aguardando mensagens...")
    print("💡 Envie uma mensagem para o bot no Telegram")
    print("🛑 Pressione Ctrl+C para parar\n")

    # Rodar bot (polling = fica checando por mensagens)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot encerrado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro ao iniciar bot: {e}")
