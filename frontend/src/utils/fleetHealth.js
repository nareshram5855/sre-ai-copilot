/** Fleet health percentage — mirrors backend.utils.fleet_health.fleet_health_pct */
export function fleetHealthPct(healthy, total) {
  if (total <= 0) return null;
  return Math.round((healthy / total) * 100);
}

export function fleetHealthDisplay(watch, loading) {
  if (loading) return { value: "—", sub: "Loading…", color: "blue" };
  const total = watch?.service_count ?? 0;
  const healthy = watch?.healthy_count ?? watch?.services?.filter((s) => s.health === "healthy").length ?? 0;
  const pct = watch?.fleet_health_pct ?? fleetHealthPct(healthy, total);

  if (pct == null) {
    const promDown = watch?.prometheus_reachable === false;
    return {
      value: "—",
      sub: promDown
        ? "Metrics unavailable — run make dev-up"
        : total === 0
          ? "No services discovered"
          : "Fleet health unknown",
      color: promDown ? "red" : "blue",
    };
  }

  return {
    value: `${pct}%`,
    sub: `${healthy}/${total} services healthy`,
    color: pct === 100 ? "emerald" : pct >= 50 ? "yellow" : "red",
  };
}
