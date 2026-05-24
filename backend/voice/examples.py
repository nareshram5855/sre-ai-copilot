"""
Quick Start Examples — Voice Module Usage

Run these examples to test the voice module.
"""

import asyncio
import base64
import json
from pathlib import Path

import httpx


# ─── Configuration ────────────────────────────────────────────────────────────

VOICE_API_BASE = "http://localhost:8080/api/v1/voice"
VOICE_ENABLED = True  # Toggle for testing


# ─── Helper: Generate Dummy Audio ─────────────────────────────────────────────

def create_dummy_wav_audio(duration_seconds: float = 3.0) -> bytes:
    """
    Create minimal valid WAV file (silence) for testing.
    
    Format:
      - Sample rate: 16000 Hz
      - Channels: 1 (mono)
      - Bit depth: 16-bit PCM
    """
    sample_rate = 16000
    channels = 1
    bit_depth = 16
    num_samples = int(sample_rate * duration_seconds)

    # WAV header
    import struct
    
    byte_rate = sample_rate * channels * bit_depth // 8
    block_align = channels * bit_depth // 8
    subchunk2_size = num_samples * channels * bit_depth // 8

    wav_header = b"RIFF"
    wav_header += struct.pack("<I", 36 + subchunk2_size)
    wav_header += b"WAVE"
    wav_header += b"fmt "
    wav_header += struct.pack("<I", 16)  # Subchunk1Size
    wav_header += struct.pack("<H", 1)   # AudioFormat (PCM)
    wav_header += struct.pack("<H", channels)
    wav_header += struct.pack("<I", sample_rate)
    wav_header += struct.pack("<I", byte_rate)
    wav_header += struct.pack("<H", block_align)
    wav_header += struct.pack("<H", bit_depth)
    wav_header += b"data"
    wav_header += struct.pack("<I", subchunk2_size)

    # Audio data (silence = zeros)
    audio_data = b"\x00" * subchunk2_size

    return wav_header + audio_data


# ─── Example 1: Voice Chat (Full Round-Trip) ─────────────────────────────────

async def example_voice_chat():
    """Send voice, get voice response."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Voice Chat (STT → LLM → TTS)")
    print("=" * 70)

    # Create dummy audio (3 seconds of silence, in practice: user speaking)
    audio_bytes = create_dummy_wav_audio(3.0)
    audio_base64 = base64.b64encode(audio_bytes).decode()

    payload = {
        "audio_base64": audio_base64,
        "audio_format": "wav",
        "language": "en-US",
        "return_text": True,  # Include transcription + response for debugging
    }

    print(f"\n→ Sending voice request...")
    print(f"  Audio size: {len(audio_bytes)} bytes")
    print(f"  Format: wav")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{VOICE_API_BASE}/chat",
                json=payload,
                timeout=60.0,  # TTS can be slow
            )
            response.raise_for_status()
            result = response.json()

            print(f"\n← Response received!")
            print(f"  User said: {result.get('user_text', '[empty]')}")
            print(f"  Assistant replied: {result.get('response_text', '[empty]')}")
            print(f"  Confidence: {result['confidence']:.2f}")
            print(f"  Audio duration: {result['duration_seconds']:.1f}s")
            print(f"  Processing time: {result['processing_time_ms']}ms")
            print(f"  STT provider: {result['provider_stt']}")
            print(f"  TTS provider: {result['provider_tts']}")

            # Decode audio response
            audio_response = base64.b64decode(result["audio_base64"])
            print(f"  Response audio size: {len(audio_response)} bytes")

            return result

        except httpx.HTTPError as exc:
            print(f"  ✗ Error: {exc}")
            return None


# ─── Example 2: Transcribe Only (STT) ─────────────────────────────────────────

async def example_transcribe():
    """Convert audio to text only."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Transcribe Only (STT)")
    print("=" * 70)

    audio_bytes = create_dummy_wav_audio(3.0)
    audio_base64 = base64.b64encode(audio_bytes).decode()

    payload = {
        "audio_base64": audio_base64,
        "audio_format": "wav",
        "language": "en-US",
        "domain_hints": ["Kubernetes", "pod", "incident", "alert"],
    }

    print(f"\n→ Transcribing audio...")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{VOICE_API_BASE}/transcribe",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            print(f"\n← Transcription complete!")
            print(f"  Text: {result['text']}")
            print(f"  Confidence: {result['confidence']:.2f}")
            print(f"  Language: {result['language']}")
            print(f"  Duration: {result['duration_seconds']:.1f}s")
            print(f"  Provider: {result['provider']}")
            print(f"  Processing time: {result['processing_time_ms']}ms")

            return result

        except httpx.HTTPError as exc:
            print(f"  ✗ Error: {exc}")
            return None


# ─── Example 3: Synthesize Only (TTS) ────────────────────────────────────────

async def example_synthesize():
    """Convert text to audio only."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Synthesize Only (TTS)")
    print("=" * 70)

    payload = {
        "text": "The OOM incident has been resolved. Pod restart count is back to zero.",
        "language": "en-US",
        "gender": "neutral",
        "rate": 1.0,
        "pitch": 0.0,
        "audio_format": "mp3",
    }

    print(f"\n→ Synthesizing audio...")
    print(f"  Text: {payload['text']}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{VOICE_API_BASE}/synthesize",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

            print(f"\n← Synthesis complete!")
            print(f"  Audio size: {len(base64.b64decode(result['audio_base64']))} bytes")
            print(f"  Format: {result['audio_format']}")
            print(f"  Duration: {result['duration_seconds']:.1f}s")
            print(f"  Provider: {result['provider']}")
            print(f"  Processing time: {result['processing_time_ms']}ms")
            print(f"  Characters: {result['character_count']}")

            return result

        except httpx.HTTPError as exc:
            print(f"  ✗ Error: {exc}")
            return None


# ─── Example 4: Health Check ─────────────────────────────────────────────────

async def example_health():
    """Check voice module status."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Voice Module Health")
    print("=" * 70)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{VOICE_API_BASE}/health", timeout=5.0)
            response.raise_for_status()
            result = response.json()

            print(f"\n← Voice Module Status:")
            print(f"  Enabled: {result['enabled']}")
            print(f"  Default TTS: {result['default_tts']}")
            print(f"  Default STT: {result['default_stt']}")

            if result["tts_providers"]:
                print(f"\n  TTS Providers:")
                for provider in result["tts_providers"]:
                    print(f"    - {provider['name']}: {len(provider['supported_languages'])} languages")

            if result["stt_providers"]:
                print(f"\n  STT Providers:")
                for provider in result["stt_providers"]:
                    print(f"    - {provider['name']}: {len(provider['supported_languages'])} languages")

            return result

        except httpx.HTTPError as exc:
            print(f"  ✗ Error: {exc}")
            return None


# ─── Example 5: Supported Languages ──────────────────────────────────────────

async def example_languages():
    """List supported languages."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Supported Languages")
    print("=" * 70)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{VOICE_API_BASE}/languages", timeout=5.0)
            response.raise_for_status()
            result = response.json()

            print(f"\n← Supported Languages:")
            print(f"\n  TTS: {', '.join(result['tts'])}")
            print(f"\n  STT: {', '.join(result['stt'])}")

            return result

        except httpx.HTTPError as exc:
            print(f"  ✗ Error: {exc}")
            return None


# ─── Main: Run All Examples ──────────────────────────────────────────────────

async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("VOICE MODULE — QUICK START EXAMPLES")
    print("=" * 70)
    print("\nPrerequisites:")
    print("  1. Start backend: python -m backend.main")
    print("  2. Enable voice: export VOICE_VOICE_ENABLED=true")
    print("  3. Install deps: pip install openai-whisper pyttsx3")
    print("\n" + "=" * 70)

    # Check if voice is enabled
    async with httpx.AsyncClient() as client:
        try:
            await client.get(f"{VOICE_API_BASE}/health", timeout=2.0)
        except Exception as exc:
            print(f"\n✗ Voice module not accessible: {exc}")
            print(f"  Make sure backend is running and VOICE_VOICE_ENABLED=true")
            return

    # Run examples
    await example_health()
    await example_languages()
    await example_transcribe()
    await example_synthesize()
    await example_voice_chat()

    print("\n" + "=" * 70)
    print("✓ All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
