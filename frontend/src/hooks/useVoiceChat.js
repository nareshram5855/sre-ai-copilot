import { useState, useCallback, useRef } from "react";
import axios from "axios";

/**
 * Hook for voice input — records audio and transcribes via /api/v1/voice/transcribe.
 * Chat response is handled by the parent (single LLM call via chat stream).
 */
export function useVoiceChat(sessionId = null) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcription, setTranscription] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [error, setError] = useState(null);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  const startRecording = useCallback(async () => {
    try {
      setError(null);
      setTranscription("");
      setConfidence(0);
      chunksRef.current = [];

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/wav";

      const mediaRecorder = new MediaRecorder(stream, { mimeType });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onerror = (event) => {
        setError(`Recording error: ${event.error}`);
        setIsRecording(false);
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      setError(`Microphone access denied: ${err.message}`);
      setIsRecording(false);
    }
  }, []);

  const stopRecording = useCallback(async () => {
    return new Promise((resolve) => {
      if (!mediaRecorderRef.current) {
        resolve(null);
        return;
      }

      const mediaRecorder = mediaRecorderRef.current;

      mediaRecorder.onstop = async () => {
        setIsRecording(false);
        setIsProcessing(true);

        try {
          const audioBlob = new Blob(chunksRef.current, { type: mediaRecorder.mimeType });
          const reader = new FileReader();

          reader.onload = async () => {
            try {
              const base64Audio = reader.result.split(",")[1];
              const audioFormat = mediaRecorder.mimeType.includes("webm") ? "webm" : "wav";

              const response = await axios.post("/api/v1/voice/transcribe", {
                audio_base64: base64Audio,
                audio_format: audioFormat,
                language: "en-US",
                session_id: sessionId,
              });

              const { text, confidence: voiceConfidence } = response.data;

              setTranscription(text);
              setConfidence(voiceConfidence);

              resolve({
                userText: text,
                confidence: voiceConfidence,
              });
            } catch (err) {
              const detail = err.response?.data?.detail;
              if (err.response?.status === 404) {
                setError("Voice module is not enabled on the backend.");
              } else {
                setError(`Transcription failed: ${detail || err.message}`);
              }
              resolve(null);
            } finally {
              setIsProcessing(false);
            }
          };

          reader.readAsDataURL(audioBlob);
        } catch (err) {
          setError(`Audio processing failed: ${err.message}`);
          setIsProcessing(false);
          resolve(null);
        }
      };

      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach((track) => track.stop());
    });
  }, [sessionId]);

  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      return await stopRecording();
    }
    await startRecording();
    return null;
  }, [isRecording, startRecording, stopRecording]);

  return {
    isRecording,
    isProcessing,
    transcription,
    confidence,
    error,
    toggleRecording,
    setTranscription,
    setConfidence,
    setError,
  };
}
