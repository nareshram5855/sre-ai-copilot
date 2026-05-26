// Lightweight wrapper around axios that injects the API key header
// when the user has stored one. Read VITE_API_KEY at build-time or read
// from localStorage at runtime so a single dev build supports both modes.
import axios from "axios";

const BUILD_KEY = import.meta.env?.VITE_API_KEY || "";

export function getApiKey() {
  if (typeof window === "undefined") return BUILD_KEY;
  try {
    return window.localStorage.getItem("sreai.apiKey") || BUILD_KEY;
  } catch {
    return BUILD_KEY;
  }
}

export function setApiKey(key) {
  if (typeof window === "undefined") return;
  if (key) window.localStorage.setItem("sreai.apiKey", key);
  else window.localStorage.removeItem("sreai.apiKey");
}

// Convenience: extra headers to merge into axios calls.
export function authHeaders() {
  const k = getApiKey();
  return k ? { "X-API-Key": k } : {};
}

// Pre-configured axios instance that always injects the API key.
export const api = axios.create();
api.interceptors.request.use((cfg) => {
  const headers = cfg.headers ?? {};
  const key = getApiKey();
  if (key && !headers["X-API-Key"] && !headers.Authorization) {
    headers["X-API-Key"] = key;
  }
  cfg.headers = headers;
  return cfg;
});
