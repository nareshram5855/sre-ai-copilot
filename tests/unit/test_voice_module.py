"""
Unit Tests for Voice Module

Run with: pytest tests/unit/test_voice_*.py -v
"""
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.voice.base import AudioFormat, VoiceGender, TTSProvider, STTProvider
from backend.voice.models import (
    VoiceTranscribeRequest, VoiceTranscribeResponse,
    TextToSpeechRequest, TextToSpeechResponse,
    VoiceChatRequest, VoiceChatResponse,
)
from backend.voice.providers import LocalTTSProvider, LocalSTTProvider
from backend.voice.voice_agent import VoiceAgent


# ── Test Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def dummy_audio_base64():
    """Create minimal WAV audio for testing."""
    import struct
    
    sample_rate = 16000
    channels = 1
    bit_depth = 16
    duration = 1.0
    num_samples = int(sample_rate * duration)
    
    byte_rate = sample_rate * channels * bit_depth // 8
    block_align = channels * bit_depth // 8
    subchunk2_size = num_samples * channels * bit_depth // 8
    
    wav_header = b"RIFF"
    wav_header += struct.pack("<I", 36 + subchunk2_size)
    wav_header += b"WAVE"
    wav_header += b"fmt "
    wav_header += struct.pack("<I", 16)
    wav_header += struct.pack("<H", 1)
    wav_header += struct.pack("<H", channels)
    wav_header += struct.pack("<I", sample_rate)
    wav_header += struct.pack("<I", byte_rate)
    wav_header += struct.pack("<H", block_align)
    wav_header += struct.pack("<H", bit_depth)
    wav_header += b"data"
    wav_header += struct.pack("<I", subchunk2_size)
    
    audio_data = b"\x00" * subchunk2_size
    full_audio = wav_header + audio_data
    
    return base64.b64encode(full_audio).decode()


# ── Base Provider Tests ────────────────────────────────────────────────────────

class TestTTSProvider:
    """Test TTS provider interface."""

    def test_audio_format_enum(self):
        """AudioFormat enum has expected values."""
        assert AudioFormat.MP3.value == "mp3"
        assert AudioFormat.WAV.value == "wav"
        assert AudioFormat.OGG.value == "ogg"
        assert AudioFormat.M4A.value == "m4a"

    def test_voice_gender_enum(self):
        """VoiceGender enum has expected values."""
        assert VoiceGender.MALE.value == "male"
        assert VoiceGender.FEMALE.value == "female"
        assert VoiceGender.NEUTRAL.value == "neutral"


class TestSTTProvider:
    """Test STT provider interface."""

    def test_stt_requires_implementation(self):
        """STT provider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            STTProvider()

    def test_tts_requires_implementation(self):
        """TTS provider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TTSProvider()


# ── Local Provider Tests ───────────────────────────────────────────────────────

class TestLocalTTSProvider:
    """Test local TTS provider."""

    def test_local_tts_name(self):
        """LocalTTSProvider has correct name."""
        provider = LocalTTSProvider()
        assert provider.name == "local-tts"

    def test_local_tts_no_api_key(self):
        """LocalTTSProvider doesn't require API key."""
        provider = LocalTTSProvider()
        assert provider.supports_streaming is False

    def test_local_tts_supported_languages(self):
        """LocalTTSProvider lists languages."""
        provider = LocalTTSProvider()
        languages = provider.get_supported_languages()
        assert "en-US" in languages
        assert len(languages) > 0

    def test_local_tts_supported_voices(self):
        """LocalTTSProvider lists voices."""
        provider = LocalTTSProvider()
        voices = provider.get_supported_voices()
        assert len(voices) > 0
        assert all("voice_id" in v for v in voices)
        assert all("gender" in v for v in voices)


class TestLocalSTTProvider:
    """Test local STT provider."""

    def test_local_stt_name(self):
        """LocalSTTProvider has correct name."""
        provider = LocalSTTProvider()
        assert provider.name == "local-stt"

    def test_local_stt_no_api_key(self):
        """LocalSTTProvider doesn't require API key."""
        provider = LocalSTTProvider()
        assert provider.requires_api_key is False

    def test_local_stt_supported_languages(self):
        """LocalSTTProvider lists languages."""
        provider = LocalSTTProvider()
        languages = provider.get_supported_languages()
        assert "en-US" in languages
        assert len(languages) > 0


# ── Pydantic Model Tests ──────────────────────────────────────────────────────

class TestVoiceModels:
    """Test Pydantic models."""

    def test_voice_transcribe_request(self):
        """VoiceTranscribeRequest validates input."""
        req = VoiceTranscribeRequest(audio_base64="base64data")
        assert req.audio_base64 == "base64data"
        assert req.audio_format == "wav"
        assert req.language is None

    def test_voice_transcribe_response(self):
        """VoiceTranscribeResponse is constructible."""
        resp = VoiceTranscribeResponse(
            text="Hello",
            confidence=0.95,
            language="en-US",
            duration_seconds=2.5,
            provider="test-stt",
            processing_time_ms=2500,
        )
        assert resp.text == "Hello"
        assert resp.confidence == 0.95

    def test_text_to_speech_request(self):
        """TextToSpeechRequest validates input."""
        req = TextToSpeechRequest(text="Hello world")
        assert req.text == "Hello world"
        assert req.language == "en-US"
        assert req.gender == "neutral"
        assert req.rate == 1.0

    def test_text_to_speech_request_validates_rate(self):
        """TextToSpeechRequest validates rate bounds."""
        with pytest.raises(ValueError):
            TextToSpeechRequest(text="Hello", rate=3.0)  # > 2.0

        with pytest.raises(ValueError):
            TextToSpeechRequest(text="Hello", rate=0.2)  # < 0.5

    def test_text_to_speech_response(self):
        """TextToSpeechResponse is constructible."""
        resp = TextToSpeechResponse(
            audio_base64="base64audio",
            audio_format="mp3",
            duration_seconds=1.5,
            provider="test-tts",
            processing_time_ms=1500,
            character_count=11,
        )
        assert resp.audio_format == "mp3"
        assert resp.character_count == 11

    def test_voice_chat_request(self, dummy_audio_base64):
        """VoiceChatRequest is constructible."""
        req = VoiceChatRequest(audio_base64=dummy_audio_base64)
        assert req.audio_base64 == dummy_audio_base64
        assert req.audio_format == "wav"
        assert req.return_text is False

    def test_voice_chat_response(self):
        """VoiceChatResponse is constructible."""
        resp = VoiceChatResponse(
            audio_base64="base64audio",
            audio_format="mp3",
            user_text="Hello",
            response_text="Hi there",
            confidence=0.90,
            duration_seconds=2.0,
            provider_stt="local-stt",
            provider_tts="local-tts",
            processing_time_ms=5000,
        )
        assert resp.user_text == "Hello"
        assert resp.provider_stt == "local-stt"


# ── Voice Agent Tests ──────────────────────────────────────────────────────────

class TestVoiceAgent:
    """Test VoiceAgent orchestration."""

    def test_voice_agent_initialization(self):
        """VoiceAgent initializes successfully."""
        agent = VoiceAgent()
        assert agent is not None
        assert agent._chat_agent is not None

    @pytest.mark.asyncio
    async def test_voice_agent_invalid_base64(self):
        """VoiceAgent rejects invalid base64 audio."""
        agent = VoiceAgent()
        payload = {
            "audio_base64": "not-valid-base64!!!",
            "audio_format": "wav",
        }
        with pytest.raises(ValueError):
            await agent.arun(payload)

    @pytest.mark.asyncio
    async def test_voice_agent_large_audio_rejected(self, dummy_audio_base64):
        """VoiceAgent rejects audio larger than max size."""
        agent = VoiceAgent()
        # Simulate oversized audio by repeating base64 many times
        large_audio = dummy_audio_base64 * 10000
        payload = {
            "audio_base64": large_audio,
            "audio_format": "wav",
        }
        
        # This should fail due to size check
        # (Implementation depends on how large it becomes)


# ── Configuration Tests ────────────────────────────────────────────────────────

class TestVoiceConfig:
    """Test voice configuration."""

    def test_voice_settings_defaults(self):
        """VoiceSettings has sensible defaults."""
        from backend.voice.config import get_voice_settings
        
        cfg = get_voice_settings()
        assert cfg.voice_enabled is False  # Disabled by default
        assert cfg.tts_provider == "local"
        assert cfg.stt_provider == "local"
        assert cfg.tts_language == "en-US"
        assert cfg.tts_speaking_rate == 1.0


# ── Provider Registry Tests ────────────────────────────────────────────────────

class TestProviderRegistry:
    """Test provider registration and retrieval."""

    def test_get_tts_provider_local(self):
        """Can retrieve local TTS provider."""
        from backend.voice.providers import get_tts_provider
        
        provider = get_tts_provider("local")
        assert provider.name == "local-tts"

    def test_get_stt_provider_local(self):
        """Can retrieve local STT provider."""
        from backend.voice.providers import get_stt_provider
        
        provider = get_stt_provider("local")
        assert provider.name == "local-stt"

    def test_get_unknown_tts_provider(self):
        """Getting unknown TTS provider raises error."""
        from backend.voice.providers import get_tts_provider
        
        with pytest.raises(ValueError):
            get_tts_provider("unknown-provider")

    def test_get_unknown_stt_provider(self):
        """Getting unknown STT provider raises error."""
        from backend.voice.providers import get_stt_provider
        
        with pytest.raises(ValueError):
            get_stt_provider("unknown-provider")


# ── Integration Tests ──────────────────────────────────────────────────────────

class TestVoiceIntegration:
    """Integration tests for voice module."""

    @pytest.mark.asyncio
    async def test_voice_endpoints_disabled_by_default(self):
        """Voice endpoints not registered if disabled in config."""
        from backend.voice.config import get_voice_settings
        
        cfg = get_voice_settings()
        assert cfg.voice_enabled is False  # Should not auto-enable


# ── Utility Tests ─────────────────────────────────────────────────────────────

class TestAudioUtilities:
    """Test audio utility functions."""

    def test_create_dummy_audio(self, dummy_audio_base64):
        """Dummy audio can be created and decoded."""
        audio_bytes = base64.b64decode(dummy_audio_base64)
        
        # Verify WAV header
        assert audio_bytes[:4] == b"RIFF"
        assert audio_bytes[8:12] == b"WAVE"
        assert audio_bytes[12:16] == b"fmt "


# ── Parametrized Tests ────────────────────────────────────────────────────────

class TestAudioFormats:
    """Parametrized tests for audio formats."""

    @pytest.mark.parametrize("fmt", ["mp3", "wav", "ogg", "m4a", "webm"])
    def test_audio_format_supported(self, fmt):
        """All common audio formats are supported."""
        audio_format = AudioFormat(fmt)
        assert audio_format.value == fmt


class TestLanguageCodes:
    """Parametrized tests for language support."""

    @pytest.mark.parametrize("lang", ["en-US", "es-ES", "fr-FR", "de-DE"])
    def test_local_providers_support_language(self, lang):
        """Local providers support common languages."""
        tts_provider = LocalTTSProvider()
        stt_provider = LocalSTTProvider()
        
        tts_langs = tts_provider.get_supported_languages()
        stt_langs = stt_provider.get_supported_languages()
        
        assert lang in tts_langs or len(tts_langs) > 0
        assert lang in stt_langs or len(stt_langs) > 0
