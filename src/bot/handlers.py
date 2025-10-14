import asyncio
import time
from datetime import datetime
from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware import admin_only, authorized_only, log_access
from bot.rate_limiter import rate_limit_commands, rate_limit_voice
from bot.validation import validate_and_sanitize_user_input
from config.logging_config import get_logger
from config.messages import messages
from config.settings import settings
from database.models import SessionStatus
from services.container import (
    get_analytics_service,
    get_audio_service,
    get_export_service,
    get_llm_service,
    get_session_manager,
    get_user_service,
    get_workout_service,
)
from services.exceptions import (
    AudioProcessingError,
    DatabaseError,
    LLMParsingError,
    ServiceUnavailableError,
    SessionError,
    ValidationError,
)

logger = get_logger(__name__)


@rate_limit_commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start - Mensagem de boas-vindas"""
    await log_access(update, context)

    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    # Usar dados sanitizados
    user_name = validation_result["user"].get("first_name", "Usuário")

    message = messages.WELCOME.format(user_name=user_name)

    await update.message.reply_text(message)


@rate_limit_commands
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /help - Ajuda"""
    await log_access(update, context)
    await update.message.reply_text(messages.HELP)


@rate_limit_commands
async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /myid - Mostra o user_id (útil para adicionar novos usuários)"""
    await log_access(update, context)

    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    # Usar dados sanitizados e validados
    user_data = validation_result["user"]
    user_id = user_data.get("id", "N/A")
    user_name = user_data.get("first_name", "não definido")
    username = user_data.get("username", "não definido")

    message = messages.USER_INFO.format(
        user_name=user_name,
        username=username,
        user_id=user_id,
    )
    await update.message.reply_text(message, parse_mode="Markdown")


@authorized_only
@rate_limit_commands
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /info - PROTEGIDO"""
    await log_access(update, context)
    user = update.effective_user

    info_text = messages.INFO_COMMAND.format(
        user_name=user.first_name,
        user_last_name=user.last_name or "",
        username=user.username or "não definido",
        user_id=user.id,
        user_language=user.language_code or "não definido",
        current_datetime=datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    )

    await update.message.reply_text(info_text, parse_mode="Markdown")


def _is_workout_message(text: str) -> bool:
    """Detecta se o texto contém conteúdo de treino"""
    # Palavras-chave relacionadas a exercícios e treino
    workout_keywords = [
        "supino", "agachamento", "levantamento", "leg press", "cadeira extensora",
        "cadeira flexora", "rosca", "tríceps", "desenvolvimento", "elevação",
        "remada", "pulldown", "puxada", "flexão", "barra fixa", "paralelas",
        "abdominal", "prancha", "burpee", "corrida", "esteira", "bicicleta",
        "elíptico", "crossfit", "hiit", "aeróbico", "cardio", "musculação",
        "repetições", "reps", "séries", "sets", "quilos", "kg", "carga",
        "treino", "exercício", "academia", "ginástica", "peso", "minutos",
        "tempo", "descanso", "intervalo",
    ]

    text_lower = text.lower()
    return any(keyword in text_lower for keyword in workout_keywords)


async def _process_workout_audio_optimized(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status_msg,
    initial_msg: str,
    file_bytes: bytes,
    workout_session,
    is_new: bool,
    start_time: float,
) -> None:
    """Processa áudio de workout com otimizações paralelas"""
    validation_result = validate_and_sanitize_user_input(update)
    user_data = validation_result["user"]
    user_id = user_data.get("id", "N/A")

    try:
        # ===== ETAPA 1: TRANSCRIÇÃO EM PARALELO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n🎙️ Transcrevendo...",
            parse_mode="Markdown",
        )

        audio_service = get_audio_service()

        # Criar task para transcrição
        transcription_task = asyncio.create_task(
            audio_service.transcribe_telegram_voice(file_bytes),
        )

        # Aguardar transcrição (não há muito para paralelizar aqui ainda)
        transcription = await transcription_task
        logger.info(f"Transcrição concluída: {transcription[:100]}...")

        # ===== ETAPA 2: LLM + PREPARAÇÃO DB EM PARALELO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n✅ Transcrito\n🤖 Processando...",
            parse_mode="Markdown",
        )

        llm_service = get_llm_service()

        # Executar LLM parsing (agora async)
        llm_task = asyncio.create_task(
            llm_service.parse_workout(transcription),
        )

        # Por enquanto aguardamos LLM, mas futuramente podemos preparar caches aqui
        parsed_data = await llm_task
        logger.info(f"LLM parsing concluído: {len(parsed_data.get('resistance_exercises', []))} resistência, {len(parsed_data.get('aerobic_exercises', []))} aeróbico")

        # ===== ETAPA 3: SALVAR NO BANCO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n✅ Transcrito\n✅ Analisado\n💾 Salvando...",
            parse_mode="Markdown",
        )

        workout_service = get_workout_service()
        processing_time = time.time() - start_time

        # ADICIONAR à sessão existente usando método batch otimizado
        workout_service.add_exercises_to_session_batch(
            session_id=workout_session.session_id,
            parsed_data=parsed_data,
            user_id=user_id,
        )

        # Atualizar metadados da sessão
        session_manager = get_session_manager()
        session_manager.update_session_metadata(
            session_id=workout_session.session_id,
            transcription=transcription,
            processing_time=processing_time,
            model_used=settings.LLM_MODEL,
        )

        # ===== ETAPA 4: RESPOSTA FINAL =====
        response = _format_success_response(
            transcription=transcription,
            parsed_data=parsed_data,
            session_id=workout_session.session_id,
            processing_time=processing_time,
            is_new_session=is_new,
            audio_count=workout_session.audio_count + 1,
        )

        await status_msg.edit_text(response, parse_mode="Markdown")

        logger.info(f"Processamento otimizado completo em {processing_time:.2f}s para usuário {user_id}")

    except ValidationError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_VALIDATION.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de validação: {e}")

    except LLMParsingError as e:
        error_msg = messages.ERROR_LLM_PARSING.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de LLM: {e}")

    except ServiceUnavailableError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_SERVICE_UNAVAILABLE.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de serviço: {e}")

    except (DatabaseError, SessionError) as e:
        error_msg = messages.ERROR_DATABASE.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de banco/sessão: {e}")
        import traceback
        traceback.print_exc()

    except Exception as e:
        error_msg = messages.ERROR_UNEXPECTED.format(error_message="Ocorreu um erro interno.")
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()


async def _process_workout_audio(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status_msg,
    initial_msg: str,
    transcription: str,
    workout_session,
    is_new: bool,
    start_time: float,
) -> None:
    """Processa workout de áudio após transcrição"""
    validation_result = validate_and_sanitize_user_input(update)
    user_data = validation_result["user"]
    user_id = user_data.get("id", "N/A")

    try:
        llm_service = get_llm_service()
        parsed_data = await llm_service.parse_workout(transcription)

        logger.info(f"LLM parsing completo: {len(parsed_data.get('resistance_exercises', []))} resistência, {len(parsed_data.get('aerobic_exercises', []))} aeróbico")

        # ===== PASSO 4: SALVAR NO BANCO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n✅ Transcrito\n✅ Analisado\n💾 Salvando...",
            parse_mode="Markdown",
        )

        workout_service = get_workout_service()
        processing_time = time.time() - start_time

        # ADICIONAR à sessão existente (não criar nova!)
        workout_service.add_exercises_to_session(
            session_id=workout_session.session_id,
            parsed_data=parsed_data,
            user_id=user_id,
        )

        # Atualizar metadados da sessão
        session_manager = get_session_manager()
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

        logger.info(f"Processamento completo em {processing_time:.2f}s para usuário {user_id}")

    except ValidationError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_VALIDATION.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de validação: {e}")

    except LLMParsingError as e:
        error_msg = messages.ERROR_LLM_PARSING.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de LLM: {e}")

    except ServiceUnavailableError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_SERVICE_UNAVAILABLE.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de serviço: {e}")

    except (DatabaseError, SessionError) as e:
        error_msg = messages.ERROR_DATABASE.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de banco/sessão: {e}")
        import traceback
        traceback.print_exc()

    except Exception as e:
        error_msg = messages.ERROR_UNEXPECTED.format(error_message="Ocorreu um erro interno.")
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()


async def _process_workout_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    workout_text: str,
    source: str = "text",
) -> None:
    """Processa mensagem de treino (texto ou áudio transcrito)"""
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    user_data = validation_result["user"]
    user_id = user_data.get("id", "N/A")
    user_name = user_data.get("first_name", "Usuário")

    logger.info(f"Novo treino recebido ({source.upper()}) de {user_name} (ID: {user_id}): {workout_text[:100]}...")

    start_time = time.time()

    # ===== ETAPA 0: GERENCIAR SESSÃO =====
    session_manager = get_session_manager()
    workout_session, is_new = session_manager.get_or_create_session(user_id)

    # Mensagem inicial diferente se for nova ou continuação
    if is_new:
        initial_msg = messages.TEXT_PROCESSING_NEW_SESSION.format(
            session_id=workout_session.session_id,
        ) if source == "text" else messages.AUDIO_PROCESSING_NEW_SESSION.format(
            session_id=workout_session.session_id,
            duration=0,  # Will be overridden by audio handler
        )
    else:
        initial_msg = messages.TEXT_PROCESSING_EXISTING_SESSION.format(
            session_id=workout_session.session_id,
            message_count=workout_session.audio_count + 1,
        ) if source == "text" else messages.AUDIO_PROCESSING_EXISTING_SESSION.format(
            session_id=workout_session.session_id,
            audio_count=workout_session.audio_count + 1,
            duration=0,  # Will be overridden by audio handler
        )

    status_msg = await update.message.reply_text(initial_msg, parse_mode="Markdown")

    try:
        # ===== PASSO 1: PARSEAR COM LLM (pula transcrição para texto) =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n🤖 Analisando...",
            parse_mode="Markdown",
        )

        llm_service = get_llm_service()
        parsed_data = await llm_service.parse_workout(workout_text)

        logger.info(f"LLM parsing completo: {len(parsed_data.get('resistance_exercises', []))} resistência, {len(parsed_data.get('aerobic_exercises', []))} aeróbico")

        # ===== PASSO 2: SALVAR NO BANCO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Analisado\n💾 Salvando...",
            parse_mode="Markdown",
        )

        workout_service = get_workout_service()
        processing_time = time.time() - start_time

        # ADICIONAR à sessão existente (não criar nova!)
        workout_service.add_exercises_to_session(
            session_id=workout_session.session_id,
            parsed_data=parsed_data,
            user_id=user_id,
        )

        # Atualizar metadados da sessão
        session_manager.update_session_metadata(
            session_id=workout_session.session_id,
            transcription=workout_text,  # Para texto, é o próprio texto
            processing_time=processing_time,
            model_used=settings.LLM_MODEL,
        )

        # ===== PASSO 3: RESPOSTA FINAL =====
        response = _format_success_response(
            transcription=workout_text,
            parsed_data=parsed_data,
            session_id=workout_session.session_id,
            processing_time=processing_time,
            is_new_session=is_new,
            audio_count=workout_session.audio_count + 1,
        )

        await status_msg.edit_text(response, parse_mode="Markdown")

        logger.info(f"Processamento completo em {processing_time:.2f}s para usuário {user_id}")

    except ValidationError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_VALIDATION.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de validação: {e}")

    except LLMParsingError as e:
        error_msg = messages.ERROR_LLM_PARSING.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de LLM: {e}")

    except ServiceUnavailableError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_SERVICE_UNAVAILABLE.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de serviço: {e}")

    except (DatabaseError, SessionError) as e:
        error_msg = messages.ERROR_DATABASE.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de banco/sessão: {e}")
        import traceback
        traceback.print_exc()

    except Exception as e:
        error_msg = messages.ERROR_UNEXPECTED.format(error_message="Ocorreu um erro interno.")
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()


@authorized_only
@rate_limit_voice  # Usar mesmo rate limit que voz para mensagens de treino (processamento pesado)
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para mensagens de TEXTO"""
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    # Usar dados sanitizados e validados
    user_data = validation_result["user"]
    message_data = validation_result["message"]

    user_id = user_data.get("id", "N/A")
    user_name = user_data.get("first_name", "Usuário")
    message_text = message_data.get("text", "")
    timestamp = update.message.date

    # Printar no console (para debug)
    logger.info(f"Mensagem de texto recebida de {user_name} (ID: {user_id}) - {timestamp}: {message_text[:settings.LOG_TEXT_PREVIEW_LENGTH]}...")

    # Verificar se é mensagem de treino
    if _is_workout_message(message_text):
        logger.info("Detectado conteúdo de treino - processando como workout")
        await _process_workout_message(update, context, message_text, "text")
    else:
        # Comportamento atual - apenas ecoar a mensagem
        response = messages.TEXT_RECEIVED.format(
            message_text=message_text,
            user_id=user_id,
            timestamp=timestamp.strftime("%H:%M:%S"),
        )
        await update.message.reply_text(response, parse_mode="Markdown")


@authorized_only
@rate_limit_voice
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para mensagens de VOZ/ÁUDIO
    Com AUTO-DETECÇÃO de sessão ativa
    """
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    # Usar dados sanitizados e validados
    user_data = validation_result["user"]
    message_data = validation_result["message"]

    user_id = user_data.get("id", "N/A")
    user_name = user_data.get("first_name", "Usuário")
    voice = update.message.voice
    voice_info = message_data.get("voice", {})

    duration = voice_info.get("duration", voice.duration)
    file_size = voice_info.get("file_size", voice.file_size)

    logger.info(f"Novo áudio recebido de {user_name} (ID: {user_id}) - Duração: {duration}s, Tamanho: {file_size / 1024:.2f} KB")

    start_time = time.time()

    # ===== ETAPA 0: GERENCIAR SESSÃO =====
    session_manager = get_session_manager()
    workout_session, is_new = session_manager.get_or_create_session(user_id)

    # Mensagem inicial diferente se for nova ou continuação
    if is_new:
        initial_msg = messages.AUDIO_PROCESSING_NEW_SESSION.format(
            session_id=workout_session.session_id,
            duration=duration,
        )
    else:
        initial_msg = messages.AUDIO_PROCESSING_EXISTING_SESSION.format(
            session_id=workout_session.session_id,
            audio_count=workout_session.audio_count + 1,
            duration=duration,
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
        logger.info(f"Áudio baixado: {len(file_bytes)} bytes")

        # ===== PASSO 2 & 3: PROCESSAR EM PARALELO =====
        await status_msg.edit_text(
            f"{initial_msg}\n\n✅ Baixado\n🎙️ Processando (paralelo)...",
            parse_mode="Markdown",
        )

        # Processar transcrição e LLM em paralelo usando a função otimizada
        await _process_workout_audio_optimized(
            update, context, status_msg, initial_msg,
            bytes(file_bytes), workout_session, is_new, start_time,
        )

    except AudioProcessingError as e:
        rate_limit_note = "\n\n⏰ _Tente novamente em alguns segundos_" if "rate_limit" in e.message.lower() else ""
        error_msg = messages.ERROR_AUDIO_PROCESSING.format(message=e.message, rate_limit_note=rate_limit_note)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro de áudio: {e}")

    except Exception as e:
        error_msg = messages.ERROR_UNEXPECTED.format(error_message="Ocorreu um erro interno.")
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        logger.error(f"Erro inesperado: {e}")
        import traceback
        traceback.print_exc()


def _format_success_response(
    transcription: str,
    parsed_data: Dict[str, Any],
    session_id: int,
    processing_time: float,
    is_new_session: bool,
    audio_count: int,
) -> str:
    """Formata resposta de sucesso com informações da sessão"""
    if is_new_session:
        response = messages.AUDIO_SUCCESS_NEW_SESSION
    else:
        response = messages.AUDIO_SUCCESS_EXISTING_SESSION.format(audio_count=audio_count)

    # Transcrição
    response += messages.format_transcription_response(transcription)

    # Exercícios
    resistance = parsed_data.get("resistance_exercises", [])
    aerobic = parsed_data.get("aerobic_exercises", [])
    response += messages.format_exercise_section(resistance, aerobic)

    # Informações da sessão
    response += f"🆔 Session ID: `{session_id}`\n"
    response += f"📊 Áudios nesta sessão: {audio_count}\n"
    response += f"⏱️ Processado em: {processing_time:.1f}s\n\n"

    # Dica
    if is_new_session:
        response += messages.AUDIO_SUCCESS_FOOTER_NEW
    else:
        response += messages.AUDIO_SUCCESS_FOOTER_CONTINUE

    return response


@authorized_only
@rate_limit_commands
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /status - Mostra sessão ativa"""
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    user_id = validation_result["user"].get("id", "N/A")

    try:
        workout_service = get_workout_service()

        # Buscar status usando método otimizado do service
        status_data = workout_service.get_user_session_status(user_id)

        if not status_data["has_session"]:
            await update.message.reply_text(
                f"📊 **Status**\n\n{status_data['message']}",
                parse_mode="Markdown",
            )
            return

        # Dados já processados pelo service
        session = status_data["session"]
        is_active = status_data["is_active"]
        minutes_passed = status_data["minutes_passed"]
        hours_passed = status_data["hours_passed"]
        resistance_count = status_data["resistance_count"]
        aerobic_count = status_data["aerobic_count"]
        timeout_hours = status_data["timeout_hours"]

        if is_active == SessionStatus.ATIVA:
            status_text = messages.STATUS_ACTIVE_SESSION.format(
                session_id=session.session_id,
                start_time=session.start_time.strftime("%H:%M"),
                minutes_passed=minutes_passed,
                audio_count=session.audio_count,
                resistance_count=resistance_count,
                aerobic_count=aerobic_count,
            )
        else:
            expired_minutes = minutes_passed
            status_text = messages.STATUS_FINISHED_SESSION.format(
                session_id=session.session_id,
                date=session.date.strftime("%d/%m/%Y"),
                start_time=session.start_time.strftime("%H:%M"),
                end_time=session.end_time.strftime("%H:%M") if session.end_time else "N/A",
                audio_count=session.audio_count,
                resistance_count=resistance_count,
                aerobic_count=aerobic_count,
                expired_minutes=expired_minutes,
            )

        await update.message.reply_text(status_text, parse_mode="Markdown")

    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            messages.ERROR_STATUS_FETCH.format(error_message=e.message),
            parse_mode="Markdown",
        )
        logger.error(f"Erro no status: {e}")

    except Exception as e:
        await update.message.reply_text(
            messages.ERROR_UNEXPECTED.format(error_message="Não foi possível buscar o status."),
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado no status: {e}")
        import traceback
        traceback.print_exc()

@authorized_only
@rate_limit_commands
async def finish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Finaliza a sessão atual manualmente"""
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    user_data = validation_result["user"]
    user_id = user_data.get("id", "N/A")
    user_name = user_data.get("first_name", "Usuário")

    logger.info(f"Comando /finish executado por {user_name} (ID: {user_id})")


    workout_service = get_workout_service()

    # Buscar sessão ativa
    last_session = workout_service.get_last_session(user_id)

    if not last_session:
        await update.message.reply_text(messages.ERROR_SESSION_NOT_FOUND)
        return

    if last_session.status == SessionStatus.FINALIZADA:
        await update.message.reply_text(
            messages.ERROR_SESSION_ALREADY_FINISHED.format(
                session_id=last_session.session_id,
                date=last_session.date.strftime("%d/%m/%Y"),
                duration=last_session.duration_minutes,
            ),
        )
        return

    # Finalizar sessão
    result = workout_service.finish_session(last_session.session_id, user_id)

    if not result["success"]:
        await update.message.reply_text(messages.ERROR_FINISH_SESSION.format(error=result["error"]))
        return

    # Formatar resumo
    stats = result["stats"]
    duration = result["duration_minutes"]

    # Seções aeróbicas e grupos musculares condicionais
    aerobic_section = ""
    if stats["aerobic_exercises"] > 0:
        aerobic_section = messages.FINISH_AEROBIC_SECTION.format(
            aerobic_exercises=stats["aerobic_exercises"],
            cardio_minutes=stats["cardio_minutes"],
        )

    muscle_groups_section = ""
    if stats["muscle_groups"]:
        muscle_groups = ", ".join(stats["muscle_groups"])
        muscle_groups_section = messages.FINISH_MUSCLE_GROUPS_SECTION.format(
            muscle_groups=muscle_groups,
        )

    response = messages.FINISH_SUCCESS.format(
        session_id=result["session_id"],
        duration=duration,
        audio_count=stats["audio_count"],
        resistance_exercises=stats["resistance_exercises"],
        total_sets=stats["total_sets"],
        total_volume_kg=stats["total_volume_kg"],
        aerobic_section=aerobic_section,
        muscle_groups_section=muscle_groups_section,
    )

    await update.message.reply_text(response, parse_mode="Markdown")

    logger.info("Sessão finalizada com sucesso")

@authorized_only
@rate_limit_commands
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /export - Exporta dados do usuário"""
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    user_id = validation_result["user"].get("id", "N/A")
    user_name = validation_result["user"].get("first_name", "Usuário")

    # Parse format from command args (default: json)
    args = context.args or []
    format_type = args[0].lower() if args and args[0].lower() in ["json", "csv"] else "json"

    try:
        export_service = get_export_service()

        # First get summary
        summary = export_service.get_export_summary(user_id)

        if summary["total_sessions"] == 0:
            await update.message.reply_text(
                "📊 **Exportar Dados**\n\n"
                "❌ Você ainda não tem dados de treino para exportar.\n\n"
                "Envie alguns áudios de treino primeiro!",
                parse_mode="Markdown",
            )
            return

        # Show summary and ask for confirmation
        summary_text = f"""
📊 **Resumo dos Seus Dados**

📈 **Total de sessões:** {summary['total_sessions']}
📅 **Período:** {summary['date_range']['earliest']} até {summary['date_range']['latest']}
💪 **Exercícios de resistência:** {summary['exercise_counts']['resistance']}
🏃 **Exercícios aeróbicos:** {summary['exercise_counts']['aerobic']}

📄 **Formato:** {format_type.upper()}

⚠️ **Nota:** A exportação pode conter dados sensíveis. Mantenha o arquivo seguro.

💾 Enviando arquivo...
        """

        status_msg = await update.message.reply_text(summary_text, parse_mode="Markdown")

        # Export data
        result = export_service.export_user_data(user_id, format=format_type)

        if not result["success"] or not result["data"]:
            await status_msg.edit_text(
                "❌ **Erro na exportação**\n\n"
                f"{result.get('message', 'Falha ao exportar dados')}",
                parse_mode="Markdown",
            )
            return

        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gym_tracker_export_{user_name}_{timestamp}.{format_type}"

        # Prepare file content
        if format_type == "json":
            import json
            file_content = json.dumps(result["data"], indent=2, ensure_ascii=False).encode("utf-8")
            mime_type = "application/json"
        else:  # csv
            file_content = result["data"].encode("utf-8")
            mime_type = "text/csv"

        # Send file
        from io import BytesIO
        file_obj = BytesIO(file_content)
        file_obj.name = filename

        await update.message.reply_document(
            document=file_obj,
            filename=filename,
            caption=f"✅ **Exportação concluída!**\n\n"
                   f"📁 **Arquivo:** `{filename}`\n"
                   f"📊 **{summary['total_sessions']} sessões exportadas**\n"
                   f"📄 **Formato:** {format_type.upper()}",
            parse_mode="Markdown",
        )

        await status_msg.delete()

        logger.info(f"Export completo: {filename} para usuário {user_id}")

    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro na exportação**\n\n{e.message}\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        logger.error(f"Erro no export: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao exportar dados.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado no export: {e}")
        import traceback
        traceback.print_exc()


@authorized_only
@rate_limit_commands
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /stats - Estatísticas e analytics do usuário"""
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    user_id = validation_result["user"].get("id", "N/A")
    user_name = validation_result["user"].get("first_name", "Usuário")

    # Parse days from command args (default: 30)
    args = context.args or []
    try:
        days = int(args[0]) if args and args[0].isdigit() else 30
        days = max(1, min(365, days))  # Limit between 1-365 days
    except (ValueError, IndexError):
        days = 30

    try:
        analytics_service = get_analytics_service()

        status_msg = await update.message.reply_text(
            f"📊 **Calculando estatísticas...**\n\nAnalisando últimos {days} dias...",
            parse_mode="Markdown",
        )

        # Get analytics
        analytics = analytics_service.get_workout_analytics(user_id, days=days)

        if "message" in analytics:  # No data found
            await status_msg.edit_text(
                f"📊 **Estatísticas - {days} dias**\n\n"
                f"❌ {analytics['message']}\n\n"
                "Envie alguns áudios de treino primeiro!",
                parse_mode="Markdown",
            )
            return

        # Format comprehensive stats message
        stats_message = _format_analytics_message(analytics, user_name)

        await status_msg.edit_text(stats_message, parse_mode="Markdown")

        logger.info(f"Stats calculadas para usuário {user_id} ({days} dias)")

    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro nas estatísticas**\n\n{e.message}\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        logger.error(f"Erro nas stats: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao calcular estatísticas.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado nas stats: {e}")
        import traceback
        traceback.print_exc()


@authorized_only
@rate_limit_commands
async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /progress - Progresso de um exercício específico"""
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    user_id = validation_result["user"].get("id", "N/A")

    # Parse exercise name from command args
    args = context.args
    if not args:
        await update.message.reply_text(
            "📈 **Como usar o comando:**\n\n"
            "/progress <nome_do_exercício>\n\n"
            "**Exemplos:**\n"
            "• `/progress supino`\n"
            "• `/progress agachamento`\n"
            "• `/progress rosca direta`",
            parse_mode="Markdown",
        )
        return

    exercise_name = " ".join(args)

    try:
        analytics_service = get_analytics_service()

        status_msg = await update.message.reply_text(
            f"📈 **Analisando progresso...**\n\nExercício: {exercise_name}",
            parse_mode="Markdown",
        )

        # Get exercise progress
        progress = analytics_service.get_exercise_progress(user_id, exercise_name)

        if not progress["found"]:
            await status_msg.edit_text(
                f"📈 **Progresso do Exercício**\n\n"
                f"❌ {progress['message']}\n\n"
                "💡 _Verifique se o nome está correto ou registre mais treinos_",
                parse_mode="Markdown",
            )
            return

        # Format progress message
        progress_message = _format_progress_message(progress)

        await status_msg.edit_text(progress_message, parse_mode="Markdown")

        logger.info(f"Progresso calculado: {exercise_name} para usuário {user_id}")

    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro no progresso**\n\n{e.message}\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        logger.error(f"Erro no progresso: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao calcular progresso.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado no progresso: {e}")
        import traceback
        traceback.print_exc()


@authorized_only
@rate_limit_commands
async def exercises_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /exercises - Lista todos os exercícios registrados no banco"""
    # Validar e sanitizar input do usuário
    validation_result = validate_and_sanitize_user_input(update)

    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    try:
        from database.connection import db
        from database.models import Exercise, ExerciseType

        session = db.get_session()

        try:
            # Buscar todos os exercícios ordenados por tipo e nome
            exercises = session.query(Exercise).order_by(
                Exercise.type,
                Exercise.name,
            ).all()

            if not exercises:
                await update.message.reply_text(
                    "📋 **Lista de Exercícios**\n\n"
                    "❌ Nenhum exercício encontrado no banco de dados.\n\n"
                    "Os exercícios são criados automaticamente quando você registra treinos.",
                    parse_mode="Markdown",
                )
                return

            # Agrupar exercícios por tipo
            resistance_exercises = []
            aerobic_exercises = []

            for exercise in exercises:
                exercise_info = f"• {exercise.name.title()}"
                if exercise.muscle_group:
                    exercise_info += f" ({exercise.muscle_group})"

                if exercise.type == ExerciseType.RESISTENCIA:
                    resistance_exercises.append(exercise_info)
                else:
                    aerobic_exercises.append(exercise_info)

            # Montar mensagem
            message = "📋 **Lista de Exercícios Registrados**\n\n"

            if resistance_exercises:
                message += f"💪 **Resistência ({len(resistance_exercises)}):**\n"
                message += "\n".join(resistance_exercises)
                message += "\n\n"

            if aerobic_exercises:
                message += f"🏃 **Aeróbicos ({len(aerobic_exercises)}):**\n"
                message += "\n".join(aerobic_exercises)
                message += "\n\n"

            message += f"📊 **Total:** {len(exercises)} exercícios"

            await update.message.reply_text(message, parse_mode="Markdown")

            logger.info(f"Lista de exercícios enviada: {len(exercises)} exercícios")

        finally:
            session.close()

    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao buscar exercícios.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado no exercises: {e}")
        import traceback
        traceback.print_exc()


def _format_analytics_message(analytics: Dict[str, Any], user_name: str) -> str:
    """Format analytics data into a readable message"""
    period = analytics["period"]
    session_stats = analytics["session_stats"]
    exercise_stats = analytics["exercise_stats"]
    frequency = analytics["workout_frequency"]
    muscle_dist = analytics["muscle_group_distribution"]
    trends = analytics["progress_trends"]

    message = f"📊 **Estatísticas de {user_name}**\n\n"
    message += f"📅 **Período:** {period['days']} dias\n"
    message += f"🏋️ **Total de sessões:** {period['total_sessions']}\n\n"

    # Session stats
    message += "📈 **Desempenho Geral:**\n"
    message += f"✅ Taxa de conclusão: {session_stats['completion_rate']:.1f}%\n"
    if session_stats["average_duration_minutes"] > 0:
        message += f"⏱️ Duração média: {session_stats['average_duration_minutes']:.0f} min\n"
    else:
        message += "⏱️ Duração média: N/A (finalize sessões com /finish)\n"
    message += f"🎤 Áudios por sessão: {session_stats['average_audios_per_session']:.1f}\n"
    if session_stats["average_energy_level"] > 0:
        message += f"⚡ Energia média: {session_stats['average_energy_level']:.1f}/10\n"
    message += "\n"

    # Exercise stats
    if exercise_stats["resistance"]["total_exercises"] > 0:
        resistance = exercise_stats["resistance"]
        message += "💪 **Exercícios de Resistência:**\n"
        message += f"🔢 Total: {resistance['total_exercises']} exercícios\n"
        message += f"📊 Séries: {resistance['total_sets']} séries\n"
        message += f"🏋️ Volume: {resistance['total_volume_kg']:,.0f}kg\n"
        if resistance["average_difficulty"] > 0:
            message += f"😤 Dificuldade média: {resistance['average_difficulty']:.1f}/10\n"
        message += "\n"

    # Frequency
    message += "📅 **Frequência:**\n"
    if frequency.get("is_extrapolated", True):
        message += f"📊 {frequency['frequency_per_week']:.1f} treinos/semana\n"
    else:
        # For periods < 7 days, show actual workouts instead of extrapolated rate
        days = frequency.get("analysis_period_days", 1)
        workouts = frequency["unique_workout_days"]
        message += f"📊 {workouts} treino(s) em {days} dia(s)\n"
        if days > 1:
            message += f"📈 Projeção: {frequency['frequency_per_week']:.1f} treinos/semana\n"
    message += f"🎯 Consistência: {frequency['consistency_score']:.1f}%\n"
    if frequency["longest_streak_days"] > 1:
        message += f"🔥 Maior sequência: {frequency['longest_streak_days']} dias\n"
    message += "\n"

    # Most trained muscle groups
    if muscle_dist.get("distribution"):
        sorted_muscles = sorted(
            muscle_dist["distribution"].items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )[:3]
        message += "🎯 **Músculos Mais Trabalhados:**\n"
        for muscle, data in sorted_muscles:
            message += f"• {muscle.title()}: {data['percentage']:.1f}%\n"
        message += "\n"

    # Trends
    if trends.get("trend") and trends["trend"] != "insufficient_data":
        trend_emoji = "📈" if trends["trend"] == "improving" else "📉" if trends["trend"] == "declining" else "➡️"
        message += f"{trend_emoji} **Tendência:** {trends['trend'].title()}\n"
        if abs(trends["volume_change_percent"]) > 5:
            message += f"📊 Volume: {trends['volume_change_percent']:+.1f}%\n"

    message += "\n💡 _Use /progress <exercício> para ver progresso específico_"

    return message


def _format_progress_message(progress: Dict[str, Any]) -> str:
    """Format exercise progress data into a readable message"""
    summary = progress["summary"]
    history = progress["progress_history"]

    message = f"📈 **Progresso: {progress['exercise_name'].title()}**\n\n"

    # Summary stats
    message += "📊 **Resumo Geral:**\n"
    message += f"🏋️ Sessões registradas: {summary['total_sessions']}\n"
    message += f"💪 Peso máximo: {summary['max_weight_ever']}kg\n"
    message += f"📈 Volume máximo: {summary['max_volume_ever']:,.0f}kg\n\n"

    # Progress indicators
    if summary["weight_progression"] != 0:
        prog_emoji = "📈" if summary["weight_progression"] > 0 else "📉"
        message += f"{prog_emoji} **Evolução de Peso:** {summary['weight_progression']:+.1f}kg\n"

    if summary["volume_progression"] != 0:
        vol_emoji = "📈" if summary["volume_progression"] > 0 else "📉"
        message += f"{vol_emoji} **Evolução de Volume:** {summary['volume_progression']:+.0f}kg\n"

    message += "\n"

    # Recent sessions (last 5)
    if history:
        recent_sessions = history[:5]
        message += "📅 **Últimas Sessões:**\n"
        for session in recent_sessions:
            date = session["date"]
            weights = session["weights_kg"]
            reps = session["reps"]
            max_weight = session["max_weight"]

            if weights and reps:
                sets_info = ", ".join([f"{r}×{w}kg" for r, w in zip(reps, weights)])
                message += f"• {date}: {sets_info}\n"
            else:
                message += f"• {date}: {session['sets']} séries\n"

    return message


@admin_only
@rate_limit_commands
async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /adduser - Adiciona usuário autorizado (ADMIN ONLY)"""
    validation_result = validate_and_sanitize_user_input(update)
    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    admin_user_id = str(validation_result["user"].get("id"))
    admin_name = validation_result["user"].get("first_name", "Admin")

    # Parse user ID from command args
    args = context.args
    if not args:
        await update.message.reply_text(
            "👥 **Como usar:**\n\n"
            "/adduser <user_id> [admin]\n\n"
            "**Exemplos:**\n"
            "• `/adduser 123456789` - Adiciona usuário normal\n"
            "• `/adduser 123456789 admin` - Adiciona admin\n\n"
            "💡 _Use /myid para ver o ID de um usuário_",
            parse_mode="Markdown",
        )
        return

    try:
        target_user_id = args[0].strip()
        is_admin = len(args) > 1 and args[1].lower() == "admin"

        user_service = get_user_service()

        # Verificar se usuário já existe
        existing_user = user_service.get_user(target_user_id)
        if existing_user:
            if existing_user.is_active:
                await update.message.reply_text(
                    f"❌ **Usuário já existe**\n\n"
                    f"👤 ID: `{target_user_id}`\n"
                    f"📝 Nome: {existing_user.first_name or 'N/A'}\n"
                    f"👑 Admin: {'Sim' if existing_user.is_admin else 'Não'}",
                    parse_mode="Markdown",
                )
                return
            # Reativar usuário inativo
            existing_user.is_active = True
            existing_user.is_admin = is_admin
            await update.message.reply_text(
                f"✅ **Usuário reativado**\n\n"
                f"👤 ID: `{target_user_id}`\n"
                f"👑 Admin: {'Sim' if is_admin else 'Não'}\n"
                f"👨‍💼 Reativado por: {admin_name}",
                parse_mode="Markdown",
            )
            return

        # Adicionar novo usuário
        user = user_service.add_user(
            user_id=target_user_id,
            is_admin=is_admin,
            created_by=admin_user_id,
        )

        await update.message.reply_text(
            f"✅ **Usuário adicionado com sucesso!**\n\n"
            f"👤 ID: `{target_user_id}`\n"
            f"👑 Admin: {'Sim' if is_admin else 'Não'}\n"
            f"👨‍💼 Adicionado por: {admin_name}\n\n"
            f"🎉 Usuário agora pode usar o bot!",
            parse_mode="Markdown",
        )

        logger.info(f"Admin {admin_name} ({admin_user_id}) adicionou usuário {target_user_id} (admin: {is_admin})")

    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro ao adicionar usuário**\n\n{e.message}",
            parse_mode="Markdown",
        )
        logger.error(f"Erro adduser: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao adicionar usuário.",
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado adduser: {e}")


@admin_only
@rate_limit_commands
async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /removeuser - Remove usuário autorizado (ADMIN ONLY)"""
    validation_result = validate_and_sanitize_user_input(update)
    if not validation_result["is_valid"]:
        error_msg = messages.ERROR_INVALID_DATA.format(errors="\n".join(validation_result["errors"]))
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return

    admin_user_id = str(validation_result["user"].get("id"))
    admin_name = validation_result["user"].get("first_name", "Admin")

    # Parse user ID from command args
    args = context.args
    if not args:
        await update.message.reply_text(
            "👥 **Como usar:**\n\n"
            "/removeuser <user_id>\n\n"
            "**Exemplo:**\n"
            "• `/removeuser 123456789`\n\n"
            "⚠️ _Isso remove o acesso do usuário ao bot_",
            parse_mode="Markdown",
        )
        return

    try:
        target_user_id = args[0].strip()

        # Não permitir que admin se remova
        if target_user_id == admin_user_id:
            await update.message.reply_text(
                "❌ **Erro**\n\nVocê não pode remover a si mesmo.",
                parse_mode="Markdown",
            )
            return

        user_service = get_user_service()

        # Verificar se usuário existe
        existing_user = user_service.get_user(target_user_id)
        if not existing_user or not existing_user.is_active:
            await update.message.reply_text(
                f"❌ **Usuário não encontrado**\n\n"
                f"ID: `{target_user_id}`",
                parse_mode="Markdown",
            )
            return

        # Remover usuário
        user_service.remove_user(target_user_id)

        await update.message.reply_text(
            f"✅ **Usuário removido com sucesso!**\n\n"
            f"👤 ID: `{target_user_id}`\n"
            f"📝 Nome: {existing_user.first_name or 'N/A'}\n"
            f"👨‍💼 Removido por: {admin_name}\n\n"
            f"🚫 Usuário não pode mais usar o bot.",
            parse_mode="Markdown",
        )

        logger.info(f"Admin {admin_name} ({admin_user_id}) removeu usuário {target_user_id}")

    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro ao remover usuário**\n\n{e.message}",
            parse_mode="Markdown",
        )
        logger.error(f"Erro removeuser: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao remover usuário.",
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado removeuser: {e}")


@admin_only
@rate_limit_commands
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /listusers - Lista usuários autorizados (ADMIN ONLY)"""
    try:
        user_service = get_user_service()
        users = user_service.list_users(include_inactive=False)

        if not users:
            await update.message.reply_text(
                "👥 **Lista de Usuários**\n\n"
                "❌ Nenhum usuário encontrado.",
                parse_mode="Markdown",
            )
            return

        # Separar admins e usuários normais
        admins = [u for u in users if u.is_admin]
        regular_users = [u for u in users if not u.is_admin]

        message = "👥 **Lista de Usuários Autorizados**\n\n"

        if admins:
            message += f"👑 **Administradores ({len(admins)}):**\n"
            for user in admins:
                name = user.first_name or "N/A"
                username = f"@{user.username}" if user.username else ""
                message += f"• `{user.user_id}` - {name} {username}\n"
            message += "\n"

        if regular_users:
            message += f"👤 **Usuários ({len(regular_users)}):**\n"
            for user in regular_users:
                name = user.first_name or "N/A"
                username = f"@{user.username}" if user.username else ""
                message += f"• `{user.user_id}` - {name} {username}\n"

        message += f"\n📊 **Total:** {len(users)} usuários"

        await update.message.reply_text(message, parse_mode="Markdown")

    except (DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro ao listar usuários**\n\n{e.message}",
            parse_mode="Markdown",
        )
        logger.error(f"Erro listusers: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao listar usuários.",
            parse_mode="Markdown",
        )
        logger.error(f"Erro inesperado listusers: {e}")


@rate_limit_commands
async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para comandos desconhecidos"""
    await update.message.reply_text(messages.UNKNOWN_COMMAND)


