"""
Voice Module — Extension & Customization Guide

How to add new TTS/STT providers, customize behavior, and integrate with other systems.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# 1. ADDING A NEW STT PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════

"""
Example: Add AWS Transcribe as STT Provider

Step 1: Extend STTProvider base class
"""

from backend.voice.base import STTProvider, AudioFormat
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class AWSTranscribeSTTProvider(STTProvider):
    """AWS Transcribe Speech-to-Text provider."""

    def __init__(self):
        self.cfg = get_voice_settings()
        if not self.cfg.aws_transcribe_enabled:
            raise RuntimeError("AWS Transcribe not enabled in config")
        
        # Initialize AWS client
        import boto3
        self.client = boto3.client(
            'transcribe',
            region_name=self.cfg.aws_region,
            aws_access_key_id=self.cfg.aws_access_key,
            aws_secret_access_key=self.cfg.aws_secret_key,
        )

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        audio_format: AudioFormat = AudioFormat.WAV,
        language: Optional[str] = None,
        hints: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """Transcribe using AWS Transcribe API."""
        import asyncio
        import uuid
        
        # Upload audio to S3
        s3_key = f"voice/{uuid.uuid4()}.wav"
        s3_url = self._upload_to_s3(audio_data, s3_key)
        
        # Submit transcription job
        job_name = f"sre-ai-{uuid.uuid4()}"
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._run_aws_transcribe(job_name, s3_url, language, hints),
        )
        
        # Clean up S3
        self._delete_from_s3(s3_key)
        
        return result

    def _run_aws_transcribe(
        self,
        job_name: str,
        s3_url: str,
        language: Optional[str],
        hints: Optional[list[str]],
    ) -> dict[str, str]:
        """Synchronous AWS Transcribe call."""
        
        # Start transcription job
        self.client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': s3_url},
            MediaFormat='wav',
            LanguageCode=language or 'en-US',
        )
        
        # Poll for completion
        while True:
            response = self.client.get_transcription_job(TranscriptionJobName=job_name)
            job = response['TranscriptionJob']
            
            if job['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                break
            
            import time
            time.sleep(1)
        
        if job['TranscriptionJobStatus'] == 'FAILED':
            raise RuntimeError(f"Transcription failed: {job.get('FailureReason')}")
        
        # Get transcript
        transcript_url = job['Transcript']['TranscriptFileUri']
        transcript_data = self._fetch_transcript(transcript_url)
        
        return {
            "text": transcript_data.get("results", {}).get("transcripts", [{}])[0].get("transcript", ""),
            "confidence": str(transcript_data.get("results", {}).get("transcripts", [{}])[0].get("confidence", 0)),
            "language": language or "en-US",
            "duration_seconds": job.get("MediaDurationSeconds", 0),
        }

    def _upload_to_s3(self, audio_data: bytes, key: str) -> str:
        """Upload audio to S3, return URL."""
        import boto3
        s3 = boto3.client('s3')
        s3.put_object(Bucket=self.cfg.aws_s3_bucket, Key=key, Body=audio_data)
        return f"s3://{self.cfg.aws_s3_bucket}/{key}"

    def _delete_from_s3(self, key: str) -> None:
        """Clean up S3 file."""
        import boto3
        s3 = boto3.client('s3')
        s3.delete_object(Bucket=self.cfg.aws_s3_bucket, Key=key)

    def _fetch_transcript(self, url: str) -> dict:
        """Fetch transcript JSON from S3."""
        import json
        import boto3
        s3 = boto3.client('s3')
        # Parse S3 URL and fetch object
        # Implementation depends on URL format

    def get_supported_languages(self) -> list[str]:
        return [
            "en-US", "es-ES", "fr-FR", "de-DE", "it-IT", "pt-BR",
            "ja-JP", "zh-CN", "ar-SA", "hi-IN"
        ]

    @property
    def name(self) -> str:
        return "aws-transcribe"

    @property
    def requires_api_key(self) -> bool:
        return True


# ═══════════════════════════════════════════════════════════════════════════════
# 2. STEP 2: REGISTER THE NEW PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════

"""
In backend/voice/providers.py, add to the provider registry:
"""

# _STT_PROVIDERS = {
#     "local": LocalSTTProvider,
#     "google-cloud": GoogleCloudSTTProvider,
#     "aws-transcribe": AWSTranscribeSTTProvider,  # Add here
# }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. STEP 3: ADD CONFIGURATION SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

"""
In backend/voice/config.py, add to VoiceSettings:
"""

# class VoiceSettings(BaseSettings):
#     # ... existing settings ...
#
#     # AWS Transcribe
#     aws_transcribe_enabled: bool = Field(default=False)
#     aws_region: str = Field(default="us-east-1")
#     aws_access_key: Optional[str] = Field(default=None)
#     aws_secret_key: Optional[str] = Field(default=None)
#     aws_s3_bucket: str = Field(default="sre-ai-voice-temp")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. STEP 4: USE IN CODE
# ═══════════════════════════════════════════════════════════════════════════════

"""
Enable via environment variables:
"""

# export VOICE_STT_PROVIDER=aws-transcribe
# export VOICE_AWS_TRANSCRIBE_ENABLED=true
# export VOICE_AWS_REGION=us-east-1
# export VOICE_AWS_ACCESS_KEY=...
# export VOICE_AWS_SECRET_KEY=...
# export VOICE_AWS_S3_BUCKET=my-voice-bucket


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ADDING A NEW TTS PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════

"""
Example: Add AWS Polly as TTS Provider
"""

from backend.voice.base import TTSProvider, VoiceGender, AudioFormat


class AWSPollyTTSProvider(TTSProvider):
    """AWS Polly Text-to-Speech provider."""

    def __init__(self):
        self.cfg = get_voice_settings()
        if not self.cfg.aws_polly_enabled:
            raise RuntimeError("AWS Polly not enabled in config")
        
        import boto3
        self.client = boto3.client(
            'polly',
            region_name=self.cfg.aws_region,
        )

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
        """Synthesize using AWS Polly API."""
        import asyncio
        
        loop = asyncio.get_event_loop()
        audio_bytes = await loop.run_in_executor(
            None,
            lambda: self._run_polly(text, language, gender, rate, pitch, output_format),
        )
        return audio_bytes

    def _run_polly(
        self,
        text: str,
        language: str,
        gender: VoiceGender,
        rate: float,
        pitch: float,
        output_format: AudioFormat,
    ) -> bytes:
        """Synchronous AWS Polly call."""
        
        # Map gender to Polly voice ID
        voice_id_map = {
            VoiceGender.MALE: "Matthew",
            VoiceGender.FEMALE: "Joanna",
            VoiceGender.NEUTRAL: "Joanna",
        }
        
        response = self.client.synthesize_speech(
            Text=text,
            OutputFormat='mp3' if output_format == AudioFormat.MP3 else 'ogg_vorbis',
            VoiceId=voice_id_map.get(gender, "Joanna"),
            LanguageCode=language,
        )
        
        return response['AudioStream'].read()

    def get_supported_languages(self) -> list[str]:
        return ["en-US", "es-ES", "fr-FR", "de-DE", "ja-JP", "pt-BR"]

    def get_supported_voices(self) -> list[dict[str, str]]:
        return [
            {"voice_id": "Matthew", "name": "Matthew", "gender": "male", "language": "en-US"},
            {"voice_id": "Joanna", "name": "Joanna", "gender": "female", "language": "en-US"},
        ]

    @property
    def name(self) -> str:
        return "aws-polly"

    @property
    def supports_streaming(self) -> bool:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 6. CUSTOM VOICE AGENT BEHAVIOR
# ═══════════════════════════════════════════════════════════════════════════════

"""
Create a specialized voice agent that does custom processing:
"""

from backend.voice.voice_agent import VoiceAgent


class IncidentVoiceAgent(VoiceAgent):
    """Custom voice agent for incident response."""

    async def _route_to_specialized_agent(self, text: str) -> str:
        """Route to specialized agent based on intent."""
        
        if any(keyword in text.lower() for keyword in ["incident", "alert", "fire", "active"]):
            # Route to incident-focused agent
            return "incident_focused_response"
        elif any(keyword in text.lower() for keyword in ["runbook", "how to", "procedure"]):
            # Route to runbook agent
            return "runbook_response"
        else:
            # Default to chat agent
            return "general_response"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SLACK INTEGRATION EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

"""
Integrate voice into Slack for on-call engineers:
"""

import asyncio
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackVoiceBot:
    """Slack bot for voice-based incident response."""

    def __init__(self, slack_token: str):
        self.client = WebClient(token=slack_token)
        self.voice_agent = VoiceAgent()

    async def handle_voice_message(self, user_id: str, file_url: str):
        """Handle voice file message from Slack."""
        
        # Download audio from Slack
        audio_bytes = await self._download_file(file_url)
        
        # Process through voice agent
        result = await self.voice_agent.execute({
            "audio_base64": base64.b64encode(audio_bytes).decode(),
            "audio_format": "wav",
            "session_id": user_id,
            "return_text": False,
        })
        
        # Upload response audio back to Slack
        audio_response = base64.b64decode(result["audio_base64"])
        
        try:
            self.client.files_upload_v2(
                channels=[user_id],
                file=audio_response,
                filename="response.mp3",
                title="SRE AI Response",
            )
        except SlackApiError as exc:
            logger.error(f"Failed to upload response: {exc}")

    async def _download_file(self, url: str) -> bytes:
        """Download file from Slack URL."""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content


# ═══════════════════════════════════════════════════════════════════════════════
# 8. PROMETHEUS METRICS FOR VOICE MODULE
# ═══════════════════════════════════════════════════════════════════════════════

"""
Add metrics to track voice module usage:
"""

from prometheus_client import Counter, Histogram, Gauge


voice_requests = Counter(
    "sre_ai_voice_requests_total",
    "Total voice requests",
    labelnames=["provider", "type"],
)

voice_duration = Histogram(
    "sre_ai_voice_duration_seconds",
    "Voice processing duration",
    labelnames=["component"],  # "stt", "llm", "tts"
)

voice_errors = Counter(
    "sre_ai_voice_errors_total",
    "Voice processing errors",
    labelnames=["component", "error_type"],
)

voice_confidence = Gauge(
    "sre_ai_voice_confidence",
    "STT confidence score (last request)",
)


# Usage in VoiceAgent:
"""
def run(self, payload):
    try:
        voice_requests.labels(provider=stt_provider.name, type="chat").inc()
        # ... process ...
    except Exception as exc:
        voice_errors.labels(component="stt", error_type=type(exc).__name__).inc()
        raise
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 9. TESTING CUSTOM PROVIDERS
# ═══════════════════════════════════════════════════════════════════════════════

"""
Unit test for custom provider:
"""

import pytest


class TestCustomSTTProvider:
    """Test custom STT provider."""

    @pytest.fixture
    def custom_provider(self):
        """Fixture to create provider."""
        return AWSTranscribeSTTProvider()

    @pytest.mark.asyncio
    async def test_custom_provider_transcribe(self, custom_provider, dummy_audio):
        """Test transcription with custom provider."""
        
        result = await custom_provider.transcribe(
            dummy_audio,
            audio_format=AudioFormat.WAV,
            language="en-US",
        )
        
        assert "text" in result
        assert "confidence" in result
        assert "language" in result
        assert result["text"] != ""

    def test_custom_provider_languages(self, custom_provider):
        """Test language support."""
        languages = custom_provider.get_supported_languages()
        assert "en-US" in languages
        assert len(languages) > 0

    def test_custom_provider_requires_api_key(self, custom_provider):
        """Test API key requirement."""
        assert custom_provider.requires_api_key is True


# ═══════════════════════════════════════════════════════════════════════════════
# 10. CHECKLIST: ADDING A NEW PROVIDER
# ═══════════════════════════════════════════════════════════════════════════════

"""
Checklist for adding new provider:

[ ] Create new provider class extending STTProvider or TTSProvider
[ ] Implement required abstract methods:
    - For STT: transcribe(), get_supported_languages(), name, requires_api_key
    - For TTS: synthesize(), get_supported_languages(), get_supported_voices(), name, supports_streaming
[ ] Add configuration settings to VoiceSettings (backend/voice/config.py)
[ ] Register provider in _STT_PROVIDERS or _TTS_PROVIDERS (backend/voice/providers.py)
[ ] Add unit tests (tests/unit/test_voice_custom_providers.py)
[ ] Add documentation to backend/voice/README.md
[ ] Test with example code
[ ] Add environment variables to .env.example
[ ] Update ARCHITECTURE.md with provider info

Performance guidelines:
- STT should complete in < 10 seconds for typical SRE audio (30-60 seconds)
- TTS should complete in < 3 seconds for typical SRE response (100-200 words)
- Implement async/await for I/O-bound operations
- Cache models or connections where applicable
- Log errors but fail gracefully with user-friendly messages
"""
