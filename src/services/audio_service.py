import os
import tempfile

from faster_whisper import WhisperModel  # ← MUDOU

from config.settings import settings


class AudioTranscriptionService:
    """Serviço para transcrever áudios usando Faster-Whisper"""

    def __init__(self, model_name: str = "base"):
        """Inicializa o Faster-Whisper
        
        Modelos disponíveis:
        - tiny: Mais rápido (~1GB RAM)
        - base: Bom balanço (recomendado) (~1GB RAM)
        - small: Melhor qualidade (~2GB RAM)
        - medium: Alta qualidade (~5GB RAM)
        - large-v3: Máxima qualidade (~10GB RAM)
        """
        print(f"🔄 Carregando Faster-Whisper '{model_name}'...")

        # device="cpu" ou device="cuda" se tiver GPU
        self.model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",  # Mais rápido em CPU
        )

        print(f"✅ Faster-Whisper '{model_name}' carregado!")

    async def transcribe_telegram_voice(self, file_bytes: bytes) -> str:
        """Transcreve um áudio do Telegram (bytes) sem salvar permanentemente
        
        Args:
            file_bytes: Bytes do arquivo de áudio
            
        Returns:
            Texto transcrito

        """
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        try:
            print("🎤 Transcrevendo áudio...")

            # Transcrever (retorna generator)
            segments, info = self.model.transcribe(
                temp_path,
                language="pt",
                beam_size=5,
                vad_filter=True,  # Remove silêncios
            )

            # Juntar todos os segmentos
            transcription = " ".join([segment.text for segment in segments]).strip()

            print(f"✅ Transcrição completa: {len(transcription)} caracteres")

            return transcription

        finally:
            # Deletar arquivo temporário
            try:
                os.unlink(temp_path)
            except:
                pass

# Instância global (Singleton pattern)
_audio_service = None

def get_audio_service() -> AudioTranscriptionService:
    """Retorna instância única do serviço de áudio"""
    global _audio_service
    if _audio_service is None:
        _audio_service = AudioTranscriptionService(
            model_name=settings.WHISPER_MODEL,
        )
    return _audio_service
