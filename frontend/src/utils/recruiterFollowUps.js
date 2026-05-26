import {
  VERIFIED_EMPLOYER_NAMES,
  RECRUITER_FOLLOW_UP_POOLS,
  RECRUITER_SUGGESTED_QUESTIONS,
  RECRUITER_HM_STARTER_QUESTIONS,
  JD_FIT_QUESTION_TEMPLATE,
  RESUME_PROFILE,
} from "../data/resumeContent.js";

export { JD_FIT_QUESTION_TEMPLATE };

export const QUESTION_TOPICS = {
  EMPLOYER: "employer",
  SKILL: "skill",
  INCIDENT: "incident",
  PORTFOLIO: "portfolio",
  RECOMMENDATION: "recommendation",
  HIRING_MANAGER: "hiringManager",
  JD_FIT: "jdFit",
  GENERIC: "generic",
};

const EMPLOYER_ALIASES = {
  citi: "Citi",
  citigroup: "Citi",
  bofa: "BofA",
  "bank of america": "BofA",
  verizon: "Verizon",
  toyota: "Toyota",
  anthem: "Anthem",
  inovus: "Inovus",
};

const PORTFOLIO_HINTS = [
  "copilot",
  "sre ai",
  "portfolio",
  "demo platform",
  "this demo",
  "langgraph",
  "command center",
  "github",
  "live demo",
  "chroma",
  "ollama",
  "minikube",
];

const EMPLOYER_HINTS = [
  "client",
  "employer",
  "company",
  "worked at",
  "work at",
  "experience at",
  "role at",
  "time at",
  "tell me about your",
  "walk me through",
];

const SKILL_HINTS = [
  "kubernetes",
  "k8s",
  "gitops",
  "terraform",
  "ansible",
  "jenkins",
  "argocd",
  "kafka",
  "observability",
  "prometheus",
  "grafana",
  "eks",
  "iac",
  "cloud",
  "linux",
  "helm",
  "skill",
  "strongest in",
  "experience with",
  "compare your",
];

const INCIDENT_HINTS = [
  "incident",
  "on-call",
  "on call",
  "production",
  "observability",
  "monitoring",
  "servicenow",
  "triage",
  "what broke",
  "war story",
];

const RECOMMENDATION_HINTS = [
  "colleague",
  "recommend",
  "linkedin",
  "reference",
  "what do people say",
  "ashwin",
  "carrie",
];

const HM_HINTS = [
  "hiring manager",
  "would you hire",
  "first 90 days",
  "90-day",
  "staff sre",
  "staff engineer",
  "biggest gap",
  "biggest weakness",
  "honest gap",
  "ownership",
  "what would you own",
  "interview loop",
  "hiring brief",
  "30-second",
  "30 second",
  "production scope",
  "production proof",
  "why you and not",
  "vs the next resume",
];

const JD_FIT_HINTS = [
  "job description",
  "map my fit",
  "fit for this role",
  "role requirements",
  "must have",
  "nice to have",
  "qualifications",
  "requirements:",
  "strong / partial",
  "strong/partial",
  "not on resume",
];

const DEMO_CTA_PATTERN = /\*?\*?\s*want me to show you the live demo\??\*?\*?/gi;

/** LLM persona leaks — strip lines/sentences that break Naresh first-person character. */
const AI_DISCLAIMER_LINE =
  /^[^\n]*(?:trained on (?:a )?(?:vast amount of )?(?:text )?data|(?:large )?language model|\bLLM\b|as an? (?:AI|assistant|chatbot|virtual assistant|conversational AI)|I(?:'m| am) an? (?:AI|assistant|chatbot|language model|virtual assistant)|don'?t have personal experience|do not have personal experience|(?:lack|without|no) personal experience|personal experiences like humans|not (?:a )?(?:real )?person|not human|my training data|text corpora|knowledge cutoff|I(?:'m| am) (?:just )?(?:a )?(?:helpful )?(?:AI )?assistant|cannot (?:have|provide) (?:personal|first-hand|firsthand))[^\n]*$/gim;

const AI_DISCLAIMER_INLINE =
  /(?:I have been trained on[^.!?]*[.!?]\s*)+|(?:While I don'?t have personal experience[^.!?]*[.!?]\s*)+|(?:As an AI[^.!?]*[.!?]\s*)+/gi;

function stripAiDisclaimerLeaks(text = "") {
  if (!text) return text;
  return text
    .replace(AI_DISCLAIMER_INLINE, "")
    .replace(AI_DISCLAIMER_LINE, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** Initial opener chips — HM-focused mix before first message. */
export function getInitialSuggestedQuestions(count = 4) {
  const hm = RECRUITER_HM_STARTER_QUESTIONS.slice(0, 2);
  const rest = RECRUITER_SUGGESTED_QUESTIONS.filter((q) => !hm.includes(q));
  return [...hm, ...rest.slice(0, Math.max(0, count - hm.length))];
}

export function isJdFitQuestion(question = "") {
  const q = question.trim();
  const lower = q.toLowerCase();
  if (JD_FIT_HINTS.some((hint) => lower.includes(hint))) return true;
  if (q.length >= 220) return true;
  if (q.split("\n").length >= 3 && q.length >= 80) return true;
  const bulletLines = q.split("\n").filter((line) => /^[\s]*[-•*]/.test(line));
  return bulletLines.length >= 2;
}

export function isHiringManagerQuestion(question = "") {
  if (isJdFitQuestion(question)) return true;
  const lower = question.toLowerCase();
  return HM_HINTS.some((hint) => lower.includes(hint));
}

export function buildHiringManagerBrief(question = "", answer = "") {
  const { name, title, email } = RESUME_PROFILE;
  const plain = answer
    .replace(/\*\*/g, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .trim();
  const excerpt = plain.length > 900 ? `${plain.slice(0, 900)}…` : plain;
  return [
    `${name} — ${title}`,
    "Verified profile summary (hiring manager debrief)",
    "",
    `Question: ${question.trim()}`,
    "",
    excerpt,
    "",
    `Contact: ${email}`,
    "Portfolio: /resume",
  ].join("\n");
}

export function isPortfolioQuestion(question = "") {
  const q = question.toLowerCase();
  return PORTFOLIO_HINTS.some((hint) => q.includes(hint));
}

export function detectQuestionTopic(question = "") {
  const q = question.toLowerCase();
  if (isJdFitQuestion(question)) return QUESTION_TOPICS.JD_FIT;
  if (PORTFOLIO_HINTS.some((hint) => q.includes(hint))) return QUESTION_TOPICS.PORTFOLIO;
  if (RECOMMENDATION_HINTS.some((hint) => q.includes(hint))) return QUESTION_TOPICS.RECOMMENDATION;
  if (isHiringManagerQuestion(question)) return QUESTION_TOPICS.HIRING_MANAGER;
  if (parseEmployersFromText(question).length > 0) return QUESTION_TOPICS.EMPLOYER;
  if (INCIDENT_HINTS.some((hint) => q.includes(hint))) return QUESTION_TOPICS.INCIDENT;
  if (SKILL_HINTS.some((hint) => q.includes(hint))) return QUESTION_TOPICS.SKILL;
  if (EMPLOYER_HINTS.some((hint) => q.includes(hint))) return QUESTION_TOPICS.EMPLOYER;
  return QUESTION_TOPICS.GENERIC;
}

export function parseEmployersFromText(text = "") {
  if (!text) return [];
  const found = new Set();
  const lower = text.toLowerCase();

  for (const [alias, label] of Object.entries(EMPLOYER_ALIASES)) {
    if (lower.includes(alias)) found.add(label);
  }

  for (const name of VERIFIED_EMPLOYER_NAMES) {
    if (lower.includes(name.toLowerCase())) {
      if (name === "Citigroup" || name === "Citi") found.add("Citi");
      else if (name === "Bank of America" || name === "BofA") found.add("BofA");
      else if (name.includes("Toyota")) found.add("Toyota");
      else if (name.includes("Inovus")) found.add("Inovus");
      else found.add(name);
    }
  }

  return [...found];
}

function personalizeEmployerPrompts(prompts, employers) {
  const primary = employers[0] || "Citi";
  return prompts.map((p) => p.replace(/\{employer\}/g, primary));
}

function buildPoolForContext(topic, employers) {
  const pools = RECRUITER_FOLLOW_UP_POOLS;

  if (topic === QUESTION_TOPICS.PORTFOLIO) {
    return [...pools.portfolio, ...pools.portfolioDemo.slice(0, 2)];
  }
  if (topic === QUESTION_TOPICS.RECOMMENDATION) {
    return [...pools.recommendation, ...pools.generic.slice(0, 2)];
  }
  if (topic === QUESTION_TOPICS.EMPLOYER || employers.length > 0) {
    const employerPool = personalizeEmployerPrompts(pools.employer, employers);
    const comparePool = employers.length >= 2 ? pools.compareEmployers : pools.employerCompare.slice(0, 2);
    return [...employerPool, ...comparePool, ...pools.skillAtClient.slice(0, 2)];
  }
  if (topic === QUESTION_TOPICS.INCIDENT) {
    return [...pools.incident, ...pools.employer.slice(0, 2)];
  }
  if (topic === QUESTION_TOPICS.SKILL) {
    return [...pools.skill, ...pools.employer.slice(0, 2)];
  }
  if (topic === QUESTION_TOPICS.JD_FIT) {
    return [...pools.jdFit, ...pools.hiringManager.slice(0, 2)];
  }
  if (topic === QUESTION_TOPICS.HIRING_MANAGER) {
    if (employers.length > 0) {
      return [
        ...pools.hiringManager,
        ...personalizeEmployerPrompts(pools.employer.slice(0, 2), employers),
      ];
    }
    return [...pools.hiringManager, ...pools.jdFit.slice(0, 2)];
  }
  return [...pools.generic, ...pools.icebreaker.slice(0, 2)];
}

function rotatePick(candidates, count, rotationIndex, exclude = new Set()) {
  const available = candidates.filter((q) => !exclude.has(q));
  if (available.length === 0) return [];

  const start = rotationIndex % Math.max(available.length, 1);
  const picked = [];
  for (let i = 0; i < available.length && picked.length < count; i += 1) {
    const item = available[(start + i) % available.length];
    if (!picked.includes(item)) picked.push(item);
  }
  return picked;
}

/**
 * Pick 3–4 contextual follow-up chips after an assistant answer.
 */
export function pickFollowUpChips({
  lastQuestion = "",
  lastAnswer = "",
  askedQuestions = [],
  rotationIndex = 0,
  count = 4,
}) {
  const employers = [
    ...new Set([
      ...parseEmployersFromText(lastQuestion),
      ...parseEmployersFromText(lastAnswer),
    ]),
  ];
  const topic = detectQuestionTopic(lastQuestion);
  const pool = buildPoolForContext(topic, employers);
  const asked = new Set(askedQuestions.map((q) => q.trim().toLowerCase()));

  const chips = rotatePick(pool, count, rotationIndex, asked);

  if (chips.length < count) {
    const filler = rotatePick(
      [...RECRUITER_FOLLOW_UP_POOLS.generic, ...RECRUITER_FOLLOW_UP_POOLS.icebreaker],
      count - chips.length,
      rotationIndex + chips.length,
      new Set([...asked, ...chips.map((c) => c.toLowerCase())])
    );
    chips.push(...filler);
  }

  return chips.slice(0, count);
}

export function sanitizeRecruiterAnswer(content, lastQuestion = "") {
  if (!content) return content;
  let cleaned = content.replace(DEMO_CTA_PATTERN, "").replace(/\n{3,}/g, "\n\n").trim();
  cleaned = stripAiDisclaimerLeaks(cleaned);
  if (isPortfolioQuestion(lastQuestion)) return cleaned;
  return cleaned;
}

export function followUpSectionLabel(topic) {
  if (topic === QUESTION_TOPICS.JD_FIT) return "Dig deeper on fit ↓";
  if (topic === QUESTION_TOPICS.HIRING_MANAGER) return "Hiring manager follow-ups ↓";
  if (topic === QUESTION_TOPICS.PORTFOLIO) return "Want to poke around the demo? ↓";
  if (topic === QUESTION_TOPICS.EMPLOYER) return "Keep going — pick your next question ↓";
  return "Curious? Try one of these ↓";
}

/** Max delay-phase lines appended after initial thoughts finish. */
export const MAX_DELAY_THOUGHTS = 6;

const DELAY_THOUGHTS_GENERIC = [
  "ah sorry — taking a min to think this through…",
  "still cross-checking verified resume bullets…",
  "want this sharp — not generic fluff…",
  "almost there…",
  "oh — this is clicking now…",
  "got it — composing the answer…",
];

const HOLDING_THOUGHTS = [
  "…still here — putting words to real wins…",
  "…one sec — making sure this is recruiter-clear…",
  "…almost ready for you…",
];

function _isCompetitiveHiringQuestion(ql = "") {
  return /\bwhy you\b|not the next resume|why should i hire|why pick you|why choose you|why not someone|what makes you different|stand out from/.test(
    ql
  );
}

function _skillFromQuestion(question = "") {
  const ql = question.toLowerCase();
  const skills = [
    ["eks", "EKS"],
    ["kubernetes", "Kubernetes"],
    ["k8s", "Kubernetes"],
    ["ansible", "Ansible"],
    ["terraform", "Terraform"],
    ["kafka", "Kafka"],
    ["gitops", "GitOps"],
    ["argocd", "ArgoCD"],
    ["jenkins", "Jenkins"],
    ["prometheus", "Prometheus"],
    ["grafana", "Grafana"],
    ["observability", "observability"],
    ["linux", "Linux"],
    ["iam", "IAM"],
    ["pingfederate", "PingFederate"],
    ["servicenow", "ServiceNow"],
  ];
  for (const [hint, label] of skills) {
    if (ql.includes(hint)) return label;
  }
  return null;
}

/** Short inner-monologue beats — unfold like live human thinking. */
function _thoughtSeq(lines) {
  return lines;
}

function _employerThoughtSequence(emp) {
  const seq = {
    Citi: _thoughtSeq([
      "Hmm… 🤔",
      "Citi — CISO org.",
      "Let me think what actually mattered there…",
      "IAM, PingDirectory, Apigee, EKS…",
      "Staying on verified bullets only — not portfolio stuff.",
    ]),
    BofA: _thoughtSeq([
      "Oh, BofA… 💼",
      "Platform engineering days.",
      "Jenkins, Ansible Tower, Kafka…",
      "Oct 2020 – Sep 2023 — got it.",
    ]),
    Verizon: _thoughtSeq([
      "Verizon… 📡",
      "Smart Family, EKS, Istio.",
      "Pulling the exact tools from memory…",
    ]),
    Toyota: _thoughtSeq([
      "Toyota… 🚗",
      "Cloud migration — EC2, ECS, EKS.",
      "Datadog and monitoring come to mind.",
    ]),
    Anthem: _thoughtSeq([
      "Anthem… 🏥",
      "24/7 incident management.",
      "CloudWatch, on-call — real prod stories.",
    ]),
    Inovus: _thoughtSeq([
      "Early career — Inovus…",
      "Ansible, AWS, first real DevOps wins.",
    ]),
  };
  return seq[emp] || _thoughtSeq([
    `Well… ${emp}. 🤔`,
    "Let me recall what I actually did there.",
    "Verified resume bullets only — no guessing.",
  ]);
}

/**
 * Human inner-monologue sequence while composing an answer.
 */
/**
 * Extra inner-monologue beats when the model is still loading after initial thoughts.
 */
export function getDelayThoughtLines(question = "") {
  const q = question.trim();
  const ql = q.toLowerCase();
  const employers = parseEmployersFromText(q);
  const topic = detectQuestionTopic(q);
  const skill = _skillFromQuestion(q);

  if (_isCompetitiveHiringQuestion(ql)) {
    const emp = employers[0] || (/\bciti/.test(ql) ? "Citi" : "enterprise");
    const focus = skill || (/\biam\b/.test(ql) ? "IAM" : "this role");
    return [
      "okay — fair challenge…",
      `lining up my ${emp} ${focus} wins vs generic resumes…`,
      "Ping, Apigee, EKS — which ones actually matter here…",
      "want proof you'll remember in the interview…",
      "ah — the honest angle is coming together…",
      "got it — ready to answer properly…",
    ];
  }

  if (/\bmanager\b|would say|brought to|what did you bring|team say/.test(ql) && employers.length > 0) {
    const emp = employers[0];
    return [
      "ah sorry — taking a min to think this through…",
      `still cross-checking ${emp} bullets on my resume…`,
      "want this honest — not polished fluff…",
      "almost there…",
      "oh — got a clear thread now…",
      "composing the answer…",
    ];
  }

  if (employers.length === 1) {
    const emp = employers[0];
    return [
      "ah sorry — taking a min to think this through…",
      `still pulling verified ${emp} details…`,
      "matching tools to what you actually asked…",
      "almost there…",
      "oh — got a clear thread now…",
      "composing the answer…",
    ];
  }

  if (employers.length >= 2) {
    return [
      "ah sorry — taking a min to line these clients up…",
      "still separating each employer — no mixing…",
      "almost there…",
      "oh nice — got it now ✨",
    ];
  }

  if (skill) {
    return [
      "ah sorry — taking a min to think this through…",
      `still mapping ${skill} to verified client work…`,
      "no guessing — resume bullets only…",
      "almost there…",
      "nice — the client story is clear now…",
      "putting it into words…",
    ];
  }

  if (topic === QUESTION_TOPICS.PORTFOLIO) {
    return [
      "ah sorry — taking a min to think this through…",
      "still keeping portfolio separate from client work…",
      "almost there…",
      "oh nice — got it now ✨",
    ];
  }

  if (topic === QUESTION_TOPICS.INCIDENT) {
    return [
      "ah sorry — taking a min to think this through…",
      "still pulling real on-call stories…",
      "almost there…",
      "oh nice — got it now ✨",
    ];
  }

  return DELAY_THOUGHTS_GENERIC;
}

/** Rotate gentle hold lines while the model is still loading after delay beats. */
export function getHoldingThoughtLines() {
  return HOLDING_THOUGHTS;
}

export function getHumanThoughtSequence(question = "") {
  const q = question.trim();
  if (!q) {
    return _thoughtSeq(["Hmm… 🤔", "Let me think…", "Pulling from verified resume…"]);
  }

  const ql = q.toLowerCase();
  const topic = detectQuestionTopic(q);
  const employers = parseEmployersFromText(q);
  const skill = _skillFromQuestion(q);

  if (_isCompetitiveHiringQuestion(ql)) {
    const emp = employers[0] || (/\bciti/.test(ql) ? "Citi" : null);
    const focus = skill || (/\biam\b/.test(ql) ? "IAM" : "this");
    return _thoughtSeq([
      "Hmm… fair question. 🤔",
      emp ? `You're screening for ${emp}-like ${focus} work…` : `You're screening for ${focus} work…`,
      "Why me vs the next resume — let me be real…",
      "Concrete wins beat buzzwords every time…",
      "Pulling verified proof only…",
    ]);
  }

  if (/\bmanager\b|would say|brought to|what did you bring|team say/.test(ql) && employers.length > 0) {
    const emp = employers[0];
    return _thoughtSeq([
      "Well… 🤔",
      `good question.`,
      `${emp} manager — what would they say?`,
      "Probably the concrete wins, not buzzwords…",
      `Let me pull real ${emp} highlights from my resume.`,
      "Honest answer coming… ✨",
    ]);
  }

  if (/\bwho are you\b|introduce|tell me about yourself/.test(ql)) {
    return _thoughtSeq([
      "Hey! 👋",
      "Quick intro…",
      "8+ years DevOps / SRE…",
      "Citi, BofA, Verizon — enterprise clients.",
      "Here we go…",
    ]);
  }

  if (/\bno jargon\b|linkedin scrolling|explain .* like|scrolling fast/.test(ql)) {
    const label = skill || "this";
    return _thoughtSeq([
      "Got it — plain English. 😊",
      `No jargon on ${label}.`,
      "How would I explain this on a LinkedIn scroll…",
      "Recruiter-friendly version…",
      "Almost there…",
    ]);
  }

  if (skill) {
    return _thoughtSeq([
      "Hmm… 🤔",
      `${skill} — good one.`,
      "Which client did I use that at…",
      "Skills matrix + job bullets…",
      "Mapping to verified employers only.",
    ]);
  }

  if (employers.length >= 2) {
    const pair = employers.slice(0, 2).join(" and ");
    return _thoughtSeq([
      "Okay… ⚖️",
      `Comparing ${pair}.`,
      "Each client separate — no mixing tools.",
      "Organizing my answer…",
    ]);
  }

  if (employers.length === 1) {
    return _employerThoughtSequence(employers[0]);
  }

  if (topic === QUESTION_TOPICS.PORTFOLIO) {
    return _thoughtSeq([
      "Ah — the SRE AI Copilot demo. 🚀",
      "Personal R&D — not client prod.",
      "Happy to walk through it…",
    ]);
  }

  if (topic === QUESTION_TOPICS.INCIDENT || /\bwhat broke\b|on-call|sev-/.test(ql)) {
    return _thoughtSeq([
      "Production incidents… 🚨",
      "Real on-call stories.",
      "ServiceNow, Prometheus — which client…",
      "Keeping portfolio separate from employer work.",
    ]);
  }

  if (topic === QUESTION_TOPICS.RECOMMENDATION) {
    return _thoughtSeq([
      "Recommendations… ⭐",
      "Ashwin at BofA — Director.",
      "Carrie on the Pega project…",
      "Pulling exact quotes…",
    ]);
  }

  if (topic === QUESTION_TOPICS.EMPLOYER) {
    return _thoughtSeq([
      "Client experience… 💼",
      "Which employer was that…",
      "Checking verified history…",
    ]);
  }

  return _thoughtSeq([
    "Hmm… 🤔",
    "Good question.",
    "Let me think this through…",
    "Pulling from verified resume only…",
  ]);
}

/** Mood keys for NareshLiveAvatar — emoji + accessible label. */
export const THOUGHT_MOODS = {
  idle: { emoji: "👋", label: "Ready to chat" },
  neutral: { emoji: "🙂", label: "Listening" },
  thinking: { emoji: "🤔", label: "Thinking" },
  apologetic: { emoji: "😅", label: "Taking a moment" },
  praying: { emoji: "🙏", label: "Bear with me" },
  gotIt: { emoji: "✨", label: "Got it" },
  skill: { emoji: "⚙️", label: "Mapping skills" },
  employer: { emoji: "💼", label: "Recalling client work" },
  manager: { emoji: "⭐", label: "Reflecting on feedback" },
  intro: { emoji: "👋", label: "Saying hello" },
  streaming: { emoji: "💬", label: "Replying" },
  confident: { emoji: "😎", label: "Sharing experience" },
  portfolio: { emoji: "🚀", label: "Exploring portfolio" },
  incident: { emoji: "🚨", label: "On-call stories" },
  recommendation: { emoji: "⭐", label: "Recommendations" },
  friendly: { emoji: "😊", label: "Plain English mode" },
  comparing: { emoji: "⚖️", label: "Comparing clients" },
};

const EMOJI_IN_TEXT = /(\p{Extended_Pictographic})/u;

const DELAY_LINE_PATTERN =
  /\b(?:sorry|taking a min|almost there|still pulling|still cross|still mapping|still separating|still keeping|still pulling real)\b/i;
const GOT_IT_PATTERN = /\b(?:got it|oh nice|here we go|honest answer coming|clicking now|coming together|ready to answer|composing the answer|putting it into words)\b/i;
const HOLDING_PATTERN = /^…/;

function _emojiFromLine(thoughtLine = "") {
  const matches = [...String(thoughtLine).matchAll(new RegExp(EMOJI_IN_TEXT, "gu"))];
  if (matches.length === 0) return null;
  return matches[matches.length - 1][1];
}

function _moodFromThoughtLine(thoughtLine = "") {
  const line = String(thoughtLine).trim();
  if (!line) return null;
  const lower = line.toLowerCase();

  if (GOT_IT_PATTERN.test(lower)) return "gotIt";
  if (HOLDING_PATTERN.test(line)) return "confident";
  if (DELAY_LINE_PATTERN.test(lower)) return "apologetic";
  if (/\bhey\b|quick intro/.test(lower)) return "intro";
  if (/plain english|no jargon|recruiter-friendly/.test(lower)) return "friendly";
  if (/comparing|no mixing/.test(lower)) return "comparing";
  if (/manager|what would they say|concrete wins/.test(lower)) return "manager";
  if (/recommendations|ashwin|carrie|pulling exact quotes/.test(lower)) return "recommendation";
  if (/production incidents|on-call|what broke|servicenow/.test(lower)) return "incident";
  if (/sre ai copilot|personal r&d|not client prod/.test(lower)) return "portfolio";
  if (/skills matrix|which client did i use|mapping to verified/.test(lower)) return "skill";
  if (
    /citi|bofa|verizon|toyota|anthem|inovus|client experience|verified bullets|employer/.test(lower)
  ) {
    return "employer";
  }
  if (/hmm|let me think|good question|pulling from verified/.test(lower)) return "thinking";

  const parsed = _emojiFromLine(line);
  if (parsed === "🤔") return "thinking";
  if (parsed === "👋") return "intro";
  if (parsed === "✨") return "gotIt";
  if (parsed === "😊") return "friendly";
  if (parsed === "⚖️") return "comparing";
  if (parsed === "⭐") return "recommendation";
  if (parsed === "🚨") return "incident";
  if (parsed === "🚀") return "portfolio";
  if (parsed === "💼") return "employer";
  if (parsed === "📡" || parsed === "🚗" || parsed === "🏥") return "employer";

  return null;
}

function _moodFromQuestion(question = "") {
  const topic = detectQuestionTopic(question);
  if (topic === QUESTION_TOPICS.SKILL) return "skill";
  if (topic === QUESTION_TOPICS.EMPLOYER) return "employer";
  if (topic === QUESTION_TOPICS.PORTFOLIO) return "portfolio";
  if (topic === QUESTION_TOPICS.INCIDENT) return "incident";
  if (topic === QUESTION_TOPICS.RECOMMENDATION) return "recommendation";

  const ql = question.toLowerCase();
  if (/\bmanager\b|would say|brought to|team say/.test(ql)) return "manager";
  if (/\bwho are you\b|introduce|tell me about yourself/.test(ql)) return "intro";
  return null;
}

/**
 * Derive Naresh avatar mood from chat context.
 * @param {string} question - active user question
 * @param {string} thoughtLine - current inner-monologue line (optional)
 * @param {"idle"|"thinking"|"delay"|"streaming"|"complete"} loadingPhase
 */
export function getThoughtMood(question = "", thoughtLine = "", loadingPhase = "idle") {
  if (loadingPhase === "streaming") {
    return { mood: "streaming", ...THOUGHT_MOODS.streaming };
  }
  if (loadingPhase === "complete") {
    return { mood: "gotIt", ...THOUGHT_MOODS.gotIt };
  }
  if (loadingPhase === "idle" && !question.trim()) {
    return { mood: "idle", ...THOUGHT_MOODS.idle };
  }
  if (loadingPhase === "idle") {
    return { mood: "neutral", ...THOUGHT_MOODS.neutral };
  }

  const fromLine = _moodFromThoughtLine(thoughtLine);
  if (fromLine) {
    return { mood: fromLine, ...THOUGHT_MOODS[fromLine] };
  }

  if (loadingPhase === "delay") {
    return { mood: "apologetic", ...THOUGHT_MOODS.apologetic };
  }

  const fromQuestion = _moodFromQuestion(question);
  if (fromQuestion) {
    return { mood: fromQuestion, ...THOUGHT_MOODS[fromQuestion] };
  }

  return { mood: "thinking", ...THOUGHT_MOODS.thinking };
}

/** Emoji cycles Naresh "speaks" from his mouth while active. */
export const MOUTH_EMOJI_CYCLES = {
  idle: ["🙂"],
  neutral: ["🙂", "😊"],
  thinking: ["🤔", "💭", "😮", "…"],
  apologetic: ["😅", "🙏", "⏳"],
  praying: ["🙏", "😅"],
  gotIt: ["😊", "✨", "💡"],
  streaming: ["💬", "😊", "🙂", "👍", "🗣️"],
  skill: ["🤓", "⚙️", "💻"],
  employer: ["💼", "😎", "👍"],
  manager: ["⭐", "🤔", "😊"],
  intro: ["👋", "😊", "🙂"],
  confident: ["😎", "👍", "💪"],
  portfolio: ["🚀", "✨", "😊"],
  incident: ["🚨", "😤", "💪"],
  recommendation: ["⭐", "🙌", "😊"],
  friendly: ["😊", "💬", "👍"],
  comparing: ["⚖️", "🤔", "💭"],
};

export function getMouthEmojiCycle(moodKey = "thinking") {
  return MOUTH_EMOJI_CYCLES[moodKey] || MOUTH_EMOJI_CYCLES.thinking;
}

export function extractEmojisFromText(text = "") {
  return [...String(text).matchAll(new RegExp(EMOJI_IN_TEXT, "gu"))].map((m) => m[1]);
}

/**
 * Primary emoji shown at Naresh's mouth — prefers emoji from active thought line.
 */
export function getActiveMouthEmoji(moodKey, thoughtLine = "", cycleIndex = 0) {
  const fromLine = extractEmojisFromText(thoughtLine);
  if (fromLine.length > 0) return fromLine[fromLine.length - 1];
  const cycle = getMouthEmojiCycle(moodKey);
  return cycle[cycleIndex % cycle.length];
}

/** Small emoji bubbles that pop from the mouth alongside speech. */
export function getSpeechBubbleEmojis(moodKey, thoughtLine = "") {
  const fromLine = extractEmojisFromText(thoughtLine);
  if (fromLine.length > 0) return fromLine;
  return getMouthEmojiCycle(moodKey).slice(0, 3);
}

/** First inner-monologue line while waiting (legacy helper). */
export function getPrimaryThinkingLine(question = "") {
  const seq = getHumanThoughtSequence(question);
  return seq[0] || DELAY_THOUGHTS_GENERIC[0];
}

/**
 * Human, question-specific "typing" lines while the recruiter waits.
 * @deprecated use getHumanThoughtSequence for richer UX
 */
export function getThinkingMessagesForQuestion(question = "") {
  return getHumanThoughtSequence(question);
}
