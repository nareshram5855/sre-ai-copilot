"""Unit tests for fleet health percentage calculation."""
from backend.utils.fleet_health import fleet_health_pct


class TestFleetHealthPct:
    def test_zero_services_not_one_hundred(self):
        assert fleet_health_pct(0, 0) is None

    def test_zero_healthy_with_services(self):
        assert fleet_health_pct(0, 7) == 0

    def test_all_healthy(self):
        assert fleet_health_pct(7, 7) == 100

    def test_partial_healthy(self):
        assert fleet_health_pct(3, 4) == 75
