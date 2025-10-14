"""User-facing messages configuration for internationalization and easy customization"""

from typing import Any, Dict


class Messages:
    """Container for all user-facing messages"""

    # Welcome and help messages
    WELCOME = """👋 Olá, {user_name}! Bem-vindo ao Gym Tracker Bot!

🎤 **Como usar:**
- Envie um áudio descrevendo seu treino
- Envie uma mensagem de texto com informações
- Use /help para ver os comandos disponíveis

Estou pronto para receber seus dados! 💪"""

    HELP = """🤖 **GYM TRACKER BOT - Comandos Disponíveis**

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
- `/myid` - Ver seu ID do Telegram
- `/status` - Ver sessão atual
- `/finish` - Finalizar treino atual
- `/stats [dias]` - Estatísticas e analytics
- `/progress <exercício>` - Progresso específico
- `/exercises` - Listar todos os exercícios
- `/export [json|csv]` - Exportar seus dados
- `/help` - Mostra esta ajuda

**👑 Comandos Admin:**
- `/adduser <id> [admin]` - Adicionar usuário
- `/removeuser <id>` - Remover usuário
- `/listusers` - Listar usuários

**⏰ Sistema de Sessões:**
- Todos os áudios em 3 horas = mesma sessão
- Após 3h sem áudio = nova sessão automática
- Use `/finish` para fechar manualmente

**💡 Dica:** Seja específico sobre o exercício!
_"supino com halteres"_ é melhor que só _"supino"_"""

    # User info messages
    USER_INFO = """🆔 **Suas Informações:**

**Nome:** {user_name}
**Username:** @{username}
**User ID:** `{user_id}`

_Copie o User ID para autorizar no bot_"""

    INFO_COMMAND = """👤 **Suas Informações:**

**Nome:** {user_name} {user_last_name}
**Username:** @{username}
**ID:** `{user_id}`
**Idioma:** {user_language}

📅 **Data/Hora atual:** {current_datetime}

✅ **Status:** Autorizado"""

    # Text processing messages
    TEXT_RECEIVED = """✅ **Mensagem recebida!**

📝 Você escreveu:
_{message_text}_

👤 Seu ID: `{user_id}`
🕐 Horário: {timestamp}

_Em breve vou processar essa informação com IA!_ 🤖"""

    # Audio processing messages
    AUDIO_PROCESSING_NEW_SESSION = """🎤 **Áudio recebido!**

✨ **Nova sessão de treino iniciada**
🆔 Session ID: `{session_id}`
⏱️ Duração: {duration}s

🔄 Processando..."""

    AUDIO_PROCESSING_EXISTING_SESSION = """🎤 **Áudio recebido!**

➕ **Adicionando à sessão #{session_id}**
📝 Áudio #{audio_count} desta sessão
⏱️ Duração: {duration}s

🔄 Processando..."""

    # Text processing messages
    TEXT_PROCESSING_NEW_SESSION = """📝 **Mensagem de treino recebida!**

✨ **Nova sessão de treino iniciada**
🆔 Session ID: `{session_id}`

🔄 Processando..."""

    TEXT_PROCESSING_EXISTING_SESSION = """📝 **Mensagem de treino recebida!**

➕ **Adicionando à sessão #{session_id}**
📝 Mensagem #{message_count} desta sessão

🔄 Processando..."""

    AUDIO_SUCCESS_NEW_SESSION = "✅ **Nova sessão criada e áudio processado!**\n\n"
    AUDIO_SUCCESS_EXISTING_SESSION = "✅ **Áudio/Texto #{audio_count} adicionado à sessão!**\n\n"

    AUDIO_SUCCESS_FOOTER_NEW = "💡 _Envie mais áudios ou texto para adicionar exercícios a esta sessão_"
    AUDIO_SUCCESS_FOOTER_CONTINUE = "💡 _Continue enviando áudios ou texto ou aguarde 3h para iniciar nova sessão_"

    # Status messages
    STATUS_NO_SESSION = """📊 **Status**

Você ainda não tem nenhuma sessão registrada.
Envie um áudio para começar!"""

    STATUS_ACTIVE_SESSION = """🟢 **Sessão Ativa**

🆔 Session ID: `{session_id}`
🕐 Iniciada: {start_time}
⏱️ Última atualização: há {minutes_passed} minutos
📝 Áudios enviados: {audio_count}
💪 Exercícios de resistência: {resistance_count}
🏃 Exercícios aeróbicos: {aerobic_count}

💡 _Envie mais áudios para adicionar exercícios_"""

    STATUS_FINISHED_SESSION = """⚪ **Última Sessão (Finalizada)**

🆔 Session ID: `{session_id}`
📅 Data: {date}
🕐 Horário: {start_time} - {end_time}
📝 Áudios enviados: {audio_count}
💪 Exercícios de resistência: {resistance_count}
🏃 Exercícios aeróbicos: {aerobic_count}

⏰ Sessão expirada há {expired_minutes} minutos

💡 _Envie um áudio para iniciar nova sessão_"""

    # Session finish messages
    FINISH_SUCCESS = """✅ **Sessão #{session_id} Finalizada!**

⏱️ **Duração Total:** {duration} minutos
📊 **Áudios Enviados:** {audio_count}

💪 **Exercícios de Resistência:** {resistance_exercises}
   └ {total_sets} séries totais
   └ {total_volume_kg:,.0f}kg de volume total

{aerobic_section}
{muscle_groups_section}
🎉 Excelente treino! Continue assim! 💪"""

    FINISH_AEROBIC_SECTION = """🏃 **Exercícios Aeróbicos:** {aerobic_exercises}
   └ {cardio_minutes} minutos de cardio

"""

    FINISH_MUSCLE_GROUPS_SECTION = "🎯 **Músculos Trabalhados:** {muscle_groups}\n\n"

    # Error messages
    ERROR_INVALID_DATA = "❌ **Dados inválidos detectados**\n\n{errors}"
    ERROR_PROCESSING = "❌ **Erro no processamento**\n\n{error_details}"
    ERROR_STATUS_FETCH = "❌ **Erro ao buscar status**\n\n{error_message}\n\n🔄 _Tente novamente_"
    ERROR_UNEXPECTED = "❌ **Erro inesperado**\n\n{error_message}\n\n🔄 _Tente novamente_"
    ERROR_FINISH_SESSION = "❌ Erro: {error}"
    ERROR_SESSION_NOT_FOUND = """❌ Você não tem nenhuma sessão ativa para finalizar.

Envie um áudio de treino para iniciar uma nova sessão!"""
    ERROR_SESSION_ALREADY_FINISHED = """ℹ️ A sessão #{session_id} já foi finalizada.

📅 Data: {date}
⏰ Duração: {duration}min"""

    # Specific error messages for different types
    ERROR_VALIDATION = "❌ **Dados inválidos**\n\n{message}{details}"
    ERROR_AUDIO_PROCESSING = "🎤 **Erro na transcrição**\n\n{message}{rate_limit_note}"
    ERROR_LLM_PARSING = "🤖 **Erro na análise**\n\n{message}\n\n💡 _Tente descrever o treino de forma mais clara_"
    ERROR_SERVICE_UNAVAILABLE = "🔌 **Serviço indisponível**\n\n{message}{details}"
    ERROR_DATABASE = "💾 **Erro interno**\n\n{message}\n\n🔄 _Tente novamente em alguns instantes_"

    # Rate limit messages
    RATE_LIMIT_GENERAL = """⏰ **Rate limit atingido**

Você está enviando muitas mensagens.
Aguarde {reset_time} segundos antes de tentar novamente.

💡 _Limite: {max_requests} mensagens por {window_seconds} segundos_"""

    RATE_LIMIT_VOICE = """🎤 **Limite de áudios atingido**

Você está enviando muitos áudios.
Aguarde {reset_time} segundos antes de enviar outro áudio.

💡 _Limite: {max_requests} áudios por {window_seconds} segundos_

⚡ _Dica: Grave áudios mais longos com múltiplos exercícios_"""

    RATE_LIMIT_COMMANDS = """🤖 **Limite de comandos atingido**

Você está usando muitos comandos.
Aguarde {reset_time} segundos.

💡 _Limite: {max_requests} comandos por {window_seconds} segundos_"""

    # Authorization messages
    ACCESS_DENIED = """🚫 **Acesso Negado**

Este bot é de uso privado.
Você não tem autorização para utilizá-lo.

_Seu ID: `{user_id}`_"""

    # Unknown command
    UNKNOWN_COMMAND = "❓ Comando não reconhecido.\nUse /help para ver os comandos disponíveis."

    @classmethod
    def format_transcription_response(cls, transcription: str) -> str:
        """Format transcription part of success message"""
        return f"📝 **Você disse:**\n_{transcription}_\n\n"

    @classmethod
    def format_exercise_section(cls, resistance_exercises: list, aerobic_exercises: list) -> str:
        """Format the exercises section of success messages"""
        response = ""

        if resistance_exercises:
            response += "💪 **Exercícios Adicionados:**\n"
            for ex in resistance_exercises:
                response += cls._format_single_exercise(ex)

        if aerobic_exercises:
            response += "🏃 **Exercícios Aeróbicos:**\n"
            for ex in aerobic_exercises:
                response += cls._format_single_aerobic_exercise(ex)
            response += "\n"

        return response

    @classmethod
    def _format_single_exercise(cls, ex: Dict[str, Any]) -> str:
        """Format a single resistance exercise"""
        weights = ex.get("weights_kg", [])
        if not weights and ex.get("weight_kg"):
            weights = [ex.get("weight_kg")] * ex.get("sets", 1)

        reps = ex.get("reps", [])
        rest_seconds = ex.get("rest_seconds")
        difficulty = ex.get("perceived_difficulty")

        response = f"• **{ex['name'].title()}**:\n"

        # Show series details
        if len(set(weights)) > 1:  # Different weights
            for i in range(ex.get("sets", 0)):
                rep = reps[i] if i < len(reps) else "?"
                weight = weights[i] if i < len(weights) else "?"
                response += f"  └ Série {i+1}: {rep} reps × {weight}kg\n"
        else:  # Same weight for all sets
            reps_str = ", ".join(map(str, reps))
            weight = weights[0] if weights else "?"
            response += f"  └ {ex.get('sets')}× ({reps_str}) com {weight}kg\n"

        # Rest time
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

        # Difficulty
        if difficulty:
            emoji, desc = cls._get_difficulty_emoji_and_desc(difficulty)
            response += f"  └ {emoji} RPE: {difficulty}/10 ({desc})\n"

        response += "\n"
        return response

    @classmethod
    def _format_single_aerobic_exercise(cls, ex: Dict[str, Any]) -> str:
        """Format a single aerobic exercise"""
        response = f"• **{ex['name'].title()}**:\n"

        # Duration (always present)
        duration = ex.get("duration_minutes")
        if duration:
            response += f"  └ ⏱️ Duração: {duration}min\n"

        # Distance
        distance = ex.get("distance_km")
        if distance:
            response += f"  └ 📏 Distância: {distance}km\n"

        # Heart rate
        heart_rate = ex.get("average_heart_rate")
        if heart_rate:
            response += f"  └ ❤️ FC média: {heart_rate} bpm\n"

        # Calories
        calories = ex.get("calories_burned")
        if calories:
            response += f"  └ 🔥 Calorias: {calories} kcal\n"

        # Intensity
        intensity = ex.get("intensity_level")
        if intensity:
            intensity_emoji, intensity_desc = cls._get_intensity_emoji_and_desc(intensity)
            response += f"  └ {intensity_emoji} Intensidade: {intensity_desc}\n"

        response += "\n"
        return response

    @classmethod
    def _get_intensity_emoji_and_desc(cls, intensity: str) -> tuple[str, str]:
        """Get emoji and description for aerobic intensity level"""
        intensity_map = {
            "low": ("😊", "Leve"),
            "moderate": ("😐", "Moderada"),
            "high": ("😤", "Alta"),
            "hiit": ("🔥", "HIIT"),
        }
        return intensity_map.get(intensity.lower(), ("⚡", intensity.title()))

    @classmethod
    def _get_difficulty_emoji_and_desc(cls, difficulty: int) -> tuple[str, str]:
        """Get emoji and description for difficulty level"""
        if difficulty <= 2:
            return "😊", "Muito fácil"
        if difficulty <= 4:
            return "🙂", "Fácil"
        if difficulty <= 6:
            return "😐", "Moderado"
        if difficulty <= 8:
            return "😤", "Difícil"
        return "🔥", "Muito difícil"


# Global messages instance
messages = Messages()

