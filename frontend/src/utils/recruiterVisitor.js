const COOKIE_NAME = "sreai_visitor";
const MAX_AGE_DAYS = 90;
const MAX_AGE_SEC = MAX_AGE_DAYS * 24 * 60 * 60;

function randomId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `v-${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
}

function readCookie(name) {
  if (typeof document === "undefined") return "";
  const prefix = `${name}=`;
  const parts = document.cookie.split(";").map((c) => c.trim());
  for (const part of parts) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return "";
}

function writeCookie(name, value, maxAgeSec) {
  if (typeof document === "undefined") return;
  const secure = typeof window !== "undefined" && window.location?.protocol === "https:";
  const bits = [
    `${name}=${encodeURIComponent(value)}`,
    `Max-Age=${maxAgeSec}`,
    "Path=/",
    "SameSite=Lax",
  ];
  if (secure) bits.push("Secure");
  document.cookie = bits.join("; ");
}

/** Stable per-device visitor id (90-day cookie) for resume analytics. */
export function getOrCreateVisitorId() {
  if (typeof window === "undefined") return "";
  try {
    let id = readCookie(COOKIE_NAME);
    if (!id) {
      id = randomId();
      writeCookie(COOKIE_NAME, id, MAX_AGE_SEC);
    }
    return id;
  } catch {
    return randomId();
  }
}

/** Simple mobile vs desktop hint for analytics (client-side only). */
export function inferDeviceClass() {
  if (typeof navigator === "undefined") return "";
  const ua = navigator.userAgent || "";
  return /Mobi|Android|iPhone|iPad|iPod/i.test(ua) ? "mobile" : "desktop";
}

export const VISITOR_COOKIE_NAME = COOKIE_NAME;
export const VISITOR_COOKIE_MAX_AGE_DAYS = MAX_AGE_DAYS;
