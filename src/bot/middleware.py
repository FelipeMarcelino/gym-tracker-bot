import logging
from datetime import datetime
from functools import wraps
from typing import Callable, Any, Awaitable

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings
from config.messages import messages
from services.async_container import get_async_user_service

logger = logging.getLogger(__name__)


def authorized_only(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]:
    """Decorator para proteger handlers - apenas usuários autorizados podem usar
    
    Uso:
    @authorized_only
    async def meu_handler(update, context):
        ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        user = update.effective_user
        user_id = user.id

        # Verificar se o usuário está autorizado usando banco de dados (async)
        user_service = await get_async_user_service()
        
        # Atualizar informações do usuário se já existe (async)
        existing_user = await user_service.get_user(str(user_id))
        if existing_user:
            await user_service.update_user_info(
                str(user_id),
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
        
        if not await user_service.is_user_authorized(str(user_id)):
            # Log da tentativa de acesso não autorizado
            logger.warning(f"Acesso negado para usuário {user_id} ({user.first_name} {user.last_name or ''}, @{user.username or 'não definido'})")

            # Mensagem para o usuário não autorizado
            await update.message.reply_text(
                messages.ACCESS_DENIED.format(user_id=user_id),
                parse_mode="Markdown",
            )
            return None  # Não executa a função original

        # Usuário autorizado - executar função normalmente
        return await func(update, context)

    return wrapper


def admin_only(func: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]:
    """Decorator para proteger handlers - apenas admins podem usar
    
    Uso:
    @admin_only 
    async def admin_handler(update, context):
        ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        user = update.effective_user
        user_id = str(user.id)

        user_service = await get_async_user_service()
        
        # Verificar se é admin (async)
        if not await user_service.is_user_admin(user_id):
            logger.warning(f"Acesso admin negado para usuário {user_id} ({user.first_name} {user.last_name or ''})")

            await update.message.reply_text(
                "🚫 **Acesso Negado**\n\nApenas administradores podem usar este comando.",
                parse_mode="Markdown",
            )
            return None

        # Admin autorizado - executar função normalmente
        return await func(update, context)

    return wrapper


async def log_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loga todos os acessos ao bot (opcional - para monitoramento)
    """
    user = update.effective_user
    message = update.message

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Determinar tipo de mensagem
    if message.text:
        msg_type = "TEXT"
        content = message.text[:settings.LOG_MESSAGE_PREVIEW_LENGTH]  # Primeiros caracteres configuráveis
    elif message.voice:
        msg_type = "VOICE"
        content = f"{message.voice.duration}s"
    else:
        msg_type = "OTHER"
        content = "-"

    # Log formatado
    logger.info(f"Acesso do usuário {user.first_name} (ID: {user.id}) - Tipo: {msg_type}, Conteúdo: {content}")
