"""Unit tests for candidate profile RAG ingestion and retrieval."""
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from backend.knowledge.profile_ingest import (
    _filter_hits_by_employer_scope,
    _is_hiring_manager_query,
    _is_jd_fit_query,
    build_profile_documents,
    ingest_profile,
    match_companies_in_query,
    match_skills_in_query,
    retrieve_profile_context,
)
from backend.routers import resume_content as rc


class TestBuildProfileDocuments:
    def test_builds_all_sections(self):
        docs = build_profile_documents()
        sections = {d.metadata["section"] for d in docs}
        assert "summary" in sections
        assert "skills" in sections
        assert "skill_matrix" in sections
        assert "recommendations" in sections
        assert "linkedin" in sections
        assert "featured_project" in sections
        assert "experience" in sections
        assert "education" in sections
        assert "certifications" in sections
        assert "achievements" in sections
        assert "technical_highlights" in sections
        assert "tech_stack_comparison" in sections

    def test_experience_chunks_have_company_metadata(self):
        docs = build_profile_documents()
        citi = next(
            d for d in docs
            if d.metadata.get("section") == "experience"
            and "Citigroup" in d.metadata.get("company", "")
        )
        assert "EKS" in citi.page_content or "ArgoCD" in citi.page_content
        assert citi.metadata["period"] == "Apr 2025 – Present"
        assert "Client experience" in citi.page_content
        assert "Also known as: citi" in citi.page_content

    def test_match_companies_in_query_aliases(self):
        assert "Citigroup (CISO Organization)" in match_companies_in_query("What did you do at Citi?")
        assert "Bank of America" in match_companies_in_query("Summarize your BofA Kafka work")
        assert "Verizon" in match_companies_in_query("Tell me about Verizon Smart Family")

    def test_match_skills_in_query_ansible_kafka_observability(self):
        assert "Ansible" in match_skills_in_query("tell me about your ansible experience")
        assert "Kafka" in match_skills_in_query("Summarize your Kafka and event-streaming experience")
        assert "observability" in match_skills_in_query("Compare your observability stack experience")
        assert "Kubernetes" in match_skills_in_query("What's your k8s experience?")

    def test_match_topics_in_query_linux(self):
        from backend.knowledge.profile_ingest import get_skill_match_terms, match_topics_in_query

        assert "linux" in match_topics_in_query("linux experience")
        assert "linux" in match_topics_in_query("unix administration background")
        terms = get_skill_match_terms("tell me about your linux experience")
        assert "linux" in terms
        assert "unix" in terms or "rhel" in terms

    def test_technical_highlights_include_langgraph(self):
        docs = build_profile_documents()
        highlights = [d for d in docs if d.metadata.get("section") == "technical_highlights"]
        assert len(highlights) >= 5
        combined = " ".join(d.page_content for d in highlights)
        assert "LangGraph" in combined
        assert "ArgoCD" in combined or "EKS" in combined

    def test_skill_matrix_includes_kubernetes(self):
        docs = build_profile_documents()
        matrix = [d for d in docs if d.metadata.get("section") == "skill_matrix"]
        assert len(matrix) >= 10
        combined = " ".join(d.page_content for d in matrix)
        assert "Kubernetes" in combined or "EKS" in combined
        assert "Expert" in combined

    def test_recommendations_include_colleague_quotes(self):
        docs = build_profile_documents()
        recs = [d for d in docs if d.metadata.get("section") == "recommendations"]
        assert len(recs) >= 2
        combined = " ".join(d.page_content for d in recs)
        assert "Ashwin" in combined or "Carrie" in combined
        assert "recommend" in combined.lower()

    def test_document_count_increased_with_matrix_and_recommendations(self):
        docs = build_profile_documents()
        # baseline ~31 + 12 skill_matrix + 2 recommendations + 1 linkedin + 3 extra skill categories
        assert len(docs) >= 45

    def test_behavioral_stories_indexed(self):
        docs = build_profile_documents()
        behavioral = [d for d in docs if d.metadata.get("section") == "behavioral_stories"]
        assert len(behavioral) == 3
        combined = " ".join(d.page_content for d in behavioral)
        assert "Broadcom load balancer" in combined
        assert "Micrometer + Prometheus" in combined
        assert "HashiCorp Vault" in combined

    def test_observability_journey_indexed(self):
        docs = build_profile_documents()
        journey = [d for d in docs if d.metadata.get("section") == "observability_journey"]
        assert len(journey) == 1
        text = journey[0].page_content
        assert "HTTP status" in text or "status code" in text.lower()
        assert "Autosys" in text
        assert "NGINX" in text
        assert "Dynatrace" in text or "Splunk" in text

    def test_jd_fit_query_detection(self):
        assert _is_jd_fit_query("Map my fit for this role:\n- K8s\n- Terraform\n")
        assert _is_hiring_manager_query("Biggest honest gap for a Staff SRE role?")
        assert not _is_jd_fit_query("What did you do at Citi?")


class TestIngestProfile:
    @patch("backend.knowledge.profile_ingest.Chroma.from_documents")
    @patch("backend.knowledge.profile_ingest._get_chroma_client")
    def test_ingest_creates_collection(self, mock_client_fn, mock_from_docs):
        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client
        mock_client.get_collection.side_effect = Exception("missing")

        count = ingest_profile(force=True)

        assert count == len(build_profile_documents())
        mock_from_docs.assert_called_once()
        args, kwargs = mock_from_docs.call_args
        assert kwargs["collection_name"] == "sre_candidate_profile"
        assert len(kwargs["documents"]) >= 10


class TestRetrieveProfileContext:
    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_kubernetes_query_returns_relevant_chunks(self, mock_retrieve):
        mock_retrieve.return_value = [
            (
                Document(
                    page_content="Senior Cloud DevOps @ Citigroup — EKS, ArgoCD GitOps, Karpenter",
                    metadata={
                        "section": "experience",
                        "company": "Citigroup (CISO Organization)",
                        "period": "Apr 2025 – Present",
                    },
                ),
                0.42,
            ),
            (
                Document(
                    page_content="Skills — sre: Kubernetes · EKS · AKS · OpenShift · Helm · Karpenter",
                    metadata={"section": "skills", "company": "", "period": ""},
                ),
                0.55,
            ),
        ]

        context, sources = retrieve_profile_context("What Kubernetes experience does he have?", k=4)

        mock_retrieve.assert_called_once_with(
            "What Kubernetes experience does he have?",
            "sre_candidate_profile",
            k=12,
        )
        assert "EKS" in context
        assert "Kubernetes" in context
        assert len(sources) >= 2

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_colleague_recommendation_query(self, mock_retrieve):
        mock_retrieve.return_value = [
            (
                Document(
                    page_content='LinkedIn recommendation from Ashwin Krishnamoorthy: "highly skilled and dependable"',
                    metadata={
                        "section": "recommendations",
                        "company": "Former colleague (~3 years)",
                        "period": "Ashwin Krishnamoorthy",
                    },
                ),
                0.35,
            ),
        ]

        context, sources = retrieve_profile_context("What do colleagues say about Naresh?", k=4)

        assert "Ashwin" in context
        assert sources[0]["section"] == "recommendations"

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_client_query_boosts_matching_experience(self, mock_retrieve):
        mock_retrieve.return_value = [
            (
                Document(
                    page_content="Skills — sre: Kubernetes · EKS · AKS · OpenShift · Helm · Karpenter",
                    metadata={"section": "skills", "company": "", "period": ""},
                ),
                0.55,
            ),
        ]

        context, sources = retrieve_profile_context("What did you do at Citi?", k=4)

        assert mock_retrieve.call_args.kwargs["k"] == 12
        assert "Citigroup (CISO Organization)" in context
        assert any(src["section"] == "experience" for src in sources)
        assert any(
            src.get("company") == "Citigroup (CISO Organization)" for src in sources
        )

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_general_client_query_includes_all_experience(self, mock_retrieve):
        mock_retrieve.return_value = []

        context, sources = retrieve_profile_context("Walk me through your client experience", k=6)

        assert "Bank of America" in context
        assert "Verizon" in context
        assert len(sources) >= 6
        assert all(src["section"] == "experience" for src in sources)

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_ansible_query_boosts_skills_and_matching_bullets(self, mock_retrieve):
        mock_retrieve.return_value = [
            (
                Document(
                    page_content="Professional summary detail 5: CI/CD with Jenkins and Helm",
                    metadata={"section": "summary_details", "company": "", "period": ""},
                ),
                0.62,
            ),
        ]

        context, sources = retrieve_profile_context("tell me about your ansible experience", k=6)

        assert mock_retrieve.call_args.kwargs["k"] == 12
        assert "Configuration Management" in context
        assert "Ansible" in context
        assert any(src["section"] in ("skills", "skill_matrix", "experience_bullet") for src in sources)
        assert any(
            src.get("section") == "experience_bullet" and src.get("company") == "Bank of America"
            for src in sources
        )
        assert "Ansible Tower" in context or "Ansible playbooks" in context

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_linux_query_boosts_os_matrix_and_bullets(self, mock_retrieve):
        mock_retrieve.return_value = []

        context, sources = retrieve_profile_context("linux experience", k=6)

        assert mock_retrieve.call_args.kwargs["k"] == 12
        assert "Linux" in context or "RHEL" in context or "Unix" in context
        assert any(
            src["section"] in ("skill_matrix", "summary_details", "experience_bullet", "experience_environment")
            for src in sources
        )
        assert "Bank of America" in context or "Verizon" in context or "Anthem" in context

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_observability_query_boosts_skills_category(self, mock_retrieve):
        mock_retrieve.return_value = []

        context, sources = retrieve_profile_context("Compare your observability stack experience", k=4)

        assert "observability" in context.lower() or "Prometheus" in context
        assert any(src["section"] == "observability_journey" for src in sources)
        assert "Autosys" in context or "NGINX" in context
        assert any(
            src["section"] in ("skills", "skill_matrix", "experience_bullet", "summary_details", "observability_journey")
            for src in sources
        )

    @patch("backend.knowledge.profile_ingest.retrieve_with_score", return_value=[])
    def test_empty_retrieval(self, _mock_retrieve):
        context, sources = retrieve_profile_context("unknown topic")
        assert context == ""
        assert sources == []

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_client_query_excludes_education_and_certs_from_sources(self, mock_retrieve):
        mock_retrieve.return_value = [
            (
                Document(
                    page_content="Client experience — Senior Cloud DevOps @ Verizon\n• Led EKS cluster setup",
                    metadata={
                        "section": "experience",
                        "company": "Verizon",
                        "period": "Sep 2023 – Oct 2024",
                    },
                ),
                0.2,
            ),
            (
                Document(
                    page_content="Master of Science, Computer Information Science",
                    metadata={
                        "section": "education",
                        "company": "Southern Arkansas University",
                        "period": "Aug 2018 – Dec 2019",
                    },
                ),
                0.15,
            ),
            (
                Document(
                    page_content="Certification: AWS Certified DevOps Engineer — Professional",
                    metadata={
                        "section": "certifications",
                        "company": "Amazon Web Services",
                        "period": "Professional",
                    },
                ),
                0.18,
            ),
        ]

        _context, sources = retrieve_profile_context("What did you do at Verizon?", k=6)

        assert any(src["section"] == "experience" for src in sources)
        assert not any(src["section"] == "education" for src in sources)
        assert not any(src["section"] == "certifications" for src in sources)

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_incident_query_excludes_featured_project(self, mock_retrieve):
        mock_retrieve.return_value = [
            (
                Document(
                    page_content="Portfolio project — SRE AI Copilot — LangGraph checkpoints with Redis",
                    metadata={
                        "section": "featured_project",
                        "company": "SRE AI Copilot",
                        "period": "2025 – Present",
                    },
                ),
                0.15,
            ),
            (
                Document(
                    page_content=(
                        "Experience bullet — Senior Cloud DevOps @ Citigroup\n"
                        "• Configured Prometheus and Grafana for EKS; ServiceNow INC automation"
                    ),
                    metadata={
                        "section": "experience_bullet",
                        "company": "Citigroup (CISO Organization)",
                        "period": "Apr 2025 – Present",
                    },
                ),
                0.35,
            ),
        ]

        context, sources = retrieve_profile_context(
            "How do you handle production incidents and observability?",
            k=6,
        )

        assert mock_retrieve.call_args.kwargs["k"] == 12
        assert "Citigroup" in context
        assert "Prometheus" in context or "ServiceNow" in context
        assert not any(src["section"] == "featured_project" for src in sources)
        assert "LangGraph" not in context

    @patch("backend.knowledge.profile_ingest.retrieve_with_score")
    def test_portfolio_query_includes_featured_project(self, mock_retrieve):
        mock_retrieve.return_value = [
            (
                Document(
                    page_content="Portfolio project — SRE AI Copilot — LangGraph multi-agent orchestration",
                    metadata={
                        "section": "featured_project",
                        "company": "SRE AI Copilot",
                        "period": "2025 – Present",
                    },
                ),
                0.2,
            ),
        ]

        context, sources = retrieve_profile_context("Tell me about your SRE AI Copilot", k=4)

        assert any(src["section"] == "featured_project" for src in sources)
        assert "LangGraph" in context or "SRE AI Copilot" in context

    def test_is_incident_observability_query_detection(self):
        from backend.knowledge.profile_ingest import (
            _is_incident_observability_query,
            _is_portfolio_query,
        )

        assert _is_incident_observability_query(
            "How do you handle production incidents and observability?"
        )
        assert not _is_portfolio_query(
            "How do you handle production incidents and observability?"
        )
        assert _is_portfolio_query("Tell me about your SRE AI Copilot portfolio")
        assert not _is_incident_observability_query("Tell me about your SRE AI Copilot")


def test_filter_hits_by_employer_scope_excludes_other_clients():
    hits = [
        (
            Document(
                page_content="BofA work",
                metadata={"section": "experience", "company": "Bank of America", "period": "2020"},
            ),
            0.1,
        ),
        (
            Document(
                page_content="Verizon work",
                metadata={"section": "experience", "company": "Verizon", "period": "2023"},
            ),
            0.2,
        ),
        (
            Document(
                page_content="Skills",
                metadata={"section": "skills", "company": "sre", "period": ""},
            ),
            0.3,
        ),
    ]
    filtered = _filter_hits_by_employer_scope(hits, ["Bank of America"])
    exp_companies = [
        doc.metadata["company"]
        for doc, _ in filtered
        if doc.metadata.get("section") == "experience"
    ]
    assert exp_companies == ["Bank of America"]
    assert any(doc.metadata.get("section") == "skills" for doc, _ in filtered)
