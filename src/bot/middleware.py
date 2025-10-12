from datetime import datetime
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings


def authorized_only(func):
    """Decorator para proteger handlers - apenas usuários autorizados podem usar
    
    Uso:
    @authorized_only
    async def meu_handler(update, context):
        ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id

        # Verificar se o usuário está autorizado
        if user_id not in settings.AUTHORIZED_USER_IDS:
            # Log da tentativa de acesso não autorizado
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🚫 ACESSO NEGADO [{timestamp}]")
            print(f"   User ID: {user_id}")
            print(f"   Nome: {user.first_name} {user.last_name or ''}")
            print(f"   Username: @{user.username or 'não definido'}")

            # Mensagem para o usuário não autorizado
            await update.message.reply_text(
                "🚫 **Acesso Negado**\n\n"
                "Este bot é de uso privado.\n"
                "Você não tem autorização para utilizá-lo.\n\n"
                f"_Seu ID: `{user_id}`_",
                parse_mode="Markdown",
            )
            return None  # Não executa a função original

        # Usuário autorizado - executar função normalmente
        return await func(update, context)

    return wrapper


async def log_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Loga todos os acessos ao bot (opcional - para monitoramento)
    """
    user = update.effective_user
    message = update.message

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determinar tipo de mensagem
    if message.text:
        msg_type = "TEXT"
        content = message.text[:50]  # Primeiros 50 caracteres
    elif message.voice:
        msg_type = "VOICE"
        content = f"{message.voice.duration}s"
    else:
        msg_type = "OTHER"
        content = "-"

    # Log formatado
    print(f"\n📊 ACESSO [{timestamp}]")
    print(f"   User: {user.first_name} (ID: {user.id})")
    print(f"   Tipo: {msg_type}")
    print(f"   Conteúdo: {content}")
