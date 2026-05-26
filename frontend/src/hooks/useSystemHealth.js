import { useState, useEffect } from "react";

export function useSystemHealth(pollMs = 30_000) {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const res = await fetch("/health");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setHealth(data);
          setFetchError(null);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setHealth(null);
          setFetchError(err?.message || "unreachable");
          setLoading(false);
        }
      }
    }

    check();
    const id = setInterval(check, pollMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [pollMs]);

  // API is "up" when backend responds — observability degradation is separate
  const online = health?.status === "healthy";
  const observabilityDegraded = health?.observability === "degraded";

  return { health, loading, online, observabilityDegraded, fetchError };
}
