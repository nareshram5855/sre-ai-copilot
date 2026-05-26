/** Lightweight chat open/ask events — keep out of RecruiterAskPanel to avoid heavy imports. */

export function openRecruiterChat() {
  window.dispatchEvent(new CustomEvent("sre-recruiter-open"));
}

export function dispatchRecruiterChatClose() {
  window.dispatchEvent(new CustomEvent("sre-recruiter-close"));
}

export function dispatchRecruiterQuickAsk(question) {
  window.dispatchEvent(new CustomEvent("sre-recruiter-quick-ask", { detail: { question } }));
}

export function dispatchRecruiterJdTemplate() {
  window.dispatchEvent(new CustomEvent("sre-recruiter-jd-template"));
}
