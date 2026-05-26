"""
Voice module configuration.
Extends the main Settings with voice-specific options.
"""
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class VoiceSettings(BaseSettings):
    """
    Voice module configuration.
    
    Enable/disable and configure TTS and STT providers independently.
    No impact on existing code if disabled.
    """

    # ── Global ────────────────────────────────────────────────────────────────
    voice_enabled: bool = Field(
        default=False,
        description="Enable voice module (if False, no endpoints registered)"
    )

    # ── STT (Speech-to-Text) ──────────────────────────────────────────────────
    stt_provider: str = Field(
        default="local",
        description="Default STT provider: local, google-cloud, azure, web-speech"
    )
    stt_local_model: str = Field(
        default="base",
        description="Local Whisper model (tiny, base, small, medium, large, etc.)"
    )
    stt_language: str = Field(
        default="en-US",
        description="Default language for STT"
    )

    # Google Cloud STT
    google_cloud_stt_enabled: bool = Field(default=False)
    google_cloud_credentials_path: Optional[str] = Field(default=None)

    # Azure STT
    azure_stt_enabled: bool = Field(default=False)
    azure_speech_key: Optional[str] = Field(default=None)
    azure_speech_region: str = Field(default="eastus")

    # ── TTS (Text-to-Speech) ──────────────────────────────────────────────────
    tts_provider: str = Field(
        default="edge",
        description="Default TTS provider: edge (neural), local, google-cloud, azure"
    )
    tts_neural_voice: Optional[str] = Field(
        default=None,
        description="Neural voice ID override, e.g. en-US-JennyNeural"
    )
    tts_local_backend: str = Field(
        default="pyttsx3",
        description="Local TTS backend: pyttsx3, espeak, gTTS"
    )
    tts_language: str = Field(
        default="en-US",
        description="Default language for TTS"
    )
    tts_gender: str = Field(
        default="neutral",
        description="Default voice gender: male, female, neutral"
    )
    tts_speaking_rate: float = Field(
        default=0.94,
        ge=0.5,
        le=2.0,
        description="Default speaking rate (0.94 = slightly slower, more natural)"
    )
    tts_audio_format: str = Field(
        default="mp3",
        description="Output audio format: mp3, wav, ogg, m4a, webm"
    )

    # Google Cloud TTS
    google_cloud_tts_enabled: bool = Field(default=False)

    # Azure TTS
    azure_tts_enabled: bool = Field(default=False)

    # ── Voice Chat Behavior ───────────────────────────────────────────────────
    voice_session_ttl_seconds: int = Field(
        default=3600,
        description="TTL for voice chat sessions (60 minutes)"
    )
    voice_max_audio_size_bytes: int = Field(
        default=52_428_800,  # 50 MB
        description="Max audio upload size (50 MB)"
    )
    voice_max_audio_duration_seconds: int = Field(
        default=600,
        description="Max audio duration (10 minutes)"
    )
    voice_streaming_chunk_size_bytes: int = Field(
        default=8192,
        description="Chunk size for streaming audio responses"
    )

    # ── Domain-Specific Hints ─────────────────────────────────────────────────
    sre_domain_hints: list[str] = Field(
        default_factory=lambda: [
            "Kubernetes", "pod", "container", "ingress", "service",
            "deployment", "namespace", "node", "cluster",
            "Prometheus", "alert", "metric", "dashboard",
            "incident", "runbook", "SLA", "RCA", "postmortem",
            "kubectl", "docker", "helm", "terraform",
            "ArgoCD", "Grafana", "Loki", "Jaeger",
        ],
        description="Domain-specific keywords to boost STT recognition in SRE domain"
    )

    # ── Logging & Debug ───────────────────────────────────────────────────────
    voice_log_audio_metadata: bool = Field(
        default=True,
        description="Log audio duration/size/format (never log content)"
    )
    voice_debug_return_text: bool = Field(
        default=False,
        description="Return debug text fields (LLM response, transcription) by default"
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "env_prefix": "VOICE_", "extra": "ignore"}


@lru_cache
def get_voice_settings() -> VoiceSettings:
    """Get cached voice settings."""
    return VoiceSettings()
