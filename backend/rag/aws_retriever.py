"""
AWS reference architecture RAG retriever.

Queries the `aws_patterns` ChromaDB collection with the user's requirements,
compliance flags, and scale — returns a formatted context string for Gemini.

Auto-ingests the aws_patterns knowledge base on first call if the collection
is empty (lazy init, no startup dependency).
"""
import logging
from pathlib import Path

from backend.rag.retriever import retrieve_similar
from backend.rag.ingestor import ingest_directory

logger = logging.getLogger(__name__)

_COLLECTION = "aws_patterns"
_KNOWLEDGE_SUBDIR = "aws_patterns"
_TOP_K = 3
_MIN_CHARS = 50  # ignore trivially short chunks

# Compliance → query enrichment terms (helps vector search hit the right docs)
_COMPLIANCE_TERMS = {
    "pci":   "PCI-DSS payment card WAF encryption tokenization audit trail",
    "hipaa": "HIPAA PHI healthcare ePHI BAA encryption audit trail",
    "sox":   "SOX financial audit immutable log change control",
    "gdpr":  "GDPR EU data residency right to erasure encryption",
}

# Scale → query enrichment terms
_SCALE_TERMS = {
    "small":  "serverless Lambda DynamoDB simple low-cost",
    "medium": "ECS Fargate container RDS moderate traffic",
    "large":  "EKS Kubernetes microservices Aurora MSK high availability",
}

# Pattern → query enrichment (helps vector search hit specialized docs)
_PATTERN_TERMS = {
    "ml/ai":       "Bedrock OpenSearch vector RAG LLM agent embeddings knowledge base",
    "event-driven": "SQS SNS EventBridge async DLQ fan-out",
    "static site":  "CloudFront S3 CDN OAC SPA",
    "streaming":    "Kinesis MSK real-time fraud detection",
    "batch":        "SQS Lambda S3 Glue batch processing",
    "rest api":     "API Gateway Lambda ECS ALB microservices",
}

_ingested = False  # module-level flag, reset when process restarts


def _ensure_ingested() -> None:
    """Ingest aws_patterns knowledge base if not already done this process lifetime."""
    global _ingested
    if _ingested:
        return

    knowledge_dir = Path(__file__).parent.parent / "knowledge" / _KNOWLEDGE_SUBDIR
    if not knowledge_dir.exists() or not any(knowledge_dir.rglob("*.md")):
        logger.warning("aws_patterns knowledge dir missing: %s", knowledge_dir)
        _ingested = True  # avoid retrying every call
        return

    try:
        # Try a test query first — if it works, collection is already populated
        existing = retrieve_similar("AWS architecture", _COLLECTION, k=1)
        if existing:
            logger.debug("aws_patterns collection already populated (%d docs checked)", len(existing))
            _ingested = True
            return
    except Exception:
        pass

    logger.info("Ingesting aws_patterns knowledge base...")
    try:
        count = ingest_directory(_COLLECTION, _KNOWLEDGE_SUBDIR)
        logger.info("aws_patterns: ingested %d chunks", count)
    except Exception as exc:
        logger.warning("aws_patterns ingest failed (RAG will be empty): %s", exc)

    _ingested = True


def retrieve_aws_patterns(
    query: str,
    compliance: list[str] | None = None,
    scale: str = "",
    patterns: list[str] | None = None,
) -> str:
    """
    Return top-k AWS reference pattern excerpts as a formatted context string.

    The returned string is injected into the Gemini system prompt verbatim —
    it grounds the LLM in real AWS reference architectures.

    Returns "" if retrieval fails (caller should proceed without RAG).
    """
    _ensure_ingested()

    # Build enriched query: requirements + compliance + scale terms
    enriched_parts = [query.strip()]
    for flag in (compliance or []):
        term = _COMPLIANCE_TERMS.get(flag.lower().replace("-", "").replace("_", ""), "")
        if term:
            enriched_parts.append(term)
    if scale:
        enriched_parts.append(_SCALE_TERMS.get(scale.lower(), ""))
    for pat in (patterns or []):
        term = _PATTERN_TERMS.get(pat.lower(), pat)
        enriched_parts.append(term)

    enriched_query = " ".join(p for p in enriched_parts if p)
    if not enriched_query.strip():
        return ""

    try:
        docs = retrieve_similar(enriched_query, _COLLECTION, k=_TOP_K)
    except Exception as exc:
        logger.warning("aws_patterns retrieval error: %s", exc)
        return ""

    if not docs:
        return ""

    # Format into a context block Gemini can reason over
    context_parts = ["## AWS Reference Architecture Patterns (from knowledge base)\n"]
    for i, doc in enumerate(docs, start=1):
        content = doc.page_content.strip()
        if len(content) < _MIN_CHARS:
            continue
        source = doc.metadata.get("source", "")
        source_name = Path(source).name if source else f"pattern-{i}"
        context_parts.append(f"### Pattern {i}: {source_name}\n{content}\n")

    if len(context_parts) == 1:  # only header, no real content
        return ""

    return "\n".join(context_parts)
