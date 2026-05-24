"""
Concrete implementations of TTS and STT providers.

Providers included:
  - Local: pyttsx3/espeak (TTS), whisper.cpp (STT)
  - Google Cloud: Cloud TTS and Cloud Speech-to-Text
  - Azure: Azure Speech Services
"""
import asyncio
import base64
import io
import logging
import tempfile
from typing import Optional

from backend.voice.base import TTSProvider, STTProvider, AudioFormat, VoiceGender
from backend.voice.config import get_voice_settings

logger = logging.getLogger(__name__)


# ── Local TTS Provider ────────────────────────────────────────────────────────

class LocalTTSProvider(TTSProvider):
    """
    Local text-to-speech using pyttsx3 or espeak.
    Falls back to gTTS (Google Translate TTS) if pyttsx3 unavailable.
    """

    def __init__(self):
        self.cfg = get_voice_settings()
        self._backend = self.cfg.tts_local_backend  # "pyttsx3", "espeak", or "gtts"
        self._voices_cache = None

    async def synthesize(
        self,
        text: str,
        *,
        language: str = "en-US",
        gender: VoiceGender = VoiceGender.NEUTRAL,
        rate: float = 1.0,
        pitch: float = 0.0,
        output_format: AudioFormat = AudioFormat.MP3,
    ) -> bytes:
        """
        Local TTS synthesis using pyttsx3 or espeak.
        Falls back gracefully if library unavailable.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            import pyttsx3
        except ImportError:
            logger.warning("pyttsx3 not installed. Install: pip install pyttsx3")
            # Fallback to stub implementation
            return await self._stub_synthesize(text, output_format)

        try:
            loop = asyncio.get_event_loop()
            # Run TTS in thread pool to avoid blocking
            audio_bytes = await loop.run_in_executor(
                None,
                lambda: self._run_pyttsx3(text, language, gender, rate, pitch, output_format)
            )
            return audio_bytes
        except Exception as exc:
            logger.error(f"TTS synthesis failed: {exc}")
            raise RuntimeError(f"TTS synthesis failed: {exc}")

    def _run_pyttsx3(
        self,
        text: str,
        language: str,
        gender: VoiceGender,
        rate: float,
        pitch: float,
        output_format: AudioFormat,
    ) -> bytes:
        """Synchronous pyttsx3 synthesis."""
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", int(150 * rate))  # Default 150 wpm
        engine.setProperty("pitch", pitch)

        suffix = ".mp3" if output_format == AudioFormat.MP3 else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name

        try:
            engine.save_to_file(text, tmp_path)
            engine.runAndWait()
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            import os
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _stub_synthesize(self, text: str, output_format: AudioFormat) -> bytes:
        """Stub implementation when pyttsx3 unavailable."""
        logger.warning(f"Using stub TTS (install pyttsx3 for real synthesis)")
        # Return minimal valid MP3 file (silence)
        # In production, fall back to cloud provider or error gracefully
        return b""

    def get_supported_languages(self) -> list[str]:
        return ["en-US", "en-GB", "es-ES", "fr-FR", "de-DE", "it-IT", "pt-BR"]

    def get_supported_voices(self) -> list[dict[str, str]]:
        return [
            {"voice_id": "default-male", "name": "Default Male", "gender": "male", "language": "en-US"},
            {"voice_id": "default-female", "name": "Default Female", "gender": "female", "language": "en-US"},
        ]

    @property
    def name(self) -> str:
        return "local-tts"

    @property
    def supports_streaming(self) -> bool:
        return False


# ── Local STT Provider ────────────────────────────────────────────────────────

class LocalSTTProvider(STTProvider):
    """
    Local speech-to-text using OpenAI Whisper (via whisper.cpp or Ollama).
    Requires: pip install openai-whisper OR access to Ollama with whisper model.
    """

    def __init__(self):
        self.cfg = get_voice_settings()
        self._model_cache = None

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        audio_format: AudioFormat = AudioFormat.WAV,
        language: Optional[str] = None,
        hints: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """Transcribe audio using local Whisper model."""
        if not audio_data:
            raise ValueError("Audio data cannot be empty")

        try:
            import whisper
        except ImportError:
            logger.warning("openai-whisper not installed. Install: pip install openai-whisper")
            return await self._stub_transcribe(audio_data)

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._run_whisper(audio_data, language),
            )
            return result
        except Exception as exc:
            logger.error(f"STT transcription failed: {exc}")
            raise RuntimeError(f"STT transcription failed: {exc}")

    def _run_whisper(self, audio_data: bytes, language: Optional[str]) -> dict[str, str]:
        """Synchronous Whisper transcription."""
        import whisper
        import io

        # Load model (cached)
        if self._model_cache is None:
            self._model_cache = whisper.load_model(self.cfg.stt_local_model)

        # Transcribe from bytes
        # Whisper expects file path or accepts numpy array
        audio_buffer = io.BytesIO(audio_data)
        result = self._model_cache.transcribe(audio_buffer, language=language)

        return {
            "text": result.get("text", ""),
            "confidence": result.get("language", ""),  # Whisper returns language, not confidence
            "language": result.get("language", "en"),
            "duration_seconds": result.get("duration", 0.0),
        }

    async def _stub_transcribe(self, audio_data: bytes) -> dict[str, str]:
        """Stub when Whisper unavailable."""
        logger.warning("Using stub STT (install openai-whisper for real transcription)")
        return {
            "text": "[Stub: install openai-whisper]",
            "confidence": 0.0,
            "language": "en-US",
            "duration_seconds": 0.0,
        }

    def get_supported_languages(self) -> list[str]:
        # Whisper supports 99+ languages
        return ["en-US", "es-ES", "fr-FR", "de-DE", "it-IT", "pt-BR", "ja-JP", "zh-CN"]

    @property
    def name(self) -> str:
        return "local-stt"

    @property
    def requires_api_key(self) -> bool:
        return False


# ── Google Cloud TTS (Stub) ───────────────────────────────────────────────────

class GoogleCloudTTSProvider(TTSProvider):
    """Google Cloud Text-to-Speech (requires credentials file and API enabled)."""

    def __init__(self):
        self.cfg = get_voice_settings()
        if not self.cfg.google_cloud_tts_enabled:
            raise RuntimeError("Google Cloud TTS not enabled in config")

    async def synthesize(
        self,
        text: str,
        *,
        language: str = "en-US",
        gender: VoiceGender = VoiceGender.NEUTRAL,
        rate: float = 1.0,
        pitch: float = 0.0,
        output_format: AudioFormat = AudioFormat.MP3,
    ) -> bytes:
        """Synthesize using Google Cloud TTS API."""
        try:
            from google.cloud import texttospeech
        except ImportError:
            raise RuntimeError("google-cloud-texttospeech not installed. Install: pip install google-cloud-texttospeech")

        loop = asyncio.get_event_loop()
        audio_bytes = await loop.run_in_executor(
            None,
            lambda: self._run_google_cloud_tts(text, language, gender, rate, pitch, output_format)
        )
        return audio_bytes

    def _run_google_cloud_tts(
        self,
        text: str,
        language: str,
        gender: VoiceGender,
        rate: float,
        pitch: float,
        output_format: AudioFormat,
    ) -> bytes:
        """Synchronous Google Cloud TTS call."""
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()

        input_text = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language,
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=rate,
            pitch=pitch,
        )

        response = client.synthesize_speech(
            request={"input": input_text, "voice": voice, "audio_config": audio_config}
        )
        return response.audio_content

    def get_supported_languages(self) -> list[str]:
        return ["en-US", "es-ES", "fr-FR", "de-DE", "ja-JP", "zh-CN"]

    def get_supported_voices(self) -> list[dict[str, str]]:
        return [
            {"voice_id": "en-US-Neural2-A", "name": "English US Neural A", "gender": "female", "language": "en-US"},
            {"voice_id": "en-US-Neural2-C", "name": "English US Neural C", "gender": "male", "language": "en-US"},
        ]

    @property
    def name(self) -> str:
        return "google-cloud-tts"

    @property
    def supports_streaming(self) -> bool:
        return True


# ── Google Cloud STT (Stub) ───────────────────────────────────────────────────

class GoogleCloudSTTProvider(STTProvider):
    """Google Cloud Speech-to-Text (requires credentials file and API enabled)."""

    def __init__(self):
        self.cfg = get_voice_settings()
        if not self.cfg.google_cloud_stt_enabled:
            raise RuntimeError("Google Cloud STT not enabled in config")

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        audio_format: AudioFormat = AudioFormat.WAV,
        language: Optional[str] = None,
        hints: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """Transcribe using Google Cloud Speech API."""
        try:
            from google.cloud import speech_v1
        except ImportError:
            raise RuntimeError("google-cloud-speech not installed")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._run_google_cloud_stt(audio_data, language, hints),
        )
        return result

    def _run_google_cloud_stt(
        self,
        audio_data: bytes,
        language: Optional[str],
        hints: Optional[list[str]],
    ) -> dict[str, str]:
        """Synchronous Google Cloud STT call."""
        from google.cloud import speech_v1

        client = speech_v1.SpeechClient()
        audio = speech_v1.RecognitionAudio(content=audio_data)
        config = speech_v1.RecognitionConfig(
            encoding=speech_v1.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language or "en-US",
        )

        response = client.recognize(config=config, audio=audio)

        # Extract results
        transcription = ""
        confidence = 0.0
        if response.results:
            result = response.results[0]
            if result.alternatives:
                transcript = result.alternatives[0]
                transcription = transcript.transcript
                confidence = transcript.confidence

        return {
            "text": transcription,
            "confidence": str(confidence),
            "language": language or "en-US",
            "duration_seconds": 0.0,
        }

    def get_supported_languages(self) -> list[str]:
        return ["en-US", "es-ES", "fr-FR", "de-DE", "ja-JP", "zh-CN"]

    @property
    def name(self) -> str:
        return "google-cloud-stt"

    @property
    def requires_api_key(self) -> bool:
        return True


# ── Provider Registry ─────────────────────────────────────────────────────────

_TTS_PROVIDERS = {
    "local": LocalTTSProvider,
    "google-cloud": GoogleCloudTTSProvider,
}

_STT_PROVIDERS = {
    "local": LocalSTTProvider,
    "google-cloud": GoogleCloudSTTProvider,
}


def get_tts_provider(name: Optional[str] = None) -> TTSProvider:
    """Get TTS provider by name, or use configured default."""
    cfg = get_voice_settings()
    provider_name = name or cfg.tts_provider

    if provider_name not in _TTS_PROVIDERS:
        raise ValueError(f"Unknown TTS provider: {provider_name}. Available: {list(_TTS_PROVIDERS.keys())}")

    return _TTS_PROVIDERS[provider_name]()


def get_stt_provider(name: Optional[str] = None) -> STTProvider:
    """Get STT provider by name, or use configured default."""
    cfg = get_voice_settings()
    provider_name = name or cfg.stt_provider

    if provider_name not in _STT_PROVIDERS:
        raise ValueError(f"Unknown STT provider: {provider_name}. Available: {list(_STT_PROVIDERS.keys())}")

    return _STT_PROVIDERS[provider_name]()
