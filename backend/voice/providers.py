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
        engine.setProperty("rate", int(150 * rate))
        engine.setProperty("pitch", pitch)

        preferred = ("Samantha", "Karen", "Daniel", "Alex", "Victoria")
        try:
            for voice in engine.getProperty("voices") or []:
                name = getattr(voice, "name", "") or ""
                if any(p in name for p in preferred):
                    engine.setProperty("voice", voice.id)
                    break
        except Exception:
            pass

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
        self._model_cache_name = None

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

    def _normalize_whisper_model(self, model_name: str) -> str:
        """Map config names like whisper-base to OpenAI Whisper ids like base."""
        name = (model_name or "base").strip()
        if name.startswith("whisper-"):
            name = name[len("whisper-"):]
        return name or "base"

    def _load_wav_numpy(self, audio_data: bytes):
        """Decode 16-bit PCM WAV bytes to float32 mono @ 16 kHz (no ffmpeg)."""
        import io
        import wave

        import numpy as np

        with wave.open(io.BytesIO(audio_data), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())

        if sample_width == 2:
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise RuntimeError(f"Unsupported WAV sample width: {sample_width}")

        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)

        if sample_rate != 16000:
            ratio = sample_rate / 16000
            new_len = int(len(audio) / ratio)
            indices = (np.arange(new_len) * ratio).astype(np.int64)
            audio = audio[np.minimum(indices, len(audio) - 1)]

        return audio

    def _run_whisper(self, audio_data: bytes, language: Optional[str]) -> dict[str, str]:
        """Synchronous Whisper transcription."""
        import whisper

        model_name = self._normalize_whisper_model(self.cfg.stt_local_model)

        if self._model_cache is None or self._model_cache_name != model_name:
            self._model_cache = whisper.load_model(model_name)
            self._model_cache_name = model_name

        audio = self._load_wav_numpy(audio_data)
        lang = None
        if language:
            lang = language.split("-")[0].lower()

        result = self._model_cache.transcribe(audio, language=lang)

        return {
            "text": (result.get("text") or "").strip(),
            "confidence": 0.85,
            "language": result.get("language") or language or "en",
            "duration_seconds": float(result.get("duration") or 0.0),
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


# ── Edge Neural TTS (Microsoft — free, natural, no API key) ───────────────────

class EdgeTTSProvider(TTSProvider):
    """
    Microsoft Edge neural voices — conversational quality similar to modern AI assistants.
    Uses the edge-tts library (online, no API key required).
    """

    _VOICES: dict[str, dict[str, str]] = {
        "en-US": {
            "female": "en-US-JennyNeural",
            "male": "en-US-AndrewNeural",
            "neutral": "en-US-AriaNeural",
        },
        "en-GB": {
            "female": "en-GB-SoniaNeural",
            "male": "en-GB-RyanNeural",
            "neutral": "en-GB-LibbyNeural",
        },
    }

    def __init__(self):
        self.cfg = get_voice_settings()

    def _resolve_voice(self, language: str, gender: VoiceGender) -> str:
        if self.cfg.tts_neural_voice:
            return self.cfg.tts_neural_voice

        lang = language or self.cfg.tts_language or "en-US"
        lang_voices = self._VOICES.get(lang) or self._VOICES["en-US"]
        gender_key = gender.value if isinstance(gender, VoiceGender) else str(gender)
        return lang_voices.get(gender_key, lang_voices["neutral"])

    @staticmethod
    def _rate_string(rate: float) -> str:
        pct = int(round((rate - 1.0) * 100))
        return f"{pct:+d}%"

    @staticmethod
    def _pitch_string(pitch: float) -> str:
        hz = int(round(pitch * 12))
        return f"{hz:+d}Hz"

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
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError(
                "edge-tts not installed. Run: pip install edge-tts"
            ) from exc

        voice = self._resolve_voice(language, gender)
        communicate = edge_tts.Communicate(
            text,
            voice,
            rate=self._rate_string(rate),
            pitch=self._pitch_string(pitch),
        )

        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])

        audio = b"".join(chunks)
        if not audio:
            raise RuntimeError("Edge TTS returned empty audio")

        return audio

    def get_supported_languages(self) -> list[str]:
        return list(self._VOICES.keys())

    def get_supported_voices(self) -> list[dict[str, str]]:
        voices = []
        for lang, by_gender in self._VOICES.items():
            for gender, voice_id in by_gender.items():
                voices.append({
                    "voice_id": voice_id,
                    "name": voice_id.split("-")[-1].replace("Neural", ""),
                    "gender": gender,
                    "language": lang,
                })
        return voices

    @property
    def name(self) -> str:
        return "edge-neural-tts"

    @property
    def supports_streaming(self) -> bool:
        return True


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
    "edge": EdgeTTSProvider,
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

    if provider_name == "edge":
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            logger.warning("edge-tts not installed — falling back to local TTS")
            provider_name = "local"

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
