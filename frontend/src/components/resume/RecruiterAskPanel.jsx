import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { Send, Loader2, Sparkles, ShieldCheck, Briefcase, FlaskConical, Minimize2, ChevronUp, ChevronDown, Copy, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  VERIFIED_EMPLOYER_NAMES,
} from "../../data/resumeContent.js";
import {
  detectQuestionTopic,
  followUpSectionLabel,
  getThoughtMood,
  pickFollowUpChips,
  sanitizeRecruiterAnswer,
  buildHiringManagerBrief,
  JD_FIT_QUESTION_TEMPLATE,
} from "../../utils/recruiterFollowUps.js";
import NareshAnimatedAvatar from "./NareshAnimatedAvatar.jsx";
import NareshThinkingSpeech from "./NareshThinkingSpeech.jsx";
import { RecruiterChatWelcome } from "./RecruiterChatWelcome.jsx";

const DELAY_THOUGHT_PATTERN =
  /\b(?:sorry|taking a min|almost there|still pulling|still cross|still mapping|still separating|still keeping|still pulling real)\b/i;

function resolveLoadingPhase({ streaming, hasContent, justCompleted, thoughtLine = "" }) {
  if (justCompleted) return "complete";
  if (streaming && hasContent) return "streaming";
  if (streaming && !hasContent) {
    if (DELAY_THOUGHT_PATTERN.test(thoughtLine)) return "delay";
    return "thinking";
  }
  return "idle";
}

const VIEW_MODES = { CLOSED: "closed", MAXIMIZED: "maximized" };
const VIEW_MODE_STORAGE_KEY = "sreai.recruiterChatView";

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function LivePulse({ active = false }) {
  return (
    <span className={`relative flex h-2 w-2 shrink-0 ${active ? "recruiter-live-pulse--active" : ""}`}>
      <span className="recruiter-live-ping animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-60" />
      <span className="recruiter-live-dot relative inline-flex rounded-full h-2 w-2 bg-teal-400" />
    </span>
  );
}

function HumanThoughtIndicator({ question, onThoughtLineChange }) {
  return (
    <NareshThinkingSpeech question={question} onThoughtLineChange={onThoughtLineChange} />
  );
}

const SECTIONS_WITH_VISIBLE_HEADERS = new Set(["glance", "employer", "portfolio", "honest"]);

const SECTION_DEFS = [
  {
    type: "opening",
    pattern: /(?:^|\n)\s*(?:\d+\.\s*)?\*\*Opening\*\*/i,
    label: "Opening",
    strip: /^\s*(?:\d+\.\s*)?\*\*Opening\*\*\s*(?:[—–\-])?\s*/i,
  },
  {
    type: "glance",
    pattern: /(?:^|\n)\s*(?:\d+\.\s*)?\*\*At a glance\*\*/i,
    label: "At a glance",
    strip: /^\s*(?:\d+\.\s*)?\*\*At a glance\*\*\s*(?:[—–\-])?\s*/i,
  },
  {
    type: "employer",
    pattern: /(?:^|\n)\s*(?:\d+\.\s*)?\*\*Where I've applied this\*\*/i,
    label: "Where I've applied this",
    strip: /^\s*(?:\d+\.\s*)?\*\*Where I've applied this\*\*\s*(?:[—–\-])?\s*/i,
  },
  {
    type: "portfolio",
    pattern: /(?:^|\n)\s*(?:\d+\.\s*)?\*\*Personal R&D project[^*]*\*\*/i,
    label: "Personal R&D project",
    strip: /^\s*(?:\d+\.\s*)?\*\*Personal R&D project[^*]*\*\*\s*(?:[—–\-:])?\s*/i,
  },
  {
    type: "honest",
    pattern: /(?:^|\n)\s*(?:\d+\.\s*)?\*\*Honest note[^*]*\*\*/i,
    label: "Honest note",
    strip: /^\s*(?:\d+\.\s*)?\*\*Honest note[^*]*\*\*\s*(?:[—–\-])?\s*/i,
  },
  {
    type: "closing",
    pattern: /(?:^|\n)\s*(?:\d+\.\s*)?\*\*Closing\*\*/i,
    label: "Closing",
    strip: /^\s*(?:\d+\.\s*)?\*\*Closing\*\*\s*(?:[—–\-])?\s*/i,
  },
];

const EMPLOYER_PATTERN = new RegExp(
  `\\b(${VERIFIED_EMPLOYER_NAMES.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\b`,
  "gi"
);

function stripSectionHeader(content, sectionDef) {
  if (!sectionDef?.strip) return content.trim();
  return content.replace(sectionDef.strip, "").trim();
}

function parseRecruiterSections(content) {
  if (!content?.trim()) return [{ type: "default", body: content || "" }];

  const markers = [];
  for (const def of SECTION_DEFS) {
    const match = content.match(def.pattern);
    if (match && match.index != null) {
      markers.push({ index: match.index, type: def.type, def });
    }
  }

  if (markers.length === 0) {
    return [{ type: "default", body: content.trim() }];
  }

  markers.sort((a, b) => a.index - b.index);

  const sections = [];
  if (markers[0].index > 0) {
    const preamble = content.slice(0, markers[0].index).trim();
    if (preamble) sections.push({ type: "default", body: preamble });
  }

  for (let i = 0; i < markers.length; i += 1) {
    const start = markers[i].index;
    const end = i + 1 < markers.length ? markers[i + 1].index : content.length;
    const raw = content.slice(start, end).trim();
    sections.push({
      type: markers[i].type,
      body: stripSectionHeader(raw, markers[i].def),
      label: markers[i].def.label,
    });
  }

  return sections;
}

function highlightEmployerText(text) {
  if (typeof text !== "string") return text;
  const parts = text.split(EMPLOYER_PATTERN);
  if (parts.length <= 1) return text;
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <span key={`${part}-${i}`} className="recruiter-employer-name">
        {part}
      </span>
    ) : (
      part
    )
  );
}

function createMarkdownComponents({ highlightEmployers = false } = {}) {
  return {
    p: ({ children }) => (
      <p className="recruiter-msg-p">{highlightEmployers ? mapChildren(children, highlightEmployerText) : children}</p>
    ),
    li: ({ children }) => (
      <li className="recruiter-msg-li">{highlightEmployers ? mapChildren(children, highlightEmployerText) : children}</li>
    ),
    strong: ({ children }) => {
      const text = flattenText(children);
      const isEmployer = VERIFIED_EMPLOYER_NAMES.some(
        (name) => text.toLowerCase() === name.toLowerCase() || text.toLowerCase().startsWith(`${name.toLowerCase()}:`)
      );
      if (isEmployer) {
        return <span className="recruiter-employer-name">{children}</span>;
      }
      return <strong className="recruiter-msg-strong">{children}</strong>;
    },
    ul: ({ children }) => <ul className="recruiter-msg-ul">{children}</ul>,
    ol: ({ children }) => <ol className="recruiter-msg-ol">{children}</ol>,
    h3: ({ children }) => <h3 className="recruiter-msg-h3">{children}</h3>,
    hr: () => <hr className="recruiter-msg-hr" />,
  };
}

function flattenText(node) {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(flattenText).join("");
  if (node?.props?.children) return flattenText(node.props.children);
  return "";
}

function mapChildren(children, fn) {
  if (typeof children === "string") return fn(children);
  if (Array.isArray(children)) return children.map((c, i) => (typeof c === "string" ? fn(c) : c));
  return children;
}

function SectionBadge({ type }) {
  if (type === "employer") {
    return (
      <span className="recruiter-section-badge recruiter-section-badge--employer">
        <ShieldCheck size={11} className="shrink-0" />
        Verified from resume
      </span>
    );
  }
  if (type === "portfolio") {
    return (
      <span className="recruiter-section-badge recruiter-section-badge--portfolio">
        <FlaskConical size={11} className="shrink-0" />
        Personal R&D · not employer work
      </span>
    );
  }
  return null;
}

/** Strip trailing partial markdown so streaming text reads cleanly (no jumbled `**`). */
function softenStreamingMarkdown(text) {
  if (!text) return "";
  let out = text;
  // Drop incomplete bold opener at end: "...word **partial"
  out = out.replace(/\*\*[^*\n]{0,80}$/, (m) => m.replace(/\*\*/g, ""));
  // Drop lone asterisk at end
  out = out.replace(/\*(?=[^\*]*$)/, "");
  return out;
}

function StreamingText({ content }) {
  const display = useMemo(() => softenStreamingMarkdown(content), [content]);
  return (
    <div className="recruiter-streaming-text" aria-live="polite" aria-busy="true">
      <p className="recruiter-streaming-body">{display}</p>
      <span
        className="recruiter-streaming-cursor"
        aria-hidden="true"
      />
    </div>
  );
}

function RecruiterMessageContent({ content, streaming, justFormatted }) {
  const defaultComponents = useMemo(() => createMarkdownComponents(), []);
  const employerComponents = useMemo(() => createMarkdownComponents({ highlightEmployers: true }), []);
  const sections = useMemo(() => parseRecruiterSections(content), [content]);

  if (streaming) {
    return <StreamingText content={content} />;
  }

  return (
    <div className={`recruiter-message ${justFormatted ? "recruiter-message--revealed" : ""}`}>
      {sections.map((section, idx) => {
        const sectionClass = section.type === "default" ? "recruiter-msg-default" : `recruiter-msg-${section.type}`;
        const components =
          section.type === "employer" || section.type === "glance"
            ? employerComponents
            : defaultComponents;

        return (
          <div key={`${section.type}-${idx}`} className={`recruiter-msg-section ${sectionClass}`}>
            {section.label && SECTIONS_WITH_VISIBLE_HEADERS.has(section.type) && (
              <div className="recruiter-msg-section-head">
                <SectionBadge type={section.type} />
                {section.type === "employer" && (
                  <Briefcase size={13} className="recruiter-section-icon recruiter-section-icon--employer shrink-0" />
                )}
                {section.type === "portfolio" && (
                  <Sparkles size={13} className="recruiter-section-icon recruiter-section-icon--portfolio shrink-0" />
                )}
                <span className="recruiter-msg-section-title">{section.label}</span>
              </div>
            )}
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
              {section.body || " "}
            </ReactMarkdown>
          </div>
        );
      })}
    </div>
  );
}

function UserAvatar() {
  return (
    <div className="w-7 h-7 rounded-full bg-gradient-to-br from-sky-500/30 to-indigo-600/35 border border-sky-400/25 flex items-center justify-center shrink-0 mt-0.5">
      <span className="text-[9px] font-bold text-sky-100">You</span>
    </div>
  );
}

const ChatBubble = function ChatBubble({ message, onLiveThoughtChange, onCopyBrief, copyBriefLabel }) {
  const isUser = message.role === "user";
  const [liveThoughtLine, setLiveThoughtLine] = useState("");

  const handleThoughtLineChange = useCallback(
    (line) => {
      setLiveThoughtLine(line);
      onLiveThoughtChange?.(line);
    },
    [onLiveThoughtChange]
  );

  useEffect(() => {
    if (!message.streaming || message.content) {
      setLiveThoughtLine("");
    }
  }, [message.streaming, message.content, message.id]);

  const loadingPhase = useMemo(
    () =>
      resolveLoadingPhase({
        streaming: message.streaming,
        hasContent: Boolean(message.content),
        justCompleted: message.justCompleted,
        thoughtLine: liveThoughtLine,
      }),
    [message.streaming, message.content, message.justCompleted, liveThoughtLine]
  );

  if (isUser) {
    return (
      <div
        data-message-id={message.id}
        className="recruiter-chat-turn flex flex-row-reverse gap-2.5 sm:gap-3 animate-[recruiter-chip-pop_0.35s_ease-out]"
      >
        <UserAvatar />
        <div className="max-w-[88%] sm:max-w-[78%]">
          <div className="rounded-2xl rounded-tr-sm px-4 py-3 recruiter-user-bubble text-stone-50 text-[0.9375rem] leading-[1.6]">
            {message.content}
          </div>
          {message.timestamp && (
            <p className="text-[10px] text-stone-500 mt-1.5 text-right">{formatTime(message.timestamp)}</p>
          )}
        </div>
      </div>
    );
  }

  const bubbleClass = [
    "rounded-2xl rounded-tl-sm recruiter-chat-bubble shadow-sm",
    message.streaming && !message.content ? "recruiter-chat-bubble--thinking px-3 py-2.5" : "px-3.5 py-3 sm:px-4 sm:py-3.5",
    message.justCompleted ? "recruiter-chat-bubble--success" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const isThinkingOnly = message.streaming && !message.content;

  return (
    <div
      data-message-id={message.id}
      className="recruiter-chat-turn flex gap-2.5 sm:gap-3 animate-[recruiter-chip-pop_0.35s_ease-out]"
    >
      {!isThinkingOnly && (
        <NareshAnimatedAvatar
          size="sm"
          question={message.replyToQuestion || ""}
          thoughtLine={liveThoughtLine}
          loadingPhase={loadingPhase}
          live={message.streaming}
        />
      )}
      <div className="max-w-[95%] sm:max-w-[90%] space-y-2 min-w-0">
        <div className={bubbleClass}>
          {isThinkingOnly ? (
            <HumanThoughtIndicator
              question={message.replyToQuestion || ""}
              onThoughtLineChange={handleThoughtLineChange}
            />
          ) : (
            <RecruiterMessageContent
              content={message.content}
              streaming={message.streaming}
              justFormatted={message.justFormatted}
            />
          )}
        </div>
        {message.timestamp && !message.streaming && (
          <div className="flex items-center gap-2 pl-1">
            <p className="text-[10px] text-stone-500">{formatTime(message.timestamp)}</p>
            {onCopyBrief && message.content && (
              <button
                type="button"
                onClick={onCopyBrief}
                className="inline-flex items-center gap-1 text-[10px] font-medium text-teal-400/90 hover:text-teal-300 transition-colors"
                title="Copy hiring manager brief"
              >
                {copyBriefLabel === "copied" ? <Check size={11} /> : <Copy size={11} />}
                {copyBriefLabel === "copied" ? "Copied" : "Copy HM brief"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SuggestedChip({ children, onClick, disabled, variant = "primary", style, className = "" }) {
  const base =
    "recruiter-chip text-left disabled:opacity-45 disabled:cursor-not-allowed max-w-full border rounded-xl leading-snug";
  const styles =
    variant === "primary"
      ? "text-[12px] px-3.5 py-2.5 border-teal-500/20 bg-recruiter-slate/60 text-stone-300 hover:text-stone-100 hover:border-teal-400/35 hover:bg-teal-950/30 sm:max-w-[300px]"
      : "text-[11px] px-2.5 py-2 border-violet-500/15 bg-recruiter-navy/50 text-stone-400 hover:text-stone-200 hover:border-violet-400/30 hover:bg-violet-950/25";
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      style={style}
      className={`${base} ${styles} ${className}`}
    >
      {variant === "primary" && (
        <Sparkles size={12} className="inline mr-1.5 text-teal-400/85 -mt-0.5" />
      )}
      {children}
    </button>
  );
}

function readStoredViewMode() {
  return VIEW_MODES.CLOSED;
}

export function RecruiterAskPanel({ onEngaged, onLoadingChange }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState(readStoredViewMode);
  const [followUpRotation, setFollowUpRotation] = useState(0);
  const [lastFollowUps, setLastFollowUps] = useState([]);
  const [showScrollToLatest, setShowScrollToLatest] = useState(false);
  const [scrollHint, setScrollHint] = useState("latest");
  const [showEarlierMessages, setShowEarlierMessages] = useState(false);
  const [copyBriefState, setCopyBriefState] = useState("idle");
  const [liveThoughtLine, setLiveThoughtLine] = useState("");
  const inputRef = useRef(null);
  const abortRef = useRef(null);
  const chatRef = useRef(null);
  const scrollRafRef = useRef(null);
  const streamTextRef = useRef("");
  const streamFlushRafRef = useRef(null);
  const streamLastPaintRef = useRef(0);
  const scrollThrottleRef = useRef(0);
  const stickToBottomRef = useRef(false);
  const replyAnchorRef = useRef(null);

  const SCROLL_PIN_THRESHOLD = 96;
  const REPLY_START_TOLERANCE = 80;

  const scrollToMessageStart = useCallback((messageId, behavior = "auto") => {
    const container = chatRef.current;
    if (!container || !messageId) return;
    const el = container.querySelector(`[data-message-id="${messageId}"]`);
    if (!el) return;
    const containerRect = container.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    const targetTop = elRect.top - containerRect.top + container.scrollTop - 12;
    container.scrollTo({ top: Math.max(0, targetTop), behavior });
    stickToBottomRef.current = false;
  }, []);

  const isReadingReplyFromStart = useCallback(() => {
    const container = chatRef.current;
    const anchorId = replyAnchorRef.current;
    if (!container || !anchorId) return true;
    const el = container.querySelector(`[data-message-id="${anchorId}"]`);
    if (!el) return true;
    const containerRect = container.getBoundingClientRect();
    const elRect = el.getBoundingClientRect();
    const anchorScrollTop = elRect.top - containerRect.top + container.scrollTop;
    return container.scrollTop <= anchorScrollTop + REPLY_START_TOLERANCE;
  }, []);

  const isNearBottom = useCallback((el) => {
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight <= SCROLL_PIN_THRESHOLD;
  }, []);

  const forceScrollToBottom = useCallback(() => {
    const el = chatRef.current;
    if (!el) return;
    stickToBottomRef.current = true;
    el.scrollTop = el.scrollHeight;
  }, []);

  const scrollChatToBottomIfPinned = useCallback(() => {
    const el = chatRef.current;
    if (!el || !stickToBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, []);

  const askedQuestions = useMemo(
    () => messages.filter((m) => m.role === "user").map((m) => m.content),
    [messages]
  );

  const lastUserQuestion = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "user") return messages[i].content;
    }
    return "";
  }, [messages]);

  const lastAssistantAnswer = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant" && !messages[i].streaming && messages[i].content) {
        return messages[i].content;
      }
    }
    return "";
  }, [messages]);

  const followUpTopic = useMemo(
    () => detectQuestionTopic(lastUserQuestion),
    [lastUserQuestion]
  );

  const activeStreamingMessage = useMemo(
    () => messages.find((m) => m.role === "assistant" && m.streaming) || null,
    [messages]
  );

  const headerLoadingPhase = useMemo(
    () =>
      resolveLoadingPhase({
        streaming: loading,
        hasContent: Boolean(activeStreamingMessage?.content),
        justCompleted: false,
        thoughtLine: liveThoughtLine,
      }),
    [loading, activeStreamingMessage?.content, liveThoughtLine]
  );

  const handleLiveThoughtChange = useCallback((line) => {
    setLiveThoughtLine(line);
  }, []);

  useEffect(() => {
    if (!loading) setLiveThoughtLine("");
  }, [loading]);

  const inputPlaceholder = loading
    ? "Waiting for Naresh's reply…"
    : "Paste a job description or ask about client experience…";

  const lastTurnStartIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "user") return i;
    }
    return 0;
  }, [messages]);

  const hiddenEarlierCount = lastTurnStartIndex;
  const visibleMessages = useMemo(() => {
    if (showEarlierMessages || hiddenEarlierCount === 0) return messages;
    return messages.slice(lastTurnStartIndex);
  }, [messages, showEarlierMessages, hiddenEarlierCount, lastTurnStartIndex]);

  const lastCompletedAssistant = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      const m = messages[i];
      if (m.role === "assistant" && !m.streaming && m.content) return m;
    }
    return null;
  }, [messages]);

  const isMultilineInput = question.includes("\n") || question.length > 120;

  useEffect(() => {
    setShowEarlierMessages(false);
  }, [lastTurnStartIndex]);

  const handleCopyBrief = useCallback(async (assistantMsg) => {
    const userQ =
      assistantMsg.replyToQuestion ||
      (() => {
        const idx = messages.findIndex((m) => m.id === assistantMsg.id);
        for (let i = idx - 1; i >= 0; i -= 1) {
          if (messages[i].role === "user") return messages[i].content;
        }
        return lastUserQuestion;
      })();
    const brief = buildHiringManagerBrief(userQ, assistantMsg.content);
    try {
      await navigator.clipboard.writeText(brief);
      setCopyBriefState(assistantMsg.id);
      window.setTimeout(() => setCopyBriefState("idle"), 2000);
    } catch {
      setCopyBriefState("error");
      window.setTimeout(() => setCopyBriefState("idle"), 2000);
    }
  }, [messages, lastUserQuestion]);

  const fillJdTemplate = useCallback(() => {
    setQuestion(JD_FIT_QUESTION_TEMPLATE);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  useEffect(() => {
    if (loading || !lastUserQuestion || !lastAssistantAnswer) return;
    const chips = pickFollowUpChips({
      lastQuestion: lastUserQuestion,
      lastAnswer: lastAssistantAnswer,
      askedQuestions,
      rotationIndex: followUpRotation,
      count: 3,
    });
    setLastFollowUps(chips);
  }, [loading, lastUserQuestion, lastAssistantAnswer, askedQuestions, followUpRotation]);

  const isMaximized = viewMode === VIEW_MODES.MAXIMIZED;
  const isClosed = viewMode === VIEW_MODES.CLOSED;
  const hasConversation = messages.length > 0;

  const openChat = useCallback(() => setViewMode(VIEW_MODES.MAXIMIZED), []);
  const closeChat = useCallback(() => setViewMode(VIEW_MODES.CLOSED), []);

  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(VIEW_MODE_STORAGE_KEY, viewMode);
    } catch (_) {}
  }, [viewMode]);

  useEffect(() => {
    if (!isMaximized) return undefined;
    const onKeyDown = (e) => {
      if (e.key === "Escape") closeChat();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isMaximized, closeChat]);

  useEffect(() => {
    if (!isMaximized) return undefined;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [isMaximized]);

  useEffect(() => {
    const el = chatRef.current;
    if (!el) return undefined;

    const onScroll = () => {
      const streaming = messages.some((m) => m.streaming);
      if (streaming && replyAnchorRef.current) {
        const atReplyStart = isReadingReplyFromStart();
        setScrollHint("start");
        setShowScrollToLatest(!atReplyStart);
        stickToBottomRef.current = false;
        return;
      }
      const pinned = isNearBottom(el);
      stickToBottomRef.current = pinned;
      setScrollHint("latest");
      setShowScrollToLatest(!pinned && messages.length > 0);
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [loading, messages, isNearBottom, isReadingReplyFromStart]);

  useEffect(() => {
    const isStreaming = messages.some((m) => m.streaming);
    if (isStreaming) {
      setShowScrollToLatest(false);
      return undefined;
    }

    if (!stickToBottomRef.current) {
      return undefined;
    }

    const now = Date.now();
    if (now - scrollThrottleRef.current < 140) {
      return undefined;
    }
    scrollThrottleRef.current = now;

    if (scrollRafRef.current) {
      window.cancelAnimationFrame(scrollRafRef.current);
    }
    scrollRafRef.current = window.requestAnimationFrame(() => {
      scrollChatToBottomIfPinned();
      scrollRafRef.current = null;
    });
    return () => {
      if (scrollRafRef.current) {
        window.cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, [messages, scrollChatToBottomIfPinned, loading]);

  const ask = useCallback(async (q) => {
    const trimmed = q.trim();
    if (!trimmed || loading) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const now = new Date();
    const assistantId = `assistant-${Date.now()}`;
    const openingFirstQuestion = messages.length === 0;

    setQuestion("");
    onEngaged?.();
    if (openingFirstQuestion) {
      setViewMode(VIEW_MODES.MAXIMIZED);
    }
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", content: trimmed, timestamp: now },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: now,
        streaming: true,
        sources: [],
        replyToQuestion: trimmed,
      },
    ]);
    setLoading(true);
    setLiveThoughtLine("");
    streamTextRef.current = "";
    stickToBottomRef.current = false;
    replyAnchorRef.current = assistantId;
    setShowScrollToLatest(false);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => scrollToMessageStart(assistantId));
    });

    const scheduleStreamFlush = (assistantId) => {
      if (streamFlushRafRef.current != null) return;
      streamFlushRafRef.current = window.requestAnimationFrame((now) => {
        streamFlushRafRef.current = null;
        if (now - streamLastPaintRef.current < 90) {
          scheduleStreamFlush(assistantId);
          return;
        }
        streamLastPaintRef.current = now;
        const snapshot = streamTextRef.current;
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: snapshot } : m))
        );
      });
    };

    try {
      const res = await fetch("/api/v1/recruiter/ask/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        let errorContent =
          "Sorry — I couldn't connect just now. Make sure the backend and Ollama are running, or email me directly from this page.";
        if (res.status === 422) {
          try {
            const errBody = await res.json();
            const tooLong = errBody?.detail?.find?.(
              (d) => d?.type === "string_too_long" && d?.loc?.includes?.("question")
            );
            if (tooLong) {
              errorContent =
                "That message is too long for one request — try pasting a shorter job description or summarize the top requirements.";
            }
          } catch {
            /* ignore parse errors */
          }
        }
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: errorContent,
                  streaming: false,
                }
              : m
          )
        );
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let text = "";
      let sources = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.token) {
              text += data.token;
              streamTextRef.current = text;
              scheduleStreamFlush(assistantId);
            }
            if (data.done) {
              if (Array.isArray(data.sources)) {
                sources = data.sources;
              }
              if (typeof data.content === "string" && data.content.trim()) {
                text = data.content;
                streamTextRef.current = text;
              }
              if (streamFlushRafRef.current != null) {
                window.cancelAnimationFrame(streamFlushRafRef.current);
                streamFlushRafRef.current = null;
              }
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: streamTextRef.current } : m
                )
              );
            }
          } catch (_) {}
        }
      }

      if (streamFlushRafRef.current != null) {
        window.cancelAnimationFrame(streamFlushRafRef.current);
        streamFlushRafRef.current = null;
      }

      const finalContent = sanitizeRecruiterAnswer(text, trimmed);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: finalContent,
                streaming: false,
                sources,
                timestamp: new Date(),
                justCompleted: true,
                justFormatted: true,
              }
            : m
        )
      );
      setFollowUpRotation((i) => i + 1);
      window.setTimeout(() => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, justCompleted: false, justFormatted: false } : m
          )
        );
      }, 1300);
    } catch (err) {
      if (err.name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: "Connection interrupted — try again, or reach out via email on this page.",
                  streaming: false,
                }
              : m
          )
        );
      }
    } finally {
      replyAnchorRef.current = null;
      setLoading(false);
    }
  }, [loading, onEngaged, forceScrollToBottom, messages.length, scrollToMessageStart]);

  useEffect(() => {
    const onOpen = () => openChat();
    const onClose = () => closeChat();
    const onQuickAsk = (e) => {
      openChat();
      const q = e.detail?.question?.trim();
      if (q) window.setTimeout(() => ask(q), 0);
    };
    const onJdTemplate = () => {
      openChat();
      window.setTimeout(() => fillJdTemplate(), 0);
    };
    window.addEventListener("sre-recruiter-open", onOpen);
    window.addEventListener("sre-recruiter-close", onClose);
    window.addEventListener("sre-recruiter-quick-ask", onQuickAsk);
    window.addEventListener("sre-recruiter-jd-template", onJdTemplate);
    return () => {
      window.removeEventListener("sre-recruiter-open", onOpen);
      window.removeEventListener("sre-recruiter-close", onClose);
      window.removeEventListener("sre-recruiter-quick-ask", onQuickAsk);
      window.removeEventListener("sre-recruiter-jd-template", onJdTemplate);
    };
  }, [ask, closeChat, fillJdTemplate, openChat]);

  const panelHeightClass = isMaximized
    ? "h-full min-h-0"
    : "h-[min(520px,calc(100svh-13rem))] sm:h-[min(580px,calc(100svh-12rem))]";

  const renderPanel = () => (
    <div
      className={`panel-card recruiter-panel-card overflow-hidden flex flex-col ${panelHeightClass} transition-shadow duration-300 ${
        loading ? "recruiter-panel-card--loading" : ""
      } ${isMaximized ? "recruiter-panel-card--maximized" : ""}`}
    >
      <div
        className={`border-b border-teal-500/12 bg-gradient-to-r from-teal-950/20 via-transparent to-violet-950/15 flex items-center gap-3 shrink-0 ${
          hasConversation ? "recruiter-panel-header--compact px-4 py-2.5" : "px-5 py-4 items-start"
        }`}
      >
        <div className="relative shrink-0">
          <NareshAnimatedAvatar
            size={hasConversation ? "sm" : "md"}
            question={lastUserQuestion}
            thoughtLine={liveThoughtLine}
            loadingPhase={headerLoadingPhase}
            live
          />
          <span className="absolute -bottom-0.5 -right-0.5 z-[1]">
            <LivePulse active={loading} />
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className={`font-semibold text-stone-100 ${hasConversation ? "text-sm" : "text-base"}`}>
              Ask Naresh's AI
            </h2>
            <span
              className={`inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full border transition-colors ${
                loading
                  ? "border-teal-400/45 bg-teal-950/50 text-teal-200"
                  : "border-emerald-500/35 bg-emerald-950/40 text-emerald-200/90"
              }`}
            >
              <LivePulse active={loading} />
              Live
            </span>
            {hasConversation && (
              <span className="text-[10px] text-stone-500 hidden sm:inline">
                Verified profile · first person
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-0.5 shrink-0 -mt-0.5 -mr-1">
          <button
            type="button"
            onClick={closeChat}
            className="recruiter-panel-control"
            aria-label="Close chat"
            title="Close"
          >
            <Minimize2 size={16} />
          </button>
        </div>
      </div>

      <div className="relative flex-1 min-h-0 flex flex-col recruiter-chat-body">
      <div
        ref={chatRef}
        className={`flex-1 min-h-0 overflow-y-auto overscroll-y-contain px-3 sm:px-5 py-4 sm:py-5 space-y-4 recruiter-chat-scroll transition-colors ${
          loading ? "bg-teal-950/5" : ""
        }`}
      >
        {hiddenEarlierCount > 0 && !showEarlierMessages && (
          <button
            type="button"
            onClick={() => setShowEarlierMessages(true)}
            className="w-full text-center text-[11px] font-medium text-stone-500 hover:text-teal-300 py-1.5 rounded-lg border border-dashed border-stone-700/50 hover:border-teal-500/30 transition-colors"
          >
            Show {hiddenEarlierCount} earlier message{hiddenEarlierCount === 1 ? "" : "s"}
          </button>
        )}
        {messages.length === 0 ? (
          <RecruiterChatWelcome
            onAsk={ask}
            onJdTemplate={fillJdTemplate}
            loading={loading}
          />
        ) : (
          visibleMessages.map((msg) => (
            <ChatBubble
              key={msg.id}
              message={msg}
              onLiveThoughtChange={
                msg.streaming && !msg.content ? handleLiveThoughtChange : undefined
              }
              onCopyBrief={
                !msg.streaming && msg.content && msg.id === lastCompletedAssistant?.id
                  ? () => handleCopyBrief(msg)
                  : undefined
              }
              copyBriefLabel={copyBriefState === msg.id ? "copied" : "idle"}
            />
          ))
        )}
      </div>
      {showScrollToLatest && (
        <button
          type="button"
          onClick={() => {
            if (scrollHint === "start" && replyAnchorRef.current) {
              scrollToMessageStart(replyAnchorRef.current, "smooth");
            } else {
              forceScrollToBottom();
            }
          }}
          className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium text-stone-200 bg-stone-900/95 border border-teal-500/30 shadow-lg shadow-black/30 hover:border-teal-400/45 hover:bg-stone-800/95 transition-colors"
          aria-label={scrollHint === "start" ? "Back to start of reply" : "Jump to latest message"}
        >
          {scrollHint === "start" ? (
            <>
              <ChevronUp size={14} className="text-teal-400" />
              Back to start of reply
            </>
          ) : (
            <>
              <ChevronDown size={14} className="text-teal-400" />
              Jump to latest
            </>
          )}
        </button>
      )}
      </div>

      <div
        className={`px-3 sm:px-4 pb-3 sm:pb-4 space-y-2 border-t pt-2.5 shrink-0 recruiter-chat-footer ${
          messages.length === 0
            ? "recruiter-chat-footer--welcome border-teal-400/25 bg-gradient-to-b from-teal-950/20 to-recruiter-navy/30"
            : "border-teal-500/10 bg-recruiter-navy/20"
        }`}
      >
        {messages.length > 0 && lastFollowUps.length > 0 && !loading && (
          <div className="space-y-1 min-w-0">
            <p className="text-[10px] font-medium text-stone-500 tracking-wide">
              {followUpSectionLabel(followUpTopic)}
            </p>
            <div className="recruiter-suggest-grid grid grid-cols-1 sm:grid-cols-3 gap-1.5">
              {lastFollowUps.map((q) => (
                <SuggestedChip
                  key={`${followUpRotation}-${q}`}
                  variant="compact"
                  disabled={loading}
                  onClick={() => ask(q)}
                  className="w-full !max-w-none line-clamp-2 text-left"
                  title={q}
                >
                  {q}
                </SuggestedChip>
              ))}
            </div>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="flex gap-2 items-end"
        >
          {isMultilineInput ? (
            <textarea
              ref={inputRef}
              rows={4}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={loading ? "Waiting for Naresh's reply…" : "Paste role requirements or ask a hiring manager question…"}
              className={`recruiter-chat-input flex-1 text-[14px] px-3.5 py-2.5 rounded-xl border text-stone-100 placeholder:text-stone-400 focus:outline-none transition-all resize-y min-h-[5.5rem] max-h-40 ${
                loading ? "recruiter-chat-input--loading" : ""
              }`}
              disabled={loading}
              aria-busy={loading}
            />
          ) : (
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={inputPlaceholder}
            className={`recruiter-chat-input flex-1 text-[15px] px-3.5 py-3 rounded-xl border text-stone-100 placeholder:text-stone-400 focus:outline-none transition-all ${
              loading ? "recruiter-chat-input--loading" : ""
            }`}
            disabled={loading}
            aria-busy={loading}
          />
          )}
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className={`inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium text-white shrink-0 transition-all ${
              loading
                ? "bg-teal-700/50 cursor-wait opacity-70"
                : "bg-gradient-to-r from-teal-600 to-indigo-600 hover:from-teal-500 hover:to-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm shadow-teal-900/25"
            }`}
            aria-busy={loading}
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin text-teal-200" aria-label="Sending" />
            ) : (
              <Send size={16} />
            )}
          </button>
        </form>
      </div>
    </div>
  );

  const fabLoadingPhase = loading
    ? messages.some((m) => m.streaming)
      ? "streaming"
      : "thinking"
    : "idle";

  return (
    <>
      <section id="ask-recruiter" className="sr-only resume-no-print" aria-hidden="true" />

      {isClosed && (
        <button
          type="button"
          onClick={openChat}
          className="recruiter-chat-fab fixed bottom-5 right-5 z-50 inline-flex items-center gap-2.5 pl-1.5 pr-4 py-1.5 rounded-full text-sm font-semibold text-white bg-gradient-to-r from-teal-700/95 to-indigo-700/95 shadow-lg shadow-black/45 border border-teal-400/30 resume-no-print hover:from-teal-600 hover:to-indigo-600 transition-all hover:scale-[1.02] active:scale-[0.98]"
          aria-label="Ask Naresh's AI"
        >
          <span className="relative shrink-0">
            <NareshAnimatedAvatar
              size="sm"
              question={lastUserQuestion}
              thoughtLine={liveThoughtLine}
              loadingPhase={fabLoadingPhase}
              live
            />
            <span className="absolute -bottom-0.5 -right-0.5 z-[1]">
              <LivePulse active={loading} />
            </span>
          </span>
          <span className="hidden sm:inline pr-0.5">
            {loading ? "Naresh's AI is replying…" : messages.length > 0 ? "Back to chat" : "Ask Naresh's AI"}
          </span>
        </button>
      )}

      {isMaximized && (
        <div
          className="recruiter-chat-overlay fixed inset-0 z-[60] flex items-stretch sm:items-center justify-center p-0 sm:p-4 resume-no-print"
          role="dialog"
          aria-modal="true"
          aria-label="Ask Naresh's AI"
        >
          <button
            type="button"
            className="recruiter-chat-overlay-backdrop absolute inset-0"
            onClick={closeChat}
            aria-label="Close chat"
          />
          {loading && (
            <div className="recruiter-page-dim absolute inset-0 pointer-events-none" aria-hidden="true" />
          )}
          <div className="relative z-10 w-full max-w-4xl h-[100dvh] sm:h-[min(100dvh,calc(100dvh-2rem))] flex flex-col pointer-events-none sm:rounded-xl sm:overflow-hidden">
            <div className="pointer-events-auto flex flex-col h-full min-h-0">
              {renderPanel()}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
