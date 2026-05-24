import asyncio
import json as _json
import re

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from backend.agents.chat_agent import ChatAgent, _SYSTEM
from backend.config import settings
from backend.memory.session_store import session_store
from backend.rag.retriever import retrieve_with_score
from backend.routers._models import ChatPayload, ChatResponse, ClearSessionResponse
from backend.routers.alertmanager import _recent_triages

router = APIRouter(prefix="/api/v1", tags=["chat"])

_agent = ChatAgent(store=session_store)

_GREETINGS = frozenset({"hello", "hi", "hey", "howdy", "sup", "yo", "greetings", "help"})

# Follow-up / continuation intent — user wants the LLM to repeat or continue
# from prior context. Must be routed through _generate() with session history loaded.
_FOLLOWUP_RE = re.compile(
    r"^(can you (come again|repeat|say that again|continue|go on|elaborate|explain more|"
    r"give more|show more|tell me more)|"
    r"(repeat|continue|elaborate|go on|keep going|more details?|"
    r"what else|tell me more|say that again|come again|"
    r"can you repeat|can you continue|one more time|again please?))[?!.,\s]*$",
    re.IGNORECASE,
)

# Conversational phrases that should never touch the LLM
_CONVERSATIONAL_RE = re.compile(
    r"^(how are you|how's it going|how do you do|what('s| is) up|"
    r"good (morning|afternoon|evening|night)|thanks|thank you|"
    r"nice to meet|who are you|what can you do|what do you do|"
    r"are you (there|ready|online|available)|"
    r"can you help|help me|i need help)[?!.,\s]*$",
    re.IGNORECASE,
)

# Detects questions about live/active/open incidents or firing alerts
# Use incidents?/alerts?/issues? etc. to match both singular and plural forms
_INCIDENT_STATUS_RE = re.compile(
    r"\b(open|active|live|current|firing|ongoing|any)\b.{0,30}\b(incidents?|alerts?|issues?|problems?|outages?)\b"
    r"|\b(incidents?|alerts?|issues?|problems?|outages?)\b.{0,30}\b(open|active|live|current|firing|ongoing|now)\b"
    r"|\bwhat.{0,20}(incidents?|alerts?|issues?|problems?)\b"
    r"|\bany.{0,20}(incidents?|alerts?)\b",
    re.IGNORECASE,
)

# L2 distance threshold — ChromaDB L2 scores: 0=identical, higher=less similar.
# Docs with score > threshold are likely irrelevant and are filtered out.
_RAG_RELEVANCE_THRESHOLD = 1.2

# General "how-to" questions: SRE topic but NOT an active incident — skip RAG,
# answer from Ollama general knowledge with a minimal prompt (faster, no context bloat).
_GENERAL_QUERY_RE = re.compile(
    r"^(how (to|do i|can i|should i)|what (is|are|'s)|explain|"
    r"show me|give me|provide|please (provide|give|show|explain|create|write)|"
    r"create|generate|write|need .{0,30}(config|yaml|template|example|sample)|"
    r"difference between|best practice|when (to|should)|why (do|is|are|does))\b",
    re.IGNORECASE,
)

# Incident-specific signals — presence of these means the query is about a live/specific event
# and SHOULD use runbooks even if it starts with a "how-to" word.
_INCIDENT_SIGNAL_RE = re.compile(
    r"\b(firing|crashed|crashloop|oom(killed)?|down|unreachable|failed|"
    r"not (running|ready|available|responding)|error rate|latency (spike|high)|"
    r"in (the\s+)?(namespace|ns)|pod\s+\w+-\w+|alert\s+\w+|"
    r"right now|currently|just (happened|started|fired)|incident)\b",
    re.IGNORECASE,
)

# SRE-domain keywords: if the query contains none of these, skip RAG entirely.
# Two patterns: (a) whole-word terms with \b, (b) prefix/compound terms without trailing \b.
_SRE_KEYWORDS = re.compile(
    r"\b(alert|pod|node|cluster|namespace|deploy|deployment|service|ingress|"
    r"configmap|secret|rbac|clusterrole|pvc|pv|volume|"
    r"prometheus|grafana|loki|log|metric|threshold|cpu|memory|oom|"
    r"crash|restart|error|failed|pending|evicted|scale|replica|hpa|"
    r"kubectl|helm|argocd|terraform|runbook|incident|sre|kubernetes|k8s|"
    r"kafka|redis|postgres|mysql|mongo|etcd|coreDNS|dns|lb|loadbalancer|"
    r"tls|cert|certificate|token|auth|permission|forbidden|timeout|latency|"
    r"disk|inode|network|firewall|security|compliance|config|configuration|"
    r"patch|fix|rollback|restore|resolve|backup|snapshot|version|upgrade|migrate|"
    r"kubeconfig|serviceaccount|"
    # Observability & APM tools
    r"dynatrace|datadog|newrelic|splunk|nagios|zabbix|opsgenie|pagerduty|victorops|"
    r"jaeger|zipkin|opentelemetry|otel|elastic|kibana|fluentd|fluentbit|"
    # Automation & IaC tools
    r"ansible|playbook|puppet|chef|saltstack|jenkins|tekton|argo|flux|"
    r"pulumi|crossplane|vault|consul|nomad|"
    # General DevOps/SRE concepts
    r"automation|monitoring|observability|pipeline|cicd|cd|ci|"
    r"oncall|on-call|postmortem|slo|sla|sli|mttr|mttd|"
    r"container|image|registry|dockerfile|compose|swarm|"
    r"aws|gcp|azure|eks|gke|aks|ecr|gcr|acr|s3|iam)\b"
    # Prefix/compound patterns: no trailing \b needed (match the start of the word)
    r"|\brole\s*bind"        # role binding / rolebinding / role bindign (typo)
    r"|\bkube\w*config"      # kubeconfig, kube-config, kube config
    r"|\bservice\s*account", # service account / serviceaccount
    re.IGNORECASE,
)


@router.post("/chat/stream")
async def chat_stream(payload: ChatPayload) -> StreamingResponse:
    """
    Streaming chat via SSE — yields tokens from Ollama as they arrive.
    The frontend reads these with fetch() + ReadableStream so the answer
    appears word-by-word instead of waiting 10s for the full response.
    """

    async def _conversational_stream(question: str):
        q = question.lower()
        if any(w in q for w in ("how are you", "how's it", "how do you do")):
            msg = "I'm ready and on-call! Ask me about any Kubernetes alert, runbook, or incident."
        elif any(w in q for w in ("thank", "thanks")):
            msg = "Happy to help! Let me know if there's anything else you need."
        elif any(w in q for w in ("who are you", "what can you do", "what do you do")):
            msg = (
                "I'm your on-call SRE assistant — I can help you:\n"
                "- Triage and explain Kubernetes alerts\n"
                "- Look up runbook steps with exact commands\n"
                "- Check live open incidents\n"
                "- Walk through root cause analysis\n\n"
                "What are you dealing with right now?"
            )
        elif any(w in q for w in ("help", "can you help", "i need help")):
            msg = (
                "Of course! Tell me the alert name, namespace, or describe the issue — "
                "I'll search the runbooks and give you exact steps."
            )
        else:
            msg = "I'm your on-call SRE assistant. Ask me about any alert, runbook, or Kubernetes issue."

        _nl = "\n"
        for line in msg.split("\n"):
            for word in (line.split(" ") if line.strip() else [""]):
                yield f"data: {_json.dumps({'token': word + ' '})}\n\n"
                await asyncio.sleep(0.015)
            yield "data: " + _json.dumps({"token": _nl}) + "\n\n"
        yield f"data: {_json.dumps({'done': True, 'sources': [], 'tier': 'local', 'complexity': 'low'})}\n\n"

    async def _greeting_stream():
        msg = (
            "Hi! I'm your on-call SRE assistant. "
            "Ask me about alerts, runbooks, or Kubernetes troubleshooting — "
            "I'll search the knowledge base and give you exact commands."
        )
        for word in msg.split():
            yield f"data: {_json.dumps({'token': word + ' '})}\n\n"
            await asyncio.sleep(0.018)
        yield f"data: {_json.dumps({'done': True, 'sources': [], 'tier': 'local', 'complexity': 'low'})}\n\n"

    async def _incident_status_stream():
        _SEV = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
        items = sorted(_recent_triages.values(), key=lambda t: (_SEV.get(t.severity, 9), t.triaged_at))

        if not items:
            msg = "No open incidents right now — all systems appear healthy."
        else:
            lines = [f"**{len(items)} open incident{'s' if len(items) > 1 else ''}:**\n"]
            for t in items:
                escalate_tag = " 🔴 **Escalate**" if t.escalate else ""
                lines.append(
                    f"- **{t.severity}** `{t.alert_name}` — ns: `{t.namespace}`{escalate_tag}\n"
                    f"  {t.summary or t.suggested_fix or 'No summary available.'}\n"
                )
            msg = "\n".join(lines)

        # Stream token-by-token, preserving newlines so markdown renders correctly
        _nl = "\n"
        for line in msg.split("\n"):
            for word in (line.split(" ") if line.strip() else [""]):
                yield f"data: {_json.dumps({'token': word + ' '})}\n\n"
                await asyncio.sleep(0.012)
            yield "data: " + _json.dumps({"token": _nl}) + "\n\n"
        yield f"data: {_json.dumps({'done': True, 'sources': [], 'tier': 'local', 'complexity': 'low'})}\n\n"

    # Fast path: skip RAG+LLM for single-word conversational openers
    if payload.question.lower().strip().rstrip("!.,?") in _GREETINGS:
        return StreamingResponse(
            _greeting_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    # Fast path: broader conversational phrases — no LLM needed
    if _CONVERSATIONAL_RE.match(payload.question.strip()):
        return StreamingResponse(
            _conversational_stream(payload.question),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    # Fast path: live incident status — answer from the in-memory triage store
    if _INCIDENT_STATUS_RE.search(payload.question):
        return StreamingResponse(
            _incident_status_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
        )

    async def _generate():
        loop = asyncio.get_event_loop()

        is_sre_query    = bool(_SRE_KEYWORDS.search(payload.question))
        is_followup     = bool(_FOLLOWUP_RE.match(payload.question.strip()))

        # General "how-to" questions (not tied to a specific firing incident):
        # skip RAG entirely, send directly to Ollama with a lightweight prompt.
        is_general = (
            is_sre_query
            and bool(_GENERAL_QUERY_RE.match(payload.question.strip()))
            and not bool(_INCIDENT_SIGNAL_RE.search(payload.question))
        )

        # Load session history early — needed to decide whether to nudge or continue
        history = await loop.run_in_executor(None, session_store.get_history, payload.session_id)
        has_history = len(history) > 0

        full_agent = payload.agent_mode == "full"

        if is_followup or (not is_sre_query and has_history):
            # Follow-up or continuation in an active session — route to LLM with history
            all_docs = []
            context  = "No relevant runbooks — continue the conversation from prior context."
            is_general = True
        elif not is_sre_query:
            # General technical question — always route to LLM, no nudge
            # The system prompt handles scope guidance naturally
            all_docs = []
            context = "No relevant runbooks found — answer from general knowledge as a helpful technical assistant."
            is_general = True
        elif is_general:
            all_docs = []
            context = "No relevant runbooks found — answer from general SRE/Kubernetes knowledge."
        else:
            # SRE query — run RAG retrieval
            runbook_docs, arch_docs = await asyncio.gather(
                loop.run_in_executor(None, retrieve_with_score,
                                     payload.question, settings.knowledge_collections["runbooks"], 4),
                loop.run_in_executor(None, retrieve_with_score,
                                     payload.question, settings.knowledge_collections["architecture"], 2),
            )
            relevant_docs = [
                (doc, score)
                for doc, score in (runbook_docs + arch_docs)
                if score <= _RAG_RELEVANCE_THRESHOLD
            ]
            all_docs = relevant_docs
            if relevant_docs:
                context = ChatAgent._format_context(relevant_docs)
            else:
                context = "No relevant runbooks or architecture docs found for this query."

        # General/follow-up queries: smaller/faster model, shorter response limit
        ollama_model  = settings.ollama_fast_model if is_general else settings.ollama_model
        num_predict   = 2048 if (is_general and not is_sre_query) else (768 if is_general else 1024)
        if is_general and not is_sre_query:
            system_content = (
                "You are a helpful technical assistant with expertise in software engineering, "
                "DevOps, SRE, and general programming. Answer the user's question thoroughly "
                "and practically. When suggesting CLI commands or code, always use fenced code blocks. "
                "When creating projects or apps, give the complete end-to-end sequence of commands "
                "so they can be run one after another."
            )
        else:
            system_content = _SYSTEM.format(context=context)
        ollama_msgs   = [{"role": "system", "content": system_content}]
        for msg in history:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            ollama_msgs.append({"role": role, "content": msg.content})
        ollama_msgs.append({"role": "user", "content": payload.question})

        full_response = ""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model":   ollama_model,
                        "messages": ollama_msgs,
                        "stream":  True,
                        "options": {"num_ctx": 4096, "num_predict": num_predict, "temperature": 0.1},
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data  = _json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                full_response += token
                                yield f"data: {_json.dumps({'token': token})}\n\n"
                            if data.get("done"):
                                # Persist exchange to session history
                                await loop.run_in_executor(
                                    None, session_store.add_exchange,
                                    payload.session_id, payload.question, full_response,
                                )
                                sources = list({
                                    doc.metadata.get("source", "").split("/")[-1]
                                    for doc, _ in all_docs if doc.metadata.get("source")
                                })
                                yield f"data: {_json.dumps({'done': True, 'sources': sources, 'tier': 'local', 'complexity': 'low'})}\n\n"
                        except Exception:
                            pass
        except Exception as exc:
            yield f"data: {_json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatPayload):
    """
    On-call knowledge assistant.
    Retrieves relevant runbooks + architecture docs, answers in natural language.
    Maintains conversation history per session_id.
    """
    result = _agent.execute(payload.model_dump())
    if result.get("_meta", {}).get("error"):
        raise HTTPException(status_code=500, detail=result.get("error", "Chat failed"))
    result.pop("_meta", None)
    return result


@router.delete("/chat/{session_id}", response_model=ClearSessionResponse)
def clear_session(session_id: str):
    """Clear conversation history for a session."""
    session_store.clear(session_id)
    return {"session_id": session_id, "cleared": True}


@router.get("/chat/sessions/count")
def session_count():
    return {"active_sessions": session_store.session_count()}
