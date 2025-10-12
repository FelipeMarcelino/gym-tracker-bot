from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Mensagem de boas-vindas
    """
    user_name = update.effective_user.first_name

    message = f"""
👋 Olá, {user_name}! Bem-vindo ao Gym Tracker Bot!

🎤 **Como usar:**
- Envie um áudio descrevendo seu treino
- Envie uma mensagem de texto com informações
- Use /help para ver os comandos disponíveis

Estou pronto para receber seus dados! 💪
    """

    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Ajuda
    """
    help_text = """
📖 **Comandos Disponíveis:**

/start - Mensagem de boas-vindas
/help - Mostra esta ajuda
/info - Informações sobre suas mensagens

🎤 **Enviar áudio:**
Grave um áudio descrevendo seu treino, por exemplo:
"Hoje fiz 3 séries de supino com 60kg, 12, 10 e 8 repetições"

💬 **Enviar texto:**
Digite informações sobre seu treino diretamente
    """

    await update.message.reply_text(help_text)


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /info - Mostra informações do usuário
    """
    user = update.effective_user

    info_text = f"""
👤 **Suas Informações:**

**Nome:** {user.first_name} {user.last_name or ''}
**Username:** @{user.username or 'não definido'}
**ID:** `{user.id}`
**Idioma:** {user.language_code or 'não definido'}

📅 **Data/Hora atual:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
    """

    await update.message.reply_text(info_text)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de TEXTO
    """
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    message_text = update.message.text
    timestamp = update.message.date

    # Printar no console (para debug)
    print("\n📝 MENSAGEM DE TEXTO RECEBIDA:")
    print(f"   Usuário: {user_name} (ID: {user_id})")
    print(f"   Horário: {timestamp}")
    print(f"   Texto: {message_text}")

    # Responder ao usuário
    response = f"""
✅ **Mensagem recebida!**

📝 Você escreveu:
_{message_text}_

👤 Seu ID: `{user_id}`
🕐 Horário: {timestamp.strftime('%H:%M:%S')}

_Em breve vou processar essa informação com IA!_ 🤖
    """

    await update.message.reply_text(response, parse_mode="Markdown")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de VOZ/ÁUDIO
    """
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    voice = update.message.voice
    timestamp = update.message.date

    # Informações do áudio
    duration = voice.duration  # segundos
    file_size = voice.file_size  # bytes
    file_id = voice.file_id

    # Printar no console
    print("\n🎤 ÁUDIO RECEBIDO:")
    print(f"   Usuário: {user_name} (ID: {user_id})")
    print(f"   Horário: {timestamp}")
    print(f"   Duração: {duration}s")
    print(f"   Tamanho: {file_size / 1024:.2f} KB")
    print(f"   File ID: {file_id}")

    # Responder ao usuário
    response = f"""
🎤 **Áudio recebido!**

⏱️ Duração: {duration} segundos
📦 Tamanho: {file_size / 1024:.2f} KB
👤 Seu ID: `{user_id}`
🕐 Horário: {timestamp.strftime('%H:%M:%S')}

_Em breve vou transcrever e processar esse áudio!_ 🤖
    """

    await update.message.reply_text(response, parse_mode="Markdown")


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para comandos desconhecidos
    """
    await update.message.reply_text(
        "❓ Comando não reconhecido.\n"
        "Use /help para ver os comandos disponíveis.",
    )
