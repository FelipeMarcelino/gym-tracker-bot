import time
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware import authorized_only, log_access
from config.settings import settings
from services.audio_service import get_audio_service
from services.llm_service import get_llm_service
from services.session_manager import get_session_manager  # ← NOVO
from services.workout_service import get_workout_service


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Mensagem de boas-vindas
    """
    await log_access(update, context)
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
    await log_access(update, context)
    help_text = """
📖 **Comandos Disponíveis:**

/start - Mensagem de boas-vindas
/help - Mostra esta ajuda
/info - Informações sobre suas mensagens
/myid - Mostra seu User ID

🎤 **Enviar áudio:**
Grave um áudio descrevendo seu treino, por exemplo:
"Hoje fiz 3 séries de supino com 60kg, 12, 10 e 8 repetições"

💬 **Enviar texto:**
Digite informações sobre seu treino diretamente
    """

    await update.message.reply_text(help_text)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /myid - Mostra o user_id (útil para adicionar novos usuários)
    """
    await log_access(update, context)
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = update.effective_user.username

    await update.message.reply_text(
        f"🆔 **Suas Informações:**\n\n"
        f"**Nome:** {user_name}\n"
        f"**Username:** @{username or 'não definido'}\n"
        f"**User ID:** `{user_id}`\n\n"
        f"_Copie o User ID para autorizar no bot_",
        parse_mode="Markdown",
    )

@authorized_only
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /info - PROTEGIDO
    """
    await log_access(update, context)
    user = update.effective_user

    info_text = f"""
👤 **Suas Informações:**

**Nome:** {user.first_name} {user.last_name or ''}
**Username:** @{user.username or 'não definido'}
**ID:** `{user.id}`
**Idioma:** {user.language_code or 'não definido'}

📅 **Data/Hora atual:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

✅ **Status:** Autorizado
    """

    await update.message.reply_text(info_text, parse_mode="Markdown")


@authorized_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de TEXTO
    """
    await log_access(update,context)
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


@authorized_only
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de VOZ/ÁUDIO
    Com AUTO-DETECÇÃO de sessão ativa
    """
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name
    voice = update.message.voice

    duration = voice.duration
    file_size = voice.file_size

    print(f"\n{'='*50}")
    print("🎤 NOVO ÁUDIO RECEBIDO")
    print(f"{'='*50}")
    print(f"👤 Usuário: {user_name} (ID: {user_id})")
    print(f"⏱️  Duração: {duration}s")
    print(f"📦 Tamanho: {file_size / 1024:.2f} KB")

    start_time = time.time()

    # ===== ETAPA 0: GERENCIAR SESSÃO =====
    session_manager = get_session_manager()
    workout_session, is_new = session_manager.get_or_create_session(user_id)

    # Mensagem inicial diferente se for nova ou continuação
    if is_new:
        initial_msg = (
            "🎤 **Áudio recebido!**\n\n"
            f"✨ **Nova sessão de treino iniciada**\n"
            f"🆔 Session ID: `{workout_session.session_id}`\n"
            f"⏱️ Duração: {duration}s\n\n"
            "🔄 Processando..."
        )
    else:
        initial_msg = (
            "🎤 **Áudio recebido!**\n\n"
            f"➕ **Adicionando à sessão #{workout_session.session_id}**\n"
            f"📝 Áudio #{workout_session.audio_count + 1} desta sessão\n"
            f"⏱️ Duração: {duration}s\n\n"
            "🔄 Processando..."
        )

    status_msg = await update.message.reply_text(initial_msg, parse_mode="Markdown")

    try:
        # ===== PASSO 1: BAIXAR ÁUDIO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n📥 Baixando áudio...",
            parse_mode="Markdown",
        )

        file = await voice.get_file()
        file_bytes = await file.download_as_bytearray()
        print(f"📥 Áudio baixado: {len(file_bytes)} bytes")

        # ===== PASSO 2: TRANSCREVER =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n🎙️ Transcrevendo...",
            parse_mode="Markdown",
        )

        audio_service = get_audio_service()
        transcription = await audio_service.transcribe_telegram_voice(bytes(file_bytes))
        print(f"✅ Transcrição: {transcription}")

        # ===== PASSO 3: PARSEAR COM LLM =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n✅ Transcrito\n🤖 Analisando...",
            parse_mode="Markdown",
        )

        llm_service = get_llm_service()
        parsed_data = llm_service.parse_workout(transcription)

        if not parsed_data:
            await status_msg.edit_text(
                "❌ **Erro ao processar**\n\n"
                "A IA não conseguiu entender o áudio.\n"
                "Tente novamente com mais clareza.",
                parse_mode="Markdown",
            )
            return

        print(f"✅ LLM parseou: {parsed_data}")

        # ===== PASSO 4: SALVAR NO BANCO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n✅ Transcrito\n✅ Analisado\n💾 Salvando...",
            parse_mode="Markdown",
        )

        workout_service = get_workout_service()
        processing_time = time.time() - start_time

        # ADICIONAR à sessão existente (não criar nova!)
        success = workout_service.add_exercises_to_session(
            session_id=workout_session.session_id,
            parsed_data=parsed_data,
            user_id=user_id,
        )

        if not success:
            await status_msg.edit_text(
                "❌ **Erro ao salvar no banco**",
                parse_mode="Markdown",
            )
            return

        # Atualizar metadados da sessão
        session_manager.update_session_metadata(
            session_id=workout_session.session_id,
            transcription=transcription,
            processing_time=processing_time,
            model_used=settings.LLM_MODEL,
        )

        # ===== PASSO 5: RESPOSTA FINAL =====
        response = _format_success_response(
            transcription=transcription,
            parsed_data=parsed_data,
            session_id=workout_session.session_id,
            processing_time=processing_time,
            is_new_session=is_new,
            audio_count=workout_session.audio_count + 1,
        )

        await status_msg.edit_text(response, parse_mode="Markdown")

        print(f"✅ PROCESSAMENTO COMPLETO em {processing_time:.2f}s")
        print(f"{'='*50}\n")

    except Exception as e:
        error_msg = f"❌ **Erro no processamento**\n\n{e!s}"
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


def _format_success_response(
    transcription: str,
    parsed_data: dict,
    session_id: int,
    processing_time: float,
    is_new_session: bool,
    audio_count: int,
) -> str:
    """Formata resposta de sucesso com informações da sessão"""
    if is_new_session:
        response = "✅ **Nova sessão criada e áudio processado!**\n\n"
    else:
        response = f"✅ **Áudio #{audio_count} adicionado à sessão!**\n\n"

    # Transcrição
    response += f"📝 **Você disse:**\n_{transcription}_\n\n"

    # Exercícios de resistência
    resistance = parsed_data.get("resistance_exercises", [])
    if resistance:
        response += "💪 **Exercícios Adicionados:**\n"
        for ex in resistance:
            reps_str = ", ".join(map(str, ex.get("reps", [])))
            response += f"• {ex['name'].title()}: {ex.get('sets')}x ({reps_str}) - {ex.get('weight_kg')}kg\n"
        response += "\n"

    # Exercícios aeróbicos
    aerobic = parsed_data.get("aerobic_exercises", [])
    if aerobic:
        response += "🏃 **Exercícios Aeróbicos:**\n"
        for ex in aerobic:
            response += f"• {ex['name'].title()}: {ex.get('duration_minutes')}min"
            if ex.get("distance_km"):
                response += f" - {ex.get('distance_km')}km"
            response += "\n"
        response += "\n"

    # Informações da sessão
    response += f"🆔 Session ID: `{session_id}`\n"
    response += f"📊 Áudios nesta sessão: {audio_count}\n"
    response += f"⏱️ Processado em: {processing_time:.1f}s\n\n"

    # Dica
    if is_new_session:
        response += "💡 _Envie mais áudios para adicionar exercícios a esta sessão_"
    else:
        response += "💡 _Continue enviando áudios ou aguarde 3h para iniciar nova sessão_"

    return response

@authorized_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status - Mostra sessão ativa"""
    user_id = str(update.effective_user.id)

    session_manager = get_session_manager()
    workout_service = get_workout_service()

    # Buscar última sessão
    db_session = db.get_session()
    last_session = db_session.query(WorkoutSession).filter_by(
        user_id=user_id,
    ).order_by(
        WorkoutSession.last_update.desc(),
    ).first()

    if not last_session:
        await update.message.reply_text(
            "📊 **Status**\n\n"
            "Você ainda não tem nenhuma sessão registrada.\n"
            "Envie um áudio para começar!",
            parse_mode="Markdown",
        )
        db_session.close()
        return

    # Verificar se está ativa
    time_since = datetime.now() - last_session.last_update
    hours_passed = time_since.total_seconds() / 3600

    is_active = hours_passed < session_manager.SESSION_TIMEOUT_HOURS

    # Buscar resumo
    summary = workout_service.get_session_summary(last_session.session_id)

    if is_active:
        status_text = (
            f"🟢 **Sessão Ativa**\n\n"
            f"🆔 Session ID: `{last_session.session_id}`\n"
            f"🕐 Iniciada: {last_session.start_time.strftime('%H:%M')}\n"
            f"⏱️ Última atualização: há {int(hours_passed * 60)} minutos\n"
            f"📝 Áudios enviados: {last_session.audio_count}\n"
            f"💪 Exercícios de resistência: {summary['resistance_count']}\n"
            f"🏃 Exercícios aeróbicos: {summary['aerobic_count']}\n\n"
            f"💡 _Envie mais áudios para adicionar exercícios_"
        )
    else:
        status_text = (
            f"⚪ **Última Sessão (Finalizada)**\n\n"
            f"🆔 Session ID: `{last_session.session_id}`\n"
            f"📅 Data: {last_session.date.strftime('%d/%m/%Y')}\n"
            f"🕐 Horário: {last_session.start_time.strftime('%H:%M')} - {last_session.end_time.strftime('%H:%M') if last_session.end_time else 'N/A'}\n"
            f"📝 Áudios enviados: {last_session.audio_count}\n"
            f"💪 Exercícios de resistência: {summary['resistance_count']}\n"
            f"🏃 Exercícios aeróbicos: {summary['aerobic_count']}\n\n"
            f"⏰ Sessão expirada há {int((hours_passed - session_manager.SESSION_TIMEOUT_HOURS) * 60)} minutos\n\n"
            f"💡 _Envie um áudio para iniciar nova sessão_"
        )

    await update.message.reply_text(status_text, parse_mode="Markdown")
    db_session.close()

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para comandos desconhecidos
    """
    log_access(update, context)
    await update.message.reply_text(
        "❓ Comando não reconhecido.\n"
        "Use /help para ver os comandos disponíveis.",
    )
