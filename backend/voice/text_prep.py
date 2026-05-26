"""Normalize assistant text for natural-sounding speech synthesis."""
import re

# Expand abbreviations that sound awkward when read literally.
_SPOKEN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bK8s\b", "Kubernetes"),
    (r"\bk8s\b", "Kubernetes"),
    (r"\bRCA\b", "root cause analysis"),
    (r"\bSLA\b", "S L A"),
    (r"\bSLO\b", "S L O"),
    (r"\bSLI\b", "S L I"),
    (r"\bAPI\b", "A P I"),
    (r"\bURL\b", "U R L"),
    (r"\bHTTP\b", "H T T P"),
    (r"\bHTTPS\b", "H T T P S"),
    (r"\bCPU\b", "C P U"),
    (r"\bRAM\b", "memory"),
    (r"\bOOM\b", "out of memory"),
    (r"\bP1\b", "priority one"),
    (r"\bP2\b", "priority two"),
    (r"\bP3\b", "priority three"),
    (r"\bP4\b", "priority four"),
)


def prepare_text_for_speech(text: str, *, max_chars: int = 5000) -> str:
    """Clean and expand text so neural TTS reads it conversationally."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    for pattern, spoken in _SPOKEN_REPLACEMENTS:
        cleaned = re.sub(pattern, spoken, cleaned)

    # Gentle pacing: ensure sentence boundaries breathe.
    cleaned = re.sub(r"([.!?])\s*(?=[A-Z])", r"\1 ", cleaned)
    cleaned = re.sub(r"([,;])\s*", r"\1 ", cleaned)

    return cleaned.strip()[:max_chars]
