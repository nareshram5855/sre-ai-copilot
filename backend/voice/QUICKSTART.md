# Voice Module — Quick Installation Guide

## 5-Minute Setup

### 1. Enable Voice Module

```bash
cd /Users/shivapriya/Downloads/sre-ai

# Add to your .env file
echo "VOICE_VOICE_ENABLED=true" >> .env
echo "VOICE_STT_PROVIDER=local" >> .env
echo "VOICE_TTS_PROVIDER=local" >> .env
echo "VOICE_TTS_AUDIO_FORMAT=mp3" >> .env
```

### 2. Install Dependencies

**Local (Recommended - No external APIs needed):**
```bash
pip install openai-whisper pyttsx3
```

**macOS-specific (for espeak):**
```bash
brew install espeak
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install espeak pulseaudio
pip install openai-whisper pyttsx3
```

### 3. Verify Installation

```bash
# Start backend (if not already running)
python -m backend.main

# In another terminal, test voice health
curl http://localhost:8080/api/v1/voice/health | jq

# Expected response: voice module enabled with local providers
```

### 4. Test Voice Chat

```bash
# Run examples
python backend/voice/examples.py
```

---

## Configuration Reference

### Enable/Disable
```env
VOICE_VOICE_ENABLED=true          # Enable voice module (default: false)
```

### STT (Speech-to-Text)
```env
VOICE_STT_PROVIDER=local            # local, google-cloud, azure
VOICE_STT_LOCAL_MODEL=whisper-base  # whisper-tiny, whisper-small, whisper-medium, whisper-large
VOICE_STT_LANGUAGE=en-US            # Default language
```

### TTS (Text-to-Speech)
```env
VOICE_TTS_PROVIDER=local            # local, google-cloud, azure
VOICE_TTS_LOCAL_BACKEND=pyttsx3     # pyttsx3, espeak, gtts
VOICE_TTS_LANGUAGE=en-US
VOICE_TTS_GENDER=neutral             # neutral, male, female
VOICE_TTS_SPEAKING_RATE=1.0         # 0.5-2.0 (0.5 slow, 2.0 fast)
VOICE_TTS_AUDIO_FORMAT=mp3          # mp3, wav, ogg, m4a, webm
```

### Advanced
```env
VOICE_VOICE_SESSION_TTL_SECONDS=3600
VOICE_VOICE_MAX_AUDIO_SIZE_BYTES=52428800
VOICE_VOICE_MAX_AUDIO_DURATION_SECONDS=600
VOICE_VOICE_DEBUG_RETURN_TEXT=false # Set true to get LLM response in debug
```

---

## Usage Examples

### JavaScript/Web

```javascript
// Record audio from microphone
const mediaRecorder = new MediaRecorder();
const chunks = [];

mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
mediaRecorder.onstop = async () => {
  const audioBlob = new Blob(chunks, { type: 'audio/wav' });
  const reader = new FileReader();
  
  reader.onload = async () => {
    const base64Audio = reader.result.split(',')[1];
    
    // Send to voice API
    const response = await fetch('http://localhost:8080/api/v1/voice/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        audio_base64: base64Audio,
        audio_format: 'wav',
        return_text: true
      })
    });
    
    const result = await response.json();
    console.log('User said:', result.user_text);
    console.log('AI responded:', result.response_text);
    
    // Play audio response
    const audio = new Audio(`data:audio/mp3;base64,${result.audio_base64}`);
    audio.play();
  };
  
  reader.readAsDataURL(audioBlob);
};

mediaRecorder.start();
// ... record voice ...
mediaRecorder.stop();
```

### Python/Command Line

```python
import asyncio
import base64
import httpx

async def voice_chat(text_input: str):
    """Convert text to speech, then speech to text."""
    
    # Step 1: Text to Speech (TTS)
    tts_response = await httpx.AsyncClient().post(
        "http://localhost:8080/api/v1/voice/synthesize",
        json={"text": text_input}
    )
    audio_bytes = base64.b64decode(tts_response.json()["audio_base64"])
    
    # Step 2: Speech to Text (STT) — in real app, this would be user's voice
    audio_base64 = base64.b64encode(audio_bytes).decode()
    
    chat_response = await httpx.AsyncClient().post(
        "http://localhost:8080/api/v1/voice/chat",
        json={"audio_base64": audio_base64, "audio_format": "mp3"}
    )
    
    result = chat_response.json()
    print(f"User: {result['user_text']}")
    print(f"AI: {result['response_text']}")

asyncio.run(voice_chat("What is the OOM incident?"))
```

### cURL

```bash
# Record voice (use a real audio file in practice)
# Example: ffmpeg -i /path/to/voice.wav -f wav -

AUDIO_FILE="/path/to/voice.wav"
AUDIO_BASE64=$(base64 < "$AUDIO_FILE" | tr -d '\n')

curl -X POST http://localhost:8080/api/v1/voice/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"audio_base64\": \"$AUDIO_BASE64\",
    \"audio_format\": \"wav\",
    \"return_text\": true
  }" | jq .
```

---

## Troubleshooting

### "Voice module not accessible"
```bash
# Check if backend is running
curl http://localhost:8080/api/v1/health

# Check if voice is enabled in config
echo $VOICE_VOICE_ENABLED
# Should output: true
```

### "STT transcription failed"
```bash
# Verify Whisper is installed and models are downloaded
python -c "import whisper; whisper.load_model('base')"
# Should show download progress and complete successfully

# Check available models
pip list | grep whisper
```

### "TTS synthesis failed"
```bash
# Verify pyttsx3 is installed
python -c "import pyttsx3; pyttsx3.init()"

# On Linux, verify espeak is installed
which espeak
```

### Slow audio processing
- **STT slow?** Use smaller Whisper model: `export VOICE_STT_LOCAL_MODEL=whisper-tiny`
- **TTS slow?** Reduce speaking rate: `export VOICE_TTS_SPEAKING_RATE=0.8`
- **LLM slow?** Use faster model: See ARCHITECTURE.md

---

## API Endpoints (Quick Reference)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/voice/chat` | POST | Full voice in → LLM → voice out |
| `/api/v1/voice/transcribe` | POST | Audio to text only |
| `/api/v1/voice/synthesize` | POST | Text to audio only |
| `/api/v1/voice/health` | GET | Check module status |
| `/api/v1/voice/languages` | GET | List supported languages |

---

## Next Steps

1. **Test locally** → Run examples
2. **Integrate into frontend** → Add microphone widget (see frontend examples)
3. **Add custom providers** → See EXTENSION_GUIDE.md
4. **Deploy to production** → Update Helm charts (Phase 4)

---

## Support & Issues

**Documentation:**
- Module design: `backend/voice/README.md`
- Extension guide: `backend/voice/EXTENSION_GUIDE.md`
- Code examples: `backend/voice/examples.py`

**Testing:**
```bash
pytest tests/unit/test_voice_module.py -v
```

**Debug:**
```bash
# Enable debug output in voice module
export VOICE_VOICE_DEBUG_RETURN_TEXT=true
export LOG_LEVEL=DEBUG

# See what's happening internally
python -c "
from backend.voice.config import get_voice_settings
print(get_voice_settings())
"
```

---

**Version:** 0.1.0  
**Status:** Production-Ready Plugin  
**No impact on existing code** ✓
