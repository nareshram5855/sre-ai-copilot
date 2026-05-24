import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Loader2, Bot, User, MessageSquare, X, FileText, Copy, Check } from "lucide-react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const SESSION_ID = `session-${Math.random().toString(36).slice(2, 9)}`;

export function ChatInterface() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content:
        "Hi! I'm your on-call SRE assistant. Ask me about runbooks, past incidents, or troubleshooting steps — I'll search the knowledge base and give you exact commands.",
      sources: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const clearSession = useCallback(async () => {
    try {
      await axios.delete(`/api/v1/chat/${SESSION_ID}`);
    } catch (_) {}
    setMessages([
      {
        role: "assistant",
        content: "Session cleared. What's your next question?",
        sources: [],
      },
    ]);
  }, []);

  async function send(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: question, sources: [] }]);
    setInput("");
    setLoading(true);

    // Add a streaming assistant message — tokens append into it as they arrive
    setMessages((prev) => [...prev, { role: "assistant", content: "", sources: [], streaming: true }]);

    try {
      const resp = await fetch("/api/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, session_id: SESSION_ID }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader  = resp.body.getReader();
      const decoder = new TextDecoder();
      let   buffer  = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();   // keep incomplete line for next chunk

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.token) {
              // Append token to the last (streaming) message
              setMessages((prev) => {
                const updated = [...prev];
                const last    = updated[updated.length - 1];
                updated[updated.length - 1] = { ...last, content: last.content + data.token };
                return updated;
              });
            }

            if (data.done) {
              setMessages((prev) => {
                const updated = [...prev];
                const last    = updated[updated.length - 1];
                updated[updated.length - 1] = {
                  ...last,
                  streaming: false,
                  sources: data.sources || [],
                  meta: { tier: data.tier, complexity: data.complexity },
                };
                return updated;
              });
            }

            if (data.error) throw new Error(data.error);
          } catch (parseErr) { /* skip malformed SSE lines */ }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        // Replace the empty streaming message with an error
        const updated = [...prev];
        const last    = updated[updated.length - 1];
        if (last?.streaming) {
          updated[updated.length - 1] = { role: "error", content: err.message || "Chat request failed", sources: [] };
        } else {
          updated.push({ role: "error", content: err.message || "Chat request failed", sources: [] });
        }
        return updated;
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-screen p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <MessageSquare size={20} className="text-sre-accent" />
            On-Call Knowledge Assistant
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            RAG-powered Q&A over runbooks and incidents — exact commands, in context.
          </p>
        </div>
        <button
          onClick={clearSession}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 border border-sre-border rounded-lg px-3 py-1.5 transition-colors"
        >
          <X size={12} /> Clear session
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-1">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            {msg.role !== "error" && (
              <div
                className={`w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs mt-1 ${
                  msg.role === "assistant" ? "bg-sre-accent" : "bg-gray-700"
                }`}
              >
                {msg.role === "assistant" ? <Bot size={14} /> : <User size={14} />}
              </div>
            )}
            <div className={`space-y-1.5 ${msg.role === "error" ? "w-full" : "max-w-[82%]"}`}>
              <div
                className={`rounded-xl px-4 py-3 text-sm ${
                  msg.role === "assistant"
                    ? "bg-sre-surface border border-sre-border text-gray-200"
                    : msg.role === "error"
                    ? "bg-red-950 border border-red-800 text-red-300"
                    : "bg-sre-accent text-white"
                }`}
              >
                {msg.role === "assistant" ? (
                  <div>
                    <MarkdownBody content={msg.content} />
                    {msg.streaming && (
                      <span className="inline-block w-0.5 h-4 bg-gray-400 ml-0.5 align-middle"
                        style={{animation: "pulse 1s ease-in-out infinite"}} />
                    )}
                  </div>
                ) : msg.role === "error" ? (
                  `Error: ${msg.content}`
                ) : (
                  msg.content
                )}
              </div>
              {msg.sources?.length > 0 && (
                <div className="flex gap-1.5 flex-wrap pl-1">
                  {msg.sources.map((src, j) => (
                    <span
                      key={j}
                      className="flex items-center gap-1 text-xs text-gray-500 bg-sre-bg border border-sre-border rounded px-2 py-0.5"
                    >
                      <FileText size={10} />
                      {src}
                    </span>
                  ))}
                </div>
              )}
              {msg.meta && (
                <p className="text-xs text-gray-600 pl-1">
                  {msg.meta.tier} · {msg.meta.complexity}
                </p>
              )}
            </div>
          </div>
        ))}

        {/* Show "Searching..." only while waiting for the FIRST token (before streaming starts) */}
        {loading && messages[messages.length - 1]?.content === "" && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-sre-accent flex items-center justify-center mt-1 flex-shrink-0">
              <Bot size={14} />
            </div>
            <div className="bg-sre-surface border border-sre-border rounded-xl px-4 py-3 flex items-center gap-2 text-sm text-gray-400">
              <Loader2 size={14} className="animate-spin" />
              Thinking
              <span className="inline-flex gap-0.5 ml-0.5">
                {[0,1,2].map(i => (
                  <span key={i} className="w-1 h-1 rounded-full bg-gray-500"
                    style={{animation:`pulse 1.2s ease-in-out ${i*0.2}s infinite`}} />
                ))}
              </span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={send} className="flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. How do I recover from a pod CrashLoopBackOff in the iam namespace?"
          className="flex-1 bg-sre-surface border border-sre-border rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-sre-accent"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-sre-accent hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-3 rounded-xl transition-colors"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button
      onClick={copy}
      className="absolute top-2 right-2 text-gray-500 hover:text-gray-300 transition-colors"
      title="Copy"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}

function MarkdownBody({ content }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Code blocks — dark background with copy button
        code({ node, inline, className, children, ...props }) {
          const code = String(children).replace(/\n$/, "");
          if (inline) {
            return (
              <code className="bg-gray-800 text-green-300 rounded px-1 py-0.5 text-xs font-mono" {...props}>
                {code}
              </code>
            );
          }
          return (
            <div className="relative mt-2 mb-2">
              <pre className="bg-gray-900 border border-gray-700 rounded-lg p-3 overflow-x-auto text-xs font-mono text-green-300 leading-relaxed pr-8">
                <code>{code}</code>
              </pre>
              <CopyButton text={code} />
            </div>
          );
        },
        // Headings — smaller since they're inside a chat bubble
        h1: ({ children }) => <p className="font-bold text-white mt-3 mb-1 text-sm">{children}</p>,
        h2: ({ children }) => <p className="font-bold text-white mt-3 mb-1 text-sm">{children}</p>,
        h3: ({ children }) => <p className="font-semibold text-gray-200 mt-2 mb-1 text-xs uppercase tracking-wide">{children}</p>,
        // Lists
        ul: ({ children }) => <ul className="list-disc list-inside space-y-1 my-1 text-gray-300">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside space-y-1 my-1 text-gray-300">{children}</ol>,
        li: ({ children }) => <li className="text-sm">{children}</li>,
        // Paragraphs
        p: ({ children }) => <p className="mb-2 last:mb-0 text-gray-200 leading-relaxed">{children}</p>,
        // Bold / italic
        strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
        em: ({ children }) => <em className="text-gray-300 italic">{children}</em>,
        // Horizontal rule
        hr: () => <hr className="border-gray-700 my-3" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
