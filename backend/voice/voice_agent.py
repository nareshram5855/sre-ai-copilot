"""
Voice Agent — orchestrates speech-to-text, LLM response, text-to-speech flow.

This agent:
  1. Transcribes incoming audio to text
  2. Routes text to chat agent (gets LLM response)
  3. Synthesizes response back to speech
  4. Returns audio

Inherits from BaseAgent to get LLM routing, RAG, and error handling benefits.
"""
import asyncio
import base64
import logging
import time
from typing import Any

from backend.agents.base import BaseAgent
from backend.agents.chat_agent import ChatAgent
from backend.memory.session_store import session_store
from backend.voice.config import get_voice_settings
from backend.voice.providers import get_stt_provider, get_tts_provider
from backend.voice.base import AudioFormat

logger = logging.getLogger(__name__)


class VoiceAgent(BaseAgent):
    """
    Implements voice interaction: audio_in → text → LLM → text → audio_out.

    Does NOT impact existing agents. Chat logic delegated to ChatAgent.
    """

    def __init__(self):
        super().__init__()
        self.cfg = get_voice_settings()
        self._chat_agent = ChatAgent(store=session_store)

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Sync entry point — delegates to arun for async provider calls."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.arun(payload))

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, self.arun(payload)).result()

    async def arun(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute voice workflow asynchronously.

        Input payload:
            - audio_base64: Base64-encoded audio
            - audio_format: Format identifier (wav, mp3, etc.)
            - language: BCP-47 language code (optional)
            - session_id: Chat session ID (optional)
            - return_text: If True, include transcription and LLM response (optional)

        Returns:
            - audio_base64: Base64-encoded audio response
            - audio_format: Format used for output
            - user_text: Transcribed user input (if return_text=True)
            - response_text: LLM response (if return_text=True)
            - confidence: STT confidence score
            - duration_seconds: Output audio duration
            - provider_stt: Name of STT provider used
            - provider_tts: Name of TTS provider used
        """
        start_time = time.monotonic()

        audio_base64 = payload.get("audio_base64", "")
        audio_format = payload.get("audio_format", "wav")
        language = payload.get("language")
        session_id = payload.get("session_id")
        return_text = payload.get("return_text", self.cfg.voice_debug_return_text)
        domain_hints = payload.get("domain_hints") or self.cfg.sre_domain_hints

        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as exc:
            raise ValueError(f"Invalid base64 audio: {exc}")

        if len(audio_bytes) > self.cfg.voice_max_audio_size_bytes:
            raise ValueError(
                f"Audio too large: {len(audio_bytes)} > {self.cfg.voice_max_audio_size_bytes}"
            )

        logger.info("VoiceAgent started: audio_format=%s, size=%d bytes", audio_format, len(audio_bytes))

        stt_provider = get_stt_provider()
        stt_result = await self._transcribe(
            audio_bytes, audio_format, language, domain_hints, stt_provider
        )
        user_text = stt_result["text"]
        confidence = float(stt_result.get("confidence", 0.0))

        logger.info("STT complete: text_len=%d, confidence=%s", len(user_text), confidence)

        chat_payload = {
            "question": user_text,
            "session_id": session_id or "voice_session",
        }
        chat_result = self._chat_agent.execute(chat_payload)
        response_text = chat_result.get("answer") or chat_result.get("response", "")

        logger.info("Chat complete: response_len=%d", len(response_text))

        tts_provider = get_tts_provider()
        audio_response, duration = await self._synthesize(response_text, tts_provider)

        elapsed = round(time.monotonic() - start_time, 3)
        logger.info("VoiceAgent completed in %ss: audio_duration=%ss", elapsed, duration)

        result = {
            "audio_base64": base64.b64encode(audio_response).decode("utf-8"),
            "audio_format": self.cfg.tts_audio_format,
            "duration_seconds": duration,
            "confidence": confidence,
            "provider_stt": stt_provider.name,
            "provider_tts": tts_provider.name,
            "processing_time_ms": int(elapsed * 1000),
        }

        if return_text:
            result["user_text"] = user_text
            result["response_text"] = response_text

        return result

    async def _transcribe(
        self,
        audio_bytes: bytes,
        audio_format: str,
        language: str | None,
        domain_hints: list[str],
        stt_provider,
    ) -> dict[str, Any]:
        """Transcribe audio to text using configured STT provider."""
        try:
            return await stt_provider.transcribe(
                audio_bytes,
                audio_format=AudioFormat(audio_format),
                language=language,
                hints=domain_hints,
            )
        except Exception as exc:
            logger.error("STT failed: %s", exc)
            raise RuntimeError(f"Speech-to-text failed: {exc}") from exc

    async def _synthesize(self, text: str, tts_provider) -> tuple[bytes, float]:
        """Synthesize text to speech, return (audio_bytes, duration_seconds)."""
        try:
            audio_bytes = await tts_provider.synthesize(
                text,
                language=self.cfg.tts_language,
                gender=self.cfg.tts_gender,
                rate=self.cfg.tts_speaking_rate,
                output_format=AudioFormat(self.cfg.tts_audio_format),
            )

            word_count = len(text.split())
            estimated_duration = max(0.5, word_count / 150.0)

            return audio_bytes, estimated_duration
        except Exception as exc:
            logger.error("TTS failed: %s", exc)
            raise RuntimeError(f"Text-to-speech failed: {exc}") from exc
