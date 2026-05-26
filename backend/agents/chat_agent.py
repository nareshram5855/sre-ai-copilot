"""
On-Call Knowledge Assistant — natural language Q&A over runbooks and architecture docs.

Design decisions:
- json_mode=False: chat answers are prose, not structured JSON
- Retrieves from BOTH runbooks and architecture so a question like
  "where is the Ping token service?" gets context from both collections
- Conversation history is capped at 10 exchanges (20 messages) per session
  to stay within Mistral's 8k context window
- Sources are returned so the engineer can verify the exact runbook
"""
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from backend.agents.base import BaseAgent
from backend.config import settings
from backend.memory.session_store import InMemorySessionStore
from backend.memory.persistence import session_store as _default_store

_SYSTEM = """You are an SRE on-call assistant helping engineers with Kubernetes, cloud infrastructure, and DevOps operations.

CONTEXT FROM RUNBOOKS:
{context}

SCOPE — you specialise in:
  Kubernetes (kubectl, helm, pods, deployments, namespaces, ingress, RBAC)
  Cloud platforms (AWS/EKS, GCP/GKE, Azure/AKS)
  Observability (Prometheus, Grafana, Loki, Datadog, Dynatrace, Splunk)
  Automation/IaC (Ansible, Terraform, ArgoCD, Jenkins, Flux)
  Incident response, runbooks, SLO/SLI, postmortems

OUT OF SCOPE — do NOT help with:
  Building web applications (Flask, Django, Node, React, etc.)
  General programming questions unrelated to SRE/DevOps
  Database design, frontend development, or non-infrastructure topics

If asked something out of scope, politely redirect:
  "I'm focused on SRE and Kubernetes operations. For that I'd suggest [brief redirect].
   Here's what I CAN help you with: [suggest a related SRE topic]."

EXECUTABLE COMMANDS — always suggest real, complete shell commands:
  Full mode (any safe command): mkdir, pip install, python, node, npm, cat, ls, find,
    touch, echo, cp, mv, git (any), docker (any), kubectl (any), helm (any), curl, wget
  SRE mode (restricted): kubectl/helm/git/docker only
  When suggesting commands to create a project or app, always give the full sequence
  of commands needed end-to-end — users can run them with the Run All button.

RULES:
1. If CONTEXT contains actual runbook content, use it as your primary source. Quote exact commands verbatim.
2. If CONTEXT says "No relevant runbooks found":
   - For SRE/Kubernetes/DevOps questions: answer from general SRE knowledge. Label steps "(standard practice)".
   - For out-of-scope questions: redirect as described above.
3. Commands MUST be in fenced code blocks with the correct namespace, flags, and values.
4. For incident questions, structure your response as:
   - **What's happening** (1-2 sentences — diagnosis)
   - **Immediate actions** (numbered steps with exact commands)
   - **Why** (1 sentence on root cause)
   - **Escalate if** (condition requiring human intervention)
5. Keep responses concise and actionable."""

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{question}"),
])


class ChatAgent(BaseAgent):

    def __init__(self, store: InMemorySessionStore | None = None) -> None:
        super().__init__()
        self._store = store or _default_store

    def run(self, payload: dict) -> dict:
        question = payload.get("question", "").strip()
        session_id = payload.get("session_id", "default")

        if not question:
            return {"answer": "Please provide a question.", "sources": [], "session_id": session_id}

        # Retrieve from runbooks + architecture — combine results
        runbook_docs = self._retrieve(question, settings.knowledge_collections["runbooks"], k=4)
        arch_docs = self._retrieve(question, settings.knowledge_collections["architecture"], k=2)
        all_docs = runbook_docs + arch_docs

        context = self._format_context(all_docs)
        history = self._store.get_history(session_id)

        llm, _, tier, complexity = self._route_llm(payload, len(all_docs), json_mode=False)

        chain = _PROMPT | llm
        response = chain.invoke({"context": context, "history": history, "question": question})
        answer = response.content

        self._store.add_exchange(session_id, question, answer)

        sources = list({
            doc.metadata.get("source", "").split("/")[-1]
            for doc, _ in all_docs
            if doc.metadata.get("source")
        })

        self.logger.info("Chat session=%s tier=%s sources=%d", session_id, tier.value, len(sources))

        return {
            "answer": answer,
            "sources": sources,
            "session_id": session_id,
            "llm_tier": tier.value,
            "complexity": complexity.value,
        }

    @staticmethod
    def _format_context(docs_with_scores: list) -> str:
        if not docs_with_scores:
            return "No relevant documents found."
        parts = []
        for doc, score in docs_with_scores:
            source = doc.metadata.get("source", "unknown").split("/")[-1]
            parts.append(f"[{source}]\n{doc.page_content[:600].strip()}")
        return "\n\n---\n\n".join(parts)
