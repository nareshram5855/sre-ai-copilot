import { useEffect, useState } from "react";
import { Heart, MessageCircle, Send, X } from "lucide-react";
import {
  getRecruiterSessionId,
  isFeedbackDismissed,
  isFeedbackSubmitted,
  markFeedbackDismissed,
  markFeedbackSubmitted,
} from "../../utils/recruiterSession.js";

const FEEDBACK_REASONS = [
  "Role requirements didn't align",
  "Experience level mismatch",
  "Location or work arrangement",
  "Compensation or budget",
  "Timing or headcount",
  "Other",
];

const ENGAGE_DELAY_MS = 45_000;

export function RecruiterFeedbackPanel({ engaged = false }) {
  const [visible, setVisible] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [feedback, setFeedback] = useState("");
  const [reasons, setReasons] = useState([]);
  const [rating, setRating] = useState(null);

  useEffect(() => {
    if (isFeedbackDismissed() || isFeedbackSubmitted()) return;

    if (engaged) {
      const timer = setTimeout(() => setVisible(true), 8000);
      return () => clearTimeout(timer);
    }

    const timer = setTimeout(() => setVisible(true), ENGAGE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [engaged]);

  function dismiss() {
    markFeedbackDismissed();
    setVisible(false);
  }

  function toggleReason(reason) {
    setReasons((prev) =>
      prev.includes(reason) ? prev.filter((r) => r !== reason) : [...prev, reason]
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!feedback.trim() || submitting) return;

    setSubmitting(true);
    setError("");

    try {
      const res = await fetch("/api/v1/recruiter/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: getRecruiterSessionId(),
          name: name.trim() || null,
          email: email.trim() || null,
          feedback: feedback.trim(),
          reasons,
          rating,
        }),
      });

      if (!res.ok) {
        throw new Error("submit failed");
      }

      markFeedbackSubmitted();
      setSubmitted(true);
      setVisible(true);
    } catch {
      setError("Could not send feedback right now — feel free to email me directly from this page.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!visible) return null;

  if (submitted) {
    return (
      <div className="fixed bottom-4 left-4 right-4 z-40 md:left-auto md:right-6 md:max-w-md resume-no-print">
        <div className="panel-card p-5 border-emerald-500/30 bg-emerald-950/20 shadow-xl shadow-black/40">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-emerald-600/15 border border-emerald-500/30 shrink-0">
              <Heart size={18} className="text-emerald-300" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white">Thank you — truly appreciated</p>
              <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                Your note helps me sharpen this profile and focus on the right opportunities. Wishing you a smooth search.
              </p>
            </div>
            <button
              type="button"
              onClick={dismiss}
              className="text-gray-500 hover:text-gray-300 transition-colors shrink-0"
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 z-40 md:left-auto md:right-6 md:max-w-lg resume-no-print">
      <div className="panel-card p-5 border-indigo-500/25 bg-gradient-to-br from-indigo-950/50 via-sre-surface to-sre-surface shadow-xl shadow-black/40">
        <div className="flex items-start gap-3 mb-4">
          <div className="p-2 rounded-lg bg-indigo-600/15 border border-indigo-500/30 shrink-0">
            <MessageCircle size={18} className="text-indigo-300" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white">A quick favor, if you have a moment</p>
            <p className="text-xs text-gray-400 mt-1 leading-relaxed">
              If this profile isn&apos;t moving forward, I&apos;d genuinely appreciate a brief note on why —
              even a sentence helps me improve. Your feedback is optional and stays between us.
            </p>
          </div>
          <button
            type="button"
            onClick={dismiss}
            className="text-gray-500 hover:text-gray-300 transition-colors shrink-0"
            aria-label="Dismiss feedback request"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <fieldset>
            <legend className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 mb-2">
              What was the main reason? (optional)
            </legend>
            <div className="flex flex-wrap gap-1.5">
              {FEEDBACK_REASONS.map((reason) => {
                const active = reasons.includes(reason);
                return (
                  <button
                    key={reason}
                    type="button"
                    onClick={() => toggleReason(reason)}
                    className={`text-[10px] px-2.5 py-1 rounded-full border transition-colors ${
                      active
                        ? "border-indigo-500/50 bg-indigo-950/50 text-indigo-200"
                        : "border-sre-border bg-sre-bg/40 text-gray-500 hover:text-gray-300 hover:border-indigo-500/30"
                    }`}
                  >
                    {reason}
                  </button>
                );
              })}
            </div>
          </fieldset>

          <div>
            <label htmlFor="recruiter-feedback-text" className="sr-only">
              Feedback
            </label>
            <textarea
              id="recruiter-feedback-text"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={3}
              placeholder="What would have made this a stronger fit? (skills, seniority, domain, etc.)"
              className="w-full text-sm px-3 py-2.5 rounded-lg bg-sre-bg border border-sre-border text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50 resize-none"
            />
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name (optional)"
              className="text-sm px-3 py-2 rounded-lg bg-sre-bg border border-sre-border text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50"
            />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email (optional)"
              className="text-sm px-3 py-2 rounded-lg bg-sre-bg border border-sre-border text-white placeholder:text-gray-600 focus:outline-none focus:border-indigo-500/50"
            />
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1" aria-label="Optional rating">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setRating(rating === n ? null : n)}
                  className={`text-xs px-1.5 py-0.5 rounded transition-colors ${
                    rating === n ? "text-amber-300" : "text-gray-600 hover:text-gray-400"
                  }`}
                  title={`${n} star${n > 1 ? "s" : ""}`}
                >
                  ★
                </button>
              ))}
              <span className="text-[10px] text-gray-600 ml-1 hidden sm:inline">Profile clarity</span>
            </div>
            <button
              type="submit"
              disabled={submitting || feedback.trim().length < 3}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              <Send size={14} />
              Send feedback
            </button>
          </div>

          {error && <p className="text-[11px] text-amber-400/90">{error}</p>}
        </form>
      </div>
    </div>
  );
}
