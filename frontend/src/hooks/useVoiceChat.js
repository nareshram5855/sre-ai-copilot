import { useState, useCallback, useRef, useEffect } from "react";
import axios from "axios";
import { blobToBase64, blobToWavBlob } from "../utils/audioUtils";

const SILENCE_THRESHOLD = 0.015;
const SILENCE_DURATION_MS = 1400;
const MIN_RECORDING_MS = 700;
const MAX_RECORDING_MS = 30000;

/**
 * Voice input with silence detection — starts on click, auto-transcribes when you stop speaking.
 */
export function useVoiceChat(sessionId = null, onTranscribed = null) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcription, setTranscription] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [error, setError] = useState(null);
  const [audioLevel, setAudioLevel] = useState(0);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const silenceStartedAtRef = useRef(null);
  const recordingStartedAtRef = useRef(null);
  const monitorFrameRef = useRef(null);
  const maxTimeoutRef = useRef(null);
  const stoppingRef = useRef(false);
  const onTranscribedRef = useRef(onTranscribed);
  onTranscribedRef.current = onTranscribed;

  const cleanupAudio = useCallback(() => {
    if (monitorFrameRef.current) {
      cancelAnimationFrame(monitorFrameRef.current);
      monitorFrameRef.current = null;
    }
    if (maxTimeoutRef.current) {
      clearTimeout(maxTimeoutRef.current);
      maxTimeoutRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    silenceStartedAtRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  useEffect(() => () => cleanupAudio(), [cleanupAudio]);

  const processRecording = useCallback(async (mimeType) => {
    setIsProcessing(true);
    try {
      const rawBlob = new Blob(chunksRef.current, { type: mimeType });
      if (rawBlob.size < 1000) {
        setError("No speech detected. Try again and speak closer to the mic.");
        return null;
      }

      const wavBlob = await blobToWavBlob(rawBlob);
      const base64Audio = await blobToBase64(wavBlob);

      const response = await axios.post("/api/v1/voice/transcribe", {
        audio_base64: base64Audio,
        audio_format: "wav",
        language: "en-US",
        session_id: sessionId,
      });

      const { text, confidence: voiceConfidence } = response.data;
      const trimmed = (text || "").trim();

      if (!trimmed || trimmed.startsWith("[Stub:")) {
        setError(
          trimmed.startsWith("[Stub:")
            ? "Voice STT not configured on server. Run: make setup-voice"
            : "Could not transcribe speech. Please try again."
        );
        return null;
      }

      setTranscription(trimmed);
      setConfidence(voiceConfidence);
      const payload = { userText: trimmed, confidence: voiceConfidence };
      onTranscribedRef.current?.(payload);
      return payload;
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 404) {
        setError("Voice module is not enabled. Set VOICE_VOICE_ENABLED=true in .env");
      } else {
        setError(`Transcription failed: ${detail || err.message}`);
      }
      return null;
    } finally {
      setIsProcessing(false);
    }
  }, [sessionId]);

  const stopRecording = useCallback(async () => {
    if (stoppingRef.current || !mediaRecorderRef.current) return null;
    stoppingRef.current = true;
    cleanupAudio();

    const mediaRecorder = mediaRecorderRef.current;
    const mimeType = mediaRecorder.mimeType;

    return new Promise((resolve) => {
      mediaRecorder.onstop = async () => {
        setIsRecording(false);
        mediaRecorderRef.current = null;
        stoppingRef.current = false;
        const result = await processRecording(mimeType);
        resolve(result);
      };

      if (mediaRecorder.state === "recording") {
        mediaRecorder.stop();
      } else {
        setIsRecording(false);
        stoppingRef.current = false;
        resolve(null);
      }
    });
  }, [cleanupAudio, processRecording]);

  const monitorSilence = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser || stoppingRef.current) return;

    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);

    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const sample = (data[i] - 128) / 128;
      sum += sample * sample;
    }
    const rms = Math.sqrt(sum / data.length);
    setAudioLevel(rms);

    const elapsed = Date.now() - (recordingStartedAtRef.current || Date.now());

    if (rms < SILENCE_THRESHOLD && elapsed > MIN_RECORDING_MS) {
      if (!silenceStartedAtRef.current) {
        silenceStartedAtRef.current = Date.now();
      } else if (Date.now() - silenceStartedAtRef.current >= SILENCE_DURATION_MS) {
        stopRecording();
        return;
      }
    } else {
      silenceStartedAtRef.current = null;
    }

    monitorFrameRef.current = requestAnimationFrame(monitorSilence);
  }, [stopRecording]);

  const startListening = useCallback(async () => {
    if (isRecording || isProcessing) return null;

    try {
      setError(null);
      setTranscription("");
      setConfidence(0);
      chunksRef.current = [];
      stoppingRef.current = false;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      mediaRecorder.onerror = () => {
        setError("Recording error");
        stopRecording();
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(250);
      recordingStartedAtRef.current = Date.now();
      silenceStartedAtRef.current = null;
      setIsRecording(true);

      monitorFrameRef.current = requestAnimationFrame(monitorSilence);
      maxTimeoutRef.current = setTimeout(() => stopRecording(), MAX_RECORDING_MS);

      return null;
    } catch (err) {
      cleanupAudio();
      setError(`Microphone access denied: ${err.message}`);
      setIsRecording(false);
      return null;
    }
  }, [isRecording, isProcessing, cleanupAudio, monitorSilence, stopRecording]);

  return {
    isRecording,
    isProcessing,
    transcription,
    confidence,
    error,
    audioLevel,
    startListening,
    stopRecording,
    setTranscription,
    setConfidence,
    setError,
  };
}
