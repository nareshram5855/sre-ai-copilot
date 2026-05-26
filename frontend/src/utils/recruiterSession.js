const SESSION_KEY = "sreai.recruiterSessionId";
const FEEDBACK_DISMISSED_KEY = "sreai.recruiterFeedbackDismissed";
const FEEDBACK_SUBMITTED_KEY = "sreai.recruiterFeedbackSubmitted";

function randomId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `rs-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

export function getRecruiterSessionId() {
  if (typeof window === "undefined") return "";
  try {
    let id = window.sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = randomId();
      window.sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return randomId();
  }
}

export function isFeedbackDismissed() {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(FEEDBACK_DISMISSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function markFeedbackDismissed() {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(FEEDBACK_DISMISSED_KEY, "1");
  } catch {
    /* ignore */
  }
}

export function isFeedbackSubmitted() {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(FEEDBACK_SUBMITTED_KEY) === "1";
  } catch {
    return false;
  }
}

export function markFeedbackSubmitted() {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(FEEDBACK_SUBMITTED_KEY, "1");
  } catch {
    /* ignore */
  }
}
