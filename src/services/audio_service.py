import os
import tempfile
import logging
from typing import Optional

from groq import Groq

from config.settings import settings
from services.exceptions import AudioProcessingError, ServiceUnavailableError, ValidationError

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """Serviço para transcrever áudios usando Groq Whisper API"""

    def __init__(self) -> None:
        logger.info("Inicializando Groq Whisper API...")
        
        if not settings.GROQ_API_KEY:
            raise ServiceUnavailableError(
                "GROQ_API_KEY não configurada",
                "Configure a variável de ambiente GROQ_API_KEY"
            )
        
        try:
            self.client = Groq(api_key=settings.GROQ_API_KEY)
            logger.info("Groq Whisper API inicializada com sucesso")
        except Exception as e:
            raise ServiceUnavailableError(
                "Falha ao inicializar cliente Groq",
                f"Erro: {str(e)}"
            )
            
        self.gym_vocabulary = """
        supino, agachamento, levantamento terra, leg press, cadeira extensora,
        cadeira flexora, rosca direta, rosca martelo, tríceps testa, tríceps corda,
        desenvolvimento, elevação lateral, remada, pulldown, puxada, flexão,
        barra fixa, paralelas, abdominal, prancha, burpee, corrida, esteira,
        bicicleta, elíptico, crossfit, HIIT, aeróbico, cardio, musculação,
        repetições, séries, quilos, kg, carga
        """

    async def transcribe_telegram_voice(self, file_bytes: bytes) -> str:
        """Transcreve um áudio do Telegram usando Groq API
        
        Args:
            file_bytes: Bytes do arquivo de áudio
            
        Returns:
            Texto transcrito
            
        Raises:
            ValidationError: Se os dados de entrada são inválidos
            AudioProcessingError: Se a transcrição falhar
            ServiceUnavailableError: Se o serviço Groq estiver indisponível

        """
        if not file_bytes:
            raise ValidationError("Arquivo de áudio vazio")
            
        max_size = settings.MAX_AUDIO_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_size:
            raise ValidationError(f"Arquivo de áudio muito grande (máximo {settings.MAX_AUDIO_FILE_SIZE_MB}MB)")
            
        temp_path: Optional[str] = None
        
        try:
            # Criar arquivo temporário
            with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
                
            logger.info(f"Transcrevendo áudio de {len(file_bytes)} bytes via Groq API...")

            # Abrir arquivo e enviar para Groq
            with open(temp_path, "rb") as audio_file:
                try:
                    transcription = self.client.audio.transcriptions.create(
                        file=(temp_path, audio_file.read()),
                        model="whisper-large-v3",
                        language="pt",
                        response_format="text",
                        prompt=self.gym_vocabulary,
                    )
                except Exception as e:
                    if "rate_limit" in str(e).lower():
                        raise ServiceUnavailableError(
                            "Limite de taxa do Groq API excedido",
                            "Tente novamente em alguns segundos"
                        )
                    elif "unauthorized" in str(e).lower():
                        raise ServiceUnavailableError(
                            "Chave API Groq inválida",
                            "Verifique a configuração GROQ_API_KEY"
                        )
                    else:
                        raise AudioProcessingError(
                            "Falha na transcrição do áudio",
                            f"Erro do Groq API: {str(e)}"
                        )

            # Groq retorna string diretamente
            transcription_text = transcription.strip()
            
            if not transcription_text:
                raise AudioProcessingError(
                    "Transcrição retornou texto vazio",
                    "Verifique se o áudio contém fala clara"
                )

            logger.info(f"Transcrição completa: {len(transcription_text)} caracteres")
            return transcription_text

        except (ValidationError, AudioProcessingError, ServiceUnavailableError):
            # Re-raise custom exceptions
            raise
        except Exception as e:
            logger.exception("Erro inesperado na transcrição")
            raise AudioProcessingError(
                "Erro inesperado na transcrição",
                f"Erro interno: {str(e)}"
            )

        finally:
            # Deletar arquivo temporário
            if temp_path:
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Falha ao deletar arquivo temporário {temp_path}: {e}")

# Service instantiation moved to container.py
# This module only defines the service class
