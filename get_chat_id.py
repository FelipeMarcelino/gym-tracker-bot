#!/usr/bin/env python3
"""
Script para descobrir o Chat ID de um canal/grupo do Telegram

Uso:
1. Adicione um bot ao seu canal como administrador
2. Configure o TELEGRAM_BOT_TOKEN no .env
3. Execute: python get_chat_id.py
4. Envie qualquer mensagem no canal
5. O script mostrará o Chat ID
"""

import os
import sys
from dotenv import load_dotenv

# Adicionar src ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

load_dotenv()

async def show_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra o chat ID quando recebe uma mensagem"""
    chat = update.effective_chat
    user = update.effective_user

    info = f"""
📊 Informações do Chat/Canal:

Chat ID: {chat.id}
Chat Type: {chat.type}
Chat Title: {chat.title if chat.title else 'N/A'}
Chat Username: @{chat.username if chat.username else 'N/A'}

User ID: {user.id if user else 'N/A'}
User Name: {user.first_name if user else 'N/A'}

═══════════════════════════════════════
Use este Chat ID nas configurações:
TELEGRAM_NOTIFY_CHAT_ID={chat.id}
═══════════════════════════════════════
    """

    print(info)

    try:
        await update.message.reply_text(
            f"✅ Chat ID descoberto!\n\n"
            f"Chat ID: `{chat.id}`\n"
            f"Type: {chat.type}\n\n"
            f"Use este ID no GitHub Secrets como TELEGRAM_NOTIFY_CHAT_ID",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"⚠️  Não foi possível responder (normal para canais): {e}")


def main():
    """Main function"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')

    if not token:
        print("❌ Erro: TELEGRAM_BOT_TOKEN não encontrado!")
        print("Configure o token no arquivo .env")
        sys.exit(1)

    print("🤖 Bot iniciado!")
    print("=" * 60)
    print("📝 INSTRUÇÕES:")
    print("=" * 60)
    print()
    print("1. Adicione o bot ao seu canal/grupo como ADMINISTRADOR")
    print("   - Vá no canal")
    print("   - Menu → Gerenciar canal → Administradores")
    print("   - Adicionar administrador → Busque seu bot")
    print()
    print("2. Envie qualquer mensagem no canal")
    print("   - Pode ser apenas 'teste'")
    print()
    print("3. O Chat ID aparecerá aqui automaticamente!")
    print()
    print("=" * 60)
    print("⏳ Aguardando mensagens...")
    print()

    # Criar aplicação
    application = Application.builder().token(token).build()

    # Adicionar handler para TODAS as mensagens
    application.add_handler(
        MessageHandler(filters.ALL, show_chat_id)
    )

    # Iniciar bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Bot encerrado!")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)
