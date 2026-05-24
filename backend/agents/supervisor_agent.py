"""
SupervisorAgent — LangGraph orchestrator that routes inputs to the right specialist.

=============================================================================
WHAT THIS DOES
=============================================================================

Before this, the frontend had to know which endpoint to call:
  - POST /api/v1/triage   ← for alert classification
  - POST /api/v1/chat     ← for Q&A
  - POST /api/v1/runbook  ← for step-by-step remediation
  - POST /api/v1/rca      ← for root cause analysis

With the Supervisor, there is ONE entry point: POST /api/v1/ask
The supervisor reads the input, classifies intent, delegates to the right
specialist agent, and returns the result.

=============================================================================
GRAPH LAYOUT
=============================================================================

           input
             │
             ▼
         classify         ← LLM classifies intent: triage|chat|runbook|rca|execute
             │
     ┌───────┼───────────────────────────────────┐
     ▼       ▼             ▼          ▼           ▼
  triage   chat_node   runbook_node  rca_node  execute_node
     │       │             │          │           │
     └───────┴─────────────┴──────────┴───────────┘
                           │
                         merge          ← normalize all agent outputs
                           │
                          END

=============================================================================
PARALLEL PATTERN (Supervisor + Send)
=============================================================================

For future use: when an alert arrives, the supervisor can fire BOTH the
TriageAgent AND the ChatAgent in parallel (triage classifies while chat
pre-fetches relevant runbooks), then merge the results:

    def route_parallel(state):
        return [
            Send("triage_node", {...}),
            Send("chat_node",   {...}),   ← pre-load runbooks while triaging
        ]

This cuts end-to-end latency for complex incidents.

=============================================================================
INTERVIEW POINTS
=============================================================================

Q: Why a supervisor instead of just routing at the API layer?
A: Single entry point simplifies the frontend — it doesn't need to classify
   intent. More importantly, the supervisor can run agents IN PARALLEL and
   merge results, something impossible with independent API endpoints.

Q: How does the supervisor decide which agent to call?
A: A fast LLM call (temperature=0, local Llama) classifies the input into
   one of 5 intents. The classify node outputs a route string. LangGraph's
   conditional_edges maps that string to the correct specialist node.

Q: How is state shared between the supervisor and specialist agents?
A: SupervisorState is the shared state. Each specialist node reads from it,
   calls the underlying agent, and writes results back to the same state.
   The merge node normalizes the output format before END.
"""

import json
import logging
from typing import Any, TypedDict

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph

from backend.config import settings

logger = logging.getLogger(__name__)


# ── State ─────────────────────────────────────────────────────────────────────

class SupervisorState(TypedDict):
    # Input
    raw_input:  str           # the raw message from the user or alertmanager
    payload:    dict          # structured payload (alert fields, question, etc.)

    # Routing
    intent:     str           # classified: triage|chat|runbook|rca|execute

    # Specialist results (each agent writes to its own key)
    triage_result:  dict
    chat_result:    dict
    runbook_result: dict
    rca_result:     dict

    # Final normalized output
    result:   dict
    agent:    str             # which specialist handled it


# ── LLM ───────────────────────────────────────────────────────────────────────

_LLM = ChatOllama(
    model=settings.ollama_model,        # mistral — consistent ctx with all other agents
    base_url=settings.ollama_base_url,
    temperature=0.0,        # deterministic routing
    format="json",
    num_ctx=2048,
    num_predict=64,
)


def _llm() -> ChatOllama:
    return _LLM


# ── Classify node ─────────────────────────────────────────────────────────────

_CLASSIFY_PROMPT = ChatPromptTemplate.from_messages([("system", """
You are a routing classifier for an SRE AI platform. Read the input and
output ONLY valid JSON: {{"intent": "<one of the intents below>"}}

INTENTS:
- "triage"   → incoming alert that needs severity classification and suggested fix
- "chat"     → a question about runbooks, past incidents, or how to fix something
- "runbook"  → request to execute a step-by-step runbook for a specific issue type
- "rca"      → request for root cause analysis of a past incident
- "execute"  → request to autonomously fix a live incident using kubectl

INPUT: {input}
""")])


def classify(state: SupervisorState) -> dict:
    chain = _CLASSIFY_PROMPT | _llm()
    try:
        response = chain.invoke({"input": state["raw_input"][:500]})
        parsed   = json.loads(response.content)
        intent   = parsed.get("intent", "chat")
    except Exception as e:
        logger.warning("classify failed (%s) — defaulting to chat", e)
        intent = "chat"

    valid = {"triage", "chat", "runbook", "rca", "execute"}
    if intent not in valid:
        intent = "chat"

    logger.info("Supervisor classified intent=%s", intent)
    return {"intent": intent}


# ── Specialist nodes ──────────────────────────────────────────────────────────
# Each node imports and calls the underlying agent.
# Imports are inside the functions to avoid circular imports.

def triage_node(state: SupervisorState) -> dict:
    from backend.agents.triage_agent import TriageAgent
    result = TriageAgent().execute(state["payload"])
    return {"triage_result": result, "agent": "TriageAgent"}


def chat_node(state: SupervisorState) -> dict:
    from backend.agents.chat_agent import ChatAgent
    result = ChatAgent().execute(state["payload"])
    return {"chat_result": result, "agent": "ChatAgent"}


def runbook_node(state: SupervisorState) -> dict:
    from backend.agents.runbook_agent import RunbookAgent
    result = RunbookAgent().execute(state["payload"])
    return {"runbook_result": result, "agent": "RunbookAgent"}


def rca_node(state: SupervisorState) -> dict:
    from backend.agents.rca_agent import RCAAgent
    result = RCAAgent().execute(state["payload"])
    return {"rca_result": result, "agent": "RCAAgent"}


def execute_node(state: SupervisorState) -> dict:
    from backend.agents.executor_agent import executor_agent
    p = state["payload"]
    result = executor_agent.start(
        incident_id=p.get("incident_id", "unknown"),
        alert_name=p.get("alert_name", p.get("name", "unknown")),
        namespace=p.get("namespace", "default"),
        triage_summary=p.get("triage_summary", ""),
    )
    return {"agent": "ExecutorAgent", "result": result or {}}


# ── Merge node ────────────────────────────────────────────────────────────────
# Normalizes output from whichever specialist ran into a single result dict.

def merge(state: SupervisorState) -> dict:
    intent = state.get("intent", "chat")
    source_map = {
        "triage":  state.get("triage_result",  {}),
        "chat":    state.get("chat_result",    {}),
        "runbook": state.get("runbook_result", {}),
        "rca":     state.get("rca_result",     {}),
        "execute": state.get("result",         {}),
    }
    result = source_map.get(intent, {})
    return {"result": {**result, "intent": intent, "routed_to": state.get("agent", "")}}


# ── Router: classify → specialist ─────────────────────────────────────────────

def route_to_specialist(state: SupervisorState) -> str:
    return {
        "triage":  "triage_node",
        "chat":    "chat_node",
        "runbook": "runbook_node",
        "rca":     "rca_node",
        "execute": "execute_node",
    }.get(state.get("intent", "chat"), "chat_node")


# ── Build graph ───────────────────────────────────────────────────────────────

def _build_supervisor_graph() -> Any:
    builder = StateGraph(SupervisorState)

    builder.add_node("classify",     classify)
    builder.add_node("triage_node",  triage_node)
    builder.add_node("chat_node",    chat_node)
    builder.add_node("runbook_node", runbook_node)
    builder.add_node("rca_node",     rca_node)
    builder.add_node("execute_node", execute_node)
    builder.add_node("merge",        merge)

    builder.set_entry_point("classify")

    builder.add_conditional_edges(
        "classify",
        route_to_specialist,
        {
            "triage_node":  "triage_node",
            "chat_node":    "chat_node",
            "runbook_node": "runbook_node",
            "rca_node":     "rca_node",
            "execute_node": "execute_node",
        },
    )

    for node in ("triage_node", "chat_node", "runbook_node", "rca_node", "execute_node"):
        builder.add_edge(node, "merge")

    builder.add_edge("merge", END)
    return builder.compile()


_supervisor_graph = _build_supervisor_graph()


# ── Public API ────────────────────────────────────────────────────────────────

class SupervisorAgent:
    """
    Single entry point for all SRE AI capabilities.
    Classify → route → specialist → merge → return.
    """

    def run(self, raw_input: str, payload: dict) -> dict:
        initial: SupervisorState = {
            "raw_input":     raw_input,
            "payload":       payload,
            "intent":        "",
            "triage_result": {},
            "chat_result":   {},
            "runbook_result":{},
            "rca_result":    {},
            "result":        {},
            "agent":         "",
        }
        final = _supervisor_graph.invoke(initial)
        return final.get("result", {})


supervisor_agent = SupervisorAgent()
