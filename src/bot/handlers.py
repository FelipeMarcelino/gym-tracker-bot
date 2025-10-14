import time
from datetime import datetime
from typing import Any, Dict

from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware import authorized_only, log_access
from bot.rate_limiter import rate_limit_commands, rate_limit_general, rate_limit_voice
from bot.validation import validate_and_sanitize_user_input
from config.settings import settings
from config.messages import messages
from database.models import SessionStatus, WorkoutSession
from services.container import (
    get_analytics_service,
    get_audio_service,
    get_llm_service,
    get_session_manager,
    get_workout_service,
    get_export_service,
)
from services.exceptions import (
    AudioProcessingError,
    DatabaseError,
    LLMParsingError,
    ServiceUnavailableError,
    SessionError,
    ValidationError,
)


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
        user_id=user_id
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
        current_datetime=datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    )

    await update.message.reply_text(info_text, parse_mode="Markdown")


@authorized_only
@rate_limit_general
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para mensagens de TEXTO"""
    await log_access(update, context)
    
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
    print("\n📝 MENSAGEM DE TEXTO RECEBIDA:")
    print(f"   Usuário: {user_name} (ID: {user_id})")
    print(f"   Horário: {timestamp}")
    print(f"   Texto: {message_text[:settings.LOG_TEXT_PREVIEW_LENGTH]}...")  # Limitar output para log

    # Responder ao usuário
    response = messages.TEXT_RECEIVED.format(
        message_text=message_text,
        user_id=user_id,
        timestamp=timestamp.strftime("%H:%M:%S")
    )

    await update.message.reply_text(response, parse_mode="Markdown")


@authorized_only
@rate_limit_voice
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para mensagens de VOZ/ÁUDIO
    Com AUTO-DETECÇÃO de sessão ativa
    """
    await log_access(update, context)
    
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

    print(f"\n{'=' * 50}")
    print("🎤 NOVO ÁUDIO RECEBIDO")
    print(f"{'=' * 50}")
    print(f"👤 Usuário: {user_name} (ID: {user_id})")
    print(f"⏱️  Duração: {duration}s")
    print(f"📦 Tamanho: {file_size / 1024:.2f} KB")

    start_time = time.time()

    # ===== ETAPA 0: GERENCIAR SESSÃO =====
    session_manager = get_session_manager()
    workout_session, is_new = session_manager.get_or_create_session(user_id)

    # Mensagem inicial diferente se for nova ou continuação
    if is_new:
        initial_msg = messages.AUDIO_PROCESSING_NEW_SESSION.format(
            session_id=workout_session.session_id,
            duration=duration
        )
    else:
        initial_msg = messages.AUDIO_PROCESSING_EXISTING_SESSION.format(
            session_id=workout_session.session_id,
            audio_count=workout_session.audio_count + 1,
            duration=duration
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

        print(f"✅ LLM parseou: {parsed_data}")

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
        print(f"{'=' * 50}\n")

    except ValidationError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_VALIDATION.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE VALIDAÇÃO: {e}")
        
    except AudioProcessingError as e:
        rate_limit_note = "\n\n⏰ _Tente novamente em alguns segundos_" if "rate_limit" in e.message.lower() else ""
        error_msg = messages.ERROR_AUDIO_PROCESSING.format(message=e.message, rate_limit_note=rate_limit_note)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE ÁUDIO: {e}")
        
    except LLMParsingError as e:
        error_msg = messages.ERROR_LLM_PARSING.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE LLM: {e}")
        
    except ServiceUnavailableError as e:
        details = f"\n\n_Detalhes: {e.details}_" if e.details else ""
        error_msg = messages.ERROR_SERVICE_UNAVAILABLE.format(message=e.message, details=details)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE SERVIÇO: {e}")
        
    except (DatabaseError, SessionError) as e:
        error_msg = messages.ERROR_DATABASE.format(message=e.message)
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE BANCO/SESSÃO: {e}")
        import traceback
        traceback.print_exc()
        
    except Exception as e:
        error_msg = messages.ERROR_UNEXPECTED.format(error_message="Ocorreu um erro interno.")
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO INESPERADO: {e}")
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
    await log_access(update, context)
    
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

        if is_active:
            status_text = messages.STATUS_ACTIVE_SESSION.format(
                session_id=session.session_id,
                start_time=session.start_time.strftime('%H:%M'),
                minutes_passed=minutes_passed,
                audio_count=session.audio_count,
                resistance_count=resistance_count,
                aerobic_count=aerobic_count
            )
        else:
            expired_minutes = int((hours_passed - timeout_hours) * 60)
            status_text = messages.STATUS_FINISHED_SESSION.format(
                session_id=session.session_id,
                date=session.date.strftime('%d/%m/%Y'),
                start_time=session.start_time.strftime('%H:%M'),
                end_time=session.end_time.strftime('%H:%M') if session.end_time else 'N/A',
                audio_count=session.audio_count,
                resistance_count=resistance_count,
                aerobic_count=aerobic_count,
                expired_minutes=expired_minutes
            )

        await update.message.reply_text(status_text, parse_mode="Markdown")
        
    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            messages.ERROR_STATUS_FETCH.format(error_message=e.message),
            parse_mode="Markdown",
        )
        print(f"❌ ERRO NO STATUS: {e}")
        
    except Exception as e:
        await update.message.reply_text(
            messages.ERROR_UNEXPECTED.format(error_message="Não foi possível buscar o status."),
            parse_mode="Markdown",
        )
        print(f"❌ ERRO INESPERADO NO STATUS: {e}")
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

    print(f"\n{'='*50}")
    print("📊 COMANDO /finish")
    print(f"{'='*50}")
    print(f"👤 Usuário: {user_name} (ID: {user_id})")


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
                date=last_session.date.strftime('%d/%m/%Y'),
                duration=last_session.duration_minutes
            )
        )
        return

    # Finalizar sessão
    result = workout_service.finish_session(last_session.session_id, user_id)

    if not result["success"]:
        await update.message.reply_text(messages.ERROR_FINISH_SESSION.format(error=result['error']))
        return

    # Formatar resumo
    stats = result["stats"]
    duration = result["duration_minutes"]
    
    # Seções aeróbicas e grupos musculares condicionais
    aerobic_section = ""
    if stats["aerobic_exercises"] > 0:
        aerobic_section = messages.FINISH_AEROBIC_SECTION.format(
            aerobic_exercises=stats["aerobic_exercises"],
            cardio_minutes=stats["cardio_minutes"]
        )
    
    muscle_groups_section = ""
    if stats["muscle_groups"]:
        muscle_groups = ", ".join(stats["muscle_groups"])
        muscle_groups_section = messages.FINISH_MUSCLE_GROUPS_SECTION.format(
            muscle_groups=muscle_groups
        )

    response = messages.FINISH_SUCCESS.format(
        session_id=result['session_id'],
        duration=duration,
        audio_count=stats['audio_count'],
        resistance_exercises=stats['resistance_exercises'],
        total_sets=stats['total_sets'],
        total_volume_kg=stats['total_volume_kg'],
        aerobic_section=aerobic_section,
        muscle_groups_section=muscle_groups_section
    )

    await update.message.reply_text(response, parse_mode="Markdown")

    print("✅ Sessão finalizada com sucesso")

@authorized_only
@rate_limit_commands
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /export - Exporta dados do usuário"""
    await log_access(update, context)
    
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
                parse_mode="Markdown"
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
                parse_mode="Markdown"
            )
            return
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gym_tracker_export_{user_name}_{timestamp}.{format_type}"
        
        # Prepare file content
        if format_type == "json":
            import json
            file_content = json.dumps(result["data"], indent=2, ensure_ascii=False).encode('utf-8')
            mime_type = "application/json"
        else:  # csv
            file_content = result["data"].encode('utf-8')
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
            parse_mode="Markdown"
        )
        
        await status_msg.delete()
        
        print(f"✅ Export completo: {filename} para usuário {user_id}")
        
    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro na exportação**\n\n{e.message}\n\n🔄 _Tente novamente_",
            parse_mode="Markdown"
        )
        print(f"❌ ERRO NO EXPORT: {e}")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao exportar dados.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown"
        )
        print(f"❌ ERRO INESPERADO NO EXPORT: {e}")
        import traceback
        traceback.print_exc()


@authorized_only
@rate_limit_commands
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /stats - Estatísticas e analytics do usuário"""
    await log_access(update, context)
    
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
            parse_mode="Markdown"
        )
        
        # Get analytics
        analytics = analytics_service.get_workout_analytics(user_id, days=days)
        
        if "message" in analytics:  # No data found
            await status_msg.edit_text(
                f"📊 **Estatísticas - {days} dias**\n\n"
                f"❌ {analytics['message']}\n\n"
                "Envie alguns áudios de treino primeiro!",
                parse_mode="Markdown"
            )
            return
        
        # Format comprehensive stats message
        stats_message = _format_analytics_message(analytics, user_name)
        
        await status_msg.edit_text(stats_message, parse_mode="Markdown")
        
        print(f"✅ Stats calculadas para usuário {user_id} ({days} dias)")
        
    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro nas estatísticas**\n\n{e.message}\n\n🔄 _Tente novamente_",
            parse_mode="Markdown"
        )
        print(f"❌ ERRO NAS STATS: {e}")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao calcular estatísticas.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown"
        )
        print(f"❌ ERRO INESPERADO NAS STATS: {e}")
        import traceback
        traceback.print_exc()


@authorized_only
@rate_limit_commands
async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /progress - Progresso de um exercício específico"""
    await log_access(update, context)
    
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
            parse_mode="Markdown"
        )
        return
    
    exercise_name = " ".join(args)
    
    try:
        analytics_service = get_analytics_service()
        
        status_msg = await update.message.reply_text(
            f"📈 **Analisando progresso...**\n\nExercício: {exercise_name}",
            parse_mode="Markdown"
        )
        
        # Get exercise progress
        progress = analytics_service.get_exercise_progress(user_id, exercise_name)
        
        if not progress["found"]:
            await status_msg.edit_text(
                f"📈 **Progresso do Exercício**\n\n"
                f"❌ {progress['message']}\n\n"
                "💡 _Verifique se o nome está correto ou registre mais treinos_",
                parse_mode="Markdown"
            )
            return
        
        # Format progress message
        progress_message = _format_progress_message(progress)
        
        await status_msg.edit_text(progress_message, parse_mode="Markdown")
        
        print(f"✅ Progresso calculado: {exercise_name} para usuário {user_id}")
        
    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro no progresso**\n\n{e.message}\n\n🔄 _Tente novamente_",
            parse_mode="Markdown"
        )
        print(f"❌ ERRO NO PROGRESSO: {e}")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nFalha ao calcular progresso.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown"
        )
        print(f"❌ ERRO INESPERADO NO PROGRESSO: {e}")
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
    message += f"⏱️ Duração média: {session_stats['average_duration_minutes']} min\n"
    message += f"🎤 Áudios por sessão: {session_stats['average_audios_per_session']:.1f}\n"
    if session_stats['average_energy_level'] > 0:
        message += f"⚡ Energia média: {session_stats['average_energy_level']:.1f}/10\n"
    message += "\n"
    
    # Exercise stats
    if exercise_stats["resistance"]["total_exercises"] > 0:
        resistance = exercise_stats["resistance"]
        message += "💪 **Exercícios de Resistência:**\n"
        message += f"🔢 Total: {resistance['total_exercises']} exercícios\n"
        message += f"📊 Séries: {resistance['total_sets']} séries\n"
        message += f"🏋️ Volume: {resistance['total_volume_kg']:,.0f}kg\n"
        if resistance['average_difficulty'] > 0:
            message += f"😤 Dificuldade média: {resistance['average_difficulty']:.1f}/10\n"
        message += "\n"
    
    # Frequency
    message += "📅 **Frequência:**\n"
    message += f"📊 {frequency['frequency_per_week']:.1f} treinos/semana\n"
    message += f"🎯 Consistência: {frequency['consistency_score']:.1f}%\n"
    if frequency['longest_streak_days'] > 1:
        message += f"🔥 Maior sequência: {frequency['longest_streak_days']} dias\n"
    message += "\n"
    
    # Most trained muscle groups
    if muscle_dist.get("distribution"):
        sorted_muscles = sorted(
            muscle_dist["distribution"].items(), 
            key=lambda x: x[1]["count"], 
            reverse=True
        )[:3]
        message += "🎯 **Músculos Mais Trabalhados:**\n"
        for muscle, data in sorted_muscles:
            message += f"• {muscle.title()}: {data['percentage']:.1f}%\n"
        message += "\n"
    
    # Trends
    if trends.get("trend") and trends["trend"] != "insufficient_data":
        trend_emoji = "📈" if trends["trend"] == "improving" else "📉" if trends["trend"] == "declining" else "➡️"
        message += f"{trend_emoji} **Tendência:** {trends['trend'].title()}\n"
        if abs(trends['volume_change_percent']) > 5:
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
    if summary['weight_progression'] != 0:
        prog_emoji = "📈" if summary['weight_progression'] > 0 else "📉"
        message += f"{prog_emoji} **Evolução de Peso:** {summary['weight_progression']:+.1f}kg\n"
    
    if summary['volume_progression'] != 0:
        vol_emoji = "📈" if summary['volume_progression'] > 0 else "📉"
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


@rate_limit_commands
async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler para comandos desconhecidos"""
    await log_access(update, context)
    await update.message.reply_text(messages.UNKNOWN_COMMAND)


