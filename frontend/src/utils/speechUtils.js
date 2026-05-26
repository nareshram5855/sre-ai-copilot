import axios from "axios";

let currentAudio = null;
let voicesLoaded = false;

/** Strip markdown so TTS reads natural speech. */
export function stripMarkdownForSpeech(text) {
  if (!text) return "";
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/#{1,6}\s+/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\bK8s\b/gi, "Kubernetes")
    .replace(/\bRCA\b/g, "root cause analysis")
    .replace(/\s+/g, " ")
    .trim();
}

function pickBestBrowserVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || [];
  if (!voices.length) return null;

  const ranked = [
    (v) => /Jenny|Aria|Samantha|Google US English|Microsoft.*Natural|Premium/i.test(v.name),
    (v) => v.lang?.startsWith("en-US") && /Female|Google|Microsoft|Samantha/i.test(v.name),
    (v) => v.lang?.startsWith("en-US"),
    (v) => v.lang?.startsWith("en"),
  ];

  for (const score of ranked) {
    const match = voices.find(score);
    if (match) return match;
  }
  return voices[0];
}

function ensureVoicesLoaded() {
  if (voicesLoaded || !window.speechSynthesis) return;
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    voicesLoaded = true;
  };
  voicesLoaded = true;
}

export function stopSpeaking() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.currentTime = 0;
    currentAudio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

async function speakWithBrowser(text) {
  if (!window.speechSynthesis) return;

  ensureVoicesLoaded();
  const voice = pickBestBrowserVoice();

  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    utterance.rate = 0.94;
    utterance.pitch = 1.02;
    if (voice) utterance.voice = voice;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

async function speakWithServer(text) {
  const { data } = await axios.post("/api/v1/voice/synthesize", {
    text: text.slice(0, 5000),
    audio_format: "mp3",
    language: "en-US",
    rate: 0.94,
  });

  const { audio_base64: b64, audio_format: fmt } = data;
  if (!b64 || b64.length < 100) return false;

  const mime = fmt === "wav" ? "audio/wav" : "audio/mpeg";
  currentAudio = new Audio(`data:${mime};base64,${b64}`);

  await new Promise((resolve, reject) => {
    currentAudio.onended = () => {
      currentAudio = null;
      resolve();
    };
    currentAudio.onerror = () => {
      currentAudio = null;
      reject(new Error("Audio playback failed"));
    };
    currentAudio.play().catch(reject);
  });
  return true;
}

/** Speak assistant response — neural server TTS first, premium browser fallback. */
export async function speakText(text) {
  const clean = stripMarkdownForSpeech(text);
  if (!clean) return;

  stopSpeaking();

  try {
    const ok = await speakWithServer(clean);
    if (ok) return;
  } catch (_) {
    /* fall through to browser TTS */
  }

  await speakWithBrowser(clean);
}
