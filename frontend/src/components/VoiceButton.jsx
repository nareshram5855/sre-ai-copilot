import { Mic, AlertCircle, Loader2, Volume2 } from "lucide-react";
import { useVoiceChat } from "../hooks/useVoiceChat";

/**
 * Voice input — click once to listen; auto-transcribes after ~1.4s of silence.
 */
export function VoiceButton({ onVoiceInput, disabled = false, sessionId = null, enabled = true, isSpeaking = false }) {
  const {
    isRecording,
    isProcessing,
    transcription,
    confidence,
    error,
    audioLevel,
    startListening,
    setError,
  } = useVoiceChat(sessionId, onVoiceInput);

  if (!enabled) return null;

  const handleClick = async () => {
    try {
      if (isRecording || isProcessing || isSpeaking) return;
      await startListening();
    } catch (err) {
      setError(`Voice action failed: ${err.message}`);
    }
  };

  const levelPct = Math.min(100, Math.round(audioLevel * 400));

  return (
    <div className="flex flex-col gap-2 w-full">
      <button
        onClick={handleClick}
        disabled={disabled || isProcessing || isRecording || isSpeaking}
        className={`
          relative flex items-center justify-center gap-2 px-4 py-2 rounded-lg
          font-medium text-xs transition-all overflow-hidden
          ${isRecording
            ? "bg-red-600 hover:bg-red-500 text-white shadow-lg"
            : isSpeaking
            ? "bg-emerald-700 text-white shadow-lg"
            : isProcessing
            ? "bg-sre-accent text-white"
            : "bg-sre-surface border border-sre-border hover:border-sre-accent text-gray-200"
          }
          ${disabled || isProcessing || isSpeaking ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        `}
        title={
          isSpeaking
            ? "Assistant is speaking…"
            : isRecording
            ? "Listening — pause speaking to send automatically"
            : "Click and speak — auto-sends when you pause, response is spoken aloud"
        }
      >
        {isRecording && (
          <span
            className="absolute inset-y-0 left-0 bg-red-400/30 transition-all duration-75"
            style={{ width: `${levelPct}%` }}
          />
        )}
        <span className="relative flex items-center gap-2">
          {isRecording ? (
            <>
              <Mic size={16} className="animate-pulse" />
              <span>Listening… pause to send</span>
            </>
          ) : isSpeaking ? (
            <>
              <Volume2 size={16} className="animate-pulse" />
              <span>Speaking…</span>
            </>
          ) : isProcessing ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              <span>Transcribing…</span>
            </>
          ) : (
            <>
              <Mic size={16} />
              <span>Voice Input</span>
            </>
          )}
        </span>
      </button>

      {error && (
        <div className="flex items-start gap-2 p-2.5 bg-red-950/40 border border-red-800/50 rounded-lg">
          <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-red-300">Voice Error</p>
            <p className="text-xs text-red-400">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-xs text-red-400 hover:text-red-300 mt-1 underline"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {transcription && (
        <div className="bg-sre-surface border border-sre-border rounded-lg p-2.5">
          <p className="text-xs font-semibold text-gray-400 mb-1">Your voice input:</p>
          <p className="text-xs text-gray-200">{transcription}</p>
          <div className="flex items-center gap-2 mt-1.5">
            <div className="flex-1 bg-sre-bg rounded-full h-1 overflow-hidden">
              <div
                className="bg-sre-accent h-full transition-all"
                style={{ width: `${Math.round(confidence * 100)}%` }}
              />
            </div>
            <span className="text-xs text-gray-500 whitespace-nowrap">
              {Math.round(confidence * 100)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
