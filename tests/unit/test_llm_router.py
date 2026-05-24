"""Unit tests for complexity scoring and tier routing."""
import pytest
from backend.llm.router import Complexity, LLMTier, score_complexity, resolve_tier


# ── Complexity scoring ────────────────────────────────────────────────────────

class TestComplexityScoring:

    def _alert(self, name="TestAlert", desc="", severity="warning", env="production", value=None):
        return {"name": name, "description": desc, "labels": {"severity": severity},
                "environment": env, "value": value}

    def test_zero_rag_hits_escalates_to_critical(self):
        alert = self._alert(severity="critical")
        assert score_complexity(alert, rag_hit_count=0) == Complexity.CRITICAL

    def test_good_rag_coverage_stays_low(self):
        alert = self._alert(severity="warning", env="staging")
        assert score_complexity(alert, rag_hit_count=5) == Complexity.LOW

    def test_critical_severity_raises_complexity(self):
        alert = self._alert(severity="critical", env="staging")
        result = score_complexity(alert, rag_hit_count=3)
        assert result in (Complexity.MEDIUM, Complexity.HIGH)

    def test_risk_keyword_breach_escalates(self):
        alert = self._alert(desc="possible security breach detected in auth service")
        result = score_complexity(alert, rag_hit_count=2)
        assert result in (Complexity.MEDIUM, Complexity.HIGH, Complexity.CRITICAL)

    def test_risk_keyword_data_loss(self):
        alert = self._alert(desc="data loss detected in token store")
        result = score_complexity(alert, rag_hit_count=2)
        assert result in (Complexity.MEDIUM, Complexity.HIGH, Complexity.CRITICAL)

    def test_staging_env_lower_than_production(self):
        prod = self._alert(severity="warning", env="production")
        staging = self._alert(severity="warning", env="staging")
        prod_score = score_complexity(prod, rag_hit_count=3)
        staging_score = score_complexity(staging, rag_hit_count=3)
        assert prod_score.value >= staging_score.value

    def test_multiple_signals_compound(self):
        alert = self._alert(
            desc="unknown cascade failure with data loss risk",
            severity="critical",
            env="production",
        )
        assert score_complexity(alert, rag_hit_count=0) == Complexity.CRITICAL


# ── Tier resolution ───────────────────────────────────────────────────────────

class TestTierResolution:

    def test_low_complexity_maps_to_local(self):
        assert resolve_tier(Complexity.LOW) == LLMTier.LOCAL

    def test_medium_maps_to_standard(self):
        assert resolve_tier(Complexity.MEDIUM) == LLMTier.STANDARD

    def test_high_maps_to_advanced(self):
        assert resolve_tier(Complexity.HIGH) == LLMTier.ADVANCED

    def test_critical_maps_to_premium(self):
        assert resolve_tier(Complexity.CRITICAL) == LLMTier.PREMIUM

    def test_all_complexities_have_a_tier(self):
        for c in Complexity:
            assert resolve_tier(c) in LLMTier


# ── LLM factory fallback ──────────────────────────────────────────────────────

class TestLLMFactory:
    """Verify the factory always returns a usable LLM even with missing keys."""

    def test_local_tier_always_returns_ollama(self):
        from backend.llm.router import get_llm
        from langchain_ollama import ChatOllama
        llm = get_llm(LLMTier.LOCAL)
        assert isinstance(llm, ChatOllama)

    def test_external_tier_without_key_falls_back_to_local(self):
        from backend.llm.router import get_llm
        from langchain_ollama import ChatOllama
        from unittest.mock import patch
        with patch("backend.llm.router.get_settings") as mock_cfg:
            mock_cfg.return_value.allow_external_llm = True
            mock_cfg.return_value.google_api_key = ""
            mock_cfg.return_value.anthropic_api_key = ""
            mock_cfg.return_value.ollama_model = "mistral"
            mock_cfg.return_value.ollama_base_url = "http://localhost:11434"
            mock_cfg.return_value.ollama_temperature = 0.1
            llm = get_llm(LLMTier.STANDARD)
        assert isinstance(llm, ChatOllama)

    def test_external_disabled_always_local(self):
        from backend.llm.router import get_llm
        from langchain_ollama import ChatOllama
        from unittest.mock import patch
        with patch("backend.llm.router.get_settings") as mock_cfg:
            mock_cfg.return_value.allow_external_llm = False
            mock_cfg.return_value.ollama_model = "mistral"
            mock_cfg.return_value.ollama_base_url = "http://localhost:11434"
            mock_cfg.return_value.ollama_temperature = 0.1
            llm = get_llm(LLMTier.PREMIUM)
        assert isinstance(llm, ChatOllama)
