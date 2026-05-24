"""
Voice module router — FastAPI endpoints for voice interaction.

Endpoints:
  POST /api/v1/voice/chat          — Send voice, get voice response
  POST /api/v1/voice/transcribe    — Transcribe audio to text only
  POST /api/v1/voice/synthesize    — Convert text to audio only
  GET  /api/v1/voice/health        — Voice module status
  GET  /api/v1/voice/languages     — Supported languages
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.voice.config import get_voice_settings
from backend.voice.models import (
    VoiceTranscribeRequest, VoiceTranscribeResponse,
    TextToSpeechRequest, TextToSpeechResponse,
    VoiceChatRequest, VoiceChatResponse,
    VoiceHealthResponse, VoiceProviderInfo,
)
from backend.voice.base import AudioFormat
from backend.voice.providers import get_stt_provider, get_tts_provider
from backend.voice.voice_agent import VoiceAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

_voice_agent = VoiceAgent()


# ── Voice Chat Endpoint ───────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=VoiceChatResponse,
    summary="Send voice message, get voice response",
    description="Transcribe audio → route to chat → synthesize response",
)
async def voice_chat(req: VoiceChatRequest) -> VoiceChatResponse:
    """
    Full voice conversation: speech-in → LLM → speech-out.
    
    Typical latency (local):
      - STT (Whisper): 2-5s for 30s audio
      - LLM (Mistral 7B): 1-3s
      - TTS (pyttsx3): 0.5-2s
      Total: ~4-10 seconds
    """
    cfg = get_voice_settings()
    start = time.monotonic()

    try:
        payload = {
            "audio_base64": req.audio_base64,
            "audio_format": req.audio_format,
            "language": req.language,
            "session_id": req.session_id or "default_voice_session",
            "return_text": req.return_text,
            "domain_hints": cfg.sre_domain_hints,
        }

        result = await _voice_agent.arun(payload)

        elapsed = round(time.monotonic() - start, 3)
        logger.info(f"Voice chat completed in {elapsed}s")

        return VoiceChatResponse(
            audio_base64=result["audio_base64"],
            audio_format=result["audio_format"],
            response_text=result.get("response_text"),
            user_text=result.get("user_text"),
            confidence=result["confidence"],
            duration_seconds=result["duration_seconds"],
            provider_stt=result["provider_stt"],
            provider_tts=result["provider_tts"],
            processing_time_ms=result["processing_time_ms"],
        )

    except Exception as exc:
        logger.error(f"Voice chat failed: {exc}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Voice chat failed: {str(exc)}")


# ── Transcription-Only Endpoint ───────────────────────────────────────────────

@router.post(
    "/transcribe",
    response_model=VoiceTranscribeResponse,
    summary="Transcribe audio to text",
    description="Speech-to-text only (no LLM, no TTS)",
)
async def transcribe_audio(req: VoiceTranscribeRequest) -> VoiceTranscribeResponse:
    """Convert audio to text."""
    start = time.monotonic()

    try:
        import base64
        audio_bytes = base64.b64decode(req.audio_base64)
        
        cfg = get_voice_settings()
        stt_provider = get_stt_provider()
        
        result = await stt_provider.transcribe(
            audio_bytes,
            audio_format=AudioFormat(req.audio_format),
            language=req.language,
            hints=req.domain_hints or cfg.sre_domain_hints,
        )

        elapsed = round(time.monotonic() - start, 3)

        return VoiceTranscribeResponse(
            text=result["text"],
            confidence=float(result.get("confidence", 0.0)),
            language=result.get("language", req.language or "en-US"),
            duration_seconds=result.get("duration_seconds", 0.0),
            provider=stt_provider.name,
            processing_time_ms=int(elapsed * 1000),
        )

    except Exception as exc:
        logger.error(f"Transcription failed: {exc}")
        raise HTTPException(status_code=400, detail=f"Transcription failed: {str(exc)}")


# ── Text-to-Speech Endpoint ───────────────────────────────────────────────────

@router.post(
    "/synthesize",
    response_model=TextToSpeechResponse,
    summary="Convert text to audio",
    description="Text-to-speech only",
)
async def synthesize_text(req: TextToSpeechRequest) -> TextToSpeechResponse:
    """Convert text to audio."""
    start = time.monotonic()

    try:
        import base64
        cfg = get_voice_settings()
        tts_provider = get_tts_provider()
        
        audio_bytes = await tts_provider.synthesize(
            req.text,
            language=req.language,
            gender=req.gender,
            rate=req.rate,
            pitch=req.pitch,
            output_format=AudioFormat(req.audio_format),
        )

        elapsed = round(time.monotonic() - start, 3)
        
        # Estimate duration
        word_count = len(req.text.split())
        duration = max(0.5, word_count / 150.0)

        return TextToSpeechResponse(
            audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
            audio_format=req.audio_format,
            duration_seconds=duration,
            provider=tts_provider.name,
            processing_time_ms=int(elapsed * 1000),
            character_count=len(req.text),
        )

    except Exception as exc:
        logger.error(f"Synthesis failed: {exc}")
        raise HTTPException(status_code=400, detail=f"Synthesis failed: {str(exc)}")


# ── Health & Status Endpoint ──────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=VoiceHealthResponse,
    summary="Voice module status",
)
async def voice_health() -> VoiceHealthResponse:
    """Get voice module health and available providers."""
    cfg = get_voice_settings()

    if not cfg.voice_enabled:
        return VoiceHealthResponse(
            enabled=False,
            tts_providers=[],
            stt_providers=[],
            default_tts="",
            default_stt="",
        )

    try:
        tts_provider = get_tts_provider()
        stt_provider = get_stt_provider()

        return VoiceHealthResponse(
            enabled=True,
            tts_providers=[
                VoiceProviderInfo(
                    name=tts_provider.name,
                    type="tts",
                    enabled=True,
                    requires_api_key=False,
                    supported_languages=tts_provider.get_supported_languages(),
                )
            ],
            stt_providers=[
                VoiceProviderInfo(
                    name=stt_provider.name,
                    type="stt",
                    enabled=True,
                    requires_api_key=stt_provider.requires_api_key,
                    supported_languages=stt_provider.get_supported_languages(),
                )
            ],
            default_tts=cfg.tts_provider,
            default_stt=cfg.stt_provider,
        )

    except Exception as exc:
        logger.error(f"Voice health check failed: {exc}")
        raise HTTPException(status_code=503, detail=f"Voice module unavailable: {str(exc)}")


# ── Supported Languages Endpoint ──────────────────────────────────────────────

@router.get(
    "/languages",
    summary="Get supported languages",
    tags=["voice"],
)
async def get_supported_languages() -> dict[str, list[str]]:
    """List supported languages for TTS and STT."""
    try:
        tts_provider = get_tts_provider()
        stt_provider = get_stt_provider()

        return {
            "tts": tts_provider.get_supported_languages(),
            "stt": stt_provider.get_supported_languages(),
        }

    except Exception as exc:
        logger.error(f"Language list failed: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
