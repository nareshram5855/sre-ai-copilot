"""Unit tests for recruiter Q&A endpoint."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.memory.recruiter_store import init_recruiter_store
from backend.routers.recruiter import (
    _build_employment_timeline,
    _build_recruiter_system,
    _build_verified_client_experience,
    _build_verified_skills_context,
    _filter_answer_sources,
    _sanitize_recruiter_answer,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def recruiter_store(tmp_path):
    init_recruiter_store(tmp_path / "recruiter.db")


def test_recruiter_achievements():
    r = client.get("/api/v1/recruiter/achievements")
    assert r.status_code == 200
    data = r.json()
    assert data["profile"]["name"] == "Naresh Vusirikayala"
    assert len(data["suggested_questions"]) >= 15
    assert len(data["achievements"]) >= 3
    assert "follow_up_pools" in data
    assert len(data["follow_up_pools"]["employer"]) >= 4
    assert any("2 AM" in q for q in data["suggested_questions"])


def test_recruiter_ask_stream_validation():
    r = client.post("/api/v1/recruiter/ask/stream", json={"question": "x"})
    assert r.status_code == 422

def test_recruiter_ask_payload_accepts_long_jd_paste():
    from backend.routers.recruiter import RecruiterAskPayload

    question = "Please map fit to this role:\n" + "- Kubernetes\n" * 120 + ("detail " * 400)
    payload = RecruiterAskPayload(question=question)
    assert len(payload.question) > 2000



def test_build_employment_timeline_has_citi_dates():
    timeline = _build_employment_timeline()
    assert "Citigroup" in timeline
    assert "Apr 2025 – Present" in timeline
    assert "Bank of America" in timeline
    assert "Oct 2020 – Sep 2023" in timeline


def test_build_recruiter_system_first_person():
    system = _build_recruiter_system("sample context", "test@example.com")
    assert "You ARE Naresh Vusirikayala" in system
    assert "You are NOT an AI assistant" in system
    assert "IDENTITY GUARDRAILS" in system
    assert "FORBIDDEN phrases" in system
    assert "trained on" in system.lower()
    assert "SKILL QUESTION EXAMPLE" in system
    assert "Always first person" in system
    assert "Sound LIVE" in system
    assert "emoji" in system.lower()
    assert "NEVER refer to yourself in third person" in system
    assert "Do NOT invent" in system
    assert "CREATIVE SYNTHESIS" in system
    assert "ANSWER STRUCTURE" in system
    assert "At a glance" in system
    assert "Do NOT end every answer" in system
    assert "CentOS" in system
    assert "Apr 2025 – Present" in system
    assert "VERIFIED CLIENT EXPERIENCE" in system
    assert "Citigroup (CISO Organization)" in system
    assert "PingFederate" in system or "ArgoCD" in system
    assert "sample context" in system
    assert "TWO EXPERIENCE BUCKETS" in system
    assert "NEVER CONFLATE BUCKETS" in system
    assert "Personal R&D project (portfolio)" in system
    assert "LangGraph" in system
    assert "NOT production work at Citigroup" in system


def test_build_recruiter_system_hiring_manager_mode():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "What would you own in your first 90 days as a hiring manager evaluating me?",
    )
    assert "HIRING MANAGER MODE" in system
    assert "ACTIVE MODE: HIRING MANAGER" in system
    assert "Fit summary" in system
    assert "Interview probe" in system


def test_build_recruiter_system_jd_fit_mode():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "Map my fit for this role (honest Strong / Partial / Not on resume):\n\nRequirements:\n- Kubernetes\n- Terraform\n",
    )
    assert "JOB DESCRIPTION / ROLE FIT MODE" in system
    assert "ACTIVE MODE: JOB DESCRIPTION / ROLE FIT" in system
    assert "Fit at a glance" in system
    assert "Gaps (honest)" in system


def test_build_recruiter_system_incident_observability_structure():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "How do you handle production incidents and observability?",
    )
    assert "INCIDENT / OBSERVABILITY / PRODUCTION QUESTIONS" in system
    assert "Personal R&D project (portfolio):" in system
    assert "ServiceNow" in system
    assert "Do NOT weave Command Center" in system
    assert "VERIFIED SKILLS & EXPERIENCE" in system
    assert "Prometheus" in system or "Grafana" in system


def test_build_recruiter_system_employer_guard_for_client_question():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "What did you do at Bank of America and Verizon?",
    )
    assert "EMPLOYER-FOCUSED QUESTION" in system
    assert "Do NOT mention LangGraph" in system
    assert "portfolio tech is OFF LIMITS" in system


def test_sanitize_recruiter_answer_strips_demo_cta():
    raw = (
        "**Closing**\n\nHappy to elaborate.\n\n"
        "Want me to show you the live demo?"
    )
    cleaned = _sanitize_recruiter_answer(raw, "What did you do at Verizon?")
    assert "live demo" not in cleaned.lower()
    assert "Happy to elaborate" in cleaned


def test_sanitize_recruiter_answer_strips_ai_disclaimer():
    raw = (
        "I have been trained on a vast amount of text data, including information about Terraform. "
        "While I don't have personal experiences like humans do, I can tell you about Terraform.\n\n"
        "Great question! 👋 I've used Terraform heavily at Bank of America for IaC modules."
    )
    cleaned = _sanitize_recruiter_answer(raw, "What is your experience with Terraform?")
    assert "trained on" not in cleaned.lower()
    assert "personal experiences like humans" not in cleaned.lower()
    assert "Bank of America" in cleaned


def test_build_recruiter_system_injects_verified_skills_for_terraform():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "what is your experience with terraform?",
    )
    assert "VERIFIED SKILLS & EXPERIENCE" in system
    assert "Terraform" in system
    assert "Bank of America" in system
    assert "SKILL QUESTION EXAMPLE" in system
    assert "WRONG (never write this)" in system


def test_sanitize_recruiter_answer_keeps_demo_cta_for_portfolio():
    raw = "Want me to show you the live demo?"
    cleaned = _sanitize_recruiter_answer(raw, "Tell me about your SRE AI Copilot")
    assert "live demo" in cleaned.lower()


def test_filter_answer_sources_excludes_education_for_employer():
    sources = [
        {"section": "experience", "company": "Verizon", "period": "Sep 2023 – Oct 2024"},
        {"section": "education", "company": "Southern Arkansas University", "period": "Aug 2018 – Dec 2019"},
        {"section": "certifications", "company": "Amazon Web Services", "period": "Professional"},
    ]
    filtered = _filter_answer_sources(sources, "What did you do at Verizon?")
    sections = {s["section"] for s in filtered}
    assert "experience" in sections
    assert "education" not in sections
    assert "certifications" not in sections


def test_build_recruiter_system_injects_verified_skills_for_ansible():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "tell me about your ansible experience",
    )
    assert "VERIFIED SKILLS & EXPERIENCE" in system
    assert "Configuration Management" in system
    assert "Ansible Tower" in system
    assert "Bank of America" in system
    assert "Ansible playbooks" in system or "Ansible roles" in system
    assert "Do NOT infer Ansible modules" in system


def test_build_recruiter_system_injects_verified_skills_for_linux():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "tell me about your linux experience",
    )
    assert "VERIFIED SKILLS & EXPERIENCE" in system
    assert "Operating Systems" in system
    assert "Ubuntu" in system or "RHEL" in system
    assert "Bank of America" in system or "RHEL platforms" in system
    assert "Do NOT say CentOS" in system
    assert "Do NOT end every answer" in system


def test_build_verified_skills_context_linux_grounding():
    block = _build_verified_skills_context("linux experience")
    assert "Linux" in block or "linux" in block.lower()
    assert "Operating Systems" in block
    assert "Bank of America" in block or "Verizon" in block or "Anthem" in block
    assert "kernel upgrades" in block or "patching" in block or "troubleshooting" in block


def test_build_verified_skills_context_ansible_grounding():
    block = _build_verified_skills_context("tell me about your ansible experience")
    assert "Ansible" in block
    assert "Configuration Management" in block
    assert "Bank of America" in block
    assert "Citigroup" in block or "SiteMinder" in block
    assert "Verizon" in block or "worker nodes" in block
    assert "Inovus" in block or "OpenStack" in block


def test_build_verified_skills_context_empty_for_unrelated():
    assert _build_verified_skills_context("what is your favorite color?") == ""


def test_build_verified_client_experience_includes_all_employers():
    block = _build_verified_client_experience()
    for company in (
        "Citigroup (CISO Organization)",
        "Toyota Motors North America",
        "Verizon",
        "Bank of America",
        "Anthem",
        "Inovus IT Services",
    ):
        assert company in block
    assert "Oct 2020 – Sep 2023" in block
    assert "Kafka" in block


def test_build_verified_client_experience_scoped_single_employer():
    block = _build_verified_client_experience(["Bank of America"])
    assert "Bank of America" in block
    assert "Oct 2020 – Sep 2023" in block
    assert "Verizon" not in block
    assert "Citigroup (CISO Organization)" not in block


def test_build_recruiter_system_single_employer_isolation():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "What did you do at Bank of America?",
    )
    assert "SINGLE-EMPLOYER FOCUS" in system
    assert "Bank of America ONLY" in system
    assert "### Bank of America" in system
    assert "### Verizon" not in system
    assert "EMPLOYER-FOCUSED QUESTION" in system


def test_build_recruiter_system_multi_employer_isolation():
    system = _build_recruiter_system(
        "sample context",
        "test@example.com",
        "Compare my work at Bank of America and Verizon",
    )
    assert "MULTI-EMPLOYER COMPARISON" in system
    assert "Bank of America" in system
    assert "Verizon" in system
    assert "### Toyota Motors North America" not in system


@patch("backend.routers.recruiter.retrieve_profile_context")
def test_recruiter_ask_uses_profile_rag(mock_retrieve):
    mock_retrieve.return_value = (
        "[1] section=experience | company=Citigroup\nEKS and ArgoCD GitOps migration",
        [
            {
                "section": "experience",
                "company": "Citigroup (CISO Organization)",
                "period": "Apr 2025 – Present",
                "score": 0.4,
                "preview": "EKS",
            }
        ],
    )

    r = client.post(
        "/api/v1/recruiter/ask/stream",
        json={"question": "What's your Kubernetes experience?"},
    )

    assert r.status_code == 200
    mock_retrieve.assert_called_once_with("What's your Kubernetes experience?", 6)
    assert "data:" in r.text
    assert "done" in r.text


@patch("google.genai.Client")
@patch("backend.routers.recruiter.retrieve_profile_context")
@patch("backend.routers.recruiter.get_settings")
def test_recruiter_gemini_disables_thinking_budget(mock_settings, mock_retrieve, mock_client_cls):
    """Gemini 2.5 Flash must not burn max_output_tokens on hidden thinking."""
    mock_retrieve.return_value = ("sample context", [])

    class _FakeAioModels:
        async def generate_content_stream(self, *, model, contents, config):
            assert model == "gemini-2.5-flash"
            assert config.thinking_config.thinking_budget == 0
            assert config.max_output_tokens >= 2048

            async def _gen():
                yield type("Chunk", (), {"text": "Great question! Verified Citi IAM work."})()

            return _gen()

    mock_client_cls.return_value.aio.models = _FakeAioModels()

    settings = mock_settings.return_value
    settings.google_api_key = "test-key"
    settings.ollama_base_url = "http://localhost:11434"

    r = client.post(
        "/api/v1/recruiter/ask/stream",
        json={
            "question": (
                "If I'm hiring for Citi-like IAM work, "
                "why you and not the next resume?"
            ),
        },
    )

    assert r.status_code == 200
    assert "done" in r.text
    assert "Verified Citi IAM work" in r.text


def test_recruiter_view_increments_total_and_unique():
    r1 = client.post("/api/v1/recruiter/view", json={"session_id": "sess-a"})
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["total_views"] == 1
    assert body1["unique_views"] == 1
    assert body1["is_new_session"] is True

    r2 = client.post("/api/v1/recruiter/view", json={"session_id": "sess-a"})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["total_views"] == 2
    assert body2["unique_views"] == 1
    assert body2["is_new_session"] is False

    r3 = client.post("/api/v1/recruiter/view", json={"session_id": "sess-b"})
    assert r3.status_code == 200
    body3 = r3.json()
    assert body3["total_views"] == 3
    assert body3["unique_views"] == 2
    assert body3["is_new_session"] is True


def test_recruiter_view_visitor_dedup():
    r1 = client.post(
        "/api/v1/recruiter/view",
        json={"visitor_id": "visitor-x", "session_id": "sess-x1", "device_class": "desktop"},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["is_new_visitor"] is True
    assert body1["unique_views"] == 1

    r2 = client.post(
        "/api/v1/recruiter/view",
        json={"visitor_id": "visitor-x", "session_id": "sess-x2"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["is_new_visitor"] is False
    assert body2["total_views"] == body1["total_views"] + 1
    assert body2["unique_views"] == body1["unique_views"]


def test_recruiter_stats_endpoint():
    client.post("/api/v1/recruiter/view", json={"session_id": "stats-sess"})
    r = client.get("/api/v1/recruiter/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["total_views"] >= 1
    assert data["unique_views"] >= 1


@patch("backend.routers.recruiter.get_settings")
def test_admin_stats_invalid_token(mock_get_settings):
    mock_get_settings.return_value.admin_token = "secret-admin"
    r = client.get("/api/v1/recruiter/admin/stats?token=wrong")
    assert r.status_code == 401


@patch("backend.routers.recruiter.get_settings")
def test_admin_stats_not_configured(mock_get_settings):
    mock_get_settings.return_value.admin_token = ""
    r = client.get("/api/v1/recruiter/admin/stats?token=anything")
    assert r.status_code == 503


@patch("backend.routers.recruiter.get_settings")
def test_admin_stats_success(mock_get_settings):
    mock_get_settings.return_value.admin_token = "secret-admin"
    client.post(
        "/api/v1/recruiter/view",
        json={"session_id": "admin-sess", "visitor_id": "admin-visitor", "device_class": "mobile"},
    )
    r = client.get("/api/v1/recruiter/admin/stats?token=secret-admin")
    assert r.status_code == 200
    data = r.json()
    assert data["total_views"] >= 1
    assert "daily_views" in data
    assert "recent_sessions" in data
    assert "recent_visitors" in data
    if data["recent_visitors"]:
        assert "device_class" in data["recent_visitors"][0]


def test_recruiter_feedback_submission():
    r = client.post(
        "/api/v1/recruiter/feedback",
        json={
            "session_id": "fb-sess",
            "name": "Alex",
            "email": "alex@example.com",
            "feedback": "Strong platform skills — looking for more people management.",
            "reasons": ["Experience level mismatch"],
            "rating": 4,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["id"], int)


def test_recruiter_feedback_validation():
    r = client.post("/api/v1/recruiter/feedback", json={"feedback": "x"})
    assert r.status_code == 422
