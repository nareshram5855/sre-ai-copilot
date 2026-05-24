import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, X, Minus, Maximize2, Send, Loader2, Bot, User, FileText, Copy, Check, Play, Terminal, AlertTriangle, Zap, ChevronRight, CheckCircle, XCircle, RefreshCw } from "lucide-react";
import axios from "axios";  // kept for DELETE /chat/:session_id (clear session)
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { VoiceButton } from "./VoiceButton";

const SESSION_ID = `session-${Math.random().toString(36).slice(2, 9)}`;

// Widget states: closed → open (normal) → maximized
const STATES = { CLOSED: "closed", OPEN: "open", MAX: "max" };

export function ChatWidget() {
  const [uiState, setUiState] = useState(STATES.CLOSED);
  // agentMode: "off" | "sre" | "full"
  const [agentMode, setAgentMode] = useState("off");
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "Hi — I'm your on-call assistant. Ask me about runbooks, past incidents, or how to fix a specific alert.",
      sources: [],
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [unread, setUnread] = useState(0);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    axios.get("/api/v1/voice/health")
      .then((res) => setVoiceEnabled(res.data?.enabled === true))
      .catch(() => setVoiceEnabled(false));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (uiState !== STATES.CLOSED) {
      setUnread(0);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [uiState]);

  const clearSession = useCallback(async () => {
    try { await axios.delete(`/api/v1/chat/${SESSION_ID}`); } catch (_) {}
    setMessages([{ role: "assistant", content: "Session cleared. What's next?", sources: [] }]);
  }, []);

  const sendQuestion = useCallback(async (question) => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setMessages((p) => [...p, { role: "user", content: trimmed, sources: [] }]);
    setInput("");
    setLoading(true);

    const useReact = agentMode === "full";
    const endpoint = useReact ? "/api/v1/agent/react" : "/api/v1/chat/stream";
    const bodyPayload = useReact
      ? { question: trimmed, session_id: SESSION_ID, full_mode: true }
      : { question: trimmed, session_id: SESSION_ID, agent_mode: agentMode };

    setMessages((p) => [...p, {
      role: "assistant",
      content: "",
      sources: [],
      streaming: true,
      reactSteps: useReact ? [] : undefined,
    }]);

    const appendToken = (token) => setMessages((p) => {
      const updated = [...p];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = { ...last, content: last.content + token };
      return updated;
    });

    const pushReactStep = (step) => setMessages((p) => {
      const updated = [...p];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = { ...last, reactSteps: [...(last.reactSteps || []), step] };
      return updated;
    });

    const finishMessage = (extra = {}) => setMessages((p) => {
      const updated = [...p];
      const last = updated[updated.length - 1];
      updated[updated.length - 1] = { ...last, streaming: false, sources: [], ...extra };
      return updated;
    });

    try {
      const resp = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(bodyPayload),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));

            if (useReact) {
              if (ev.type === "thinking") appendToken(ev.text + "\n\n");
              if (ev.type === "text") appendToken(ev.token);
              if (ev.type === "tool_call") pushReactStep({ kind: "call", name: ev.name, args: ev.args, status: "running" });
              if (ev.type === "tool_result") {
                setMessages((p) => {
                  const updated = [...p];
                  const last = updated[updated.length - 1];
                  const steps = [...(last.reactSteps || [])];
                  for (let i = steps.length - 1; i >= 0; i--) {
                    if (steps[i].kind === "call" && steps[i].name === ev.name && steps[i].status === "running") {
                      steps[i] = { ...steps[i], result: ev.result, success: ev.success, status: ev.success ? "done" : "error" };
                      break;
                    }
                  }
                  updated[updated.length - 1] = { ...last, reactSteps: steps };
                  return updated;
                });
              }
              if (ev.type === "done") { finishMessage(); if (uiState === STATES.CLOSED) setUnread((n) => n + 1); }
              if (ev.type === "error") throw new Error(ev.message);
            } else {
              if (ev.token) appendToken(ev.token);
              if (ev.done) { finishMessage({ sources: ev.sources || [] }); if (uiState === STATES.CLOSED) setUnread((n) => n + 1); }
              if (ev.error) throw new Error(ev.error);
            }
          } catch (_) {}
        }
      }
    } catch (err) {
      setMessages((p) => {
        const updated = [...p];
        const last = updated[updated.length - 1];
        if (last?.streaming) {
          updated[updated.length - 1] = { role: "error", content: err.message || "Request failed", sources: [] };
        } else {
          updated.push({ role: "error", content: err.message || "Request failed", sources: [] });
        }
        return updated;
      });
    } finally {
      setLoading(false);
    }
  }, [agentMode, loading, uiState]);

  const handleVoiceInput = useCallback((voiceData) => {
    const { userText } = voiceData;
    if (!userText?.trim()) return;
    sendQuestion(userText);
  }, [sendQuestion]);

  async function send(e) {
    e.preventDefault();
    await sendQuestion(input);
  }

  const panelClass =
    uiState === STATES.MAX
      ? "fixed inset-4 z-50 flex flex-col rounded-2xl shadow-2xl border border-sre-border bg-sre-bg"
      : "fixed bottom-20 right-5 z-50 w-[400px] h-[560px] flex flex-col rounded-2xl shadow-2xl border border-sre-border bg-sre-bg";

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={() => setUiState(uiState === STATES.CLOSED ? STATES.OPEN : STATES.CLOSED)}
        className="fixed bottom-5 right-5 z-50 w-13 h-13 bg-sre-accent hover:bg-indigo-500 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105"
        style={{ width: 52, height: 52 }}
        title="Ask the on-call assistant"
      >
        {uiState !== STATES.CLOSED ? (
          <X size={20} />
        ) : (
          <>
            <MessageSquare size={20} />
            {unread > 0 && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-bold">
                {unread}
              </span>
            )}
          </>
        )}
      </button>

      {/* Chat panel */}
      {uiState !== STATES.CLOSED && (
        <div className={panelClass}>
          {/* Header */}
          <div className="flex items-center gap-2.5 px-4 py-3 border-b border-sre-border flex-shrink-0">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 transition-colors ${
              agentMode === "full" ? "bg-emerald-600" : agentMode === "sre" ? "bg-indigo-500" : "bg-sre-accent"
            }`}>
              {agentMode !== "off" ? <Zap size={14} /> : <Bot size={14} />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white leading-none">On-Call Assistant</p>
              <p className="text-xs mt-0.5">
                {agentMode === "full"
                  ? <span className="text-emerald-400 font-medium">Full Agent · runs any command</span>
                  : agentMode === "sre"
                  ? <span className="text-indigo-400 font-medium">SRE Agent · kubectl/helm/git/docker</span>
                  : <span className="text-gray-500">RAG · Mistral 7B · Local</span>}
              </p>
            </div>
            <div className="flex items-center gap-1">
              {/* Agent mode cycle: off → sre → full → off */}
              <button
                onClick={() => setAgentMode(m => m === "off" ? "sre" : m === "sre" ? "full" : "off")}
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded border transition-colors ${
                  agentMode === "full"
                    ? "bg-emerald-700 border-emerald-600 text-white"
                    : agentMode === "sre"
                    ? "bg-indigo-600 border-indigo-500 text-white"
                    : "bg-sre-surface border-sre-border text-gray-400 hover:text-gray-200 hover:border-gray-500"
                }`}
                title={agentMode === "off" ? "Enable SRE agent (kubectl/helm/git/docker)" : agentMode === "sre" ? "Switch to Full agent (any command)" : "Disable agent mode"}
              >
                <Zap size={10} />
                {agentMode === "full" ? "Full" : agentMode === "sre" ? "SRE" : "Agent"}
              </button>
              <button
                onClick={clearSession}
                className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 rounded hover:bg-sre-border transition-colors"
                title="Clear session"
              >
                Clear
              </button>
              <button
                onClick={() => setUiState(uiState === STATES.MAX ? STATES.OPEN : STATES.MAX)}
                className="text-gray-500 hover:text-gray-300 p-1.5 rounded hover:bg-sre-border transition-colors"
                title={uiState === STATES.MAX ? "Restore" : "Maximize"}
              >
                {uiState === STATES.MAX ? <Minus size={14} /> : <Maximize2 size={14} />}
              </button>
              <button
                onClick={() => setUiState(STATES.CLOSED)}
                className="text-gray-500 hover:text-gray-300 p-1.5 rounded hover:bg-sre-border transition-colors"
                title="Close"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                {msg.role !== "error" && (
                  <div className={`w-6 h-6 rounded-full flex-shrink-0 flex items-center justify-center mt-0.5 ${msg.role === "assistant" ? "bg-sre-accent" : "bg-gray-700"}`}>
                    {msg.role === "assistant" ? <Bot size={12} /> : <User size={12} />}
                  </div>
                )}
                <div className={`space-y-1 ${msg.role === "error" ? "w-full" : "max-w-[85%]"}`}>
                  <div className={`rounded-xl px-3 py-2 text-xs ${
                    msg.role === "assistant" ? "bg-sre-surface border border-sre-border text-gray-200"
                    : msg.role === "error" ? "bg-red-950 border border-red-800 text-red-300 w-full"
                    : "bg-sre-accent text-white"
                  }`}>
                    {msg.role === "assistant" ? (
                      <div>
                        {/* ReAct tool-call steps (Full Agent mode) */}
                        {msg.reactSteps?.length > 0 && (
                          <ReactStepsPanel steps={msg.reactSteps} streaming={msg.streaming} />
                        )}
                        <MarkdownBody content={msg.content || " "} agentMode={agentMode} />
                        {msg.streaming && !msg.reactSteps && (
                          <span className="inline-block w-0.5 h-3 bg-gray-400 ml-0.5 align-middle"
                            style={{ animation: "pulse 1s ease-in-out infinite" }} />
                        )}
                      </div>
                    ) : msg.role === "error" ? (
                      `Error: ${msg.content}`
                    ) : (
                      msg.content
                    )}
                  </div>
                  {msg.sources?.length > 0 && (
                    <div className="flex gap-1 flex-wrap pl-1">
                      {msg.sources.map((src, j) => (
                        <span key={j} className="flex items-center gap-1 text-xs text-gray-600 bg-sre-bg border border-sre-border rounded px-1.5 py-0.5">
                          <FileText size={9} />{src}
                        </span>
                      ))}
                    </div>
                  )}
                  {/* AgentRunPanel — SRE mode only (Full mode uses ReAct tool calls instead) */}
                  {msg.role === "assistant" && !msg.streaming && agentMode === "sre" && (() => {
                    const cmds = extractRunnableCommands(msg.content || "");
                    return cmds.length >= 1 ? (
                      <AgentRunPanel
                        commands={cmds}
                        taskContext={msg.content}
                        sessionId={SESSION_ID}
                        fullMode={false}
                        autoRun={true}
                        key={`panel-${i}`}
                      />
                    ) : null;
                  })()}
                </div>
              </div>
            ))}
            {loading && messages[messages.length - 1]?.content === "" && (
              <div className="flex gap-2">
                <div className="w-6 h-6 rounded-full bg-sre-accent flex items-center justify-center flex-shrink-0">
                  <Bot size={12} />
                </div>
                <div className="bg-sre-surface border border-sre-border rounded-xl px-3 py-2 flex items-center gap-1.5 text-xs text-gray-400">
                  <Loader2 size={11} className="animate-spin" /> Thinking...
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input with Voice Support */}
          <div className="px-3 py-3 border-t border-sre-border flex-shrink-0 space-y-3">
            <VoiceButton 
              onVoiceInput={handleVoiceInput}
              disabled={loading}
              sessionId={SESSION_ID}
              enabled={voiceEnabled}
            />
            <form onSubmit={send} className="flex gap-2">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about an alert or runbook..."
                className="flex-1 bg-sre-surface border border-sre-border rounded-lg px-3 py-2 text-xs text-gray-100 placeholder-gray-600 focus:outline-none focus:border-sre-accent"
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="bg-sre-accent hover:bg-indigo-500 disabled:opacity-40 text-white px-3 py-2 rounded-lg transition-colors"
              >
                <Send size={13} />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

// Commands that can be executed via the terminal
const RUNNABLE_RE = /^(helm |kubectl (get|describe|apply|create|rollout|logs|top|version|explain|diff)|git (init|clone|status|log)|docker (build|pull|images|ps))/i;

// Extract runnable commands from markdown content (code blocks only)
function extractRunnableCommands(content) {
  const re = /```(?:[^\n]*)?\n([\s\S]*?)```/g;
  const cmds = [];
  let m;
  while ((m = re.exec(content)) !== null) {
    const code = m[1].trim();
    if (RUNNABLE_RE.test(code)) cmds.push(code);
  }
  return cmds;
}

// Source-code languages — blocks labelled with these are never shell commands
const _SOURCE_LANGS = new Set(["python", "python3", "py", "java", "kotlin", "kt", "go", "rust", "rs", "c", "cpp", "c++", "csharp", "cs"]);

// Detects source code syntax that can't run in bash
const _SOURCE_CODE_RE = /^(from\s+\w|import\s+[\w{]|def\s+\w|class\s+\w+[\s:{(]|if\s+__name__|public\s+(class|interface|enum|static|void|\w)|private\s+\w|protected\s+\w|package\s+\w+\.\w+|func\s+\w+\s*\(|type\s+\w+\s+struct|#include\s+[<"])/m;

// Allowlist: lines must START with one of these to be considered a shell command.
// This is the same approach Claude Code uses for its Bash tool input — whitelist of known entry points.
const _SHELL_CMD_RE = /^(mkdir|rmdir|cd|touch|echo|printf|cat|ls|find|python3?|pip3?|pipx|npm|node|npx|yarn|pnpm|bun|brew|apt(?:-get)?|yum|dnf|apk|pacman|git|docker|kubectl|helm|make|cmake|curl|wget|mv|cp|rm|chmod|chown|ln|stat|file|which|whereis|sudo|sh|bash|zsh|fish|env|export|source|\.|eval|set|unset|kill|pkill|ps|df|du|tar|gzip|gunzip|zip|unzip|ssh|scp|rsync|psql|mysql|redis-cli|mongosh?|terraform|ansible|pulumi|cargo|go|java|javac|mvn|gradle|poetry|conda|pip3?|pytest|jest|mocha|eslint|tsc|rustc|gcc|g\+\+|clang|swift|ruby|rails|bundle|rake|php|composer|dotnet|nuget|open|pbcopy|pbpaste|osascript|defaults|launchctl|systemctl|service|journalctl|crontab|sleep|date|time|timeout|nohup|screen|tmux|watch|less|more|head|tail|grep|sed|awk|sort|uniq|wc|tr|cut|xargs|tee|diff|patch|jq|yq|base64|md5|sha256sum|openssl|ping|curl|nc|netcat|nmap|lsof|netstat|ss|dig|nslookup|strace|ltrace|perf|htop|top|kill|pkill|fuser|at|cron|watch|\.\/|~\/|\/usr\/|\/opt\/|\/home\/|\/tmp\/|\/var\/|\/bin\/|\/sbin\/)/i;

// Extract runnable shell commands from code blocks (Full mode).
// Uses an ALLOWLIST approach: only lines starting with known shell command entry points
// are included. This prevents tree output, sample program output, and prose from
// being treated as commands — the same principle Claude Code uses for its Bash tool.
function extractAllCodeBlocks(content) {
  const re = /```([^\n]*)\n([\s\S]*?)```/g;
  const cmds = [];
  let m;
  while ((m = re.exec(content)) !== null) {
    const lang = m[1].trim().toLowerCase().split(/[\s,]/)[0];
    const rawBlock = m[2];
    if (!rawBlock.trim()) continue;

    // Skip source-code language blocks entirely
    if (_SOURCE_LANGS.has(lang)) continue;

    // Skip config/data blocks (YAML, JSON, HTML)
    const trimmed = rawBlock.trim();
    if (/^[{<\[]/.test(trimmed) || /^(apiVersion|kind|metadata|spec):/.test(trimmed)) continue;

    // If block is source code by content, skip
    if (_SOURCE_CODE_RE.test(trimmed)) continue;

    // Split into per-line commands
    let continuation = "";
    for (const rawLine of rawBlock.split("\n")) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) { continuation = ""; continue; }

      // Handle shell line-continuation backslash (keep building the command)
      if (rawLine.trimEnd().endsWith("\\")) {
        continuation += line.replace(/\\$/, " ");
        continue;
      }

      const cmd = (continuation + line).trim();
      continuation = "";
      if (!cmd) continue;

      // ALLOWLIST: only accept lines that start with a known shell command
      // This filters out: tree output (|----), sample output, greetings, file paths listed as prose
      if (_SHELL_CMD_RE.test(cmd)) {
        cmds.push(cmd);
      }
    }
    // Flush any dangling continuation
    if (continuation.trim() && _SHELL_CMD_RE.test(continuation.trim())) {
      cmds.push(continuation.trim());
    }
  }
  return cmds;
}

// ── ReactStepsPanel ───────────────────────────────────────────────────────────
// Renders live tool-call steps from the ReAct agent (Full Agent mode).
// Shows: tool name + args → result/output — no command extraction needed.

function ReactStepsPanel({ steps, streaming }) {
  const TOOL_ICONS = { bash_execute: "⚡", write_file: "✎", read_file: "📄", list_dir: "📁" };
  const TOOL_LABELS = { bash_execute: "bash", write_file: "write", read_file: "read", list_dir: "ls" };

  return (
    <div className="mb-2 border border-emerald-900 rounded-lg overflow-hidden bg-gray-950">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-950 border-b border-emerald-900">
        <Zap size={10} className="text-emerald-400" />
        <span className="text-[11px] text-emerald-300 font-medium">Full Agent · Tool calls</span>
        {streaming && (
          <span className="ml-auto flex items-center gap-1.5 text-[10px] text-emerald-400">
            <Loader2 size={9} className="animate-spin" />
            working… {steps.length} calls
          </span>
        )}
        {!streaming && <span className="ml-auto text-[10px] text-emerald-600">✓ {steps.length} calls</span>}
      </div>
      <div className="divide-y divide-gray-900">
        {steps.map((s, i) => (
          <div key={i} className="px-3 py-1.5">
            <div className="flex items-center gap-1.5">
              {s.status === "running"
                ? <Loader2 size={9} className="animate-spin text-emerald-400 flex-shrink-0" />
                : s.status === "done"
                  ? <CheckCircle size={9} className="text-green-400 flex-shrink-0" />
                  : <XCircle size={9} className="text-red-400 flex-shrink-0" />
              }
              <span className="text-[9px] text-emerald-500 font-mono">
                {TOOL_ICONS[s.name] || "🔧"} {TOOL_LABELS[s.name] || s.name}
              </span>
              {s.name === "bash_execute" && s.args?.command && (
                <code className="text-[9px] text-green-300 font-mono truncate max-w-[300px]">{s.args.command}</code>
              )}
              {s.name === "write_file" && s.args?.path && (
                <code className="text-[9px] text-blue-300 font-mono">{s.args.path}</code>
              )}
              {(s.name === "read_file" || s.name === "list_dir") && (
                <code className="text-[9px] text-gray-400 font-mono">{s.args?.path || "."}</code>
              )}
            </div>
            {/* Show result summary */}
            {s.result && (
              <div className="ml-4 mt-0.5">
                {s.result.error && (
                  <p className="text-[9px] text-red-400 font-mono">{s.result.error}</p>
                )}
                {s.result.stdout && (
                  <pre className="text-[9px] text-gray-400 font-mono whitespace-pre-wrap max-h-16 overflow-y-auto">{s.result.stdout.slice(0, 300)}</pre>
                )}
                {s.result.stderr && !s.result.stdout && (
                  <pre className="text-[9px] text-yellow-600 font-mono whitespace-pre-wrap max-h-16 overflow-y-auto">{s.result.stderr.slice(0, 300)}</pre>
                )}
                {s.name === "write_file" && s.result.success && (
                  <p className="text-[9px] text-blue-400">Wrote {s.result.bytes_written} bytes → {s.result.path}</p>
                )}
                {s.name === "list_dir" && s.result.entries && (
                  <p className="text-[9px] text-gray-500">{s.result.entries.slice(0, 8).join(", ")}{s.result.entries.length > 8 ? "…" : ""}</p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── AgentRunPanel ─────────────────────────────────────────────────────────────
// Shows a "Run All" button; on click streams the /agent/run-plan endpoint and
// displays live step-by-step execution with auto-fix indicators.

function AgentRunPanel({ commands, taskContext, sessionId, fullMode, autoRun }) {
  const [phase, setPhase]   = useState("idle"); // idle | running | done
  const [steps, setSteps]   = useState([]);     // {step, command, status, lines, fixCmd, fixed}
  const [summary, setSummary] = useState(null);
  const bottomRef = useRef(null);
  const abortRef  = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [steps]);

  // Auto-execute when mounted in agent mode
  useEffect(() => {
    if (autoRun) runAll();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function upsertStep(stepNum, patch) {
    setSteps(prev => {
      const idx = prev.findIndex(s => s.step === stepNum);
      if (idx === -1) return [...prev, { step: stepNum, lines: [], status: "running", command: "", ...patch }];
      const updated = [...prev];
      updated[idx] = { ...updated[idx], ...patch };
      return updated;
    });
  }

  function appendLine(stepNum, line, kind, isFix) {
    setSteps(prev => {
      const idx = prev.findIndex(s => s.step === stepNum);
      if (idx === -1) return prev;
      const updated = [...prev];
      updated[idx] = { ...updated[idx], lines: [...updated[idx].lines, { text: line, kind, isFix }] };
      return updated;
    });
  }

  async function runAll() {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setPhase("running");
    setSteps([]);
    setSummary(null);
    try {
      const resp = await fetch("/api/v1/agent/run-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ commands, task_context: taskContext, session_id: sessionId, full_mode: !!fullMode }),
        signal: ctrl.signal,
      });
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "plan_start") {
              // pre-populate steps as pending
              setSteps(commands.map((cmd, i) => ({ step: i+1, command: cmd, status: "pending", lines: [] })));
            }
            if (ev.type === "step_start") {
              upsertStep(ev.step, { command: ev.command, status: ev.is_fix ? "fixing" : "running" });
            }
            if (ev.type === "stdout") appendLine(ev.step, ev.line, "out", ev.is_fix);
            if (ev.type === "stderr") appendLine(ev.step, ev.line, "err", ev.is_fix);
            if (ev.type === "step_done") upsertStep(ev.step, { status: ev.fixed ? "fixed" : "done" });
            if (ev.type === "step_error") upsertStep(ev.step, { status: "error" });
            if (ev.type === "analyzing") upsertStep(ev.step, { status: "analyzing", analyzeMsg: ev.message });
            if (ev.type === "root_cause") upsertStep(ev.step, { rootCause: ev.root_cause });
            if (ev.type === "fix_applied") upsertStep(ev.step, { fixCmd: ev.fix_command, fixExpl: ev.explanation });
            if (ev.type === "no_fix") upsertStep(ev.step, { status: "failed", fixExpl: ev.explanation });
            if (ev.type === "fix_blocked") upsertStep(ev.step, { status: "failed", fixExpl: ev.reason });
            if (ev.type === "plan_halted") {
              // Mark failed step and skip all remaining steps
              upsertStep(ev.step, { status: "failed" });
              setSteps(prev => prev.map(s =>
                s.step > ev.step ? { ...s, status: "skipped" } : s
              ));
              setSummary({ success: false, succeeded: ev.succeeded, total: ev.total, halted: true, haltReason: ev.reason, haltStep: ev.step });
              setPhase("done");
            }
            if (ev.type === "plan_done") {
              setSummary({ success: ev.success, succeeded: ev.succeeded, total: ev.total });
              setPhase("done");
            }
          } catch (_) {}
        }
      }
    } catch (err) {
      if (err.name === "AbortError") {
        setSummary({ success: false, error: "Stopped by user." });
      } else {
        setSummary({ success: false, error: err.message });
      }
      setPhase("done");
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  const statusIcon = (s) => {
    if (s === "done" || s === "fixed") return <CheckCircle size={11} className="text-green-400 flex-shrink-0" />;
    if (s === "error" || s === "failed") return <XCircle size={11} className="text-red-400 flex-shrink-0" />;
    if (s === "skipped") return <span className="text-[9px] text-gray-600 flex-shrink-0 font-mono">—</span>;
    if (s === "running" || s === "fixing" || s === "analyzing")
      return <Loader2 size={11} className="animate-spin text-indigo-400 flex-shrink-0" />;
    return <ChevronRight size={11} className="text-gray-600 flex-shrink-0" />;
  };

  return (
    <div className="mt-2">
      {phase === "idle" && !autoRun && (
        <button
          onClick={runAll}
          className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-medium px-3 py-1.5 rounded-lg transition-colors"
        >
          <Zap size={11} /> Run All {commands.length} commands {fullMode ? "(Full shell)" : "(SRE)"}
        </button>
      )}

      {(phase !== "idle" || autoRun) && (
        <div className="border border-indigo-900 rounded-lg overflow-hidden bg-gray-950">
          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-indigo-950 border-b border-indigo-900">
            <Zap size={11} className="text-indigo-400" />
            <span className="text-[11px] text-indigo-300 font-medium">
              Agentic Execution {fullMode ? "· Full shell" : "· SRE"}
            </span>
            {phase === "running" && (
              <>
                <Loader2 size={10} className="animate-spin text-indigo-400 ml-auto" />
                <button
                  onClick={stop}
                  className="text-[10px] text-red-400 hover:text-red-300 border border-red-900 hover:border-red-700 rounded px-1.5 py-0.5 ml-1 transition-colors"
                >
                  Stop
                </button>
              </>
            )}
            {phase === "done" && summary && (
              <>
                <span className={`ml-auto text-[10px] font-medium ${summary.success ? "text-green-400" : summary.halted ? "text-orange-400" : "text-red-400"}`}>
                  {summary.error
                    ? summary.error
                    : summary.success
                      ? `✓ All ${summary.total} done`
                      : summary.halted
                        ? `⚠ Halted at step ${summary.haltStep} — ${summary.succeeded}/${summary.total} done`
                        : `${summary.succeeded}/${summary.total} succeeded`}
                </span>
                <button
                  onClick={runAll}
                  className="text-[10px] text-indigo-400 hover:text-indigo-300 border border-indigo-900 hover:border-indigo-700 rounded px-1.5 py-0.5 ml-2 flex items-center gap-1 transition-colors"
                >
                  <RefreshCw size={8} /> Retry
                </button>
              </>
            )}
          </div>

          {/* Steps */}
          <div className="divide-y divide-gray-900">
            {steps.map((s) => (
              <div key={s.step} className={`px-3 py-2 ${s.status === "skipped" ? "opacity-35" : ""}`}>
                {/* Step header */}
                <div className="flex items-start gap-1.5 mb-1">
                  <div className="mt-0.5">{statusIcon(s.status)}</div>
                  <div className="flex-1 min-w-0">
                    <code className={`text-[10px] font-mono break-all ${
                      s.status === "skipped" ? "text-gray-500" : "text-green-300"
                    }`}>{s.command}</code>
                    <div className="flex gap-1.5 mt-0.5">
                      {s.status === "skipped" && (
                        <span className="text-[9px] text-gray-600">skipped — plan halted</span>
                      )}
                      {s.status === "fixed" && (
                        <span className="text-[9px] bg-amber-900 text-amber-300 px-1.5 py-0.5 rounded">auto-fixed</span>
                      )}
                      {s.status === "analyzing" && (
                        <span className="text-[9px] text-indigo-400 flex items-center gap-1">
                          <Loader2 size={8} className="animate-spin" /> Analysing with LLM…
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Root cause reasoning — shown after LLM analysis */}
                {s.rootCause && (
                  <div className="ml-5 mb-1.5 bg-red-950 border border-red-900 rounded px-2 py-1">
                    <p className="text-[9px] text-red-400 font-semibold mb-0.5">Root cause</p>
                    <p className="text-[10px] text-red-300">{s.rootCause}</p>
                  </div>
                )}

                {/* Fix command — amber while running, green only on success */}
                {s.fixCmd && (
                  <div className={`ml-5 mb-1.5 rounded px-2 py-1 border ${
                    s.status === "fixed"
                      ? "bg-green-950 border-green-900"
                      : "bg-amber-950 border-amber-900"
                  }`}>
                    <p className={`text-[9px] font-semibold mb-0.5 ${
                      s.status === "fixed" ? "text-green-400" : "text-amber-400"
                    }`}>
                      {s.status === "fixed" ? "✓ Fix succeeded" : "🔧 Fix attempted"}
                    </p>
                    <code className={`text-[10px] font-mono break-all ${
                      s.status === "fixed" ? "text-green-200" : "text-amber-200"
                    }`}>{s.fixCmd}</code>
                    {s.fixExpl && <p className={`text-[9px] mt-0.5 ${
                      s.status === "fixed" ? "text-green-600" : "text-amber-500"
                    }`}>{s.fixExpl}</p>}
                  </div>
                )}

                {/* No fix available */}
                {s.fixExpl && !s.fixCmd && (
                  <div className="ml-5 mb-1.5 text-[9px] text-gray-500 bg-gray-900 rounded px-2 py-1">
                    {s.fixExpl}
                  </div>
                )}

                {/* Output lines — collapsible by height */}
                {s.lines.length > 0 && (
                  <div className="ml-5 max-h-28 overflow-y-auto bg-black rounded px-2 py-1 mt-0.5">
                    {s.lines.map((l, li) => (
                      <p key={li} className={`text-[10px] font-mono leading-snug ${
                        l.isFix ? "opacity-60 " : ""
                      }${l.kind === "err" ? "text-yellow-400" : "text-green-300"}`}>
                        {l.text}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          {/* Halt banner — shown when plan was stopped due to unrecoverable failure */}
          {summary?.halted && (
            <div className="mx-3 mb-3 mt-1 bg-orange-950 border border-orange-900 rounded px-3 py-2">
              <p className="text-[10px] text-orange-400 font-semibold mb-0.5">
                ⚠ Plan halted at step {summary.haltStep}
              </p>
              <p className="text-[10px] text-orange-300">{summary.haltReason}</p>
              <p className="text-[9px] text-orange-600 mt-1">
                Fix the issue above, then retry the plan.
              </p>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  function copy() { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000); }
  return (
    <button onClick={copy} className="text-gray-500 hover:text-gray-300 flex items-center" title="Copy">
      {copied ? <Check size={11} /> : <Copy size={11} />}
    </button>
  );
}

function CommandBlock({ code, agentMode }) {
  const [phase, setPhase] = useState("idle"); // idle | confirm | running | done | error
  const [output, setOutput] = useState([]);
  const [exitCode, setExitCode] = useState(null);
  const fullMode = agentMode === "full";
  const agentOn  = agentMode !== "off";
  // Full mode uses the same allowlist as extractAllCodeBlocks
  // SRE mode uses the kubectl/helm/git/docker allowlist
  const _c = code.trim();
  const isRunnable = fullMode
    ? _SHELL_CMD_RE.test(_c) && !_SOURCE_CODE_RE.test(_c)
    : RUNNABLE_RE.test(_c);

  async function run() {
    setPhase("running");
    setOutput([]);
    try {
      const resp = await fetch("/api/v1/chat/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: code.trim(), session_id: SESSION_ID, full_mode: fullMode }),
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n"); buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            if (ev.type === "stdout" || ev.type === "stderr")
              setOutput(p => [...p, { kind: ev.type, text: ev.line }]);
            if (ev.type === "done") { setExitCode(ev.exit_code); setPhase(ev.exit_code === 0 ? "done" : "error"); }
            if (ev.type === "error") { setOutput(p => [...p, { kind: "stderr", text: ev.message }]); setPhase("error"); }
          } catch (_) {}
        }
      }
    } catch (err) {
      setOutput(p => [...p, { kind: "stderr", text: err.message }]);
      setPhase("error");
    }
  }

  return (
    <div className="mt-2 mb-2">
      <div className="relative">
        {/* Badge: ⚡ runnable (agent on) | dim badge (agent off) | locked (not in allowlist) */}
        {agentOn && isRunnable && (
          <div className={`absolute -top-2 left-1 z-10 text-white text-[9px] px-1.5 rounded font-mono ${
            fullMode ? "bg-emerald-700" : "bg-indigo-600"
          }`}>
            ⚡ runnable
          </div>
        )}
        {agentOn && !isRunnable && !fullMode && (
          <div className="absolute -top-2 left-1 z-10 bg-gray-800 text-gray-500 text-[9px] px-1.5 rounded font-mono">
            switch to Full mode to run
          </div>
        )}
        {!agentOn && isRunnable && (
          <div className="absolute -top-2 left-1 z-10 bg-gray-700 text-gray-400 text-[9px] px-1.5 rounded font-mono">
            enable Agent ⚡ to run
          </div>
        )}
        <pre className={`bg-gray-900 border rounded p-2 pt-3.5 overflow-x-auto text-xs font-mono text-green-300 leading-relaxed pr-20 ${
          agentOn && isRunnable ? (fullMode ? "border-emerald-900" : "border-indigo-800") : "border-gray-700"
        }`}>
          <code>{code}</code>
        </pre>
        <div className="absolute top-2.5 right-1.5 flex gap-1.5 items-center">
          <CopyButton text={code} />
          {isRunnable && agentOn && phase === "idle" && (
            <button onClick={() => setPhase("confirm")}
              className={`text-white rounded px-1.5 py-0.5 flex items-center gap-1 text-[10px] font-medium transition-colors ${
                fullMode ? "bg-emerald-700 hover:bg-emerald-600" : "bg-indigo-600 hover:bg-indigo-500"
              }`} title="Run this command">
              <Play size={9} /> Run
            </button>
          )}
          {!isRunnable && agentOn && !fullMode && (
            <span className="text-gray-600 text-[10px]" title="Switch to Full mode to run any command">locked</span>
          )}
        </div>
      </div>
      {agentOn && !isRunnable && !fullMode && (
        <p className="text-[10px] text-gray-600 mt-0.5 pl-1">
          SRE mode: <span className="text-gray-500">kubectl · helm · git · docker</span> only — switch to <span className="text-emerald-600">Full</span> mode for any command
        </p>
      )}

      {/* Approval modal */}
      {phase === "confirm" && (
        <div className="mt-1.5 bg-yellow-950 border border-yellow-700 rounded p-2 text-xs">
          <div className="flex items-center gap-1.5 text-yellow-400 mb-2">
            <AlertTriangle size={11} /> <span className="font-semibold">Run this command?</span>
          </div>
          <div className="flex gap-2">
            <button onClick={run}
              className="bg-indigo-600 hover:bg-indigo-500 text-white px-2.5 py-1 rounded text-xs transition-colors">
              ✓ Approve &amp; Run
            </button>
            <button onClick={() => setPhase("idle")}
              className="text-gray-400 hover:text-gray-200 px-2 py-1 rounded text-xs transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Terminal output */}
      {(phase === "running" || phase === "done" || phase === "error") && (
        <div className="mt-1.5 bg-black border border-gray-800 rounded p-2">
          <div className="flex items-center gap-1.5 text-gray-500 text-xs mb-1.5 border-b border-gray-800 pb-1">
            <Terminal size={10} />
            <span>Terminal output</span>
            {phase === "running" && <Loader2 size={10} className="animate-spin ml-auto" />}
            {phase === "done"    && <span className="ml-auto text-green-400">exit 0</span>}
            {phase === "error"   && <span className="ml-auto text-red-400">exit {exitCode ?? "err"}</span>}
          </div>
          <div className="max-h-40 overflow-y-auto space-y-0.5">
            {output.map((l, i) => (
              <p key={i} className={`text-xs font-mono leading-relaxed ${l.kind === "stderr" ? "text-yellow-400" : "text-green-300"}`}>
                {l.text}
              </p>
            ))}
            {phase === "running" && output.length === 0 && (
              <p className="text-xs text-gray-600 font-mono">Running...</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function MarkdownBody({ content, agentMode }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      code({ inline, children }) {
        const code = String(children).replace(/\n$/, "");
        if (inline) return <code className="bg-gray-800 text-green-300 rounded px-1 text-xs font-mono">{code}</code>;
        return <CommandBlock code={code} agentMode={agentMode} />;
      },
      h1: ({ children }) => <p className="font-bold text-white mt-2 mb-1 text-xs">{children}</p>,
      h2: ({ children }) => <p className="font-bold text-white mt-2 mb-1 text-xs">{children}</p>,
      h3: ({ children }) => <p className="font-semibold text-gray-300 mt-1.5 mb-0.5 text-xs uppercase tracking-wide">{children}</p>,
      ul: ({ children }) => <ul className="list-disc list-inside space-y-0.5 my-1 text-gray-300">{children}</ul>,
      ol: ({ children }) => <ol className="list-decimal list-inside space-y-0.5 my-1 text-gray-300">{children}</ol>,
      li: ({ children }) => <li className="text-xs">{children}</li>,
      p: ({ children }) => <p className="mb-1.5 last:mb-0 text-gray-200 leading-relaxed text-xs">{children}</p>,
      strong: ({ children }) => <strong className="text-white font-semibold">{children}</strong>,
    }}>
      {content}
    </ReactMarkdown>
  );
}
