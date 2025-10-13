import time
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware import authorized_only, log_access
from config.settings import settings
from database.connection import db
from database.models import SessionStatus, WorkoutSession
from services.audio_service import get_audio_service
from services.llm_service import get_llm_service
from services.session_manager import get_session_manager  # ← NOVO
from services.workout_service import get_workout_service
from services.exceptions import (
    AudioProcessingError,
    DatabaseError,
    LLMParsingError,
    ServiceUnavailableError,
    SessionError,
    ValidationError,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Mensagem de boas-vindas"""
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
    """Comando /help - Ajuda"""
    await log_access(update, context)
    help_text = """
🤖 **GYM TRACKER BOT - Comandos Disponíveis**

**📝 Registrar Treino:**
🎤 Envie um áudio descrevendo seu treino!

Exemplo: _"Fiz supino reto com barra, 3 séries de 12, 10 e 8 repetições com 40, 50 e 60 kg, 1 minuto de descanso, estava bem pesado"_

**🎯 O que você pode informar:**
- Nome do exercício (com equipamento)
- Número de séries e repetições
- Peso usado (pode ser diferente por série)
- Tempo de descanso entre séries
- Dificuldade percebida (fácil, pesado, etc)
- Seu peso corporal
- Nível de energia (1-10)

**📊 Comandos:**
- `/start` - Inicia o bot
- `/status` - Ver sessão atual
- `/finish` - Finalizar treino atual
- `/help` - Mostra esta ajuda

**⏰ Sistema de Sessões:**
- Todos os áudios em 3 horas = mesma sessão
- Após 3h sem áudio = nova sessão automática
- Use `/finish` para fechar manualmente

**💡 Dica:** Seja específico sobre o exercício!
_"supino com halteres"_ é melhor que só _"supino"_
"""
    await update.message.reply_text(help_text)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /myid - Mostra o user_id (útil para adicionar novos usuários)"""
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
    """Comando /info - PROTEGIDO"""
    await log_access(update, context)
    user = update.effective_user

    info_text = f"""
👤 **Suas Informações:**

**Nome:** {user.first_name} {user.last_name or ""}
**Username:** @{user.username or "não definido"}
**ID:** `{user.id}`
**Idioma:** {user.language_code or "não definido"}

📅 **Data/Hora atual:** {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}

✅ **Status:** Autorizado
    """

    await update.message.reply_text(info_text, parse_mode="Markdown")


@authorized_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de TEXTO"""
    await log_access(update, context)
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
🕐 Horário: {timestamp.strftime("%H:%M:%S")}

_Em breve vou processar essa informação com IA!_ 🤖
    """

    await update.message.reply_text(response, parse_mode="Markdown")


@authorized_only
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para mensagens de VOZ/ÁUDIO
    Com AUTO-DETECÇÃO de sessão ativa
    """
    await log_access(update, context)
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.first_name
    voice = update.message.voice

    duration = voice.duration
    file_size = voice.file_size

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
        error_msg = f"❌ **Dados inválidos**\n\n{e.message}"
        if e.details:
            error_msg += f"\n\n_Detalhes: {e.details}_"
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE VALIDAÇÃO: {e}")
        
    except AudioProcessingError as e:
        error_msg = f"🎤 **Erro na transcrição**\n\n{e.message}"
        if "rate_limit" in e.message.lower():
            error_msg += "\n\n⏰ _Tente novamente em alguns segundos_"
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE ÁUDIO: {e}")
        
    except LLMParsingError as e:
        error_msg = f"🤖 **Erro na análise**\n\n{e.message}\n\n💡 _Tente descrever o treino de forma mais clara_"
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE LLM: {e}")
        
    except ServiceUnavailableError as e:
        error_msg = f"🔌 **Serviço indisponível**\n\n{e.message}"
        if e.details:
            error_msg += f"\n\n_Detalhes: {e.details}_"
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE SERVIÇO: {e}")
        
    except (DatabaseError, SessionError) as e:
        error_msg = f"💾 **Erro interno**\n\n{e.message}\n\n🔄 _Tente novamente em alguns instantes_"
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO DE BANCO/SESSÃO: {e}")
        import traceback
        traceback.print_exc()
        
    except Exception as e:
        error_msg = f"❌ **Erro inesperado**\n\nOcorreu um erro interno.\n\n🔄 _Tente novamente_"
        await status_msg.edit_text(error_msg, parse_mode="Markdown")
        print(f"❌ ERRO INESPERADO: {e}")
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
            # Pegar weights_kg (novo) ou weight_kg (legado)
            weights = ex.get("weights_kg", [])
            if not weights and ex.get("weight_kg"):
                # Compatibilidade com formato antigo
                weights = [ex.get("weight_kg")] * ex.get("sets", 1)

            reps = ex.get("reps", [])
            rest_seconds = ex.get("rest_seconds")
            difficulty = ex.get("perceived_difficulty")

            # Formatação bonita
            response += f"• **{ex['name'].title()}**:\n"

            # Mostrar série por série se houver pesos diferentes
            if len(set(weights)) > 1:  # Pesos diferentes
                for i in range(ex.get("sets", 0)):
                    rep = reps[i] if i < len(reps) else "?"
                    weight = weights[i] if i < len(weights) else "?"
                    response += f"  └ Série {i+1}: {rep} reps × {weight}kg\n"
            else:  # Mesmo peso para todas
                reps_str = ", ".join(map(str, reps))
                weight = weights[0] if weights else "?"
                response += f"  └ {ex.get('sets')}× ({reps_str}) com {weight}kg\n"

            if rest_seconds:
                if rest_seconds >= 60:
                    minutes = rest_seconds // 60
                    seconds = rest_seconds % 60
                    if seconds > 0:
                        response += f"  └ ⏱️ Descanso: {minutes}min {seconds}s\n"
                    else:
                        response += f"  └ ⏱️ Descanso: {minutes}min\n"
                else:
                    response += f"  └ ⏱️ Descanso: {rest_seconds}s\n"

            # Dificuldade percebida
            if difficulty:
                # Emoji e descrição baseado no RPE
                if difficulty <= 2:
                    emoji = "😊"
                    desc = "Muito fácil"
                elif difficulty <= 4:
                    emoji = "🙂"
                    desc = "Fácil"
                elif difficulty <= 6:
                    emoji = "😐"
                    desc = "Moderado"
                elif difficulty <= 8:
                    emoji = "😤"
                    desc = "Difícil"
                else:
                    emoji = "🔥"
                    desc = "Muito difícil"

                response += f"  └ {emoji} RPE: {difficulty}/10 ({desc})\n"

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
    await log_access(update, context)
    user_id = str(update.effective_user.id)

    try:
        session_manager = get_session_manager()
        workout_service = get_workout_service()

        # Buscar última sessão
        db_session = db.get_session()
        last_session = (
            db_session.query(WorkoutSession)
            .filter_by(
                user_id=user_id,
            )
            .order_by(
                WorkoutSession.last_update.desc(),
            )
            .first()
        )

        if not last_session:
            await update.message.reply_text(
                "📊 **Status**\n\nVocê ainda não tem nenhuma sessão registrada.\nEnvie um áudio para começar!",
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
        
    except (ValidationError, DatabaseError) as e:
        await update.message.reply_text(
            f"❌ **Erro ao buscar status**\n\n{e.message}\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        print(f"❌ ERRO NO STATUS: {e}")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ **Erro inesperado**\n\nNão foi possível buscar o status.\n\n🔄 _Tente novamente_",
            parse_mode="Markdown",
        )
        print(f"❌ ERRO INESPERADO NO STATUS: {e}")
        import traceback
        traceback.print_exc()

@authorized_only
async def finish_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finaliza a sessão atual manualmente"""
    user = update.effective_user
    user_id = str(user.id)

    print(f"\n{'='*50}")
    print("📊 COMANDO /finish")
    print(f"{'='*50}")
    print(f"👤 Usuário: {user.first_name} (ID: {user_id})")


    workout_service = get_workout_service()

    # Buscar sessão ativa
    last_session = workout_service.get_last_session(user_id)

    if not last_session:
        await update.message.reply_text(
            "❌ Você não tem nenhuma sessão ativa para finalizar.\n\n"
            "Envie um áudio de treino para iniciar uma nova sessão!",
        )
        return

    if last_session.status == SessionStatus.FINALIZADA:
        await update.message.reply_text(
            f"ℹ️ A sessão #{last_session.session_id} já foi finalizada.\n\n"
            f"📅 Data: {last_session.date.strftime('%d/%m/%Y')}\n"
            f"⏰ Duração: {last_session.duration_minutes}min",
        )
        return

    # Finalizar sessão
    result = workout_service.finish_session(last_session.session_id, user_id)

    if not result["success"]:
        await update.message.reply_text(f"❌ Erro: {result['error']}")
        return

    # Formatar resumo
    stats = result["stats"]
    duration = result["duration_minutes"]

    response = f"✅ **Sessão #{result['session_id']} Finalizada!**\n\n"
    response += f"⏱️ **Duração Total:** {duration} minutos\n"
    response += f"📊 **Áudios Enviados:** {stats['audio_count']}\n\n"

    response += f"💪 **Exercícios de Resistência:** {stats['resistance_exercises']}\n"
    response += f"   └ {stats['total_sets']} séries totais\n"
    response += f"   └ {stats['total_volume_kg']:,.0f}kg de volume total\n\n"

    if stats["aerobic_exercises"] > 0:
        response += f"🏃 **Exercícios Aeróbicos:** {stats['aerobic_exercises']}\n"
        response += f"   └ {stats['cardio_minutes']} minutos de cardio\n\n"

    if stats["muscle_groups"]:
        muscle_groups = ", ".join(stats["muscle_groups"])
        response += f"🎯 **Músculos Trabalhados:** {muscle_groups}\n\n"

    response += "🎉 Excelente treino! Continue assim! 💪"

    await update.message.reply_text(response, parse_mode="Markdown")

    print("✅ Sessão finalizada com sucesso")

async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para comandos desconhecidos"""
    await log_access(update, context)
    await update.message.reply_text(
        "❓ Comando não reconhecido.\nUse /help para ver os comandos disponíveis.",
    )


