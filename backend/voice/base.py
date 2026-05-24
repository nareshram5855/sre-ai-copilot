"""
Abstract base classes for Text-to-Speech (TTS) and Speech-to-Text (STT) providers.

Providers should implement these interfaces to be compatible with the voice module.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class AudioFormat(str, Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    M4A = "m4a"
    WEBM = "webm"


class VoiceGender(str, Enum):
    """Voice gender options for TTS."""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class TTSProvider(ABC):
    """
    Abstract base for Text-to-Speech providers.
    
    Implementers:
      - GoogleCloudTTS
      - AzureTTS
      - OllamaTTS (fallback, local)
    """

    @abstractmethod
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
        Convert text to speech.
        
        Args:
            text: Text to synthesize
            language: BCP-47 language code (e.g., "en-US", "es-ES")
            gender: Preferred voice gender
            rate: Speaking rate (0.5 = half speed, 2.0 = double speed)
            pitch: Pitch adjustment in semitones (-20 to +20)
            output_format: Audio output format
            
        Returns:
            Audio bytes in the specified format
            
        Raises:
            ValueError: If text is empty or too long
            RuntimeError: If synthesis fails (network, auth, etc.)
        """
        ...

    @abstractmethod
    def get_supported_languages(self) -> list[str]:
        """Return list of supported BCP-47 language codes."""
        ...

    @abstractmethod
    def get_supported_voices(self) -> list[dict[str, str]]:
        """
        Return available voices.
        
        Returns:
            List of dicts with: {"voice_id": str, "name": str, "gender": str, "language": str}
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'google-cloud', 'azure', 'ollama')."""
        ...

    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming audio output."""
        ...


class STTProvider(ABC):
    """
    Abstract base for Speech-to-Text providers.
    
    Implementers:
      - GoogleCloudSTT
      - AzureSTT
      - WebSpeechAPI (browser-side)
      - WhisperLocal (local Ollama/whisper.cpp)
    """

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        *,
        audio_format: AudioFormat = AudioFormat.WAV,
        language: Optional[str] = None,
        hints: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """
        Convert speech to text.
        
        Args:
            audio_data: Audio bytes
            audio_format: Audio format of the input
            language: BCP-47 language code (auto-detect if None)
            hints: Domain-specific terms to boost recognition (e.g., Kubernetes terms)
            
        Returns:
            Dict with keys:
              - "text": Transcribed text
              - "confidence": Confidence score (0.0-1.0)
              - "language": Detected language code
              - "duration_seconds": Audio duration
              
        Raises:
            ValueError: If audio_data is empty or invalid
            RuntimeError: If transcription fails
        """
        ...

    @abstractmethod
    def get_supported_languages(self) -> list[str]:
        """Return list of supported BCP-47 language codes."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'google-cloud', 'azure', 'whisper')."""
        ...

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider requires an API key to function."""
        ...
