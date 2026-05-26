"""Architecture documentation metadata API — mirrors frontend docs content for future consumers."""
from fastapi import APIRouter

from backend.routers.docs_content import (
    API_GROUPS,
    COMPONENT_MAP,
    DOC_SECTIONS,
    INTEGRATIONS,
    MERMAID,
    SECURITY_ITEMS,
    TECH_STACK,
)
from backend.routers.resume_content import (
    FEATURED_PROJECT,
    RESUME_CERTIFICATIONS,
    RESUME_EDUCATION,
    RESUME_EXPERIENCE,
    RESUME_LINKS,
    RESUME_PROFILE,
    RESUME_SKILLS,
    RESUME_SUMMARY,
)

router = APIRouter(prefix="/api/v1/docs", tags=["docs"])


@router.get("/architecture")
def get_architecture_docs() -> dict:
    """
    Return structured architecture documentation metadata.

    Used by external portals, CLI tools, or future dynamic doc renderers.
    Content is kept in sync with frontend/src/components/docs/docsContent.js
    via backend/routers/docs_content.py.
    """
    return {
        "title": "SRE AI Copilot — Enterprise Architecture",
        "version": "0.1.0",
        "sections": DOC_SECTIONS,
        "tech_stack": TECH_STACK,
        "component_map": COMPONENT_MAP,
        "integrations": INTEGRATIONS,
        "security": SECURITY_ITEMS,
        "api_groups": API_GROUPS,
        "mermaid": MERMAID,
    }


@router.get("/resume")
def get_resume_docs() -> dict:
    """
    Return structured resume / portfolio metadata.

    Mirrors frontend/src/data/resumeContent.js for external portals or CLI tools.
    """
    return {
        "title": "SRE AI Copilot — Resume & Portfolio",
        "profile": RESUME_PROFILE,
        "summary": RESUME_SUMMARY,
        "skills": RESUME_SKILLS,
        "featured_project": FEATURED_PROJECT,
        "experience": RESUME_EXPERIENCE,
        "education": RESUME_EDUCATION,
        "certifications": RESUME_CERTIFICATIONS,
        "links": RESUME_LINKS,
    }
