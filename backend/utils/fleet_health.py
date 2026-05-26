"""Fleet health percentage helpers shared by API and frontend logic."""


def fleet_health_pct(healthy: int, total: int) -> int | None:
    """Return healthy/total as 0–100, or None when no services are known."""
    if total <= 0:
        return None
    return round(healthy / total * 100)
