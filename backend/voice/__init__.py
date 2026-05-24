"""
Voice Module — Plugin for speech-to-text and text-to-speech.

This module runs completely independently of the core SRE AI system.
It can be enabled/disabled via configuration without impacting any existing code.

Components:
  - base.py:        Abstract base classes for TTS/STT providers
  - providers.py:   Implementations (Google Cloud, Azure, local Ollama, Web Speech API)
  - models.py:      Pydantic models for voice I/O
  - config.py:      Voice-specific configuration
  - voice_agent.py: Agent that uses text agents + voice transformation
  - router.py:      FastAPI router with voice endpoints

Usage:
  from backend.voice.config import get_voice_settings
  from backend.voice.providers import get_tts_provider, get_stt_provider

  # Only registered if enabled in config
  if get_voice_settings().enabled:
      app.include_router(voice_router)
"""

__version__ = "0.1.0"
__all__ = ["get_voice_settings", "get_tts_provider", "get_stt_provider", "VoiceAgent"]
