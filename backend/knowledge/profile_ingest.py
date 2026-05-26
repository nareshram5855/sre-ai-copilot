"""
Resume / candidate profile ingestion for recruiter RAG.

Chunks resume_content.py into logical documents (summary, jobs, skills, project,
achievements) — separate from runbook/architecture collections.
"""
from __future__ import annotations

import logging

from langchain_chroma import Chroma
from langchain_core.documents import Document

from backend.config import settings
from backend.rag.embeddings import get_embeddings
from backend.rag.ingestor import _get_chroma_client
from backend.rag.retriever import retrieve_with_score
from backend.routers import resume_content as rc

logger = logging.getLogger(__name__)

_PROFILE_DOMAIN = "profile"

# Aliases recruiters use in chat — mapped to RESUME_EXPERIENCE company strings.
_EMPLOYER_ALIASES: dict[str, list[str]] = {
    "Citigroup (CISO Organization)": ["citi", "citigroup", "ciso"],
    "Toyota Motors North America": ["toyota"],
    "Verizon": ["verizon", "vsf", "smart family", "verizon smart family"],
    "Bank of America": ["bank of america", "bofa", "boa"],
    "Anthem": ["anthem"],
    "Inovus IT Services": ["inovus"],
}

_CLIENT_QUERY_HINTS = (
    "client",
    "clients",
    "employer",
    "employers",
    "company",
    "companies",
    "work history",
    "worked at",
    "work at",
    "experience at",
    "project at",
    "projects at",
    "role at",
    "job at",
    "consulting",
    "stint",
    "tenure",
    "where did you work",
    "who did you work for",
    "which clients",
    "which companies",
    "tell me about your time",
)

_SKILL_QUERY_HINTS = (
    "experience with",
    "experience in",
    "experience using",
    "tell me about your",
    "how do you use",
    "how have you used",
    "what is your",
    "what's your",
    "do you know",
    "are you familiar",
    "proficiency",
    "skill in",
    "skills in",
    "worked with",
    "work with",
    "using ",
    "used ",
    "hands-on",
    "hands on",
    "expertise",
    "strongest in",
    "compare your",
)

# Recruiter chat aliases → canonical skill/category from resume_content.
_SKILL_ALIASES: dict[str, list[str]] = {
    "kubernetes": ["k8s", "kube"],
    "ansible": ["ansible tower"],
    "kafka": ["event streaming", "event-streaming"],
    "observability": ["monitoring stack", "monitoring tools"],
    "terraform": ["iac", "infrastructure as code"],
    "prometheus": ["prom"],
    "grafana": [],
    "jenkins": [],
    "argocd": ["gitops"],
    "eks": ["elastic kubernetes service"],
    "vault": ["hashicorp vault", "secrets", "secrets management"],
    "micrometer": ["heap", "gc", "jvm metrics"],
    "linux (ubuntu, fedora, rhel)": ["linux", "unix", "unix/linux", "rhel", "red hat linux", "ubuntu", "fedora"],
    "shell/bash": ["bash", "shell scripting", "shell scripts"],
}

_INCIDENT_OBSERVABILITY_HINTS = (
    "incident",
    "incidents",
    "observability",
    "monitoring",
    "on-call",
    "on call",
    "oncall",
    "triage",
    "alerting",
    "alert manager",
    "alertmanager",
    "servicenow",
    "service now",
    "production support",
    "production incident",
    "sox",
    "netcool",
    "dynatrace",
    "splunk",
    "datadog",
    "elasticsearch",
    "health check",
    "status code",
    "autosys",
    "elk",
    "logging",
    "metrics",
    "apm",
    "custom monitoring",
    "major incident",
    "24/7",
    "slo",
    "sli",
)

_HIRING_MANAGER_QUERY_HINTS = (
    "hiring manager",
    "would you hire",
    "first 90 days",
    "90-day",
    "staff sre",
    "staff engineer",
    "senior vs staff",
    "biggest gap",
    "biggest weakness",
    "weakness for this role",
    "honest gap",
    "ownership",
    "what would you own",
    "lead a team",
    "manage engineers",
    "interview loop",
    "debrief",
    "hiring brief",
    "30-second",
    "30 second",
    "why you over",
    "vs the next resume",
    "not the next resume",
    "production proof",
    "scope at",
)

_JD_FIT_QUERY_HINTS = (
    "job description",
    "paste jd",
    "paste the jd",
    "role requirements",
    "role requirement",
    "must have",
    "nice to have",
    "qualifications",
    "responsibilities",
    "we're hiring",
    "we are hiring",
    "looking for a",
    "map my fit",
    "fit for this role",
    "strong/partial",
    "strong | partial",
    "requirements:",
    "required skills",
)

_BEHAVIORAL_QUERY_HINTS = (
    "tell me about a time",
    "describe a time",
    "give me an example",
    "behavioral",
    "star format",
    "situation when",
    "conflict with",
    "conflict between",
    "development team",
    "dev team",
    "monitoring failed",
    "alerting failed",
    "didn't catch",
    "did not catch",
    "memory leak",
    "major production",
    "production incident",
    "war story",
    "what broke",
    "how did you fix",
    "deal with a conflict",
    "hardcoded",
    "credentials",
    "vault",
    "network isolation",
    "privatelink",
    "private endpoint",
    "multi-tenant",
    "mongodb atlas",
    "networkpolicy",
    "namespace isolation",
    "secret rotation",
    "vault agent",
    "sidecar injector",
    "vault injector",
    "openshift migration",
    "zero downtime",
)

_PORTFOLIO_QUERY_HINTS = (
    "copilot",
    "sre ai",
    "portfolio",
    "demo platform",
    "this demo",
    "this project",
    "this repository",
    "github",
    "langgraph",
    "command center",
    "interview presentation",
    "live demo",
    "rag runbook",
    "chroma",
    "ollama",
    "minikube",
)

# Portfolio-only sections/chunks — excluded from employer-focused retrieval.
_PORTFOLIO_SECTIONS = frozenset({"featured_project"})
_BROAD_TOPIC_ALIASES: dict[str, list[str]] = {
    "linux": [
        "linux",
        "unix",
        "unix/linux",
        "rhel",
        "red hat",
        "ubuntu",
        "fedora",
        "operating system",
        "operating systems",
        "shell/bash",
        "bash",
        "ssh",
    ],
    "cloud": ["aws", "azure", "gcp", "multi-cloud", "ec2", "cloud platform"],
    "kubernetes": ["k8s", "kube", "eks", "aks", "openshift", "helm", "container"],
    "observability": ["monitoring", "prometheus", "grafana", "splunk", "datadog", "logging"],
    "cicd": ["ci/cd", "continuous integration", "continuous delivery", "jenkins", "gitops", "argocd"],
}


def _collection_name() -> str:
    return settings.knowledge_collections[_PROFILE_DOMAIN]


def _is_client_experience_query(query: str) -> bool:
    """True when the recruiter is asking about employers, clients, or work history."""
    q = query.lower()
    return any(hint in q for hint in _CLIENT_QUERY_HINTS) or bool(match_companies_in_query(query))


def _is_portfolio_query(query: str) -> bool:
    """True when the recruiter is asking about the SRE AI Copilot portfolio project."""
    q = query.lower()
    return any(hint in q for hint in _PORTFOLIO_QUERY_HINTS)


def _is_incident_observability_query(query: str) -> bool:
    """True when the recruiter asks about production incidents, monitoring, or observability."""
    q = query.lower()
    if _is_behavioral_query(query):
        return True
    if any(hint in q for hint in _INCIDENT_OBSERVABILITY_HINTS):
        return True
    topics = match_topics_in_query(query)
    skills = match_skills_in_query(query)
    observability_terms = {"observability", "Prometheus", "Grafana", "Splunk", "Datadog", "Dynatrace"}
    return "observability" in topics or bool(observability_terms.intersection(set(skills)))


def _is_jd_fit_query(query: str) -> bool:
    """True when the user pasted a JD or asks for explicit role-fit mapping."""
    q = query.strip()
    lower = q.lower()
    if any(hint in lower for hint in _JD_FIT_QUERY_HINTS):
        return True
    if len(q) >= 220:
        return True
    if q.count("\n") >= 2 and len(q) >= 80:
        return True
    bullet_lines = sum(1 for line in q.splitlines() if line.strip().startswith(("-", "•", "*")))
    return bullet_lines >= 2


def _is_hiring_manager_query(query: str) -> bool:
    """True for hiring-manager decision / scope / fit framing (not generic recruiter screen)."""
    if _is_jd_fit_query(query):
        return True
    q = query.lower()
    return any(hint in q for hint in _HIRING_MANAGER_QUERY_HINTS)


def _is_behavioral_query(query: str) -> bool:
    """True when the recruiter asks STAR / behavioral interview style questions."""
    q = query.lower()
    return any(hint in q for hint in _BEHAVIORAL_QUERY_HINTS)


def _is_portfolio_chunk(doc: Document) -> bool:
    """True for chunks that describe the SRE AI Copilot portfolio — not employer production work."""
    meta = doc.metadata or {}
    section = meta.get("section", "")
    if section in _PORTFOLIO_SECTIONS:
        return True
    if section == "tech_stack_comparison" and meta.get("company") == "demo":
        return True
    content = doc.page_content.lower()
    if section == "technical_highlights" and any(
        marker in content
        for marker in ("sre ai copilot", "langgraph", "245 automated tests", "github actions cd to minikube")
    ):
        return True
    if section == "achievements" and ("this demo" in content or "sre ai copilot" in content):
        return True
    return False


def _filter_portfolio_chunks(
    hits: list[tuple[Document, float]],
    *,
    exclude_portfolio: bool,
) -> list[tuple[Document, float]]:
    if not exclude_portfolio:
        return hits
    return [(doc, score) for doc, score in hits if not _is_portfolio_chunk(doc)]


# Sections that rarely help employer/skill/incident answers — keep out of grounded-in UI.
_LOW_VALUE_SECTIONS_FOR_WORK_QUESTIONS = frozenset({"education", "certifications"})


def _filter_hits_by_employer_scope(
    hits: list[tuple[Document, float]],
    matched_companies: list[str],
) -> list[tuple[Document, float]]:
    """When the question names specific employer(s), drop other clients' experience chunks."""
    if not matched_companies:
        return hits

    allowed = set(matched_companies)
    global_sections = frozenset({
        "skills",
        "skill_matrix",
        "summary",
        "summary_details",
        "linkedin",
    })
    experience_sections = frozenset({
        "experience",
        "experience_bullet",
        "experience_environment",
    })

    filtered: list[tuple[Document, float]] = []
    for doc, score in hits:
        meta = doc.metadata or {}
        section = meta.get("section", "")
        company = meta.get("company", "")

        if section in global_sections:
            filtered.append((doc, score))
            continue

        if section in experience_sections:
            if company in allowed:
                filtered.append((doc, score))
            continue

        if section == "recommendations":
            if any(c.lower() in doc.page_content.lower() for c in matched_companies):
                filtered.append((doc, score))
            continue

        if section == "achievements":
            if any(c.split("(")[0].strip().lower() in doc.page_content.lower() for c in matched_companies):
                filtered.append((doc, score))
            continue

        if section in _PORTFOLIO_SECTIONS:
            continue

        if company and company not in allowed:
            continue

        filtered.append((doc, score))

    return filtered if filtered else hits


def _filter_sources_for_query(
    hits: list[tuple[Document, float]],
    query: str,
) -> list[tuple[Document, float]]:
    """Drop education/certs and portfolio chunks from sources for work-focused questions."""
    portfolio_query = _is_portfolio_query(query)
    if portfolio_query:
        return hits

    client_query = _is_client_experience_query(query)
    skill_query = _is_skill_query(query)
    incident_query = _is_incident_observability_query(query)
    matched_companies = match_companies_in_query(query)

    if not (client_query or skill_query or incident_query or matched_companies):
        return hits

    filtered: list[tuple[Document, float]] = []
    for doc, score in hits:
        meta = doc.metadata or {}
        section = meta.get("section", "")
        if section in _LOW_VALUE_SECTIONS_FOR_WORK_QUESTIONS:
            continue
        if _is_portfolio_chunk(doc):
            continue
        filtered.append((doc, score))

    return filtered if filtered else hits


def match_companies_in_query(query: str) -> list[str]:
    """Return RESUME_EXPERIENCE company names mentioned directly or via alias."""
    q = query.lower()
    matched: list[str] = []
    for company in rc.RESUME_EXPERIENCE:
        name = company["company"]
        name_lower = name.lower()
        aliases = [name_lower, *_EMPLOYER_ALIASES.get(name, [])]
        if any(alias in q for alias in aliases):
            matched.append(name)
    return matched


def _build_skill_vocabulary() -> list[tuple[str, str]]:
    """Return (keyword_lower, canonical) pairs sorted longest-first for greedy matching."""
    vocab: dict[str, str] = {}

    for row in rc.RESUME_SKILL_MATRIX:
        for skill in row["skills"]:
            vocab[skill.lower()] = skill

    for category, items in rc.RESUME_SKILLS.items():
        vocab[category.lower()] = category
        for item in items:
            for part in item.split(" · "):
                part = part.strip()
                if part:
                    vocab[part.lower()] = part

    for canonical, aliases in _SKILL_ALIASES.items():
        resolved = vocab.get(canonical.lower(), canonical)
        vocab[canonical.lower()] = resolved
        for alias in aliases:
            vocab[alias.lower()] = resolved

    return sorted(vocab.items(), key=lambda item: len(item[0]), reverse=True)


def match_skills_in_query(query: str) -> list[str]:
    """Return resume skills/categories mentioned in the query (longest match wins)."""
    q = query.lower()
    matched: list[str] = []
    seen: set[str] = set()
    for keyword, canonical in _build_skill_vocabulary():
        if keyword in q:
            key = canonical.lower()
            if key not in seen:
                matched.append(canonical)
                seen.add(key)
    return matched


def match_topics_in_query(query: str) -> list[str]:
    """Return broad resume topics (linux, cloud, kubernetes, …) mentioned in the query."""
    q = query.lower()
    matched: list[str] = []
    for topic, aliases in _BROAD_TOPIC_ALIASES.items():
        if topic in q or any(alias in q for alias in aliases):
            matched.append(topic)
    return matched


def get_skill_match_terms(query: str) -> list[str]:
    """Lowercase terms for matching resume bullets, matrix rows, and skill categories."""
    terms: list[str] = [skill.lower() for skill in match_skills_in_query(query)]
    for topic in match_topics_in_query(query):
        terms.append(topic)
        terms.extend(alias.lower() for alias in _BROAD_TOPIC_ALIASES.get(topic, []))
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term and term not in seen:
            deduped.append(term)
            seen.add(term)
    return deduped


def _is_skill_query(query: str) -> bool:
    """True when the recruiter is asking about a tool, skill, or technology area."""
    skills = match_skills_in_query(query)
    topics = match_topics_in_query(query)
    if not skills and not topics:
        return False
    q = query.lower()
    if any(hint in q for hint in _SKILL_QUERY_HINTS):
        return True
    # Direct mentions like "your ansible experience" or "compare observability stack"
    return any(
        token in q
        for token in (
            " experience",
            " skill",
            " skills",
            " stack",
            " tooling",
            " tools",
            " background",
        )
    )


def _skill_matches_text(text: str, skills: list[str], *, terms: list[str] | None = None) -> bool:
    text_lower = text.lower()
    match_terms = terms if terms is not None else [s.lower() for s in skills]
    for term in match_terms:
        if term in text_lower:
            return True
    for skill in skills:
        if skill.lower() in text_lower:
            return True
    return False


def _build_skills_category_document(category: str, items: list[str]) -> Document:
    return Document(
        page_content=f"Skills — {category}:\n" + "\n".join(f"• {s}" for s in items),
        metadata={"section": "skills", "company": category, "period": ""},
    )


def _build_skill_matrix_document(row: dict) -> Document:
    endorsed = "LinkedIn-endorsed" if row.get("endorsed_on_linkedin") else "Portfolio"
    skill_lines = "\n".join(f"• {s}" for s in row["skills"])
    return Document(
        page_content=(
            f"Skill matrix — {row['category']} ({row['proficiency']}, {endorsed}):\n"
            f"{skill_lines}"
        ),
        metadata={
            "section": "skill_matrix",
            "company": row["category"],
            "period": row["proficiency"],
        },
    )


def _build_experience_bullet_document(job: dict, bullet: str) -> Document:
    return Document(
        page_content=(
            f"Experience bullet — {job['role']} @ {job['company']} ({job['period']})\n"
            f"• {bullet}"
        ),
        metadata={
            "section": "experience_bullet",
            "company": job["company"],
            "period": job["period"],
            "role": job.get("role", ""),
        },
    )


def _build_skill_boosted_documents(
    skills: list[str],
    *,
    match_terms: list[str] | None = None,
) -> list[tuple[Document, float]]:
    """Build authoritative chunks for skills matrix, categories, and matching bullets."""
    if not skills and not match_terms:
        return []

    terms = match_terms or [s.lower() for s in skills]
    bullets: list[Document] = []
    environments: list[Document] = []
    matrix_rows: list[Document] = []
    summaries: list[Document] = []
    categories: list[Document] = []

    for category, items in rc.RESUME_SKILLS.items():
        if _skill_matches_text(category, skills, terms=terms) or any(
            _skill_matches_text(item, skills, terms=terms) for item in items
        ):
            categories.append(_build_skills_category_document(category, items))

    for row in rc.RESUME_SKILL_MATRIX:
        if _skill_matches_text(row["category"], skills, terms=terms) or any(
            _skill_matches_text(skill, skills, terms=terms) for skill in row["skills"]
        ):
            matrix_rows.append(_build_skill_matrix_document(row))

    for idx, bullet in enumerate(getattr(rc, "RESUME_SUMMARY_DETAILS", []) or [], start=1):
        if _skill_matches_text(bullet, skills, terms=terms):
            summaries.append(
                Document(
                    page_content=f"Professional summary detail {idx}: {bullet}",
                    metadata={"section": "summary_details", "company": "", "period": ""},
                )
            )

    for job in rc.RESUME_EXPERIENCE:
        env = job.get("environment", "")
        if env and _skill_matches_text(env, skills, terms=terms):
            environments.append(
                Document(
                    page_content=(
                        f"Environment — {job['role']} @ {job['company']} ({job['period']})\n"
                        f"{env}"
                    ),
                    metadata={
                        "section": "experience_environment",
                        "company": job["company"],
                        "period": job["period"],
                        "role": job.get("role", ""),
                    },
                )
            )
        for bullet in job["bullets"]:
            if _skill_matches_text(bullet, skills, terms=terms):
                bullets.append(_build_experience_bullet_document(job, bullet))

    # Recruiter answers need employer examples first, then matrix/summary context.
    ordered = bullets + environments + matrix_rows + summaries + categories
    boosted: list[tuple[Document, float]] = []
    seen: set[str] = set()

    for doc in ordered:
        key = f"{doc.metadata.get('section','')}::{doc.metadata.get('company','')}::{doc.page_content[:120]}"
        if key in seen:
            continue
        seen.add(key)
        boosted.append((doc, 0.0))

    return boosted


def _build_portfolio_boosted_documents() -> list[tuple[Document, float]]:
    """Authoritative chunks for SRE AI Copilot portfolio questions."""
    project = rc.FEATURED_PROJECT
    docs: list[tuple[Document, float]] = [
        (
            Document(
                page_content=(
                    f"Personal R&D portfolio project: {project['name']}\n"
                    f"NOT employer production work — independent demo built to showcase SRE + AI skills.\n"
                    f"Role: {project['role']}\n"
                    f"Period: {project['period']}\n"
                    f"Repository: {project['repo_label']}\n\n"
                    f"{project['summary']}\n\n"
                    f"Tech stack: {', '.join(project['tech_stack'])}"
                ),
                metadata={
                    "section": "featured_project",
                    "company": project["name"],
                    "period": project["period"],
                    "portfolio": True,
                },
            ),
            0.0,
        )
    ]
    for highlight in project["highlights"]:
        docs.append(
            (
                Document(
                    page_content=(
                        f"Portfolio project (not employer work) — SRE AI Copilot — "
                        f"{highlight['label']}: {highlight['detail']}"
                    ),
                    metadata={
                        "section": "featured_project",
                        "company": project["name"],
                        "period": project["period"],
                        "portfolio": True,
                    },
                ),
                0.0,
            )
        )
    return docs


def _build_behavioral_document(story: dict) -> Document:
    skills = ", ".join(story.get("skills", []))
    return Document(
        page_content=(
            f"SRE behavioral interview story — {story['title']}\n"
            f"Interview question: {story['question']}\n"
            f"Theme: {story.get('theme', '')}\n"
            f"Skills demonstrated: {skills}\n\n"
            f"Situation: {story['situation']}\n\n"
            f"Action: {story['action']}\n\n"
            f"Result: {story['result']}"
        ),
        metadata={
            "section": "behavioral_stories",
            "company": "",
            "period": "",
            "theme": story.get("theme", ""),
        },
    )


def _build_behavioral_boosted_documents(query: str) -> list[tuple[Document, float]]:
    """Boost behavioral STAR stories when the recruiter asks incident/behavioral questions."""
    q = query.lower()
    stories = getattr(rc, "RESUME_BEHAVIORAL_STORIES", []) or []
    boosted: list[tuple[Document, float]] = []
    for story in stories:
        score = 0.0
        theme = story.get("theme", "")
        if theme == "production_incident" and any(
            h in q for h in ("incident", "production", "what broke", "major", "war story", "fix it")
        ):
            score = 0.0
        elif theme == "observability_gap" and any(
            h in q for h in ("monitoring", "alerting", "observability", "memory leak", "didn't catch", "failed to catch")
        ):
            score = 0.0
        elif theme == "cross_team_collaboration" and any(
            h in q for h in ("conflict", "development team", "dev team", "vault", "credentials", "hardcoded")
        ):
            score = 0.0
        elif theme == "network_isolation" and any(
            h in q for h in ("network isolation", "privatelink", "private endpoint", "multi-tenant",
                             "mongodb", "networkpolicy", "namespace", "isolation", "network security")
        ):
            score = 0.0
        elif theme == "secrets_management" and any(
            h in q for h in ("secret rotation", "vault agent", "sidecar", "vault injector",
                             "secret management", "downtime", "openshift migration", "vm to container",
                             "restart", "secrets", "hashicorp vault")
        ):
            score = 0.0
        elif _is_behavioral_query(query):
            score = 0.0
        else:
            continue
        boosted.append((_build_behavioral_document(story), score))
    return boosted


def _is_observability_focused_query(query: str) -> bool:
    """True when the recruiter asks about monitoring, logging, metrics, or APM."""
    q = query.lower()
    hints = (
        "observability",
        "monitoring",
        "prometheus",
        "grafana",
        "splunk",
        "dynatrace",
        "datadog",
        "elk",
        "logging",
        "metrics",
        "health check",
        "status code",
        "autosys",
        "apm",
        "alerting",
        "compare your observability",
        "monitoring tools",
        "monitoring stack",
        "log analysis",
    )
    return any(h in q for h in hints)


def _build_observability_journey_document() -> Document:
    journey = getattr(rc, "RESUME_OBSERVABILITY_JOURNEY", None)
    if not journey:
        return Document(page_content="", metadata={"section": "observability_journey"})
    diy = "\n".join(f"• {line}" for line in journey["diy_phase"])
    enterprise = "\n".join(f"• {line}" for line in journey["enterprise_phase"])
    skills = ", ".join(journey.get("skills", []))
    return Document(
        page_content=(
            f"Observability career journey — {journey['title']}\n"
            f"LEAD WITH THIS ORIGIN STORY for observability, monitoring, logging, metrics, or APM questions.\n"
            f"Skills: {skills}\n\n"
            f"How it started: {journey['lead']}\n\n"
            f"DIY / early custom observability (shell, Python, NGINX, Autosys):\n{diy}\n\n"
            f"Enterprise platforms at verified employers:\n{enterprise}\n\n"
            f"Hiring manager framing: {journey['recruiter_hook']}"
        ),
        metadata={
            "section": "observability_journey",
            "company": journey.get("primary_employer", ""),
            "period": "",
            "theme": "observability_journey",
        },
    )


def _build_experience_document(job: dict) -> Document:
    """Single experience chunk with employer aliases for better retrieval."""
    bullets = "\n".join(f"• {b}" for b in job["bullets"])
    description = job.get("description", "")
    environment = job.get("environment", "")
    aliases = _EMPLOYER_ALIASES.get(job["company"], [])
    alias_line = f"Also known as: {', '.join(aliases)}\n" if aliases else ""
    desc_block = f"Description: {description}\n\n" if description else ""
    env_block = f"\n\nEnvironment: {environment}" if environment else ""
    return Document(
        page_content=(
            f"Client experience — {job['role']} @ {job['company']}\n"
            f"{alias_line}"
            f"Period: {job['period']}\n"
            f"Location: {job['location']}\n\n"
            f"{desc_block}{bullets}{env_block}"
        ),
        metadata={
            "section": "experience",
            "company": job["company"],
            "period": job["period"],
            "role": job.get("role", ""),
        },
    )


def build_profile_documents() -> list[Document]:
    """Build logical resume chunks with section / company / period metadata."""
    docs: list[Document] = []
    profile = rc.RESUME_PROFILE

    docs.append(
        Document(
            page_content=(
                f"{profile['name']}\n"
                f"{profile['title']}\n"
                f"Location: {profile['location']}\n"
                f"Email: {profile['email']}\n"
                f"Phone: {profile['phone']}\n"
                f"Tagline: {profile['tagline']}\n\n"
                f"Summary:\n{rc.RESUME_SUMMARY}"
            ),
            metadata={"section": "summary", "company": "", "period": ""},
        )
    )

    for idx, bullet in enumerate(getattr(rc, "RESUME_SUMMARY_DETAILS", []) or [], start=1):
        docs.append(
            Document(
                page_content=f"Professional summary detail {idx}: {bullet}",
                metadata={"section": "summary_details", "company": "", "period": ""},
            )
        )

    for category, items in rc.RESUME_SKILLS.items():
        docs.append(_build_skills_category_document(category, items))

    for row in rc.RESUME_SKILL_MATRIX:
        docs.append(_build_skill_matrix_document(row))

    for rec in rc.RESUME_RECOMMENDATIONS:
        author_line = rec["author"]
        if rec.get("title"):
            author_line += f", {rec['title']}"
        if rec.get("company"):
            author_line += f" @ {rec['company']}"
        relationship = rec.get("relationship", "")
        rel_line = f"Relationship: {relationship}\n" if relationship else ""
        docs.append(
            Document(
                page_content=(
                    f"LinkedIn recommendation from {author_line}:\n"
                    f"{rel_line}"
                    f"\"{rec['text']}\""
                ),
                metadata={
                    "section": "recommendations",
                    "company": rec.get("company", ""),
                    "period": rec.get("author", ""),
                },
            )
        )

    linkedin = rc.RESUME_LINKEDIN
    docs.append(
        Document(
            page_content=(
                f"LinkedIn profile: {linkedin['url']}\n"
                f"Headline: {linkedin['headline']}\n"
                f"Connections: {linkedin['connections']} · Followers: {linkedin['followers']}\n"
                f"{linkedin['source_note']}"
            ),
            metadata={"section": "linkedin", "company": "LinkedIn", "period": ""},
        )
    )

    project = rc.FEATURED_PROJECT
    docs.append(
        Document(
            page_content=(
                f"Personal R&D portfolio project: {project['name']}\n"
                f"NOT employer production work — independent demo built to showcase SRE + AI skills.\n"
                f"Role: {project['role']}\n"
                f"Period: {project['period']}\n"
                f"Repository: {project['repo_label']}\n\n"
                f"{project['summary']}\n\n"
                f"Tech stack: {', '.join(project['tech_stack'])}"
            ),
            metadata={
                "section": "featured_project",
                "company": project["name"],
                "period": project["period"],
                "portfolio": True,
            },
        )
    )
    for highlight in project["highlights"]:
        docs.append(
            Document(
                page_content=(
                    f"Portfolio project (not employer work) — SRE AI Copilot — "
                    f"{highlight['label']}: {highlight['detail']}"
                ),
                metadata={
                    "section": "featured_project",
                    "company": project["name"],
                    "period": project["period"],
                    "portfolio": True,
                },
            )
        )

    for job in rc.RESUME_EXPERIENCE:
        docs.append(_build_experience_document(job))

    for edu in rc.RESUME_EDUCATION:
        docs.append(
            Document(
                page_content=(
                    f"{edu['degree']}\n"
                    f"{edu['institution']} ({edu['period']})\n"
                    f"{edu['detail']}"
                ),
                metadata={
                    "section": "education",
                    "company": edu["institution"],
                    "period": edu["period"],
                },
            )
        )

    for cert in rc.RESUME_CERTIFICATIONS:
        docs.append(
            Document(
                page_content=f"Certification: {cert['name']} — {cert['issuer']} ({cert['year']})",
                metadata={"section": "certifications", "company": cert["issuer"], "period": cert["year"]},
            )
        )

    for achievement in rc.RESUME_ACHIEVEMENTS:
        docs.append(
            Document(
                page_content=f"Achievement — {achievement['title']}: {achievement['detail']}",
                metadata={"section": "achievements", "company": "", "period": ""},
            )
        )

    for story in getattr(rc, "RESUME_BEHAVIORAL_STORIES", []) or []:
        docs.append(_build_behavioral_document(story))

    if getattr(rc, "RESUME_OBSERVABILITY_JOURNEY", None):
        docs.append(_build_observability_journey_document())

    for highlight in rc.TECHNICAL_HIGHLIGHTS:
        docs.append(
            Document(
                page_content=f"Technical highlight — {highlight['title']}: {highlight['detail']}",
                metadata={"section": "technical_highlights", "company": "", "period": ""},
            )
        )

    for side, rows in rc.TECH_STACK_COMPARISON.items():
        lines = "\n".join(f"• {row['category']}: {row['tools']}" for row in rows)
        docs.append(
            Document(
                page_content=f"Tech stack comparison — {side}:\n{lines}",
                metadata={"section": "tech_stack_comparison", "company": side, "period": ""},
            )
        )

    return docs


def profile_collection_count() -> int:
    """Return document count for the profile collection, or 0 if missing."""
    try:
        client = _get_chroma_client()
        return client.get_collection(_collection_name()).count()
    except Exception:
        return 0


def ingest_profile(*, force: bool = False) -> int:
    """Ingest resume content into the candidate profile ChromaDB collection."""
    collection_name = _collection_name()
    documents = build_profile_documents()
    if not documents:
        logger.warning("No profile documents to ingest")
        return 0

    chroma_client = _get_chroma_client()

    if not force:
        try:
            if chroma_client.get_collection(collection_name).count() > 0:
                count = chroma_client.get_collection(collection_name).count()
                logger.info("Profile collection '%s' already has %d docs — skipping", collection_name, count)
                return count
        except Exception:
            pass

    try:
        chroma_client.delete_collection(collection_name)
    except Exception:
        pass

    Chroma.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        collection_name=collection_name,
        client=chroma_client,
    )
    logger.info("Ingested %d profile documents into '%s'", len(documents), collection_name)
    return len(documents)


def ensure_profile_ingested() -> int:
    """Auto-ingest on startup when the profile collection is empty."""
    count = profile_collection_count()
    if count > 0:
        logger.info("Profile RAG ready — %d chunks indexed", count)
        return count
    logger.info("Profile collection empty — running initial ingest")
    return ingest_profile(force=True)


def _format_profile_hits(hits: list[tuple[Document, float]]) -> tuple[str, list[dict]]:
    lines: list[str] = []
    sources: list[dict] = []
    for idx, (doc, score) in enumerate(hits, start=1):
        meta = doc.metadata or {}
        section = meta.get("section", "unknown")
        company = meta.get("company", "")
        period = meta.get("period", "")
        header = f"[{idx}] section={section}"
        if company:
            header += f" | company={company}"
        if period:
            header += f" | period={period}"
        lines.append(f"{header}\n{doc.page_content}")
        sources.append(
            {
                "section": section,
                "company": company or None,
                "period": period or None,
                "score": round(float(score), 4),
                "preview": doc.page_content[:160].replace("\n", " "),
            }
        )
    return "\n\n---\n\n".join(lines), sources


def _merge_profile_hits(
    primary: list[tuple[Document, float]],
    boosted: list[tuple[Document, float]],
    k: int,
) -> list[tuple[Document, float]]:
    """Prefer boosted experience chunks, then fill with semantic hits up to k."""
    merged: list[tuple[Document, float]] = []
    seen: set[str] = set()

    def _key(doc: Document) -> str:
        meta = doc.metadata or {}
        return f"{meta.get('section','')}::{meta.get('company','')}::{doc.page_content[:120]}"

    for group in (boosted, primary):
        for doc, score in group:
            key = _key(doc)
            if key in seen:
                continue
            seen.add(key)
            merged.append((doc, score))
            if len(merged) >= k:
                return merged
    return merged


def retrieve_profile_context(
    query: str,
    k: int = 6,
) -> tuple[str, list[dict]]:
    """Retrieve top-k profile chunks and format them for the recruiter prompt."""
    query = query.strip()
    client_query = _is_client_experience_query(query)
    skill_query = _is_skill_query(query)
    incident_query = _is_incident_observability_query(query)
    behavioral_query = _is_behavioral_query(query)
    hm_query = _is_hiring_manager_query(query)
    jd_fit_query = _is_jd_fit_query(query)
    portfolio_query = _is_portfolio_query(query)
    exclude_portfolio = incident_query and not portfolio_query
    matched_companies = match_companies_in_query(query)
    matched_skills = match_skills_in_query(query)
    matched_topics = match_topics_in_query(query)
    match_terms = get_skill_match_terms(query)
    effective_k = max(k, 12) if (
        client_query or skill_query or incident_query or behavioral_query or hm_query
    ) else k
    if jd_fit_query:
        effective_k = max(effective_k, 16)

    hits = retrieve_with_score(query, _collection_name(), k=effective_k)

    boosted: list[tuple[Document, float]] = []
    if portfolio_query:
        boosted.extend(_build_portfolio_boosted_documents())
    elif skill_query and (matched_skills or matched_topics):
        boosted.extend(
            _build_skill_boosted_documents(matched_skills, match_terms=match_terms)
        )
    if behavioral_query:
        boosted.extend(_build_behavioral_boosted_documents(query))
    if _is_observability_focused_query(query):
        boosted.insert(0, (_build_observability_journey_document(), 0.0))
    if incident_query and not portfolio_query:
        incident_terms = list(match_terms)
        for hint in _INCIDENT_OBSERVABILITY_HINTS:
            if hint in query.lower() and hint not in incident_terms:
                incident_terms.append(hint)
        boosted.extend(
            _build_skill_boosted_documents(
                matched_skills or ["observability"],
                match_terms=incident_terms or ["incident", "observability", "monitoring", "servicenow"],
            )
        )
    if client_query:
        if matched_companies:
            for company in matched_companies:
                job = next(j for j in rc.RESUME_EXPERIENCE if j["company"] == company)
                boosted.append((_build_experience_document(job), 0.0))
        else:
            for job in rc.RESUME_EXPERIENCE:
                boosted.append((_build_experience_document(job), 0.0))
    elif jd_fit_query or (hm_query and not portfolio_query):
        for job in rc.RESUME_EXPERIENCE:
            boosted.append((_build_experience_document(job), 0.0))
        for row in rc.RESUME_SKILL_MATRIX[:8]:
            boosted.append(
                (
                    Document(
                        page_content=f"Skill matrix — {row['category']} ({row['proficiency']})",
                        metadata={"section": "skill_matrix", "category": row["category"]},
                    ),
                    0.05,
                )
            )

    if boosted:
        hits = _merge_profile_hits(hits, boosted, effective_k)
    elif not hits:
        return "", []

    hits = _filter_portfolio_chunks(hits, exclude_portfolio=exclude_portfolio)
    hits = _filter_sources_for_query(hits, query)
    if matched_companies:
        hits = _filter_hits_by_employer_scope(hits, matched_companies)

    if not hits:
        return "", []

    return _format_profile_hits(hits)
