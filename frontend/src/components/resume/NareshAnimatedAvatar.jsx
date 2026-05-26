import { useId, useMemo } from "react";
import { getThoughtMood } from "../../utils/recruiterFollowUps.js";

const EXPRESSION_CLASS = {
  idle: "naresh-face--idle",
  neutral: "naresh-face--neutral",
  thinking: "naresh-face--think",
  apologetic: "naresh-face--sorry",
  praying: "naresh-face--sorry",
  gotIt: "naresh-face--bright",
  skill: "naresh-face--focus",
  employer: "naresh-face--confident",
  manager: "naresh-face--reflect",
  intro: "naresh-face--wave",
  streaming: "naresh-face--talk",
  confident: "naresh-face--confident",
  portfolio: "naresh-face--bright",
  incident: "naresh-face--focus",
  recommendation: "naresh-face--reflect",
  friendly: "naresh-face--warm",
  comparing: "naresh-face--think",
};

export default function NareshAnimatedAvatar({
  size = "md",
  question = "",
  thoughtLine = "",
  loadingPhase = "idle",
  live = false,
  isTyping = false,
  className = "",
}) {
  const moodState = useMemo(
    () => getThoughtMood(question, thoughtLine, loadingPhase),
    [question, thoughtLine, loadingPhase]
  );

  const thinking = loadingPhase === "thinking" || loadingPhase === "delay";
  const streaming = loadingPhase === "streaming";
  const expressionClass = EXPRESSION_CLASS[moodState.mood] || "naresh-face--neutral";

  const uid = useId().replace(/:/g, "");
  const bgId = `nareshProBg-${uid}`;
  const skinId = `nareshProSkin-${uid}`;

  const sizeClass =
    size === "lg" ? "naresh-avatar--lg" : size === "sm" ? "naresh-avatar--sm" : "naresh-avatar--md";
  const stateClass = [
    thinking ? "naresh-avatar--thinking" : "",
    streaming ? "naresh-avatar--streaming" : "",
    isTyping ? "naresh-avatar--mouth-active" : "",
    live ? "naresh-avatar--live" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      className={`naresh-avatar naresh-avatar--pro ${sizeClass} ${stateClass} self-start shrink-0 ${className}`}
      aria-label={`Naresh — ${moodState.label}`}
      role="img"
    >
      <div className="naresh-avatar-ring-wrap">
        {thinking && <span className="naresh-avatar-pulse-ring" aria-hidden="true" />}

        <svg
          className={`naresh-avatar-svg ${expressionClass}`}
          viewBox="0 0 100 100"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id={bgId} x1="10" y1="8" x2="90" y2="98">
              <stop offset="0%" stopColor="#1e3a5f" />
              <stop offset="55%" stopColor="#1e1b4b" />
              <stop offset="100%" stopColor="#0f172a" />
            </linearGradient>
            <linearGradient id={skinId} x1="35" y1="28" x2="65" y2="72">
              <stop offset="0%" stopColor="#e8b88a" />
              <stop offset="100%" stopColor="#c68642" />
            </linearGradient>
          </defs>

          {/* Professional portrait frame */}
          <rect x="4" y="4" width="92" height="92" rx="14" fill={`url(#${bgId})`} />
          <rect
            x="4"
            y="4"
            width="92"
            height="92"
            rx="14"
            stroke="rgba(99,102,241,0.35)"
            strokeWidth="1.5"
            fill="none"
          />

          {/* Shirt & collar */}
          <path d="M18 88 C28 72 72 72 82 88 L82 96 L18 96 Z" fill="#1e293b" />
          <path d="M38 84 L50 94 L62 84" fill="#334155" />
          <path
            d="M32 84 C38 78 62 78 68 84"
            stroke="rgba(148,163,184,0.35)"
            strokeWidth="1"
            fill="none"
          />
          <rect x="46" y="76" width="8" height="10" rx="2" fill="#475569" />

          <g className="naresh-avatar-head">
            {/* Face */}
            <ellipse cx="50" cy="46" rx="26" ry="28" fill={`url(#${skinId})`} />

            {/* Hair — professional, not bald */}
            <path
              className="naresh-hair"
              d="M24 44 C26 22 74 22 76 44 C70 30 58 24 50 24 C42 24 30 30 24 44 Z"
              fill="#1a1625"
            />
            <path
              d="M26 40 C32 28 42 24 50 24 C58 24 68 28 74 40"
              stroke="#2d2640"
              strokeWidth="1"
              fill="none"
              opacity="0.6"
            />

            {/* Ears */}
            <ellipse cx="24" cy="48" rx="3" ry="4.5" fill="#c68642" opacity="0.85" />
            <ellipse cx="76" cy="48" rx="3" ry="4.5" fill="#c68642" opacity="0.85" />

            {/* Brows — above glasses */}
            <g className="naresh-brow naresh-brow--left">
              <path d="M32 40 Q38 36 44 39" stroke="#3d2f24" strokeWidth="2" strokeLinecap="round" />
            </g>
            <g className="naresh-brow naresh-brow--right">
              <path d="M56 39 Q62 36 68 40" stroke="#3d2f24" strokeWidth="2" strokeLinecap="round" />
            </g>

            {/* Eyes (behind lenses) */}
            <g className="naresh-eye naresh-eye--left">
              <ellipse cx="38" cy="48" rx="5" ry="5.5" fill="#fff" />
              <circle className="naresh-pupil" cx="38.5" cy="49" r="2.5" fill="#1e293b" />
              <ellipse className="naresh-lid" cx="38" cy="47" rx="5.5" ry="6" fill="#c68642" />
            </g>
            <g className="naresh-eye naresh-eye--right">
              <ellipse cx="62" cy="48" rx="5" ry="5.5" fill="#fff" />
              <circle className="naresh-pupil" cx="61.5" cy="49" r="2.5" fill="#1e293b" />
              <ellipse className="naresh-lid" cx="62" cy="47" rx="5.5" ry="6" fill="#c68642" />
            </g>

            {/* Spectacles — always visible, IT professional */}
            <g className="naresh-specs">
              <rect
                x="28"
                y="42"
                width="18"
                height="13"
                rx="3.5"
                stroke="#cbd5e1"
                strokeWidth="1.8"
                fill="rgba(148,163,184,0.08)"
              />
              <rect
                x="54"
                y="42"
                width="18"
                height="13"
                rx="3.5"
                stroke="#cbd5e1"
                strokeWidth="1.8"
                fill="rgba(148,163,184,0.08)"
              />
              <path d="M46 48.5 H54" stroke="#cbd5e1" strokeWidth="1.6" strokeLinecap="round" />
              <path d="M26 47.5 H22" stroke="#94a3b8" strokeWidth="1.4" strokeLinecap="round" />
              <path d="M78 47.5 H82" stroke="#94a3b8" strokeWidth="1.4" strokeLinecap="round" />
              <circle cx="35" cy="47" r="1.2" fill="rgba(224,242,254,0.5)" />
              <circle cx="63" cy="47" r="1.2" fill="rgba(224,242,254,0.5)" />
            </g>

            {/* Nose */}
            <path d="M50 52 L50 58" stroke="#a16207" strokeWidth="1.4" strokeLinecap="round" opacity="0.4" />

            {/* Mouth expressions */}
            <g className="naresh-mouth">
              <path
                className="naresh-mouth-shape naresh-mouth-shape--smile"
                d="M40 64 Q50 69 60 64"
                stroke="#7c2d12"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
              <path
                className="naresh-mouth-shape naresh-mouth-shape--think"
                d="M43 65 Q50 63 57 65"
                stroke="#7c2d12"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
              <path
                className="naresh-mouth-shape naresh-mouth-shape--talk"
                d="M44 64 Q50 68 56 64"
                stroke="#7c2d12"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
              <path
                className="naresh-mouth-shape naresh-mouth-shape--grin"
                d="M38 62 Q50 72 62 62"
                stroke="#7c2d12"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
              <path
                className="naresh-mouth-shape naresh-mouth-shape--sorry"
                d="M42 67 Q50 64 58 67"
                stroke="#7c2d12"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
            </g>
          </g>
        </svg>
      </div>

      {live && !thinking && <span className="naresh-avatar-live-dot" aria-hidden="true" />}
    </div>
  );
}
