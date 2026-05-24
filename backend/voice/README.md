# Voice Module — Plugin Architecture Documentation

> **Status:** Production-Ready Plugin  
> **Impact on Existing Code:** ZERO - Completely decoupled  
> **Installation:** Optional, enable via config  
> **Version:** 0.1.0  

---

## Overview

The Voice Module is a **completely separate, opt-in plugin** for the SRE AI Copilot that adds speech-to-text and text-to-speech capabilities.

### Key Design Principles

1. **Zero Impact** — No modifications to existing agents, routers, or core logic
2. **Pluggable** — Enable/disable via configuration
3. **Provider-Agnostic** — Swap TTS/STT providers without code changes
4. **Modular** — Each component (STT, TTS, Agent, Router) is independent
5. **Extensible** — Easy to add new providers (Azure, AWS Polly, etc.)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Router                           │
│                                                             │
│  POST /api/v1/voice/chat       ← Voice chat endpoint       │
│  POST /api/v1/voice/transcribe ← STT-only endpoint         │
│  POST /api/v1/voice/synthesize ← TTS-only endpoint         │
│  GET  /api/v1/voice/health     ← Status endpoint           │
└─────────┬───────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Voice Agent                              │
│  (orchestrates: STT → Chat Agent → TTS)                    │
└────┬────────────────────────────────────────────────────────┘
     │
     ├─────────────┬──────────────┬───────────────┐
     ▼             ▼              ▼               ▼
┌─────────┐ ┌──────────┐   ┌──────────┐   ┌────────────┐
│ STT     │ │ Chat     │   │ Base     │   │ Config     │
│Provider │ │ Agent    │   │ Classes  │   │ (Settings) │
│         │ │          │   │          │   │            │
│-local   │ │-inherits │   │-TTS      │   │-voice_     │
│-google  │ │ BaseAgent│   │-STT      │   │  enabled   │
│-azure   │ │-uses LLM │   │-abstract │   │-providers  │
│         │ │-routing  │   │          │   │-languages  │
└─────────┘ └──────────┘   └──────────┘   └────────────┘
```

---

## File Structure

```
backend/voice/
├── __init__.py          # Module exports
├── base.py              # Abstract TTSProvider, STTProvider classes
├── config.py            # VoiceSettings configuration
├── models.py            # Pydantic request/response models
├── providers.py         # Concrete implementations (Local, Google Cloud, Azure)
├── voice_agent.py       # VoiceAgent (orchestrator)
├── router.py            # FastAPI endpoints
└── README.md            # This file
```

---

## Installation & Setup

### 1. Enable Voice Module (Optional)

By default, voice is **disabled**. To enable:

**Option A: Environment Variables**
```bash
export VOICE_VOICE_ENABLED=true
export VOICE_STT_PROVIDER=local
export VOICE_TTS_PROVIDER=local
```

**Option B: `.env` File**
```env
VOICE_VOICE_ENABLED=true
VOICE_STT_PROVIDER=local
VOICE_TTS_PROVIDER=local
VOICE_TTS_AUDIO_FORMAT=mp3
VOICE_TTS_LANGUAGE=en-US
```

### 2. Install Dependencies

**Local (default — recommended for SRE use):**
```bash
pip install openai-whisper pyttsx3
# On macOS: brew install espeak
```

**Google Cloud (if using Google providers):**
```bash
pip install google-cloud-texttospeech google-cloud-speech
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

**Azure (if using Azure providers):**
```bash
pip install azure-cognitiveservices-speech
export AZURE_SPEECH_KEY=your_key
export AZURE_SPEECH_REGION=eastus
```

### 3. Register Router in `backend/main.py`

The voice router is **optional**. It's only registered if enabled in config:

```python
# In backend/main.py (no changes needed if already present)

from backend.voice.router import router as voice_router
from backend.voice.config import get_voice_settings

# ... existing code ...

if get_voice_settings().voice_enabled:
    app.include_router(voice_router)
    logger.info("Voice module enabled")
```

This is **already included** in the provided `main.py`. No edits needed.

---

## Configuration Reference

All settings are **optional**. Defaults provided.

### Global

| Env Var | Default | Description |
|---------|---------|-------------|
| `VOICE_VOICE_ENABLED` | `false` | Enable/disable entire module |

### STT (Speech-to-Text)

| Env Var | Default | Description |
|---------|---------|-------------|
| `VOICE_STT_PROVIDER` | `local` | Provider: `local`, `google-cloud`, `azure` |
| `VOICE_STT_LOCAL_MODEL` | `whisper-base` | Whisper model size |
| `VOICE_STT_LANGUAGE` | `en-US` | Default language for transcription |
| `VOICE_GOOGLE_CLOUD_STT_ENABLED` | `false` | Enable Google Cloud STT |
| `VOICE_GOOGLE_CLOUD_CREDENTIALS_PATH` | — | Path to credentials.json |
| `VOICE_AZURE_STT_ENABLED` | `false` | Enable Azure STT |
| `VOICE_AZURE_SPEECH_KEY` | — | Azure API key |
| `VOICE_AZURE_SPEECH_REGION` | `eastus` | Azure region |

### TTS (Text-to-Speech)

| Env Var | Default | Description |
|---------|---------|-------------|
| `VOICE_TTS_PROVIDER` | `local` | Provider: `local`, `google-cloud`, `azure` |
| `VOICE_TTS_LOCAL_BACKEND` | `pyttsx3` | Local backend: `pyttsx3`, `espeak`, `gtts` |
| `VOICE_TTS_LANGUAGE` | `en-US` | Default language |
| `VOICE_TTS_GENDER` | `neutral` | Default voice: `male`, `female`, `neutral` |
| `VOICE_TTS_SPEAKING_RATE` | `1.0` | Speed: 0.5-2.0 |
| `VOICE_TTS_AUDIO_FORMAT` | `mp3` | Output format: `mp3`, `wav`, `ogg`, `m4a`, `webm` |
| `VOICE_GOOGLE_CLOUD_TTS_ENABLED` | `false` | Enable Google Cloud TTS |
| `VOICE_AZURE_TTS_ENABLED` | `false` | Enable Azure TTS |

### Voice Chat Behavior

| Env Var | Default | Description |
|---------|---------|-------------|
| `VOICE_VOICE_SESSION_TTL_SECONDS` | `3600` | Session timeout |
| `VOICE_VOICE_MAX_AUDIO_SIZE_BYTES` | `52_428_800` | Max upload: 50 MB |
| `VOICE_VOICE_MAX_AUDIO_DURATION_SECONDS` | `600` | Max duration: 10 min |
| `VOICE_VOICE_DEBUG_RETURN_TEXT` | `false` | Return transcription/LLM response for debugging |

---

## API Endpoints

### 1. Voice Chat (Full Round-Trip)

**Request:**
```bash
curl -X POST http://localhost:8080/api/v1/voice/chat \
  -H "Content-Type: application/json" \
  -d '{
    "audio_base64": "...",
    "audio_format": "wav",
    "language": "en-US",
    "return_text": true
  }'
```

**Response:**
```json
{
  "audio_base64": "...",
  "audio_format": "mp3",
  "user_text": "What is the OOM incident?",
  "response_text": "The OOM incident occurred in the demo namespace...",
  "confidence": 0.95,
  "duration_seconds": 4.2,
  "provider_stt": "local-stt",
  "provider_tts": "local-tts",
  "processing_time_ms": 8432
}
```

**Latency (Local):**
- STT (Whisper): 2-5s per 30s audio
- LLM (Chat): 1-3s
- TTS (pyttsx3): 0.5-2s
- **Total: ~4-10s**

---

### 2. Transcribe Only (STT)

**Request:**
```bash
curl -X POST http://localhost:8080/api/v1/voice/transcribe \
  -H "Content-Type: application/json" \
  -d '{
    "audio_base64": "...",
    "audio_format": "wav",
    "language": "en-US"
  }'
```

**Response:**
```json
{
  "text": "What is the incident status?",
  "confidence": 0.96,
  "language": "en-US",
  "duration_seconds": 3.2,
  "provider": "local-stt",
  "processing_time_ms": 3100
}
```

---

### 3. Synthesize Only (TTS)

**Request:**
```bash
curl -X POST http://localhost:8080/api/v1/voice/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The incident has been resolved",
    "language": "en-US",
    "gender": "neutral",
    "rate": 1.0,
    "audio_format": "mp3"
  }'
```

**Response:**
```json
{
  "audio_base64": "...",
  "audio_format": "mp3",
  "duration_seconds": 2.1,
  "provider": "local-tts",
  "processing_time_ms": 820,
  "character_count": 38
}
```

---

### 4. Health Check

**Request:**
```bash
curl http://localhost:8080/api/v1/voice/health
```

**Response:**
```json
{
  "enabled": true,
  "tts_providers": [
    {
      "name": "local-tts",
      "type": "tts",
      "enabled": true,
      "requires_api_key": false,
      "supported_languages": ["en-US", "es-ES", "fr-FR"]
    }
  ],
  "stt_providers": [
    {
      "name": "local-stt",
      "type": "stt",
      "enabled": true,
      "requires_api_key": false,
      "supported_languages": ["en-US", "es-ES", "fr-FR"]
    }
  ],
  "default_tts": "local",
  "default_stt": "local"
}
```

---

### 5. Supported Languages

**Request:**
```bash
curl http://localhost:8080/api/v1/voice/languages
```

**Response:**
```json
{
  "tts": ["en-US", "es-ES", "fr-FR", "de-DE"],
  "stt": ["en-US", "es-ES", "fr-FR", "de-DE"]
}
```

---

## Adding New Providers

### Create a New STT Provider

1. **Extend `STTProvider`:**

```python
# backend/voice/providers.py

class MyCustomSTTProvider(STTProvider):
    
    async def transcribe(
        self,
        audio_data: bytes,
        *,
        audio_format: AudioFormat = AudioFormat.WAV,
        language: Optional[str] = None,
        hints: Optional[list[str]] = None,
    ) -> dict[str, str]:
        # Your implementation
        return {
            "text": transcribed_text,
            "confidence": 0.95,
            "language": language or "en-US",
            "duration_seconds": duration,
        }
    
    def get_supported_languages(self) -> list[str]:
        return ["en-US", "es-ES"]
    
    @property
    def name(self) -> str:
        return "my-custom-stt"
    
    @property
    def requires_api_key(self) -> bool:
        return True
```

2. **Register in provider registry:**

```python
# backend/voice/providers.py

_STT_PROVIDERS = {
    "local": LocalSTTProvider,
    "google-cloud": GoogleCloudSTTProvider,
    "my-custom": MyCustomSTTProvider,  # Add here
}
```

3. **Use via config:**

```bash
export VOICE_STT_PROVIDER=my-custom
```

---

## Testing

### Unit Test Example

```python
# tests/unit/test_voice_agent.py

import pytest
from backend.voice.voice_agent import VoiceAgent
from backend.voice.providers import LocalSTTProvider, LocalTTSProvider

@pytest.mark.asyncio
async def test_voice_chat_basic():
    agent = VoiceAgent()
    
    # Create dummy audio (WAV header)
    dummy_audio = b"RIFF" + b"\x00" * 100
    payload = {
        "audio_base64": base64.b64encode(dummy_audio).decode(),
        "audio_format": "wav",
        "language": "en-US",
        "return_text": True,
    }
    
    result = agent.execute(payload)
    
    assert "audio_base64" in result
    assert "user_text" in result
    assert "response_text" in result
    assert result["provider_stt"] == "local-stt"
    assert result["provider_tts"] == "local-tts"
```

---

## Troubleshooting

### "Voice module unavailable"

**Check:** Is voice enabled in config?
```bash
echo $VOICE_VOICE_ENABLED  # Should be true
```

### "STT transcription failed"

**Check 1:** Is Whisper installed?
```bash
pip install openai-whisper
```

**Check 2:** Is the Whisper model downloaded?
```bash
python -c "import whisper; whisper.load_model('base')"
```

### "TTS synthesis failed"

**Check 1:** Is pyttsx3 installed?
```bash
pip install pyttsx3
```

**Check 2:** On Linux, do you have espeak installed?
```bash
sudo apt-get install espeak
```

### Audio quality is poor

**TTS:** Adjust `VOICE_TTS_SPEAKING_RATE` (lower = clearer, slower)
```bash
export VOICE_TTS_SPEAKING_RATE=0.9
```

**STT:** Use larger Whisper model
```bash
export VOICE_STT_LOCAL_MODEL=whisper-medium
```

---

## Performance Notes

### Local Latency (Typical)

| Component | Time | Notes |
|-----------|------|-------|
| STT (Whisper) | 2-5s | Per 30s audio; depends on model size |
| LLM Chat | 1-3s | With Mistral 7B local |
| TTS (pyttsx3) | 0.5-2s | Depends on text length |
| **Total** | ~4-10s | For typical SRE query |

### Optimization Tips

1. **Faster STT:** Use smaller Whisper model
   ```bash
   export VOICE_STT_LOCAL_MODEL=whisper-tiny
   ```

2. **Faster TTS:** Use system TTS backend
   ```bash
   # macOS native: /usr/bin/say
   # Linux: espeak
   ```

3. **Preload Models:** Voice Agent caches models on first use

---

## Security & Privacy

✅ **Local-First:** By default, all audio processing stays on-device
✅ **No Logging:** Audio content never logged; only metadata (size, duration, format)
✅ **Sanitization:** Payload sanitized before external LLM calls (existing ChatAgent behavior)

### If Using Cloud Providers

⚠️ Set `VOICE_GOOGLE_CLOUD_STT_ENABLED=true` or `VOICE_AZURE_STT_ENABLED=true` only after:
- Reviewing data classification policy with security team
- Ensuring credentials are properly rotated
- Auditing external calls

---

## Integration Examples

### Slack Bot

```python
# backends/integrations/slack_voice.py

from backend.voice.router import voice_chat
from slack_sdk import WebClient

async def handle_slack_voice_message(user_id: str, audio_url: str):
    # Download audio from Slack
    audio_bytes = download_from_slack(audio_url)
    
    # Convert to chat
    result = await voice_chat(VoiceChatRequest(
        audio_base64=base64.b64encode(audio_bytes).decode(),
        audio_format="wav",
        session_id=user_id,
    ))
    
    # Reply with voice
    slack_client = WebClient(token=slack_token)
    slack_client.files_upload(
        channels=user_id,
        file=base64.b64decode(result.audio_base64),
        filename="response.mp3",
    )
```

### iOS App

```swift
// iOS app → calls /api/v1/voice/chat endpoint

import AVFoundation

let audioData = try AVAudioFile(forReading: audioURL)
let base64Audio = audioData.toBase64()

let request = VoiceChatRequest(
    audio_base64: base64Audio,
    audio_format: "wav",
    language: "en-US"
)

let response = try await APIClient.post("/api/v1/voice/chat", body: request)
// Play response audio...
```

---

## Future Enhancements

- [ ] Streaming audio input/output (WebSocket)
- [ ] Multi-language conversation switching
- [ ] Voice biometrics for auth
- [ ] Audio quality metrics (MOS scoring)
- [ ] Custom voice training
- [ ] Offline LLM + audio models (no internet required)

---

## Support

For issues or questions:

1. Check `/backend/voice/README.md` (this file)
2. Review logs: `backend/voice/providers.py` (debug logs)
3. Test endpoints manually: See API Endpoints section
4. Verify config: `get_voice_settings()` from Python shell

---

**Version:** 0.1.0  
**Last Updated:** 2026-05-24  
**Maintainer:** SRE AI Team
