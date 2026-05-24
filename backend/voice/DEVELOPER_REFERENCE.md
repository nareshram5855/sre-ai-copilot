# Voice Module — Developer Reference Card

Quick lookup guide for developers using or extending the voice module.

---

## 📋 Quick Reference

### Import Voice Module

```python
from backend.voice.config import get_voice_settings
from backend.voice.providers import get_tts_provider, get_stt_provider
from backend.voice.voice_agent import VoiceAgent
from backend.voice.models import VoiceTranscribeRequest, TextToSpeechRequest
```

### Check If Enabled

```python
cfg = get_voice_settings()
if cfg.voice_enabled:
    # Voice module is ready
    pass
```

### Get Providers

```python
# Get configured providers
tts = get_tts_provider()  # Uses VOICE_TTS_PROVIDER setting
stt = get_stt_provider()  # Uses VOICE_STT_PROVIDER setting

# Or get specific provider
tts = get_tts_provider("google-cloud")
stt = get_stt_provider("aws-transcribe")
```

### Use Voice Agent

```python
agent = VoiceAgent()

# Execute voice chat workflow
result = agent.execute({
    "audio_base64": base64_encoded_audio,
    "audio_format": "wav",
    "language": "en-US",
    "return_text": True,  # Include transcription for debugging
})

print(f"User said: {result['user_text']}")
print(f"AI said: {result['response_text']}")
print(f"Confidence: {result['confidence']}")
print(f"Processing time: {result['processing_time_ms']}ms")
```

---

## 🔧 Common Tasks

### Transcribe Audio Only

```python
stt = get_stt_provider()
result = await stt.transcribe(
    audio_bytes,
    audio_format=AudioFormat.WAV,
    language="en-US",
    hints=["Kubernetes", "pod", "incident"]  # Domain keywords
)
# Returns: {"text": "...", "confidence": 0.95, "language": "en-US", ...}
```

### Synthesize Text Only

```python
tts = get_tts_provider()
audio_bytes = await tts.synthesize(
    "The incident has been resolved",
    language="en-US",
    gender=VoiceGender.NEUTRAL,
    rate=1.0,
    output_format=AudioFormat.MP3,
)
```

### Check Provider Availability

```python
stt = get_stt_provider()
print(f"Provider: {stt.name}")
print(f"Languages: {stt.get_supported_languages()}")
print(f"Requires API key: {stt.requires_api_key}")

tts = get_tts_provider()
print(f"Provider: {tts.name}")
print(f"Supports streaming: {tts.supports_streaming}")
print(f"Voices: {tts.get_supported_voices()}")
```

### Handle Errors Gracefully

```python
try:
    result = await stt.transcribe(audio_bytes)
except ValueError as e:
    logger.error(f"Invalid audio: {e}")
except RuntimeError as e:
    logger.error(f"STT service failed: {e}")
    # Optionally fall back to another provider
    fallback_stt = get_stt_provider("google-cloud")
```

---

## 📡 API Endpoints Cheat Sheet

### Voice Chat (Full Round-Trip)

```bash
curl -X POST http://localhost:8080/api/v1/voice/chat \
  -H "Content-Type: application/json" \
  -d '{
    "audio_base64": "...",
    "audio_format": "wav",
    "language": "en-US",
    "session_id": "user123",
    "return_text": true
  }'
```

### Transcribe Only

```bash
curl -X POST http://localhost:8080/api/v1/voice/transcribe \
  -d '{"audio_base64": "...", "audio_format": "wav"}'
```

### Synthesize Only

```bash
curl -X POST http://localhost:8080/api/v1/voice/synthesize \
  -d '{
    "text": "Hello world",
    "audio_format": "mp3",
    "gender": "neutral",
    "rate": 1.0
  }'
```

### Health Status

```bash
curl http://localhost:8080/api/v1/voice/health | jq
```

### Supported Languages

```bash
curl http://localhost:8080/api/v1/voice/languages | jq
```

---

## 🔐 Configuration Cheat Sheet

### Enable/Disable

```bash
VOICE_VOICE_ENABLED=true              # Enable voice module
VOICE_VOICE_ENABLED=false             # Disable (default)
```

### Select Providers

```bash
# STT Provider (local | google-cloud | azure)
VOICE_STT_PROVIDER=local

# TTS Provider (local | google-cloud | azure)
VOICE_TTS_PROVIDER=local
```

### Local Configuration

```bash
VOICE_STT_LOCAL_MODEL=whisper-base    # STT model size
VOICE_TTS_LOCAL_BACKEND=pyttsx3       # TTS backend
VOICE_TTS_SPEAKING_RATE=1.0           # Speed (0.5-2.0)
VOICE_TTS_GENDER=neutral              # Voice gender
VOICE_TTS_AUDIO_FORMAT=mp3            # Output format
```

### Cloud Provider Keys

```bash
# Google Cloud
VOICE_GOOGLE_CLOUD_CREDENTIALS_PATH=/path/to/credentials.json

# Azure
VOICE_AZURE_SPEECH_KEY=your_key
VOICE_AZURE_SPEECH_REGION=eastus
```

### Limits

```bash
VOICE_VOICE_MAX_AUDIO_SIZE_BYTES=52428800    # 50 MB
VOICE_VOICE_MAX_AUDIO_DURATION_SECONDS=600   # 10 min
VOICE_VOICE_SESSION_TTL_SECONDS=3600         # 1 hour
```

---

## 🧪 Testing Quick Reference

### Run Unit Tests

```bash
# All voice tests
pytest tests/unit/test_voice_module.py -v

# Specific test class
pytest tests/unit/test_voice_module.py::TestVoiceAgent -v

# With coverage
pytest tests/unit/test_voice_module.py --cov=backend.voice
```

### Run Examples

```bash
# All examples (requires running backend)
python backend/voice/examples.py

# Or test individual endpoints
python -c "
import asyncio
from backend.voice.examples import example_health
asyncio.run(example_health())
"
```

### Manual Testing

```bash
# Test health endpoint
curl http://localhost:8080/api/v1/voice/health

# Test with httpie (prettier)
http GET http://localhost:8080/api/v1/voice/health

# Test with full debug output
curl -v http://localhost:8080/api/v1/voice/health
```

---

## 📚 Module Structure

```
backend/voice/
├── __init__.py           # Module exports
├── base.py               # Abstract classes: TTSProvider, STTProvider
├── config.py             # VoiceSettings (all configuration)
├── models.py             # Pydantic: VoiceTranscribeRequest, etc.
├── providers.py          # Implementations: Local, Google, Azure
├── voice_agent.py        # VoiceAgent orchestrator
├── router.py             # FastAPI endpoints (/api/v1/voice/*)
├── examples.py           # 5 working code examples
├── README.md             # Full documentation
├── QUICKSTART.md         # 5-minute setup
├── EXTENSION_GUIDE.md    # How to add providers
├── IMPLEMENTATION_SUMMARY.md # What was created
└── .env.example          # Configuration presets
```

---

## 🎯 Common Customizations

### Add Domain Hints for SRE Terms

```python
# In VoiceSettings or per-request
domain_hints = [
    "Kubernetes", "pod", "deployment", "service",
    "Prometheus", "alert", "incident", "runbook",
    "kubectl", "helm", "ArgoCD", "Grafana",
]

result = await stt.transcribe(
    audio_bytes,
    hints=domain_hints
)
```

### Create Custom Voice Agent

```python
from backend.voice.voice_agent import VoiceAgent

class CustomVoiceAgent(VoiceAgent):
    def run(self, payload: dict) -> dict:
        # Your custom logic
        result = super().run(payload)
        
        # Post-process result
        result["custom_field"] = "custom_value"
        return result
```

### Create Custom TTS Provider

```python
from backend.voice.base import TTSProvider

class MyTTSProvider(TTSProvider):
    async def synthesize(self, text, **kwargs) -> bytes:
        # Your API call here
        pass
    
    def get_supported_languages(self) -> list[str]:
        return ["en-US", "es-ES"]
    
    @property
    def name(self) -> str:
        return "my-provider"
    
    @property
    def supports_streaming(self) -> bool:
        return False

# Register: _TTS_PROVIDERS["my-provider"] = MyTTSProvider
```

---

## 🐛 Debugging

### Enable Debug Output

```bash
export VOICE_VOICE_DEBUG_RETURN_TEXT=true    # Return text fields in responses
export LOG_LEVEL=DEBUG                       # Enable debug logging
```

### Check Configuration

```python
from backend.voice.config import get_voice_settings

cfg = get_voice_settings()
print(f"Enabled: {cfg.voice_enabled}")
print(f"STT Provider: {cfg.stt_provider}")
print(f"TTS Provider: {cfg.tts_provider}")
print(f"Language: {cfg.tts_language}")
```

### Verify Provider

```python
from backend.voice.providers import get_stt_provider

try:
    stt = get_stt_provider()
    print(f"✓ {stt.name} ready")
    print(f"  Languages: {stt.get_supported_languages()}")
except Exception as e:
    print(f"✗ Provider error: {e}")
```

### Check Dependencies

```bash
# Check if Whisper installed
python -c "import whisper; print(whisper.__version__)"

# Check if pyttsx3 installed
python -c "import pyttsx3; print(pyttsx3.__version__)"

# Try loading a model
python -c "import whisper; whisper.load_model('tiny')"
```

---

## 📊 Performance Targets

| Component | Target | Tuning |
|-----------|--------|--------|
| STT | 2-5s/30s | Use `whisper-tiny` for speed |
| LLM | 1-3s | Use `llama3.2:3b` for speed |
| TTS | 0.5-2s | Use system TTS or reduce rate |
| **Total** | **4-10s** | Profile each component |

---

## ✅ Pre-Deployment Checklist

- [ ] Voice enabled in `.env`: `VOICE_VOICE_ENABLED=true`
- [ ] Dependencies installed: `pip install openai-whisper pyttsx3`
- [ ] Health check passes: `curl /api/v1/voice/health`
- [ ] Example code runs: `python backend/voice/examples.py`
- [ ] Unit tests pass: `pytest tests/unit/test_voice_module.py`
- [ ] API endpoints documented in team wiki
- [ ] Monitoring/metrics set up (if needed)
- [ ] Configuration backed up (`.env` file)

---

## 🔗 Quick Links

| Resource | Path |
|----------|------|
| Module Guide | `backend/voice/README.md` |
| Quick Setup | `backend/voice/QUICKSTART.md` |
| How to Extend | `backend/voice/EXTENSION_GUIDE.md` |
| Implementation Details | `backend/voice/IMPLEMENTATION_SUMMARY.md` |
| Code Examples | `backend/voice/examples.py` |
| Unit Tests | `tests/unit/test_voice_module.py` |
| Config Template | `backend/voice/.env.example` |

---

## 💡 Tips & Tricks

### Faster Iteration

```bash
# Run just your modified test
pytest tests/unit/test_voice_module.py::TestYourClass -v --tb=short

# Run with print statements
pytest -v -s tests/unit/test_voice_module.py
```

### Debug API Calls

```bash
# Use -v for verbose
curl -v http://localhost:8080/api/v1/voice/health

# Pretty print JSON
curl http://localhost:8080/api/v1/voice/health | python -m json.tool
```

### Profile Performance

```python
import time

start = time.perf_counter()
result = agent.execute(payload)
elapsed = time.perf_counter() - start

print(f"Total: {elapsed:.2f}s")
print(f"Processing time from result: {result['processing_time_ms']}ms")
```

---

## 📞 Support

**Stuck?** Check these in order:

1. **QUICKSTART.md** — Setup instructions
2. **README.md** — Full documentation
3. **examples.py** — Working code examples
4. **Test file** — See test cases for usage patterns
5. **EXTENSION_GUIDE.md** — For custom implementations

---

**Quick Reference Version:** 0.1.0  
**Updated:** 2026-05-24
