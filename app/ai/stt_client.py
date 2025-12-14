import io
import logging
from typing import Optional
from anyio import to_thread
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Инициализируем клиент один раз
_client = OpenAI(api_key=settings.openai_api_key)


async def transcribe_audio(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    """
    Транскрибирует аудиофайл через OpenAI Whisper API.
    
    Args:
        file_bytes: байты аудиофайла
        filename: имя файла (для определения формата)
    
    Returns:
        Распознанный текст (строка)
    
    Raises:
        Exception: если транскрипция не удалась
    """
    try:
        audio_file = io.BytesIO(file_bytes)
        audio_file.name = filename

        def _call():
            return _client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        resp = await to_thread.run_sync(_call)
        text = getattr(resp, "text", None) or ""
        logger.info(f"[STT] Transcribed {len(file_bytes)} bytes, got {len(text)} chars")
        return text
    except Exception as e:
        logger.error(f"[STT] Error transcribing audio: {e}")
        raise

