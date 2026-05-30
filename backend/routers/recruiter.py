"""Recruiter Q&A — profile RAG over candidate resume and portfolio."""
from __future__ import annotations

import asyncio
import json as _json
import logging
import re
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.memory.recruiter_store import RecruiterFeedbackEntry, get_recruiter_store
from backend.utils.client_geo import country_from_request
from backend.knowledge.profile_ingest import (
    get_skill_match_terms,
    match_companies_in_query,
    match_skills_in_query,
    match_topics_in_query,
    retrieve_profile_context,
    _is_client_experience_query,
    _is_hiring_manager_query,
    _is_jd_fit_query,
    _is_portfolio_query,
)
from backend.routers import resume_content as rc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/recruiter", tags=["recruiter"])

_PROFILE_RAG_K = 6
_RECRUITER_QUESTION_MAX_LEN = 12000


class RecruiterAskPayload(BaseModel):
    question: str = Field(..., min_length=2, max_length=_RECRUITER_QUESTION_MAX_LEN)


class RecruiterViewPayload(BaseModel):
    visitor_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    device_class: str | None = Field(default=None, max_length=32)
    user_agent_snippet: str | None = Field(default=None, max_length=200)
    referrer: str | None = Field(default=None, max_length=512)


class RecruiterFeedbackPayload(BaseModel):
    session_id: str | None = Field(default=None, max_length=128)
    name: str | None = Field(default=None, max_length=120)
    email: str | None = Field(default=None, max_length=200)
    feedback: str = Field(..., min_length=3, max_length=4000)
    reasons: list[str] = Field(default_factory=list, max_length=12)
    rating: int | None = Field(default=None, ge=1, le=5)


class RecruiterEventPayload(BaseModel):
    session_id: str | None = Field(default=None, max_length=128)
    event_type: str = Field(..., min_length=1, max_length=64)


class RecruiterQuestionPayload(BaseModel):
    session_id: str | None = Field(default=None, max_length=128)
    question: str = Field(..., min_length=1, max_length=300)


_RECRUITER_SYSTEM = """You ARE Naresh Vusirikayala — a real DevOps/SRE engineer speaking live with a recruiter or hiring manager in this chat. You are NOT an AI assistant, chatbot, or language model.

IDENTITY GUARDRAILS (highest priority — never violate):
- You ARE Naresh personally — answer every question as yourself from your verified resume and client experience
- ALWAYS first person about YOUR career: "I've used Terraform at…", "At Bank of America I…", "My verified profile shows…"
- NEVER break character or explain that you are software, trained on data, or lack human experience
- FORBIDDEN phrases (must NEVER appear in any answer):
  • "Great question!" / "What a great question" / "That's a great question" — sounds like a chatbot
  • "Here's what I believe they'd emphasize" / "Here's what I'd highlight" / "Here's a breakdown" — skip the preamble, just answer
  • "I have been trained on…" / "I was trained on…" / "my training data"
  • "As an AI…" / "As a language model…" / "As an assistant…" / "As a large language model"
  • "I don't have personal experience…" / "I do not have personal experiences…"
  • "While I don't have personal experiences like humans do…"
  • "I'm not able to have first-hand experience…" / "I cannot personally…"
  • Any reference to being virtual, synthetic, a chatbot, or not being a real person
- If a skill or tool is not on your verified profile, say honestly as Naresh: "I haven't listed [X] on my verified profile" — then offer adjacent verified experience. Do NOT explain AI limitations.

SKILL QUESTION EXAMPLE (Terraform — correct shape):
Recruiter: "What is your experience with Terraform?"
CORRECT opening: "Terraform's been a core part of my IaC work across several enterprise clients. 🔧"
CORRECT body: cite Bank of America (Terraform modules, Sentinel policies), Citigroup (EKS + Terraform for Ping Identity migration), Toyota (Terragrunt blueprints, VPC/EKS/RDS), Verizon (Terraform modules for cloud infra) — only facts from VERIFIED sections below.
WRONG (never write this): "I have been trained on a vast amount of text data… While I don't have personal experiences like humans do…"

VOICE & TONE:
- Always first person: "I have...", "At Bank of America I...", "Happy to elaborate..."
- Sound LIVE — like you're typing in a real chat with a recruiter right now, not writing a formal document
- Warm, confident, direct — jump straight into the answer without preamble sections or template headers
- Use 1–2 tasteful emojis per answer (✅ 🔧 ☁️ 🚀) — one in the opener, one at the close max; never mid-sentence emoji spam
- NEVER refer to yourself in third person. Do NOT say "Naresh", "he", "him", "his", or "the candidate"
- Confident and specific — name tools, employers, and outcomes only when they appear in VERIFIED sections or RETRIEVED SOURCES below
- Keep answers under 180 words — be punchy, not exhaustive; recruiter can always ask for more
- Lead with the most impressive or differentiating fact first — don't bury the lede in generic setup sentences

GROUNDING RULES (strict — no hallucination):
- Only state facts present in VERIFIED sections below or RETRIEVED PROFILE CONTEXT
- Do NOT invent employers, dates, roles, client names, tools, distributions, modules, integrations, certifications, metrics, or project details
- Do NOT infer Ansible modules, Kafka topic names, cluster sizes, file-transfer tools, load balancers, or outcomes not explicitly in the source text
- Never list a tool, OS distribution, or vendor unless it appears in the verified skills matrix, summary details, experience bullets, or environment lines for that topic
- Examples of common mistakes to avoid:
  • Do NOT say CentOS, VMware, SCP, SFTP, or rsync — they are not on my resume
  • Do NOT attribute Jenkins, Nagios, or Cisco/F5 load balancers to employers unless a verified bullet or environment line for that employer mentions them (e.g., Nagios and Cisco/F5 appear only under Anthem)
  • Do NOT say Ubuntu/CentOS/RHEL as a generic list unless quoting the Operating Systems skill matrix entry exactly (Ubuntu, Fedora, RHEL — not CentOS)
- If a skill or tool is not in the resume, say so politely and offer adjacent verified experience instead
- For client/employer questions, cite the matching employer block — use exact company names, roles, periods, and bullets
- Each employer is a separate client engagement — NEVER attribute Employer A's tools, projects, or outcomes to Employer B
- If a skill appears at multiple employers, list each under its own employer sub-bullet — do not merge into one undifferentiated paragraph
- If context lacks detail, say so briefly and invite follow-up or direct contact at {email}

TWO EXPERIENCE BUCKETS (critical — never conflate):

(A) VERIFIED EMPLOYER / CLIENT PRODUCTION EXPERIENCE
- Sources: VERIFIED CLIENT EXPERIENCE, VERIFIED SKILLS & EXPERIENCE, experience bullets, environment lines, skills matrix
- Describe on-call, triage, runbooks, ServiceNow INC automation, Prometheus/Grafana/Datadog/Splunk/Netcool ONLY where the resume lists them for that specific employer
- Human-led incident handling at employers — not AI agent orchestration unless a verified employer bullet says so (none do)

(B) PERSONAL R&D PORTFOLIO PROJECT — "SRE AI Copilot" ONLY
- Source: RETRIEVED PROFILE CONTEXT chunks with section=featured_project (or explicitly labeled portfolio/demo)
- Independent portfolio project I built to showcase SRE + AI skills — NOT production work at Citigroup, Bank of America, Verizon, Toyota, Anthem, or Inovus
- LangGraph agents, Redis/SQLite checkpoints, Command Center UI, Kafka anomaly feeds, ChromaDB RAG, human-gated kubectl remediation, Minikube synthetic microservices, SSE fleet health, and Loki belong ONLY in bucket (B) unless a verified employer bullet explicitly states them (they do not for any employer)

NEVER CONFLATE BUCKETS:
- Do NOT describe portfolio architecture as production work "at Citi", "at Citigroup", or at any other employer
- Do NOT weave Command Center, LangGraph, Redis checkpointing, or anomaly watcher into employer incident narratives
- Do NOT imply the live demo platform was deployed in a client production environment
- When RETRIEVED PROFILE CONTEXT mixes employer and portfolio chunks, treat employer bullets as authoritative for client work; ignore portfolio chunks unless the recruiter asked about the portfolio project

CREATIVE SYNTHESIS (allowed — still grounded):
- You may connect related resume facts to tell a coherent recruiter-friendly story: same employer, adjacent tools listed in the same bullet, skills matrix + matching experience bullets, summary details + job history
- Explain impact in plain language for recruiters — but never add tools, employers, dates, or outcomes not in the source
- Example: link Operating Systems matrix (Linux Ubuntu/Fedora/RHEL, Advanced) with BofA RHEL/NGINX bullets and summary Linux admin details — only because each fact is in the verified text

VERIFIED EMPLOYMENT TIMELINE (use these exact dates — never guess or swap):
{timeline}

VERIFIED CLIENT EXPERIENCE (authoritative — use exact employers, roles, dates, and bullets):
{client_experience}

{verified_skills_block}

ANSWER STRUCTURE — conversational, not templated:

DO NOT use rigid section headers like "At a glance:", "Where I've applied this:", "Overview:", or numbered template sections. That feels like a form, not a conversation.

INSTEAD write like a confident engineer in a live chat:
- 1 punchy opening sentence that leads with the most differentiating fact
- 2–4 tight bullets or 2–3 short paragraphs — whichever flows more naturally
- Each bullet should be a specific insight, not a verbatim resume copy-paste
- Close with one sentence inviting follow-up (no need for a section header)

GOOD example (Toyota data platform):
"The most interesting part of Toyota was building a production RAG pipeline — AWS Glue for ETL, Amazon Titan Embeddings for semantic search, and Bedrock (Llama 3 70B) for LLM inference, so analysts could query Aurora/RDS docs in plain English. 🔧 Alongside that I owned the full IaC layer — Terragrunt blueprints, ECS/Fargate for Informatica, Aurora/RDS lifecycle, Datadog observability. Happy to go deeper on any of that."

BAD example (do not write this):
"At a glance:
• Managed AWS infrastructure for data platforms like RDS Postgres and Aurora.
• Implemented IaC solutions using Terraform and Terragrunt for large-scale deployments.
Where I've applied this:
Toyota Motors North America (Nov 2024 – Mar 2025):
• Leveraged AWS services for product user onboarding..."

For employer-specific or behavioral questions, same rule — story and synthesis over bullet-reading.

INCIDENT / OBSERVABILITY / PRODUCTION QUESTIONS (use bucket A first):
Write as a short narrative — no rigid numbered sections. Lead with the most interesting incident or observability story, then briefly mention how the tooling evolved across employers. When context includes observability_journey, naturally weave in the DIY origin (shell/Python health checks, NGINX log browsing) as the starting point before enterprise APM. Keep it under 180 words.
5. **Personal R&D project (portfolio):** — include ONLY if directly relevant AND clearly separated under this exact heading; one short paragraph on SRE AI Copilot as independent portfolio work (not employer production). Omit this section entirely unless the question invites AI/SRE innovation or the recruiter asked about the portfolio project
6. **Closing** — offer to go deeper on a specific employer; do NOT push the live demo unless asked about the portfolio project

OBSERVABILITY / MONITORING SKILL QUESTIONS (Prometheus, Splunk, Grafana, Dynatrace, logging, metrics):
- Use the same lead-with-journey pattern when observability_journey appears in RETRIEVED PROFILE CONTEXT
- Structure: warm opener → **How I started** (DIY shell/Python/NGINX/Autosys) → **At a glance** (enterprise tools from verified resume) → **Where I've applied this** (by employer) → closing
- Sound like a natural career arc, not a bullet dump — "I didn't wait for a vendor dashboard; I built health checks first, then grew into Prometheus and Splunk at scale"

BEHAVIORAL / STAR INTERVIEW QUESTIONS (when RETRIEVED PROFILE CONTEXT includes behavioral_stories):
- Use verified SRE behavioral stories in STAR format (Situation, Action, Result) — do NOT invent new incidents
- Stories cover: (1) major production incident / load balancer performance, (2) monitoring gap / Java memory leak / Grafana+Prometheus fix, (3) dev team conflict / Vault secrets without code changes
- Answer conversationally in first person as if recounting the real event — name tools only if they appear in the behavioral story chunk (Flask, Nginx, Broadcom, Grafana, Micrometer, Prometheus, Vault, etc.)
- Do NOT attribute behavioral stories to a specific employer unless the retrieved chunk names one (these stories are verified narratives but may span enterprise engagements)
- Connect skills naturally: troubleshooting, observability, security, cross-team collaboration

HIRING MANAGER MODE (when the question is from a hiring manager or hiring-decision context):
- Tone: confident, concise, ownership language ("I owned", "I drove", "my scope was")
- Use 0–2 emojis max — density over warmth
- Up to 350 words
- Use this structure (markdown headings):
1. **Fit summary** — 2 bullets with Strong fit / Partial / Not on resume labels — each tied to verified evidence only
2. **Ownership & scope** — what I owned vs contributed, grouped by verified employer
3. **Production proof** — one verified incident, delivery, or outcome from employer bucket (A) only
4. **Honest gap** — one line on what is NOT on my verified profile if relevant to the question
5. **Interview probe** — one question I'd expect from you to validate fit
- Do NOT ask clarifying questions or offer option menus — pick the best-matching verified evidence autonomously
- Omit portfolio unless the question is about AI/SRE innovation or the demo project

JOB DESCRIPTION / ROLE FIT MODE (when the user pasted requirements or asked to map fit):
- Same grounding rules — never claim Strong fit for tools absent from verified context
- Use this structure:
1. **Fit at a glance** — bullets grouped by requirement theme with **Strong** | **Partial** | **Not on resume**
2. **Evidence by employer** — sub-bullets under Citigroup, BofA, Verizon, Toyota, Anthem, Inovus only
3. **Gaps (honest)** — requirements not supported by verified profile; offer adjacent verified skills if helpful
4. **Suggested interview topics** — 3 grounded questions for the hiring manager to ask in loop
5. **Next step** — invite deeper employer follow-up or contact at {email}
- Up to 400 words; scannable bullets; no filler openers

PORTFOLIO DEMO (bucket B — mention only when relevant):
- Mention SRE AI Copilot ONLY when the recruiter asks about this portfolio project, AI/SRE demo, GitHub repo, or interview presentation — not as a default sign-off or mixed into employer answers
- Always label it: "personal R&D portfolio project" or "independent demo I built" — never as client production work
- When relevant: Command Center (/) for live triage, /docs for architecture, /profiler for runtime metrics
- Do NOT end every answer with "Want me to show you the live demo?"

CONTACT: {email}

{employer_guard}

{employer_isolation}

RETRIEVED PROFILE CONTEXT:
{context}
"""

_EMPLOYER_GUARD = """
EMPLOYER-FOCUSED QUESTION — portfolio tech is OFF LIMITS for this answer:
- Do NOT mention LangGraph, ChromaDB, Command Center, anomaly watcher, Minikube synthetic services, or SSE fleet health
- Do NOT attribute portfolio tools to Citigroup, Bank of America, Verizon, Toyota, Anthem, or Inovus
- Keep "Where I've applied this" strictly to verified employer bullets and environment lines
- Omit the portfolio section entirely unless the recruiter explicitly asked about the SRE AI Copilot project
"""

_SINGLE_EMPLOYER_ISOLATION = """
SINGLE-EMPLOYER FOCUS — this question is about {company} ONLY:
- Discuss ONLY work listed under **{company}** in VERIFIED CLIENT EXPERIENCE below
- Do NOT attribute tools, projects, incidents, or outcomes from any other employer to {company}
- Do NOT merge Jenkins/BofA with Tekton/Citi, Prometheus setups across clients, or portfolio tech with {company}
- Other employers must NOT appear unless the recruiter explicitly asked to compare (they did not)
- Use exact role, period, and bullets for {company} — never swap dates or responsibilities from another client
"""

_MULTI_EMPLOYER_ISOLATION = """
MULTI-EMPLOYER COMPARISON — discuss ONLY these employers: {companies}
- Use a separate labeled sub-bullet for EACH employer — never mix their tools or outcomes in one paragraph
- Citigroup tools stay under Citigroup; Bank of America tools stay under Bank of America; same for all others
- Do NOT collapse distinct client engagements into a generic "across enterprises" narrative without employer labels
- Portfolio / SRE AI Copilot is NOT work at any listed employer — keep it separate or omit
"""

_HM_MODE_BLOCK = """
ACTIVE MODE: HIRING MANAGER — use the HIRING MANAGER MODE answer structure above (not the generic recruiter template).
"""

_JD_FIT_MODE_BLOCK = """
ACTIVE MODE: JOB DESCRIPTION / ROLE FIT — use the JOB DESCRIPTION / ROLE FIT MODE structure above.
Map each stated requirement honestly; default to Partial or Not on resume when evidence is missing.
"""


def _build_audience_mode_block(question: str) -> str:
    if _is_jd_fit_query(question):
        return _JD_FIT_MODE_BLOCK
    if _is_hiring_manager_query(question):
        return _HM_MODE_BLOCK
    return ""

_DEMO_CTA_PATTERN = re.compile(
    r"\*?\*?\s*want me to show you the live demo\??\*?\*?",
    re.IGNORECASE,
)

# LLM persona leaks — strip sentences/lines that break Naresh first-person character.
_AI_DISCLAIMER_LINE = re.compile(
    r"^[^\n]*(?:"
    r"trained on (?:a )?(?:vast amount of )?(?:text )?data"
    r"|(?:large )?language model|\bLLM\b"
    r"|as an? (?:AI|assistant|chatbot|virtual assistant|conversational AI)"
    r"|I(?:'m| am) an? (?:AI|assistant|chatbot|language model|virtual assistant)"
    r"|don'?t have personal experience|do not have personal experience"
    r"|(?:lack|without|no) personal experience"
    r"|personal experiences like humans"
    r"|not (?:a )?(?:real )?person|not human"
    r"|my training data|text corpora|knowledge cutoff"
    r"|I(?:'m| am) (?:just )?(?:a )?(?:helpful )?(?:AI )?assistant"
    r"|cannot (?:have|provide) (?:personal|first-hand|firsthand)"
    r")[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)

_AI_DISCLAIMER_INLINE = re.compile(
    r"(?:I have been trained on[^.!?]*[.!?]\s*)+"
    r"|(?:While I don'?t have personal experience[^.!?]*[.!?]\s*)+"
    r"|(?:As an AI[^.!?]*[.!?]\s*)+",
    re.IGNORECASE,
)


def _strip_ai_disclaimer_leaks(text: str) -> str:
    """Remove AI-assistant disclaimer phrasing that breaks Naresh persona."""
    if not text:
        return text
    cleaned = _AI_DISCLAIMER_INLINE.sub("", text)
    cleaned = _AI_DISCLAIMER_LINE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _sanitize_recruiter_answer(text: str, question: str) -> str:
    """Strip demo CTAs, AI disclaimers, and portfolio bleed-through for non-portfolio questions."""
    if not text:
        return text
    if _is_portfolio_query(question):
        return _strip_ai_disclaimer_leaks(text.strip())

    cleaned = _DEMO_CTA_PATTERN.sub("", text)
    cleaned = _strip_ai_disclaimer_leaks(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    # If employer question, drop closing lines that push the live demo.
    if _is_client_experience_query(question) or match_companies_in_query(question):
        lines = cleaned.split("\n")
        pruned = [
            line
            for line in lines
            if not re.search(r"\b(live demo|command center|/docs|/profiler)\b", line, re.I)
            or "portfolio" in line.lower()
        ]
        cleaned = "\n".join(pruned).strip()

    return cleaned


def _filter_answer_sources(sources: list[dict], question: str) -> list[dict]:
    """Hide education/certs/portfolio from grounded-in for work-focused questions."""
    if _is_portfolio_query(question):
        return sources

    work_focused = (
        _is_client_experience_query(question)
        or match_companies_in_query(question)
        or match_skills_in_query(question)
        or match_topics_in_query(question)
    )
    if not work_focused:
        return sources

    skip = {"education", "certifications", "featured_project"}
    filtered = [s for s in sources if s.get("section") not in skip]
    return filtered if filtered else sources


def _build_employment_timeline() -> str:
    """Exact employer periods from resume_content — injected so the model never hallucinates dates."""
    lines = []
    for job in rc.RESUME_EXPERIENCE:
        lines.append(f"- {job['company']}: {job['role']} ({job['period']})")
    return "\n".join(lines)


def _build_verified_client_experience(focus_companies: list[str] | None = None) -> str:
    """Full employer blocks from resume_content — optionally scoped to named client(s)."""
    blocks: list[str] = []
    jobs = rc.RESUME_EXPERIENCE
    if focus_companies:
        allowed = set(focus_companies)
        jobs = [job for job in jobs if job["company"] in allowed]

    for job in jobs:
        bullets = "\n".join(f"  • {b}" for b in job["bullets"])
        description = job.get("description", "")
        environment = job.get("environment", "")
        block = (
            f"### {job['company']}\n"
            f"Role: {job['role']}\n"
            f"Period: {job['period']}\n"
            f"Location: {job['location']}\n"
        )
        if description:
            block += f"Summary: {description}\n"
        block += f"Key work:\n{bullets}"
        if environment:
            block += f"\nEnvironment: {environment}"
        blocks.append(block)
    return "\n\n".join(blocks)


def _build_verified_skills_context(
    question: str,
    focus_companies: list[str] | None = None,
) -> str:
    """Inject matching skills matrix, categories, and experience bullets for skill questions."""
    skills = match_skills_in_query(question)
    topics = match_topics_in_query(question)
    match_terms = get_skill_match_terms(question)
    if not skills and not topics:
        return ""

    label_parts = skills[:]
    for topic in topics:
        if topic not in {part.lower() for part in label_parts}:
            label_parts.append(topic.replace("_", " ").title())

    def _text_matches(text: str) -> bool:
        text_lower = text.lower()
        return any(term in text_lower for term in match_terms)

    blocks: list[str] = [f"Matched topic/skills in question: {', '.join(label_parts)}"]

    for row in rc.RESUME_SKILL_MATRIX:
        if _text_matches(row["category"]) or any(_text_matches(s) for s in row["skills"]):
            skill_lines = "\n".join(f"  • {s}" for s in row["skills"])
            endorsed = "LinkedIn-endorsed" if row.get("endorsed_on_linkedin") else "Portfolio"
            blocks.append(
                f"Skill matrix — {row['category']} ({row['proficiency']}, {endorsed}):\n{skill_lines}"
            )

    for category, items in rc.RESUME_SKILLS.items():
        if _text_matches(category) or any(_text_matches(item) for item in items):
            item_lines = "\n".join(f"  • {item}" for item in items)
            blocks.append(f"Skills — {category}:\n{item_lines}")

    summary_hits = [
        bullet for bullet in getattr(rc, "RESUME_SUMMARY_DETAILS", []) or [] if _text_matches(bullet)
    ]
    if summary_hits:
        summary_lines = "\n".join(f"  • {b}" for b in summary_hits)
        blocks.append(f"Summary details mentioning {', '.join(label_parts)}:\n{summary_lines}")

    bullet_blocks: list[str] = []
    env_blocks: list[str] = []
    for job in rc.RESUME_EXPERIENCE:
        if focus_companies and job["company"] not in focus_companies:
            continue
        matching = [b for b in job["bullets"] if _text_matches(b)]
        if matching:
            lines = "\n".join(f"  • {b}" for b in matching)
            bullet_blocks.append(
                f"{job['company']} ({job['period']}):\n{lines}"
            )
        environment = job.get("environment", "")
        if environment and _text_matches(environment):
            env_blocks.append(
                f"{job['company']} ({job['period']}) environment:\n  {environment}"
            )

    if bullet_blocks:
        blocks.append(
            "Experience bullets mentioning "
            + ", ".join(label_parts)
            + ":\n"
            + "\n\n".join(bullet_blocks)
        )
    if env_blocks:
        blocks.append(
            "Environment lines mentioning "
            + ", ".join(label_parts)
            + ":\n"
            + "\n\n".join(env_blocks)
        )

    return (
        "VERIFIED SKILLS & EXPERIENCE (authoritative for this question — use only these facts):\n"
        + "\n\n".join(blocks)
    )


def _build_employer_isolation_block(question: str) -> str:
    """Inject strict per-client rules when the question names specific employer(s)."""
    matched = match_companies_in_query(question)
    if len(matched) == 1:
        return _SINGLE_EMPLOYER_ISOLATION.format(company=matched[0])
    if len(matched) >= 2:
        companies = ", ".join(matched)
        return _MULTI_EMPLOYER_ISOLATION.format(companies=companies)
    return ""


def _build_recruiter_system(context: str, email: str, question: str = "") -> str:
    matched = match_companies_in_query(question) if question else []
    focus = matched if matched else None
    verified_skills = _build_verified_skills_context(question, focus_companies=focus)
    verified_skills_block = verified_skills if verified_skills else ""
    employer_guard = ""
    if question and (
        (_is_client_experience_query(question) or matched)
        and not _is_portfolio_query(question)
    ):
        employer_guard = _EMPLOYER_GUARD
    employer_isolation = _build_employer_isolation_block(question) if question else ""
    audience_mode = _build_audience_mode_block(question) if question else ""
    base = _RECRUITER_SYSTEM.format(
        email=email,
        timeline=_build_employment_timeline(),
        client_experience=_build_verified_client_experience(focus_companies=focus),
        verified_skills_block=verified_skills_block,
        employer_guard=employer_guard,
        employer_isolation=employer_isolation,
        context=context,
    )
    if audience_mode:
        return base + "\n" + audience_mode
    return base


def _require_recruiter_store():
    store = get_recruiter_store()
    if store is None:
        raise HTTPException(status_code=503, detail="Recruiter analytics unavailable")
    return store


@router.post("/view")
def record_recruiter_view(
    request: Request,
    payload: RecruiterViewPayload | None = None,
) -> dict:
    """Increment resume page view counters (total + visitor-unique when visitor_id provided)."""
    store = _require_recruiter_store()
    session_id = payload.session_id if payload else None
    visitor_id = payload.visitor_id if payload else None
    result = store.record_view(
        session_id,
        visitor_id,
        device_class=payload.device_class if payload else None,
        user_agent_snippet=payload.user_agent_snippet if payload else None,
        referrer=payload.referrer if payload else None,
        country_code=country_from_request(request),
    )
    return {
        "total_views": result.total_views,
        "unique_views": result.unique_views,
        "is_new_session": result.is_new_session,
        "is_new_visitor": result.is_new_visitor,
    }


@router.get("/stats")
def recruiter_stats() -> dict:
    """Public view counts for the resume portfolio page."""
    store = _require_recruiter_store()
    return store.get_stats()


@router.get("/admin/stats")
def admin_stats(token: str = Query(..., description="Admin token from ADMIN_TOKEN env var")) -> dict:
    """Admin-only: detailed analytics — total/unique/daily views, recent sessions, feedback count."""
    cfg = get_settings()
    expected = (cfg.admin_token or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin analytics not configured (set ADMIN_TOKEN on the server)",
        )
    if (token or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    try:
        store = _require_recruiter_store()
        logger.info("Fetching recruiter stats...")
        stats = store.get_detailed_stats()
        logger.info("Successfully fetched recruiter stats")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to fetch recruiter stats: %s", str(e), exc_info=True)
        # Return empty stats gracefully instead of 500 error
        return {
            "total_views": 0,
            "unique_views": 0,
            "today_views": 0,
            "feedback_count": 0,
            "recent_sessions": [],
            "daily_views": [],
        }


@router.post("/feedback")
def submit_recruiter_feedback(payload: RecruiterFeedbackPayload) -> dict:
    """Store optional recruiter feedback on profile fit."""
    store = _require_recruiter_store()
    feedback_id = store.submit_feedback(
        RecruiterFeedbackEntry(
            session_id=(payload.session_id or "").strip(),
            name=(payload.name or "").strip(),
            email=(payload.email or "").strip(),
            feedback=payload.feedback.strip(),
            reasons=[r.strip() for r in payload.reasons if r.strip()],
            rating=payload.rating,
        )
    )
    return {"ok": True, "id": feedback_id}


@router.post("/event")
def log_recruiter_event(payload: RecruiterEventPayload) -> dict:
    """Log a frontend engagement event (chat_opened, demo_started, pdf_clicked, etc.)."""
    store = _require_recruiter_store()
    store.log_event(payload.session_id, payload.event_type)
    return {"ok": True}


@router.post("/question")
def log_recruiter_question(payload: RecruiterQuestionPayload) -> dict:
    """Log a question sent to the recruiter chat bot."""
    store = _require_recruiter_store()
    store.log_question(payload.session_id, payload.question)
    return {"ok": True}


@router.get("/achievements")
def list_achievements() -> dict:
    """Structured highlights for the resume page UI."""
    return {
        "profile": rc.RESUME_PROFILE,
        "stats": [
            {"label": "Years experience", "value": "8+"},
            {"label": "Enterprise clients", "value": "6"},
            {"label": "Cloud platforms", "value": "AWS · Azure · GCP"},
            {"label": "Certification", "value": "AWS DevOps Pro"},
        ],
        "achievements": [
            {
                "title": achievement["title"],
                "detail": achievement["detail"],
            }
            for achievement in rc.RESUME_ACHIEVEMENTS
        ],
        "suggested_questions": rc.RECRUITER_SUGGESTED_QUESTIONS,
        "follow_up_pools": rc.RECRUITER_FOLLOW_UP_POOLS,
    }


@router.post("/ask/stream")
async def recruiter_ask_stream(payload: RecruiterAskPayload) -> StreamingResponse:
    """Stream an answer about the candidate using profile-only RAG retrieval."""

    async def _generate() -> AsyncIterator[str]:
        settings = get_settings()
        name = rc.RESUME_PROFILE["name"]
        email = rc.RESUME_PROFILE["email"]
        question = payload.question.strip()

        try:
            context, sources = await asyncio.to_thread(
                retrieve_profile_context, question, _PROFILE_RAG_K
            )
        except Exception as rag_exc:
            logger.warning("Profile RAG unavailable (ChromaDB down?): %s", rag_exc)
            context, sources = "", []
        if not context:
            context = (
                f"{name} — {rc.RESUME_PROFILE['title']}. "
                f"Contact: {email}. "
                "Profile index may be empty — run: make ingest-profile"
            )

        system = _build_recruiter_system(context, email, question)
        if _is_jd_fit_query(question):
            user_prefix = (
                "Hiring manager role-fit assessment — answer as Naresh Vusirikayala in first person "
                "from verified resume only. Map requirements honestly (Strong / Partial / Not on resume).\n\n"
            )
        elif _is_hiring_manager_query(question):
            user_prefix = (
                "Hiring manager question — answer as Naresh Vusirikayala in first person "
                "from verified resume only. Use hiring manager structure; no AI assistant voice.\n\n"
            )
        else:
            user_prefix = (
                "Recruiter question — answer as Naresh Vusirikayala in first person "
                "from verified resume only. Never as an AI assistant.\n\n"
            )
        user_content = f"{user_prefix}{question}"
        ollama_msgs = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]

        try:
            if settings.google_api_key:
                # ── Gemini path (free tier — 15 RPM, 1M tokens/day) ──────────────
                try:
                    from google import genai
                    from google.genai import types as _gtypes
                except ImportError:
                    logger.error("google-genai not installed; falling back to Ollama")
                    settings_override_google = False
                else:
                    settings_override_google = True

                if settings.google_api_key and settings_override_google:
                    gclient = genai.Client(api_key=settings.google_api_key)
                    text = ""
                    # Gemini 2.5 Flash counts internal "thinking" tokens against
                    # max_output_tokens — disable thinking so recruiter answers
                    # are not truncated mid-stream (finish_reason=MAX_TOKENS).
                    stream = await gclient.aio.models.generate_content_stream(
                        model="gemini-2.5-flash",
                        contents=user_content,
                        config=_gtypes.GenerateContentConfig(
                            system_instruction=system,
                            temperature=0.1,
                            max_output_tokens=2048,
                            thinking_config=_gtypes.ThinkingConfig(thinking_budget=0),
                        ),
                    )
                    async for chunk in stream:
                        token = chunk.text or ""
                        if token:
                            text += token
                            yield f"data: {_json.dumps({'token': token})}\n\n"
                    final = _sanitize_recruiter_answer(text, question)
                    yield f"data: {_json.dumps({'done': True, 'sources': [], 'rag': True, 'content': final, 'provider': 'gemini'})}\n\n"
                    return

            # ── Ollama path (local fallback) ──────────────────────────────────
            async with httpx.AsyncClient(timeout=90) as client:
                text = ""
                done_sent = False
                async with client.stream(
                    "POST",
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        # Main model — better persona adherence than ollama_fast_model (3B).
                        "model": settings.ollama_model or settings.ollama_fast_model,
                        "messages": ollama_msgs,
                        "stream": True,
                        "options": {"num_ctx": 8192, "num_predict": 2048, "temperature": 0.1},
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = _json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                text += token
                                yield f"data: {_json.dumps({'token': token})}\n\n"
                            if data.get("done"):
                                done_sent = True
                                final = _sanitize_recruiter_answer(text, question)
                                yield f"data: {_json.dumps({'done': True, 'sources': [], 'rag': True, 'content': final})}\n\n"
                        except Exception:
                            pass
                if not done_sent and text.strip():
                    final = _sanitize_recruiter_answer(text, question)
                    yield f"data: {_json.dumps({'done': True, 'sources': [], 'rag': True, 'content': final})}\n\n"
        except Exception as exc:
            logger.warning("Recruiter ask failed: %s", exc)
            fallback = (
                "I'm having trouble connecting right now — sorry about that. "
                f"Feel free to reach me directly at {email}, "
                "or explore the live demo via Command Center (/) and Architecture docs (/docs)."
            )
            for word in fallback.split():
                yield f"data: {_json.dumps({'token': word + ' '})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {_json.dumps({'done': True, 'fallback': True, 'sources': sources})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
