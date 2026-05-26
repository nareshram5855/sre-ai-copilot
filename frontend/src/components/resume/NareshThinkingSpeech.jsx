import { useEffect, useMemo, useRef, useState } from "react";
import {
  getDelayThoughtLines,
  getHoldingThoughtLines,
  getHumanThoughtSequence,
  getThoughtMood,
  MAX_DELAY_THOUGHTS,
} from "../../utils/recruiterFollowUps.js";
import NareshAnimatedAvatar from "./NareshAnimatedAvatar.jsx";

const DELAY_PATTERN =
  /\b(?:sorry|taking a min|almost there|still pulling|still cross|still mapping|still separating|still keeping|still lining|fair challenge|scanning|matching tools)\b/i;
const GOT_IT_PATTERN =
  /\b(?:got it|oh nice|here we go|honest answer coming|clicking now|coming together|ready to answer|composing the answer|putting it into words|clear thread)\b/i;
const HOLDING_PATTERN = /^…/;

const THINKING_CAPTIONS = {
  thinking: "Naresh is thinking…",
  apologetic: "Hang on — still thinking…",
  praying: "Bear with me…",
  gotIt: "Got it — composing reply…",
  confident: "Almost ready…",
  skill: "Pulling up my experience…",
  employer: "Recalling client work…",
  manager: "What would they say…",
  intro: "Quick intro…",
  portfolio: "About this demo…",
  incident: "On-call memory…",
  recommendation: "Pulling references…",
  friendly: "Plain English mode…",
  comparing: "Comparing clients…",
  streaming: "Naresh is replying…",
  neutral: "Naresh is thinking…",
  idle: "Ready to chat…",
};

function spokenText(line = "") {
  return String(line)
    .replace(/\p{Extended_Pictographic}/gu, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function resolveLoadingPhase(thought = "", isDelayPhase = false, isHolding = false) {
  if (isHolding) return "delay";
  if (HOLDING_PATTERN.test(thought)) return "delay";
  if (GOT_IT_PATTERN.test(thought)) return "thinking";
  if (DELAY_PATTERN.test(thought) || isDelayPhase) return "delay";
  return "thinking";
}

export default function NareshThinkingSpeech({ question, onThoughtLineChange }) {
  const initialThoughts = useMemo(() => getHumanThoughtSequence(question), [question]);
  const delayThoughts = useMemo(() => getDelayThoughtLines(question), [question]);
  const holdingThoughts = useMemo(() => getHoldingThoughtLines(), []);
  const maxDelayLines = Math.min(MAX_DELAY_THOUGHTS, delayThoughts.length);

  const [delayCount, setDelayCount] = useState(0);
  const [step, setStep] = useState(0);
  const [typedLen, setTypedLen] = useState(0);
  const [lineVisible, setLineVisible] = useState(true);
  const [holdingIndex, setHoldingIndex] = useState(0);
  const [inHoldingLoop, setInHoldingLoop] = useState(false);
  const delayKickRef = useRef(false);

  const thoughts = useMemo(() => {
    const base = [...initialThoughts, ...delayThoughts.slice(0, delayCount)];
    if (inHoldingLoop) {
      return [...base, holdingThoughts[holdingIndex % holdingThoughts.length]];
    }
    return base;
  }, [initialThoughts, delayThoughts, delayCount, inHoldingLoop, holdingIndex, holdingThoughts]);

  const safeStep = Math.min(step, Math.max(thoughts.length - 1, 0));
  const currentThought = thoughts[safeStep] || "";
  const spoken = spokenText(currentThought);
  const atLastLine = safeStep >= thoughts.length - 1;
  const isDelayPhase = safeStep >= initialThoughts.length;
  const canAppendDelay = delayCount < maxDelayLines && !inHoldingLoop;
  const isTyping = typedLen < spoken.length;
  const isPausing = !isTyping && spoken.length > 0;
  const isHolding = inHoldingLoop && atLastLine;

  const loadingPhase = useMemo(
    () => resolveLoadingPhase(currentThought, isDelayPhase, isHolding),
    [currentThought, isDelayPhase, isHolding]
  );

  const moodState = useMemo(
    () => getThoughtMood(question, currentThought, loadingPhase),
    [question, currentThought, loadingPhase]
  );

  const caption = THINKING_CAPTIONS[moodState.mood] || THINKING_CAPTIONS.thinking;

  useEffect(() => {
    setStep(0);
    setTypedLen(0);
    setDelayCount(0);
    setLineVisible(true);
    setHoldingIndex(0);
    setInHoldingLoop(false);
    delayKickRef.current = false;
  }, [question]);

  useEffect(() => {
    onThoughtLineChange?.(currentThought);
  }, [currentThought, onThoughtLineChange]);

  /* Kick delay thoughts early if initial sequence finishes but model still loading */
  useEffect(() => {
    if (delayKickRef.current || inHoldingLoop) return undefined;
    if (step < initialThoughts.length - 1) return undefined;

    const t = window.setTimeout(() => {
      if (canAppendDelay && !delayKickRef.current) {
        delayKickRef.current = true;
        setDelayCount((n) => Math.max(n, 1));
      }
    }, 4500);

    return () => window.clearTimeout(t);
  }, [question, step, initialThoughts.length, canAppendDelay, inHoldingLoop]);

  /* Holding loop — rotate gentle lines while still waiting */
  useEffect(() => {
    if (!inHoldingLoop) return undefined;
    const t = window.setInterval(() => {
      setLineVisible(false);
      window.setTimeout(() => {
        setHoldingIndex((i) => i + 1);
        setTypedLen(0);
        setLineVisible(true);
      }, 200);
    }, 3200);
    return () => window.clearInterval(t);
  }, [inHoldingLoop]);

  useEffect(() => {
    if (!spoken) return undefined;

    if (typedLen < spoken.length) {
      const delay = isDelayPhase || isHolding ? 18 + Math.floor(Math.random() * 20) : 20 + Math.floor(Math.random() * 22);
      const t = window.setTimeout(() => setTypedLen((n) => n + 1), delay);
      return () => window.clearTimeout(t);
    }

    const pause = isHolding ? 2800 : isDelayPhase ? 750 + Math.floor(Math.random() * 400) : 650 + Math.floor(Math.random() * 450);
    const t = window.setTimeout(() => {
      if (!atLastLine) {
        setLineVisible(false);
        window.setTimeout(() => {
          setStep((s) => s + 1);
          setTypedLen(0);
          setLineVisible(true);
        }, 220);
        return;
      }
      if (canAppendDelay) {
        setLineVisible(false);
        window.setTimeout(() => {
          setDelayCount((n) => n + 1);
          setStep((s) => s + 1);
          setTypedLen(0);
          setLineVisible(true);
        }, 220);
        return;
      }
      if (!inHoldingLoop) {
        setInHoldingLoop(true);
        setLineVisible(false);
        window.setTimeout(() => {
          setStep((s) => s + 1);
          setTypedLen(0);
          setLineVisible(true);
        }, 220);
      }
    }, pause);
    return () => window.clearTimeout(t);
  }, [typedLen, spoken, atLastLine, canAppendDelay, thoughts.length, isDelayPhase, isHolding, inHoldingLoop]);

  const visibleText = spoken.slice(0, typedLen);
  const bubbleClass = [
    "naresh-speech-bubble",
    isTyping ? "naresh-speech-bubble--typing" : "",
    isPausing && isDelayPhase ? "naresh-speech-bubble--pause" : "",
    isHolding ? "naresh-speech-bubble--holding" : "",
    GOT_IT_PATTERN.test(currentThought) ? "naresh-speech-bubble--ready" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const avatarClass = [
    "naresh-avatar--in-speech",
    isDelayPhase ? "naresh-avatar--delay-phase" : "",
    isHolding ? "naresh-avatar--holding" : "",
    GOT_IT_PATTERN.test(currentThought) ? "naresh-avatar--ready" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="naresh-thinking-speech" aria-live="polite" aria-busy="true">
      <NareshAnimatedAvatar
        size="lg"
        question={question}
        thoughtLine={currentThought}
        loadingPhase={loadingPhase}
        isTyping={isTyping}
        live
        className={avatarClass}
      />

      <div className={bubbleClass}>
        <span className="naresh-speech-tail" aria-hidden="true" />
        <div className="naresh-speech-shimmer" aria-hidden="true">
          <span className="naresh-speech-shimmer-fill" />
        </div>
        <p className="naresh-speech-caption">{caption}</p>
        <div className="naresh-speech-words">
          <p
            key={`${question}-${safeStep}-${holdingIndex}`}
            className={`naresh-speech-line ${lineVisible ? "naresh-speech-line--visible" : "naresh-speech-line--fade"}`}
          >
            {visibleText}
            {isTyping && <span className="naresh-speech-cursor" aria-hidden="true" />}
          </p>
        </div>
      </div>
    </div>
  );
}
