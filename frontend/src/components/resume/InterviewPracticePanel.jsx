import { useState, useEffect, useCallback } from "react";
import { Shuffle, Eye, EyeOff, Send, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const markdownComponents = {
  p: ({ children }) => <p className="recruiter-msg-p">{children}</p>,
  ul: ({ children }) => <ul className="recruiter-msg-ul">{children}</ul>,
  ol: ({ children }) => <ol className="recruiter-msg-ol">{children}</ol>,
  li: ({ children }) => <li className="recruiter-msg-li">{children}</li>,
  strong: ({ children }) => <strong className="recruiter-msg-strong">{children}</strong>,
  h3: ({ children }) => <h3 className="recruiter-msg-h3">{children}</h3>,
};

export function InterviewPracticePanel({ token }) {
  const [stories, setStories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [current, setCurrent] = useState(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState("");
  const [grading, setGrading] = useState(false);
  const [showReference, setShowReference] = useState(false);

  const selectStory = useCallback((story) => {
    setCurrent(story);
    setAnswer("");
    setFeedback("");
    setShowReference(false);
  }, []);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const res = await fetch(`/api/v1/recruiter/admin/practice/stories?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || `Failed to load (${res.status})`);
        }
        const data = await res.json();
        if (!active) return;
        const list = data.stories || [];
        setStories(list);
        if (list.length) selectStory(list[Math.floor(Math.random() * list.length)]);
      } catch (e) {
        if (active) setError(e.message);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [token, selectStory]);

  function pickRandom() {
    if (!stories.length) return;
    selectStory(stories[Math.floor(Math.random() * stories.length)]);
  }

  async function grade() {
    if (!current || !answer.trim()) return;
    setGrading(true);
    setFeedback("");
    try {
      const res = await fetch(`/api/v1/recruiter/admin/practice/grade?token=${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: current.question,
          situation: current.situation,
          action: current.action,
          result: current.result,
          answer,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Grading failed (${res.status})`);
      }
      const data = await res.json();
      setFeedback(data.feedback || "");
    } catch (e) {
      setFeedback(`_Could not grade: ${e.message}_`);
    } finally {
      setGrading(false);
    }
  }

  if (loading) return <p className="text-gray-500 text-xs">Loading questions…</p>;
  if (error) return <p className="text-red-400 text-xs">{error}</p>;
  if (!current) return <p className="text-gray-500 text-xs">No questions available.</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {stories.map((s) => (
          <button
            key={s.theme}
            onClick={() => selectStory(s)}
            className={`px-2.5 py-1 rounded-full text-[10px] border transition-colors capitalize ${
              current.theme === s.theme
                ? "border-indigo-500 text-indigo-300 bg-indigo-950/40"
                : "border-sre-border text-gray-500 hover:text-gray-300 hover:border-gray-600"
            }`}
          >
            {s.theme.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <div className="bg-sre-bg rounded-lg px-4 py-3 border border-sre-border">
        <p className="text-gray-500 text-[10px] uppercase tracking-wider mb-1">Question</p>
        <p className="text-white text-sm font-medium">{current.question}</p>
      </div>

      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="Type or paste the answer you'd say out loud..."
        rows={5}
        className="w-full bg-sre-bg border border-sre-border rounded-lg px-3 py-2.5 text-white text-xs placeholder-gray-600 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
      />

      <div className="flex gap-2">
        <button
          onClick={grade}
          disabled={grading || !answer.trim()}
          className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded-lg py-2 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
        >
          {grading ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
          {grading ? "Grading…" : "Grade my answer"}
        </button>
        <button
          onClick={() => setShowReference((v) => !v)}
          className="px-3 py-2 rounded-lg border border-sre-border text-gray-400 hover:text-white text-xs transition-colors flex items-center gap-1.5"
        >
          {showReference ? <EyeOff size={12} /> : <Eye size={12} />}
          {showReference ? "Hide" : "Show"} answer
        </button>
        <button
          onClick={pickRandom}
          className="px-3 py-2 rounded-lg border border-sre-border text-gray-400 hover:text-white text-xs transition-colors flex items-center gap-1.5"
        >
          <Shuffle size={12} /> Random
        </button>
      </div>

      {showReference && (
        <div className="bg-sre-bg rounded-lg px-4 py-3 border border-sre-border space-y-2 text-[11px] text-gray-300 leading-relaxed">
          <p>
            <span className="text-gray-500 uppercase text-[10px] tracking-wider">Situation — </span>
            {current.situation}
          </p>
          <p>
            <span className="text-gray-500 uppercase text-[10px] tracking-wider">Action — </span>
            {current.action}
          </p>
          <p>
            <span className="text-gray-500 uppercase text-[10px] tracking-wider">Result — </span>
            {current.result}
          </p>
        </div>
      )}

      {feedback && (
        <div className="bg-emerald-950/15 border border-emerald-800/30 rounded-lg px-4 py-3 text-[11px] text-gray-200">
          <p className="text-emerald-400 text-[10px] uppercase tracking-wider mb-1.5">Coach feedback</p>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {feedback}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
