"""
Pydantic models for voice module I/O.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ── Voice Input Models ────────────────────────────────────────────────────────

class VoiceTranscribeRequest(BaseModel):
    """Request to transcribe audio to text."""
    
    audio_base64: str = Field(..., description="Base64-encoded audio data")
    audio_format: str = Field(default="wav", description="Audio format: wav, mp3, ogg, webm")
    language: Optional[str] = Field(default=None, description="BCP-47 language code, e.g., 'en-US'")
    domain_hints: Optional[list[str]] = Field(
        default=None,
        description="Domain-specific keywords (e.g., ['Kubernetes', 'pod', 'ingress']) to boost recognition"
    )


class VoiceTranscribeResponse(BaseModel):
    """Response from transcription."""
    
    text: str = Field(..., description="Transcribed text")
    confidence: float = Field(..., description="Confidence score 0.0-1.0")
    language: str = Field(..., description="Detected language code")
    duration_seconds: float = Field(..., description="Audio duration in seconds")
    provider: str = Field(..., description="STT provider used")
    processing_time_ms: float = Field(..., description="Time to process audio")


# ── Voice Chat Models ─────────────────────────────────────────────────────────

class VoiceChatRequest(BaseModel):
    """Send voice message and get voice response."""
    
    audio_base64: str = Field(..., description="Base64-encoded audio data")
    audio_format: str = Field(default="wav", description="Audio format")
    language: Optional[str] = Field(default=None, description="BCP-47 language code")
    session_id: Optional[str] = Field(default=None, description="Chat session ID for context")
    return_text: bool = Field(
        default=False,
        description="Also return transcribed text and LLM response text (for debugging)"
    )


class VoiceChatResponse(BaseModel):
    """Voice chat response with optional text debug info."""
    
    audio_base64: str = Field(..., description="Base64-encoded audio response")
    audio_format: str = Field(default="mp3", description="Audio format")
    response_text: Optional[str] = Field(None, description="LLM response text (if return_text=True)")
    user_text: Optional[str] = Field(None, description="Transcribed user input (if return_text=True)")
    confidence: float = Field(..., description="STT confidence for input")
    duration_seconds: float = Field(..., description="Audio response duration")
    provider_stt: str = Field(..., description="STT provider used")
    provider_tts: str = Field(..., description="TTS provider used")
    processing_time_ms: float = Field(..., description="Total processing time")


# ── Text-to-Speech Models ─────────────────────────────────────────────────────

class TextToSpeechRequest(BaseModel):
    """Request to convert text to audio."""
    
    text: str = Field(..., description="Text to synthesize", min_length=1, max_length=5000)
    language: str = Field(default="en-US", description="BCP-47 language code")
    gender: str = Field(
        default="neutral",
        description="Voice gender: male, female, neutral"
    )
    rate: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Speaking rate (0.5=half speed, 2.0=double speed)"
    )
    pitch: float = Field(
        default=0.0,
        ge=-20,
        le=20,
        description="Pitch adjustment in semitones"
    )
    audio_format: str = Field(default="mp3", description="Output audio format")


class TextToSpeechResponse(BaseModel):
    """Response from text-to-speech."""
    
    audio_base64: str = Field(..., description="Base64-encoded audio data")
    audio_format: str = Field(..., description="Audio format")
    duration_seconds: float = Field(..., description="Audio duration in seconds")
    provider: str = Field(..., description="TTS provider used")
    processing_time_ms: float = Field(..., description="Time to synthesize")
    character_count: int = Field(..., description="Number of characters synthesized")


# ── Voice Status Models ───────────────────────────────────────────────────────

class VoiceProviderInfo(BaseModel):
    """Information about a voice provider."""
    
    name: str = Field(..., description="Provider name")
    type: Literal["tts", "stt"] = Field(..., description="Provider type")
    enabled: bool = Field(..., description="Whether provider is enabled")
    requires_api_key: bool = Field(..., description="Whether API key is required")
    supported_languages: list[str] = Field(default_factory=list, description="Supported language codes")


class VoiceHealthResponse(BaseModel):
    """Voice module health status."""
    
    enabled: bool = Field(..., description="Whether voice module is enabled")
    tts_providers: list[VoiceProviderInfo] = Field(..., description="Available TTS providers")
    stt_providers: list[VoiceProviderInfo] = Field(..., description="Available STT providers")
    default_tts: str = Field(..., description="Default TTS provider")
    default_stt: str = Field(..., description="Default STT provider")
