import { getRecruiterSessionId } from "./recruiterSession.js";

function post(path, body) {
  fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => {});
}

export function logEvent(eventType) {
  post("/api/v1/recruiter/event", {
    session_id: getRecruiterSessionId(),
    event_type: eventType,
  });
}

export function logQuestion(question) {
  if (!question?.trim()) return;
  post("/api/v1/recruiter/question", {
    session_id: getRecruiterSessionId(),
    question: question.trim().slice(0, 300),
  });
}
