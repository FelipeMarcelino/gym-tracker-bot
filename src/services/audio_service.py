import asyncio
import logging
import tempfile
from typing import Optional

import aiofiles
import aiofiles.os
from groq import AsyncGroq

from config.settings import settings
from services.exceptions import (
    AudioProcessingError,
    ServiceUnavailableError,
    ValidationError,
)

logger = logging.getLogger(__name__)


class AudioTranscriptionService:
    """Serviço para transcrever áudios usando Groq Whisper API"""

    def __init__(self) -> None:
        logger.info('Inicializando Groq Whisper API...')

        if not settings.GROQ_API_KEY:
            raise ServiceUnavailableError(
                'GROQ_API_KEY não configurada',
                'Configure a variável de ambiente GROQ_API_KEY',
            )

        try:
            self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            logger.info('Groq Whisper API inicializada com sucesso')
        except Exception as e:
            raise ServiceUnavailableError(
                f'Falha ao inicializar cliente Groq. Erro: {e!s}',
                f'Erro: {e!s}',
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
            raise ValidationError('Arquivo de áudio vazio')

        max_size = settings.MAX_AUDIO_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_size:
            raise ValidationError(
                f'Arquivo de áudio muito grande (máximo {settings.MAX_AUDIO_FILE_SIZE_MB}MB)'
            )

        temp_path: Optional[str] = None

        try:
            # Criar arquivo temporário usando asyncio.to_thread
            temp_file = await asyncio.to_thread(
                tempfile.NamedTemporaryFile,
                delete=False,
                suffix='.ogg',
            )

            # Escrever dados de forma assíncrona
            async with aiofiles.open(temp_file.name, 'wb') as f:
                await f.write(file_bytes)
            temp_path = temp_file.name
            temp_file.close()  # Close the file descriptor

            logger.info(
                f'Transcrevendo áudio de {len(file_bytes)} bytes via Groq API...'
            )

            # Ler arquivo e enviar para Groq de forma assíncrona
            async with aiofiles.open(temp_path, 'rb') as audio_file:
                audio_data = await audio_file.read()
                try:
                    transcription = (
                        await self.client.audio.transcriptions.create(
                            file=(temp_path, audio_data),
                            model=settings.WHISPER_MODEL,
                            language='pt',
                            response_format='text',
                            temperature=0,
                            prompt=self.gym_vocabulary,
                        )
                    )
                except Exception as e:
                    # Check for rate limit errors (HTTP 429 or rate limit in message)
                    error_str = str(e).lower()
                    is_rate_limit = (
                        'rate limit' in error_str
                        or 'rate_limit' in error_str
                        or '429' in error_str
                        or 'too many requests' in error_str
                        or (hasattr(e, 'status_code') and e.status_code == 429)
                    )

                    if is_rate_limit:
                        raise ServiceUnavailableError(
                            'Limite de taxa do Groq API excedido',
                            'Tente novamente em alguns segundos',
                        )

                    # Check for authentication errors (HTTP 401)
                    is_auth_error = (
                        'unauthorized' in error_str
                        or '401' in error_str
                        or ('invalid' in error_str and 'key' in error_str)
                        or (hasattr(e, 'status_code') and e.status_code == 401)
                    )

                    if is_auth_error:
                        raise ServiceUnavailableError(
                            'Chave API Groq inválida',
                            'Verifique a configuração GROQ_API_KEY',
                        )

                    raise AudioProcessingError(
                        'Falha na transcrição do áudio',
                        f'Erro do Groq API: {e!s}',
                    )

            # Groq retorna string diretamente
            transcription_text = transcription.strip()

            if not transcription_text:
                raise AudioProcessingError(
                    'Transcrição retornou texto vazio',
                    'Verifique se o áudio contém fala clara',
                )

            logger.info(
                f'Transcrição completa: {len(transcription_text)} caracteres'
            )
            return transcription_text

        except (
            ValidationError,
            AudioProcessingError,
            ServiceUnavailableError,
        ):
            # Re-raise custom exceptions
            raise
        except Exception as e:
            logger.exception('Erro inesperado na transcrição')
            raise AudioProcessingError(
                'Erro inesperado na transcrição',
                f'Erro interno: {e!s}',
            )

        finally:
            # Deletar arquivo temporário de forma assíncrona
            if temp_path:
                try:
                    await aiofiles.os.remove(temp_path)
                except Exception as e:
                    logger.warning(
                        f'Falha ao deletar arquivo temporário {temp_path}: {e}'
                    )


# Service instantiation moved to container.py
# This module only defines the service class
