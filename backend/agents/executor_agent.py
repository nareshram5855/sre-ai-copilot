"""
ExecutorAgent — LangGraph-powered autonomous incident remediation.

=============================================================================
ARCHITECTURE: How LangGraph changes everything
=============================================================================

BEFORE (plain Python while-loop):
  - State lived in a Python dict in RAM → lost on process restart
  - Parallel tool calls were impossible → get_pods, get_logs, top_pods ran one by one
  - Approval gate was manual (set approved=False, check in a loop) → fragile
  - No visibility into graph transitions → hard to debug

AFTER (LangGraph StateGraph):
  - State is a TypedDict managed by LangGraph → MemorySaver persists between API calls
  - Parallel dispatch: get_pods + get_logs + top_pods fire SIMULTANEOUSLY → 3x faster gather
  - Approval gate uses interrupt_before → graph literally pauses at a node boundary
  - Every node transition is a named edge → visual graph, traceable in LangSmith

=============================================================================
GRAPH LAYOUT
=============================================================================

  START
    │
    ▼
  gather_initial ──────────────────────────────────────────────────
    │ (parallel Send)                                              │
    ├──▶ gather_pods    ──┐                                       │
    ├──▶ gather_logs    ──┼──▶ reason  ◀──────────────────────────
    └──▶ gather_metrics ──┘      │
                                 │ route_after_reason()
                                 ├──▶ execute_read  ──▶ reason
                                 ├──▶ execute_write ──▶ reason   (interrupt_before)
                                 └──▶ END

  MemorySaver checkpoints state at every node transition.
  interrupt_before=["execute_write"] pauses the graph before ANY write.
  Resume by calling graph.invoke(None, config=same_thread_id).

=============================================================================
KEY INTERVIEW CONCEPTS (how to explain this)
=============================================================================

Q: How does parallel execution work?
A: LangGraph's Send API. The gather_initial node returns a list of Send objects —
   each one targets a different node with its own input. LangGraph fires them all
   in the same "superstep" (concurrent Python threads), then merges results into
   the shared state before the next node runs.

Q: How does the approval gate work?
A: interrupt_before=["execute_write"] is set at graph compile time. When the graph
   reaches that node, it saves state via MemorySaver and raises an interrupt.
   Control returns to the API caller. The frontend shows "Approve?" to the engineer.
   When they approve, the API calls graph.invoke(None, config) with the same
   thread_id — LangGraph rehydrates state from MemorySaver and continues from
   exactly where it stopped.

Q: How does cross-session persistence work?
A: MemorySaver is a key-value store keyed by thread_id (our execution_id UUID).
   Every node transition checkpoints the full state. If the backend restarts
   mid-incident, the next API call with the same thread_id rehydrates from the
   last checkpoint. In production, swap MemorySaver for SqliteSaver or RedisSaver.

Q: How does the agent re-reason after seeing tool output?
A: The reason node is called after EVERY tool execution. It receives the full
   state (scratchpad of all past steps) and outputs the next action. The graph
   loops reason → execute_read → reason → execute_write → reason until the LLM
   sets done=True. The LLM re-reads its full history on every call — that IS
   the memory.
=============================================================================
"""

import json
import logging
import operator
import queue
import subprocess
import threading
import time
import uuid
from enum import Enum
from typing import Annotated, Any, TypedDict

import httpx

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from backend.config import settings
from backend.memory.audit_store import log_execution_audit

logger = logging.getLogger(__name__)


# ── Namespace inference ───────────────────────────────────────────────────────
# Control plane and infrastructure alerts don't carry a meaningful namespace label
# in Prometheus — alertmanager fires them as namespace="" or namespace="unknown".
# Map alert name patterns to the correct Kubernetes namespace before any tool runs.

_ALERT_NAMESPACE_MAP: list[tuple[str, str]] = [
    # Kubernetes control plane (static pods in kube-system)
    ("kubecontrollermanager",          "kube-system"),
    ("kubeapiserverdown",              "kube-system"),
    ("kubeapidown",                    "kube-system"),
    ("kubescheduler",                  "kube-system"),
    ("kubeproxy",                      "kube-system"),
    ("kubelet",                        "kube-system"),
    ("kubenode",                       "kube-system"),
    ("kubedeployment",                 "kube-system"),
    ("kubedaemonset",                  "kube-system"),
    # etcd (always kube-system in kubeadm clusters)
    ("etcd",                           "kube-system"),
    # Cert-manager
    ("certmanager",                    "cert-manager"),
    ("certificateexpir",               "cert-manager"),
]


def _infer_namespace(alert_name: str, namespace: str) -> str:
    """
    Return the correct namespace for an alert.
    Falls back to 'default' when the incoming value is absent/unknown.
    """
    if namespace and namespace not in ("unknown", "", "null"):
        return namespace
    alert_lower = alert_name.lower()
    for keyword, ns in _ALERT_NAMESPACE_MAP:
        if keyword in alert_lower:
            logger.info("Inferred namespace=%s from alert_name=%s", ns, alert_name)
            return ns
    return "default"


# ── Event stream store ────────────────────────────────────────────────────────
# Each execution gets a queue. The SSE endpoint drains it in real-time.
# Nodes push events as they complete so the frontend sees each step live.
_event_queues: dict[str, queue.Queue] = {}

def _push_event(execution_id: str, event_type: str, data: dict) -> None:
    q = _event_queues.get(execution_id)
    if q:
        q.put_nowait({"type": event_type, "data": data})

def _close_stream(execution_id: str) -> None:
    q = _event_queues.get(execution_id)
    if q:
        q.put_nowait(None)   # sentinel — SSE generator stops on None


def _maybe_learn_from_execution(snapshot: dict | None) -> None:
    """Persist successful resolutions to the resolved_incidents knowledge base."""
    if not snapshot or snapshot.get("status") != ExecutionStatus.RESOLVED.value:
        return
    try:
        from backend.agents.learning_agent import learning_agent
        from backend.routers.alertmanager import get_fire_count

        fire_count = get_fire_count(
            snapshot.get("alert_name", ""),
            snapshot.get("namespace", ""),
        )
        result = learning_agent.ingest_from_execution(snapshot, fire_count=fire_count)
        if result.get("ingested"):
            logger.info(
                "LearningAgent stored resolution for %s/%s (promoted=%s)",
                snapshot.get("alert_name"),
                snapshot.get("namespace"),
                result.get("promoted_to_runbook"),
            )
    except Exception as exc:
        logger.warning("LearningAgent ingest skipped: %s", exc)


# ── Status ────────────────────────────────────────────────────────────────────

class ExecutionStatus(str, Enum):
    RUNNING          = "running"
    WAITING_APPROVAL = "waiting_approval"
    RESOLVED         = "resolved"
    ESCALATED        = "escalated"
    FAILED           = "failed"


# ── LangGraph State ───────────────────────────────────────────────────────────
#
# TypedDict is LangGraph's state container. Every node receives the full state
# and returns a partial update (only the keys it changed).
#
# Annotated[list, operator.add] tells LangGraph to APPEND incoming list items
# rather than replace the whole list. This is what makes parallel nodes safe:
# gather_pods appends its result, gather_logs appends its result, gather_metrics
# appends its result — all three merge into scratchpad without overwriting each other.

class ExecutorState(TypedDict):
    # ── Input (set once at start) ──────────────────────────────────────────
    execution_id:   str
    incident_id:    str
    alert_name:     str
    namespace:      str
    triage_summary: str

    # ── Parallel gather results (each parallel node writes its own key) ────
    pods_info:    str          # from gather_pods
    logs_info:    str          # from gather_logs
    metrics_info: str          # from gather_metrics

    # ── Scratchpad (Annotated → append-only, safe for parallel writes) ─────
    scratchpad: Annotated[list[dict], operator.add]

    # ── Control flow ───────────────────────────────────────────────────────
    status:           str
    next_action:      str        # tool name the LLM chose
    next_args:        dict       # tool args the LLM chose
    last_thought:     str
    final_summary:    str
    done:             bool
    escalate:         bool
    code_suggestions: list       # code-level fix suggestions when kubectl can't resolve


# ── kubectl tool implementations ──────────────────────────────────────────────

_KUBECTL_TIMEOUT = 30

def _kubectl(args: list[str]) -> str:
    try:
        r = subprocess.run(
            ["kubectl"] + args,
            capture_output=True, text=True, timeout=_KUBECTL_TIMEOUT,
        )
        out = r.stdout.strip()
        return out if r.returncode == 0 else f"ERROR (exit {r.returncode}): {r.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {_KUBECTL_TIMEOUT}s"
    except Exception as e:
        return f"EXCEPTION: {e}"


def _kubectl_with_poll(args: list[str], poll_args: list[str], success_text: str, timeout: int = 90) -> str:
    trigger = _kubectl(args)
    if "ERROR" in trigger or "EXCEPTION" in trigger:
        return trigger
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _kubectl(poll_args)
        if success_text in status:
            return f"SUCCESS: {status}"
        time.sleep(3)
    return f"TIMEOUT: did not complete in {timeout}s — {_kubectl(poll_args)}"


# Tool registry: name → (callable, requires_approval)
def _tool_get_pods(namespace: str, **_) -> str:
    return _kubectl(["get", "pods", "-n", namespace, "-o", "wide"])

def _tool_describe_pod(pod: str, namespace: str, **_) -> str:
    return _kubectl(["describe", "pod", pod, "-n", namespace])

def _query_loki(namespace: str, pod_name: str | None = None, tail: int | None = None) -> str:
    """
    Fetch logs from Loki instead of running kubectl logs directly.
    Logs from kubectl are ephemeral and lost on pod restart; Loki retains them.

    LogQL label selectors:
      - namespace is always set
      - pod is set to a regex match when known (e.g.  pod=~"oom-demo.*")
      - Falls back to namespace-only query if pod name is unknown
    """
    import time as _time
    cfg  = settings
    tail = tail or cfg.loki_max_lines
    now  = int(_time.time() * 1e9)                      # nanoseconds
    start = now - (cfg.loki_log_window_minutes * 60 * int(1e9))

    # Build LogQL selector.
    # pod_name is used as-is as a prefix regex: pod=~"<pod_name>.*"
    # Callers are responsible for passing the right prefix (deployment base name,
    # component prefix, or full pod name). No suffix-stripping happens here.
    if pod_name and pod_name not in ("unknown", ""):
        logql = f'{{namespace="{namespace}",pod=~"{pod_name}.*"}}'
    else:
        logql = f'{{namespace="{namespace}"}}'

    try:
        resp = _HTTP.get(
            f"{cfg.loki_base_url}/loki/api/v1/query_range",
            params={
                "query":     logql,
                "start":     start,
                "end":       now,
                "limit":     tail,
                "direction": "backward",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        streams = data.get("data", {}).get("result", [])
        if not streams:
            return f"(no logs found in Loki for {logql} in last {cfg.loki_log_window_minutes}m)"

        # Flatten all log lines from all streams, sorted newest-first
        lines = []
        for stream in streams:
            pod_label = stream.get("stream", {}).get("pod", pod_name or namespace)
            for ts_ns, line in stream.get("values", []):
                lines.append((int(ts_ns), pod_label, line))

        lines.sort(key=lambda x: x[0], reverse=True)

        out = []
        for _, lbl, raw_line in lines[:tail]:
            # Promtail wraps lines in JSON: {"log": "...", "stream": "...", "time": "..."}
            # Extract just the log message so LLM sees plain text, not JSON noise.
            try:
                parsed = json.loads(raw_line)
                msg = parsed.get("log", raw_line).rstrip("\n")
            except (json.JSONDecodeError, TypeError):
                msg = raw_line.rstrip("\n")
            out.append(f"[{lbl}] {msg}")

        formatted = "\n".join(out)
        return formatted or "(empty log result from Loki)"

    except httpx.ConnectError:
        return f"(Loki unreachable at {cfg.loki_base_url} — run: kubectl port-forward svc/loki 3100:3100 -n monitoring)"
    except Exception as exc:
        return f"(Loki query failed: {exc})"


def _tool_get_logs(pod: str, namespace: str, tail: int = 50, **_) -> str:
    return _query_loki(namespace=namespace, pod_name=pod, tail=tail)

def _tool_top_pods(namespace: str, **_) -> str:
    return _kubectl(["top", "pods", "-n", namespace])

def _tool_rollout_restart(deployment: str, namespace: str, **_) -> str:
    return _kubectl_with_poll(
        args=["rollout", "restart", f"deployment/{deployment}", "-n", namespace],
        poll_args=["rollout", "status", f"deployment/{deployment}", "-n", namespace, "--timeout=5s"],
        success_text="successfully rolled out",
    )

def _tool_patch_resources(deployment: str, namespace: str, memory_limit: str, cpu_limit: str = "", **_) -> str:
    patch: dict = {"spec": {"template": {"spec": {"containers": [
        {"name": deployment, "resources": {"limits": {"memory": memory_limit}}}
    ]}}}}
    if cpu_limit:
        patch["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]["cpu"] = cpu_limit
    return _kubectl(["patch", "deployment", deployment, "-n", namespace, "--patch", json.dumps(patch)])

def _tool_scale(deployment: str, namespace: str, replicas: int, **_) -> str:
    return _kubectl(["scale", "deployment", deployment, "-n", namespace, f"--replicas={replicas}"])

def _tool_delete_pod(pod: str, namespace: str, **_) -> str:
    return _kubectl(["delete", "pod", pod, "-n", namespace, "--force", "--grace-period=0"])


TOOL_REGISTRY: dict[str, tuple[callable, bool]] = {
    "get_pods":        (_tool_get_pods,        False),
    "describe_pod":    (_tool_describe_pod,    False),
    "get_logs":        (_tool_get_logs,        False),
    "top_pods":        (_tool_top_pods,        False),
    "rollout_restart": (_tool_rollout_restart, True),
    "patch_resources": (_tool_patch_resources, True),
    "scale":           (_tool_scale,           True),
    "delete_pod":      (_tool_delete_pod,      True),
}


# ── Public accessor used by routers + frontend (single source of truth) ──────

def list_write_actions() -> list[str]:
    """Return tool names that require human approval before execution."""
    return [name for name, (_fn, requires_approval) in TOOL_REGISTRY.items() if requires_approval]


def list_read_actions() -> list[str]:
    """Return tool names that are auto-approved (read-only)."""
    return [name for name, (_fn, requires_approval) in TOOL_REGISTRY.items() if not requires_approval]


# ── LLM prompt ────────────────────────────────────────────────────────────────

# Static system message — identical across ALL executor calls.
# Ollama KV-caches this prefix after the first call, so subsequent calls only prefill the dynamic part.
_SYSTEM_STATIC = """You are an autonomous SRE executor agent. Fix Kubernetes incidents.

STEP 1 — CLASSIFY the alert into exactly one category before acting:
  CONTROL_PLANE : alert name contains KubeControllerManager | KubeAPIServer | KubeAPI | KubeScheduler | KubeProxy | Kubelet | KubeNode
  ETCD          : alert name contains etcd
  OOM_MEMORY    : logs or triage show OOMKilled | OutOfMemoryError | Java heap | heap space | memory pressure
  CRASH_LOOP    : pod restarts > 5, no OOM evidence in logs
  REPLICA       : alert name contains ReplicaMismatch | Unavailable | Pending | Deployment

STEP 2 — APPLY the rule for that category (ONLY that category):
  CONTROL_PLANE | ETCD →
    Check CLUSTER STATE Pods for the component (controller-manager / scheduler / etcd / apiserver / proxy).
    If pod is Running  : done=true, escalate=true. Reason: "Component is Running — alert is stale or probe-based."
    If pod is Crashing : done=true, escalate=true. Reason: "Static pod crash — cannot use rollout restart, human required."
    NEVER call patch_resources or rollout_restart for control plane / etcd.

  OOM_MEMORY →
    IMMEDIATELY patch_resources(deployment, namespace, memory_limit).
    Do not read more data — Pods/Logs already have the evidence.
    memory_limit = 4× current limit from logs. Format: 256Mi 512Mi 1Gi 2Gi (no MB/GB).

  CRASH_LOOP →
    describe_pod(pod, namespace) to read Events. Then rollout_restart(deployment, namespace).

  REPLICA →
    get_pods(namespace) to count ready vs desired. If ImagePullError/Unschedulable → escalate.

TOOLS (read=auto | write=human-approved):
  get_pods(namespace) | describe_pod(pod, namespace) | top_pods(namespace)
  rollout_restart(deployment, namespace) [WRITE]
  patch_resources(deployment, namespace, memory_limit) [WRITE]
  scale(deployment, namespace, replicas) [WRITE]
  delete_pod(pod, namespace) [WRITE]

OUTPUT FORMAT — output ONLY valid JSON, nothing else:
{"thought":"<1 sentence stating category and action>","action":"<tool or empty>","args":{},"done":false,"escalate":false}

HARD RULES:
1. NEVER use the alert name, category name, or "OOMKilled" as a pod or deployment name.
2. NEVER repeat an action already in STEPS TAKEN — if same args returned nothing useful, escalate.
3. After 1 read step you MUST write or escalate. Never exceed 2 read steps.
4. Deployment name = pod base name with random suffix removed (oom-demo-54d77-xxx → oom-demo).
5. For CONTROL_PLANE/ETCD: always set escalate=true. These cannot be auto-remediated."""

# Dynamic user message — changes each call (cluster state + scratchpad + incident).
# Only these tokens need prefill after the static system is cached.
_USER_TEMPLATE = """INCIDENT: {alert_name} | namespace: {namespace}
CATEGORY: {alert_category}
TRIAGE:   {triage_summary}

CLUSTER STATE (live — do not re-fetch anything already shown here):
Pods:    {pods_info}
Logs:    {logs_info}
Metrics: {metrics_info}

STEPS ALREADY TAKEN:
{scratchpad}

Apply the STEP 2 rule for category {alert_category}. Output next action JSON:"""


# ── Graph node functions ───────────────────────────────────────────────────────

# Persistent httpx client — avoids TCP connection overhead per call.
# Direct API call bypasses LangChain's streaming aggregation loop overhead.
_HTTP = httpx.Client(timeout=60)


def _call_ollama(user_message: str) -> str:
    """
    Two-message call: static system + dynamic user.
    Ollama KV-caches the static system prefix after the first call.
    Subsequent calls only prefill the user message tokens (~300-500 tok vs 1500+).
    """
    t0 = time.time()
    resp = _HTTP.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": [
                {"role": "system",  "content": _SYSTEM_STATIC},
                {"role": "user",    "content": user_message},
            ],
            "stream":  False,
            "format":  "json",
            "options": {
                "num_ctx":     2048,
                "num_predict": 150,
                "temperature": 0.1,
            },
        },
    )
    resp.raise_for_status()
    d = resp.json()
    logger.info(
        "ollama: %.2fs | prefill=%.0fms (%d tok) | gen=%.0fms (%d tok @ %.1f tok/s)",
        time.time() - t0,
        d.get("prompt_eval_duration", 0) / 1e6,
        d.get("prompt_eval_count", 0),
        d.get("eval_duration", 0) / 1e6,
        d.get("eval_count", 0),
        d.get("eval_count", 0) / max(d.get("eval_duration", 1), 1) * 1e9,
    )
    return d["message"]["content"]


def _llm() -> ChatOllama:
    return ChatOllama(model=settings.ollama_model, base_url=settings.ollama_base_url)


# ── Parallel gather nodes (all three fire simultaneously) ─────────────────────
#
# These three nodes are dispatched in the same superstep by the Send API.
# LangGraph runs them concurrently. Each writes to its own state key.
# The reason node only runs after ALL THREE have completed.

def gather_pods(state: ExecutorState) -> dict:
    _push_event(state["execution_id"], "gather", {"label": "pods", "status": "running"})
    result = _tool_get_pods(namespace=state["namespace"])
    _push_event(state["execution_id"], "gather", {"label": "pods", "status": "done", "output": result[:400]})
    logger.info("gather_pods done: %d chars", len(result))
    return {"pods_info": result}


def _loki_pod_filter(alert_name: str, category: str, triage_summary: str) -> str | None:
    """
    Derive a targeted pod-name prefix for the Loki query from the alert name.
    Without this, a namespace-wide query mixes logs from every pod in the namespace —
    the LLM sees noise instead of the signal from the failing component.

    Returns a string used as pod=~"<prefix>.*" in LogQL, or None for namespace-wide query.

    K8s pod naming: <deployment>-<rs-hash(9-10 hex)>-<pod-hash(5 alnum)>
    We strip the last two segments to recover the deployment base name.
    """
    import re
    alert_lower = alert_name.lower()

    # ── Control plane: exact static-pod prefixes (kubeadm convention) ──────────
    CONTROL_PLANE_PODS = {
        "kubecontrollermanager": "kube-controller-manager",
        "kubeapiserverdown":     "kube-apiserver",
        "kubeapidown":           "kube-apiserver",
        "kubeapiserver":         "kube-apiserver",
        "kubescheduler":         "kube-scheduler",
        "kubeproxy":             "kube-proxy",
        "kubelet":               "kubelet",
    }
    for keyword, pod_prefix in CONTROL_PLANE_PODS.items():
        if keyword in alert_lower:
            return pod_prefix
    if "etcd" in alert_lower:
        return "etcd"

    # ── App-level: parse deployment base name from triage_summary ────────────
    # Triage often surfaces the pod name: "oom-demo-54d7647999-4px4v has OOMKilled"
    # We strip the K8s random suffix to recover the deployment name.
    if category in ("OOM_MEMORY", "CRASH_LOOP", "REPLICA"):
        combined = (triage_summary + " " + alert_name).lower()
        skip_kw  = ("kube-", "kubernetes", "namespace", "alertname", "severity", "warning", "critical")

        # Find all hyphenated lowercase tokens (K8s naming pattern)
        candidates = re.findall(r'\b([a-z][a-z0-9]{1,}(?:-[a-z0-9]{1,})+)\b', combined)
        for candidate in candidates:
            if any(kw in candidate for kw in skip_kw):
                continue
            parts = candidate.split("-")
            if len(parts) < 2:
                continue

            # Detect and strip K8s random suffix:
            #   pod-hash   = 5 alphanumeric chars (last segment)
            #   RS-hash    = 9-10 alphanumeric chars (second-to-last)
            has_pod_hash = len(parts[-1]) == 5 and parts[-1].isalnum()
            has_rs_hash  = len(parts) >= 3 and len(parts[-2]) in (9, 10) and parts[-2].isalnum()

            if has_pod_hash and has_rs_hash:
                base = "-".join(parts[:-2])
            elif has_pod_hash:
                base = "-".join(parts[:-1])
            else:
                base = candidate   # service name with no random suffix (e.g. iam-token-service)

            if len(base) >= 3:
                return base

    return None   # namespace-wide fallback


def gather_logs(state: ExecutorState) -> dict:
    """
    Fetch logs from Loki for the specific component or pod related to this alert.
    Uses a targeted pod-name filter derived from the alert name so the LLM sees
    only relevant log lines — not a 100-line dump from every pod in the namespace.
    """
    _push_event(state["execution_id"], "gather", {"label": "logs", "status": "running"})

    category   = _classify_alert_category(state["alert_name"], "", state.get("triage_summary", ""))
    pod_filter = _loki_pod_filter(state["alert_name"], category, state.get("triage_summary", ""))

    logger.info("gather_logs: Loki query ns=%s pod_filter=%s", state["namespace"], pod_filter)
    result = _query_loki(namespace=state["namespace"], pod_name=pod_filter)

    _push_event(state["execution_id"], "gather", {"label": "logs", "status": "done", "output": result[:400]})
    logger.info("gather_logs done (Loki, filter=%s): %d chars", pod_filter or "ns-wide", len(result))
    return {"logs_info": result}


def gather_metrics(state: ExecutorState) -> dict:
    _push_event(state["execution_id"], "gather", {"label": "metrics", "status": "running"})
    result = _tool_top_pods(namespace=state["namespace"])
    _push_event(state["execution_id"], "gather", {"label": "metrics", "status": "done", "output": result[:400]})
    logger.info("gather_metrics done: %d chars", len(result))
    return {"metrics_info": result}


# ── Router: initial parallel dispatch ─────────────────────────────────────────
#
# This function returns a list of Send objects.
# LangGraph fires ALL of them simultaneously — this is what makes it parallel.
# Each Send says: "call this node with this input."

def route_parallel_gather(state: ExecutorState) -> list[Send]:
    return [
        Send("gather_pods",    state),
        Send("gather_logs",    state),
        Send("gather_metrics", state),
    ]


# ── Reason node: LLM decides next action ─────────────────────────────────────

def _extract_deployment(pods_info: str) -> str | None:
    """Extract the deployment name from kubectl get pods output by stripping the pod random suffix."""
    for line in pods_info.splitlines()[1:]:     # skip header row
        parts = line.split()
        if not parts:
            continue
        pod_name = parts[0]
        segs = pod_name.split("-")
        # Standard Kubernetes naming: <deploy>-<replicaset-hash>-<pod-hash>
        # ReplicaSet hash is 9 chars, pod hash is 5 chars
        if len(segs) >= 3 and len(segs[-1]) <= 6 and len(segs[-2]) in (5, 9, 10):
            return "-".join(segs[:-2])
        # Fallback: drop just the last segment
        if len(segs) >= 2:
            return "-".join(segs[:-1])
        return pod_name
    return None


def _suggest_memory(logs_info: str, triage: str) -> str:
    """
    Adaptive memory suggestion: parse the actual heap/memory limit from logs
    and suggest 4x that value (rounded to next standard Kubernetes size).
    Falls back to 512Mi if undetectable.
    """
    import re
    combined = logs_info + " " + triage
    # Match patterns like "Heap limit: 61MB", "memory limit 256Mi", "64m", "limit: 128Mi"
    match = re.search(r'(?:heap limit|memory limit|limit)[:\s]+(\d+)\s*(mb|mi|gb|gi|m|g)\b',
                      combined, re.IGNORECASE)
    if not match:
        # Also try plain number + unit e.g. "[OOM-DEMO] Heap limit: 61MB"
        match = re.search(r'(\d+)\s*(mb|mi|gb|gi)\b', combined, re.IGNORECASE)

    if match:
        val  = int(match.group(1))
        unit = match.group(2).upper()
        # Normalise to MiB
        mb = val if unit in ("MB", "MI", "M") else val * 1024
        # Suggest 4x the current limit, rounded to standard sizes
        target_mb = mb * 4
        for size in [128, 256, 512, 1024, 2048, 4096]:
            if size >= target_mb:
                return f"{size}Mi" if size < 1024 else f"{size // 1024}Gi"

    return "512Mi"   # safe default


def _analyze_for_code_fix(logs_info: str, triage_summary: str, alert_name: str) -> list:
    """
    Detect application-level issues that kubectl commands alone cannot resolve.
    Returns a list of code-level suggestion dicts, or empty list if no code issue detected.

    Patterns detected:
      - Memory leak (OOM despite high memory limit)
      - Stack overflow / infinite recursion
      - NullPointerException / null reference
      - Connection / resource leak (pool exhausted)
      - Infinite retry loop causing CrashLoop
      - Missing config / secrets
    """
    import re
    suggestions = []
    combined  = (logs_info + " " + triage_summary + " " + alert_name).lower()

    # ── Memory Leak (OOM + already has high limit → leak, not under-provisioning) ──
    has_oom        = any(k in combined for k in ("outofmemoryerror", "oomkilled", "heap space", "java heap", "gc overhead"))
    has_high_limit = any(k in combined for k in ("1gi", "2gi", "4gi", "2048mi", "4096mi", "1024mi"))
    if has_oom and has_high_limit:
        suggestions.append({
            "issue_type":   "memory_leak",
            "title":        "Memory Leak Detected",
            "root_cause":   "Pod OOMs even with a high memory limit — the application is leaking memory, not just under-provisioned. Increasing limits is a short-term band-aid.",
            "code_pattern": "Look for: unclosed streams/connections, static collections that grow unbounded, event listeners that accumulate without removal, in-memory caches with no eviction policy.",
            "fix_suggestion": "Profile the heap with async-profiler or JProfiler to locate the leak. Common fixes: close resources in try-with-resources, use bounded Caffeine caches, remove listeners on shutdown.",
            "code_example": """// BAD — grows forever
private static final Map<String, Session> CACHE = new HashMap<>();

// GOOD — bounded + auto-evicting
private static final Cache<String, Session> CACHE = Caffeine.newBuilder()
    .maximumSize(10_000)
    .expireAfterWrite(1, TimeUnit.HOURS)
    .build();""",
        })

    # ── Stack Overflow / Infinite Recursion ────────────────────────────────────
    if any(k in combined for k in ("stackoverflow", "stack overflow", "stackoverflowerror")):
        suggestions.append({
            "issue_type":   "stack_overflow",
            "title":        "Stack Overflow — Infinite Recursion",
            "root_cause":   "The JVM call stack is exhausted. A method is calling itself (directly or via a proxy) without a base case.",
            "code_pattern":  "Check: toString/equals/hashCode calling themselves, Spring AOP proxies that call back into the same bean, serialization hooks (Jackson @JsonSerialize) that re-serialize the same object.",
            "fix_suggestion": "Add a proper base case, convert recursive logic to iterative, or increase stack depth with -Xss4m as a temporary measure. For Spring, use self-injection via ApplicationContext to break the cycle.",
            "code_example": """// BAD — infinite recursion
@Override
public String toString() {
    return "Order{details=" + this.toString() + "}";  // calls itself!
}

// GOOD — use fields directly
@Override
public String toString() {
    return "Order{id=" + id + ", total=" + total + "}";
}""",
        })

    # ── NullPointerException ────────────────────────────────────────────────────
    if any(k in combined for k in ("nullpointerexception", "null pointer", "nullreferenceexception")):
        npe_context = ""
        npe_match = re.search(r'at\s+([\w.$]+)\.([\w$<>]+)\(.*?:(\d+)\)', logs_info)
        if npe_match:
            npe_context = f" in {npe_match.group(1)}.{npe_match.group(2)}() line {npe_match.group(3)}"
        suggestions.append({
            "issue_type":   "null_reference",
            "title":        f"NullPointerException{npe_context}",
            "root_cause":   "An object reference is null when accessed. Common causes: missing @Autowired wiring, unset config values, race condition during startup, external API returning null.",
            "code_pattern":  "Check: @Value-injected fields with no defaults, return values from Optional.get() without isPresent(), service fields used before @PostConstruct completes.",
            "fix_suggestion": "Add null guards or use Optional. For @Value fields, add defaults: @Value(\"${key:default}\"). For external calls, always check for null before chaining.",
            "code_example": """// BAD
String env = System.getenv("API_KEY").trim();  // NPE if env var missing

// GOOD — null-safe with Optional
String env = Optional.ofNullable(System.getenv("API_KEY"))
    .map(String::trim)
    .orElseThrow(() -> new IllegalStateException("API_KEY env var is required"));

// Spring @Value with default
@Value("${api.key:}")
private String apiKey;""",
        })

    # ── Connection / Resource Leak ──────────────────────────────────────────────
    if any(k in combined for k in ("connection pool", "pool exhausted", "too many connections",
                                    "no available connections", "connection timeout", "connectionpoolexhausted")):
        suggestions.append({
            "issue_type":   "connection_leak",
            "title":        "Database / Resource Connection Leak",
            "root_cause":   "Connections are checked out from the pool but never returned, exhausting available connections for new requests.",
            "code_pattern":  "Look for: connections opened in try blocks without a finally close, @Transactional methods that spawn threads (child thread doesn't inherit transaction), long-running transactions holding connections open.",
            "fix_suggestion": "Use try-with-resources for all Connection/Stream objects. Verify @Transactional boundaries. Set pool validation-query and connection-timeout. Monitor pool metrics via /actuator/metrics/hikaricp.",
            "code_example": """// BAD — connection leaks on exception
Connection conn = dataSource.getConnection();
ResultSet rs = conn.createStatement().executeQuery(sql);

// GOOD — auto-closed by try-with-resources
try (Connection conn = dataSource.getConnection();
     PreparedStatement ps = conn.prepareStatement(sql);
     ResultSet rs = ps.executeQuery()) {
    while (rs.next()) { /* process */ }
}  // all resources closed even on exception""",
        })

    # ── Infinite Retry Loop → CrashLoop ────────────────────────────────────────
    # Note: "backoff" is intentionally excluded — it appears in K8s "CrashLoopBackOff" status and causes false positives
    if (any(k in combined for k in ("retrying", "retry attempt", "max retries exceeded", "attempt 1 of", "will retry"))
            and any(k in combined for k in ("crashloopbackoff", "crash loop", "restarting", "exit code 1"))):
        suggestions.append({
            "issue_type":   "infinite_retry",
            "title":        "Infinite Retry Loop Causing CrashLoop",
            "root_cause":   "The application retries a failing operation (DB connect, service call) on startup without a max-attempts limit, crashing the pod each time.",
            "code_pattern":  "Search startup/init code for: while(true) retry loops, @EventListener(ApplicationReadyEvent) that call external services without circuit breakers.",
            "fix_suggestion": "Cap retries with exponential backoff + jitter. Use Resilience4j Retry with maxAttempts. Separate startup liveness probe from readiness probe so the pod has time to retry without being killed.",
            "code_example": """// BAD — retries forever, pod gets killed
while (true) {
    try { db.ping(); break; }
    catch (Exception e) { Thread.sleep(1000); }
}

// GOOD — bounded retry with Resilience4j
RetryConfig cfg = RetryConfig.custom()
    .maxAttempts(10)
    .waitDuration(Duration.ofSeconds(2))
    .retryExceptions(SQLException.class)
    .build();
Retry.decorateCheckedSupplier(Retry.of("db", cfg), db::ping).get();""",
        })

    # ── Missing Config / Secrets ────────────────────────────────────────────────
    if any(k in combined for k in ("no such property", "required property", "missing secret",
                                    "configmap not found", "keynotfoundexception",
                                    "environment variable not set", "illegalstateexception")):
        suggestions.append({
            "issue_type":   "config_error",
            "title":        "Missing Configuration or Secret",
            "root_cause":   "A required environment variable, Kubernetes Secret, or ConfigMap key is absent, preventing the application from starting.",
            "code_pattern":  "Check: YAML/properties required keys, @Value('${...}') without defaults, Kubernetes secretKeyRef/configMapKeyRef in pod spec.",
            "fix_suggestion": "Verify the Secret/ConfigMap exists in the correct namespace. Add @Value defaults for optional fields. Use kubectl describe pod to see exact env-var injection errors.",
            "code_example": """# Diagnose missing env vars
kubectl describe pod <pod-name> -n <namespace> | grep -A5 "Error\\|Warning"
kubectl exec -n <namespace> <pod> -- env | sort

# Add to secret (base64-encoded)
kubectl create secret generic myapp-secret \\
  --from-literal=DB_PASSWORD=s3cret -n <namespace>

# Spring — add safe default so app starts with warning, not crash
@Value("${DB_PASSWORD:NOT_SET}")
private String dbPassword;""",
        })

    return suggestions


def _classify_alert_category(alert_name: str, logs_info: str, triage_summary: str) -> str:
    """
    Classify the alert into one of five categories the system prompt and fast_decide use.
    Deterministic — no LLM needed.
    """
    alert_lower  = alert_name.lower()
    combined     = (logs_info + " " + triage_summary).lower()

    if any(k in alert_lower for k in (
        "kubecontrollermanager", "kubeapiserverdown", "kubeapidown", "kubeapiserver",
        "kubescheduler", "kubeproxy", "kubelet", "kubenode",
    )):
        return "CONTROL_PLANE"

    if "etcd" in alert_lower:
        return "ETCD"

    if any(k in combined for k in (
        "outofmemoryerror", "oomkilled", "java heap", "heap space",
        "gc overhead", "killed process", "cannot allocate memory",
    )):
        return "OOM_MEMORY"

    if any(k in alert_lower for k in ("replicamismatch", "unavailable", "pending", "deployment")):
        return "REPLICA"

    return "CRASH_LOOP"


def _fast_decide(state: ExecutorState) -> dict | None:
    """
    Context-aware fast path — skips the LLM when the diagnosis is unambiguous.
    Adapts the fix (deployment name, memory size) from actual cluster state.
    Returns a decision dict or None (fall through to LLM).
    """
    logs   = state.get("logs_info")    or ""
    pods   = state.get("pods_info")    or ""
    triage = state.get("triage_summary") or ""
    ns     = state["namespace"]
    steps  = state.get("scratchpad", [])
    category = _classify_alert_category(state["alert_name"], logs, triage)

    # Only fast-path on the first reason call — subsequent calls need LLM for nuance
    if steps:
        return None

    # ── CONTROL_PLANE / ETCD fast path ────────────────────────────────────────
    # Control plane components are static pods — rollout restart and patch_resources
    # don't apply. Inspect pod status and escalate with a clear explanation.
    if category in ("CONTROL_PLANE", "ETCD"):
        component_keywords = {
            "kubecontrollermanager": "controller-manager",
            "kubescheduler":         "scheduler",
            "kubeproxy":             "proxy",
            "kubeapiserver":         "apiserver",
            "kubeapidown":           "apiserver",
            "etcd":                  "etcd",
            "kubelet":               "kubelet",
        }
        alert_lower = state["alert_name"].lower()
        component = next(
            (v for k, v in component_keywords.items() if k in alert_lower),
            "component",
        )
        pod_status = "(not found)"
        for line in pods.splitlines()[1:]:
            parts = line.split()
            if parts and component in parts[0].lower():
                pod_status = parts[2] if len(parts) > 2 else "Unknown"
                break

        if "running" in pod_status.lower():
            thought = (
                f"{state['alert_name']}: {component} pod is Running in {ns}. "
                f"Alert is likely a transient probe failure or monitoring lag — not an active outage. "
                f"No kubectl action can fix a stale alert. Escalating for human verification."
            )
        elif pod_status == "(not found)":
            thought = (
                f"{state['alert_name']}: no {component} pod found in {ns}. "
                f"Component may run as a host process (not a pod) or node is unreachable. "
                f"Requires manual investigation — escalating."
            )
        else:
            thought = (
                f"{state['alert_name']}: {component} pod is {pod_status} in {ns}. "
                f"Control plane / etcd crashes require human intervention — "
                f"static pods cannot be restarted via kubectl rollout. Escalating immediately."
            )

        logger.info("fast_decide: %s → escalate (component=%s status=%s)", category, component, pod_status)
        return {
            "thought":  thought,
            "action":   "",
            "args":     {},
            "done":     True,
            "escalate": True,
        }

    deployment = _extract_deployment(pods)

    logs_lower   = logs.lower()
    triage_lower = triage.lower()

    pods_lower = pods.lower()
    oom_evidence = any(kw in logs_lower or kw in triage_lower or kw in pods_lower for kw in (
        "outofmemoryerror", "oomkilled", "java heap", "heap space",
        "killed process", "cannot allocate memory",
    ))

    # Parse restart count from pods_info for adaptive sizing
    restart_count = 0
    for line in pods.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            try:
                restart_count = int(parts[3])
            except ValueError:
                pass
            break

    if oom_evidence and deployment:
        memory_limit = _suggest_memory(logs, triage)
        # If many restarts and logs didn't reveal current limit, scale up more aggressively
        if memory_limit == "512Mi" and restart_count > 20:
            memory_limit = "1Gi"
        source = "logs" if "heap" in logs_lower else "pod status (OOMKilled)"
        thought = (
            f"OOM detected via {source} — {deployment} has restarted {restart_count}x. "
            f"Patching to {memory_limit}."
        )
        logger.info("fast_decide: OOM → patch_resources(%s, %s)", deployment, memory_limit)
        return {
            "thought":  thought,
            "action":   "patch_resources",
            "args":     {"deployment": deployment, "namespace": ns, "memory_limit": memory_limit},
            "done":     False,
            "escalate": False,
        }

    # High restart count with no OOM → get logs first to understand why
    if restart_count >= 10 and deployment and not oom_evidence:
        # Only do rollout_restart if logs already explain the issue
        logs_has_data = bool(logs_lower) and "(no pod" not in logs_lower and len(logs_lower) > 30
        if logs_has_data:
            logger.info("fast_decide: high restarts (%d) + logs available → rollout_restart(%s)", restart_count, deployment)
            return {
                "thought":  f"{deployment} has restarted {restart_count}x. Logs don't show OOM — rolling restart to clear bad state.",
                "action":   "rollout_restart",
                "args":     {"deployment": deployment, "namespace": ns},
                "done":     False,
                "escalate": False,
            }
        # No logs yet → let LLM decide (it will get_logs first)
        logger.info("fast_decide: high restarts but no logs → falling through to LLM")

    return None   # fall through to LLM for complex/ambiguous cases


def reason(state: ExecutorState) -> dict:
    # Fast path: skip LLM for unambiguous OOM cases
    fast = _fast_decide(state)
    if fast:
        _push_event(state["execution_id"], "decision", {
            "thought":  fast["thought"], "action": fast["action"],
            "args":     fast["args"],    "done":   fast["done"],
            "escalate": fast["escalate"],
        })
        return {
            "last_thought": fast["thought"],
            "next_action":  fast["action"],
            "next_args":    fast["args"],
            "done":         fast["done"],
            "escalate":     fast["escalate"],
        }

    _push_event(state["execution_id"], "thinking", {
        "step": len(state.get("scratchpad", [])) + 1,
        "message": "LLM reasoning over cluster state...",
    })
    scratchpad_text  = _format_scratchpad(state.get("scratchpad", []))
    alert_category   = _classify_alert_category(
        state["alert_name"],
        state.get("logs_info", ""),
        state.get("triage_summary", ""),
    )

    user_message = _USER_TEMPLATE.format(
        pods_info      = state.get("pods_info",    "(not gathered yet)"),
        logs_info      = state.get("logs_info",    "(not gathered yet)"),
        metrics_info   = state.get("metrics_info", "(not gathered yet)"),
        scratchpad     = scratchpad_text,
        alert_name     = state["alert_name"],
        namespace      = state["namespace"],
        triage_summary = state["triage_summary"],
        alert_category = alert_category,
    )
    try:
        content = _call_ollama(user_message)
        parsed = json.loads(content)
    except Exception as e:
        logger.error("LLM reason failed: %s", e)
        return {
            "done": True, "escalate": True,
            "final_summary": f"LLM unavailable: {e}",
            "status": ExecutionStatus.FAILED.value,
        }

    thought  = parsed.get("thought", "")
    action   = parsed.get("action", "")
    args     = parsed.get("args", {})
    done     = parsed.get("done", False)
    escalate = parsed.get("escalate", False)

    logger.info("reason → action=%s done=%s escalate=%s", action, done, escalate)
    _push_event(state["execution_id"], "decision", {
        "thought": thought, "action": action, "args": args,
        "done": done, "escalate": escalate,
    })

    updates: dict = {
        "last_thought": thought,
        "next_action":  action,
        "next_args":    args,
        "done":         done,
        "escalate":     escalate,
    }

    if done:
        updates["status"] = ExecutionStatus.ESCALATED.value if escalate else ExecutionStatus.RESOLVED.value
        updates["final_summary"] = thought
        code_suggs = _analyze_for_code_fix(
            state.get("logs_info", ""),
            state.get("triage_summary", ""),
            state["alert_name"],
        )
        if code_suggs:
            _push_event(state["execution_id"], "code_fix", {"suggestions": code_suggs})
            updates["code_suggestions"] = code_suggs

    return updates


# ── Execute read tool (auto-approved) ─────────────────────────────────────────

def _inject_defaults(args: dict, state: ExecutorState) -> dict:
    """Ensure namespace is always populated from state when LLM omits or blanks it."""
    merged = dict(args)
    if not merged.get("namespace"):
        merged["namespace"] = state["namespace"]
    return merged


def execute_read(state: ExecutorState) -> dict:
    action = state["next_action"]
    args   = _inject_defaults(state["next_args"], state)
    fn, _ = TOOL_REGISTRY.get(action, (None, None))

    if fn is None:
        observation = f"ERROR: unknown tool '{action}'"
        err = observation
    else:
        err = ""
        try:
            observation = fn(**args)
        except Exception as e:
            observation = f"ERROR: {e}"
            err = str(e)

    log_execution_audit(
        execution_id=state["execution_id"],
        incident_id=state.get("incident_id", ""),
        action_type="tool_read",
        tool_name=action,
        command_details={"action": action, "args": args},
        status="error" if err else "success",
        error=err,
        approval_required=False,
    )

    step = {
        "thought":     state["last_thought"],
        "action":      action,
        "args":        args,
        "observation": observation[:1000],    # cap so state doesn't bloat
        "write":       False,
    }
    _push_event(state["execution_id"], "step", {**step, "step_num": len(state.get("scratchpad", [])) + 1})
    logger.info("execute_read %s → %d chars", action, len(observation))
    return {"scratchpad": [step], "status": ExecutionStatus.RUNNING.value}


# ── Execute write tool (fires AFTER human approval via interrupt_before) ───────
#
# LangGraph's interrupt_before=["execute_write"] means the graph PAUSES
# before entering this node. The MemorySaver checkpoints the state.
# The API returns "waiting_approval" to the frontend.
# When the engineer approves via POST /approve, the API calls:
#   graph.invoke(None, config={"configurable": {"thread_id": execution_id}})
# LangGraph rehydrates from the checkpoint and runs THIS node.

def execute_write(state: ExecutorState) -> dict:
    action = state["next_action"]
    args   = _inject_defaults(state["next_args"], state)
    fn, _ = TOOL_REGISTRY.get(action, (None, None))

    if fn is None:
        observation = f"ERROR: unknown tool '{action}'"
        err = observation
    else:
        err = ""
        try:
            observation = fn(**args)
        except Exception as e:
            observation = f"ERROR: {e}"
            err = str(e)

    log_execution_audit(
        execution_id=state["execution_id"],
        incident_id=state.get("incident_id", ""),
        action_type="tool_write",
        tool_name=action,
        command_details={"action": action, "args": args},
        status="error" if err else "success",
        error=err,
        approval_required=True,
        approved_by="engineer",
    )

    step = {
        "thought":     state["last_thought"],
        "action":      action,
        "args":        args,
        "observation": observation[:1000],
        "write":       True,
    }
    _push_event(state["execution_id"], "step", {**step, "step_num": len(state.get("scratchpad", [])) + 1})
    logger.info("execute_write %s → %d chars", action, len(observation))
    return {"scratchpad": [step], "status": ExecutionStatus.RUNNING.value}


# ── Routing after reason ───────────────────────────────────────────────────────
#
# LangGraph calls this to decide which edge to follow after the reason node.
# Returns a string matching one of the registered edge targets.

MAX_STEPS = 8   # hard cap — prevents runaway loops when LLM doesn't set done=True


def _escalate_and_end(execution_id: str, reason_text: str) -> str:
    """Push a terminal escalation event then return END."""
    _push_event(execution_id, "decision", {
        "thought":  reason_text,
        "action":   "",
        "args":     {},
        "done":     True,
        "escalate": True,
    })
    return END


def route_after_reason(state: ExecutorState) -> str:
    scratchpad   = state.get("scratchpad", [])
    exec_id      = state.get("execution_id", "")
    alert_name   = state.get("alert_name", "incident")

    # Hard cap
    if len(scratchpad) >= MAX_STEPS:
        return _escalate_and_end(exec_id,
            f"Reached {MAX_STEPS}-step cap without resolving {alert_name}. "
            f"Escalating for human investigation.")

    if state.get("done"):
        return END

    action = state.get("next_action", "")
    if not action or action not in TOOL_REGISTRY:
        return _escalate_and_end(exec_id,
            f"No valid action determined for {alert_name}. Escalating.")

    # Loop detection: same action repeated with same/empty/error result → stuck
    recent = [s for s in scratchpad if s.get("action") == action]
    if len(recent) >= 1:
        last_obs = (recent[-1].get("observation") or "").strip()
        is_stuck = not last_obs or "error" in last_obs.lower()
        if is_stuck:
            return _escalate_and_end(exec_id,
                f"Action '{action}' already ran and returned no useful data. "
                f"Further retries will not help — escalating.")

    # Block re-fetching data the parallel gather already collected
    if action in ("get_logs", "top_pods") and not scratchpad:
        logs_empty = not (state.get("logs_info") or "").strip() or "(no pod" in (state.get("logs_info") or "")
        pods_empty = not (state.get("pods_info") or "").strip()
        if action == "get_logs" and not logs_empty:
            return _escalate_and_end(exec_id,
                "Logs already gathered in parallel phase — re-fetching adds no value. Escalating.")
        if action == "top_pods" and not pods_empty:
            return _escalate_and_end(exec_id,
                "Metrics already gathered in parallel phase — re-fetching adds no value. Escalating.")

    _, requires_approval = TOOL_REGISTRY[action]
    return "execute_write" if requires_approval else "execute_read"


# ── Scratchpad formatter ───────────────────────────────────────────────────────

def _format_scratchpad(steps: list[dict]) -> str:
    if not steps:
        return "No actions taken yet — use the initial state above to decide first action."
    lines = []
    for i, s in enumerate(steps, 1):
        lines.append(f"--- Step {i} {'[WRITE]' if s.get('write') else '[READ]'} ---")
        lines.append(f"Thought:     {s.get('thought', '')}")
        lines.append(f"Action:      {s.get('action', '')}({json.dumps(s.get('args', {}))})")
        obs = s.get("observation", "")
        if len(obs) > 600:
            obs = obs[:600] + f"\n... [{len(obs)-600} chars truncated]"
        lines.append(f"Observation:\n{obs}")
    return "\n".join(lines)


# ── Build the graph ───────────────────────────────────────────────────────────

def _build_graph(checkpointer: Any) -> Any:
    builder = StateGraph(ExecutorState)

    # Register nodes
    builder.add_node("gather_pods",    gather_pods)
    builder.add_node("gather_logs",    gather_logs)
    builder.add_node("gather_metrics", gather_metrics)
    builder.add_node("reason",         reason)
    builder.add_node("execute_read",   execute_read)
    builder.add_node("execute_write",  execute_write)

    # START → parallel gather (all 3 simultaneously via Send API)
    builder.add_conditional_edges(
        "__start__",
        route_parallel_gather,
        ["gather_pods", "gather_logs", "gather_metrics"],
    )

    # All 3 gather nodes → reason (LangGraph waits for ALL to complete)
    builder.add_edge("gather_pods",    "reason")
    builder.add_edge("gather_logs",    "reason")
    builder.add_edge("gather_metrics", "reason")

    # reason → route to read / write / END
    builder.add_conditional_edges(
        "reason",
        route_after_reason,
        {"execute_read": "execute_read", "execute_write": "execute_write", END: END},
    )

    # Read loops back to reason
    builder.add_edge("execute_read", "reason")

    # Write loops back to reason (after interrupt is cleared)
    builder.add_edge("execute_write", "reason")

    # Checkpointer: checkpoints state at every node boundary.
    # interrupt_before: graph pauses BEFORE execute_write, saves state,
    # returns control to caller. Resume with graph.invoke(None, same_config).
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["execute_write"],
    )


_graph: Any | None = None


def init_graph(checkpointer: Any | None = None) -> None:
    """Build or rebuild the compiled executor graph (called from persistence init)."""
    global _graph
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
    _graph = _build_graph(checkpointer)
    logger.info("ExecutorAgent graph initialized with %s checkpointer", type(checkpointer).__name__)


def _get_graph() -> Any:
    if _graph is None:
        init_graph()
    return _graph


# ── Public API ────────────────────────────────────────────────────────────────

class ExecutorAgent:
    """
    Thin wrapper that maps HTTP API calls to LangGraph graph invocations.

    Each incident gets a unique execution_id (= LangGraph thread_id).
    MemorySaver uses this to checkpoint and restore state across API calls.
    """

    def start(
        self,
        incident_id: str,
        alert_name: str,
        namespace: str,
        triage_summary: str,
    ) -> dict:
        execution_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": execution_id}}

        # Infer correct namespace before the graph starts — control plane alerts
        # arrive with namespace="" or "unknown" from Prometheus.
        namespace = _infer_namespace(alert_name, namespace)

        initial_state: ExecutorState = {
            "execution_id":   execution_id,
            "incident_id":    incident_id,
            "alert_name":     alert_name,
            "namespace":      namespace,
            "triage_summary": triage_summary,
            "pods_info":      "",
            "logs_info":      "",
            "metrics_info":   "",
            "scratchpad":     [],
            "status":           ExecutionStatus.RUNNING.value,
            "next_action":      "",
            "next_args":        {},
            "last_thought":     "",
            "final_summary":    "",
            "done":             False,
            "escalate":         False,
            "code_suggestions": [],
        }

        # Create event queue for SSE streaming BEFORE spawning thread
        _event_queues[execution_id] = queue.Queue()
        _push_event(execution_id, "start", {
            "alert_name": alert_name,
            "namespace":  namespace,
            "category":   _classify_alert_category(alert_name, "", triage_summary),
        })

        log_execution_audit(
            execution_id=execution_id,
            incident_id=incident_id,
            action_type="execution_start",
            tool_name="",
            command_details={
                "alert_name": alert_name,
                "namespace": namespace,
                "triage_summary": triage_summary[:500],
            },
            status="started",
        )

        # Run the graph in a background thread so the HTTP handler returns immediately.
        # The SSE endpoint connects to the queue while the graph is still running.
        config["recursion_limit"] = (MAX_STEPS * 2) + 10

        def _run():
            try:
                _get_graph().invoke(initial_state, config=config)
            except Exception as exc:
                logger.exception("ExecutorAgent graph error: %s", exc)
                _push_event(execution_id, "error", {"message": str(exc)})
                log_execution_audit(
                    execution_id=execution_id,
                    incident_id=incident_id,
                    action_type="execution_error",
                    status="error",
                    error=str(exc),
                )
            finally:
                snapshot = self._snapshot(execution_id)
                status = snapshot.get("status", "failed") if snapshot else "failed"
                if snapshot and snapshot.get("status") == "waiting_approval":
                    pending = snapshot.get("pending_action") or {}
                    log_execution_audit(
                        execution_id=execution_id,
                        incident_id=incident_id,
                        action_type="approval_required",
                        tool_name=pending.get("action", ""),
                        command_details=pending,
                        status="pending",
                        approval_required=True,
                    )
                _maybe_learn_from_execution(snapshot)
                if status not in ("waiting_approval",):
                    _close_stream(execution_id)

        threading.Thread(target=_run, daemon=True, name=f"executor-{execution_id[:8]}").start()

        return {"execution_id": execution_id, "status": "running"}

    def approve(self, execution_id: str) -> dict:
        """
        Resume a graph that is paused at interrupt_before=execute_write.
        Passing None as input tells LangGraph: "continue from checkpoint."
        """
        config = {"configurable": {"thread_id": execution_id}}
        graph_state = _get_graph().get_state(config)

        if not graph_state:
            raise ValueError(f"No state found for execution_id={execution_id}")

        # Extract pending action from saved state for the SSE event
        state_vals = graph_state.values or {}
        next_action = state_vals.get("next_action", "")
        next_args   = state_vals.get("next_args", {})

        # Recreate queue (start() closes it unless waiting_approval)
        _event_queues[execution_id] = queue.Queue()
        _push_event(execution_id, "approved", {"action": next_action, "args": next_args})
        log_execution_audit(
            execution_id=execution_id,
            incident_id=state_vals.get("incident_id", ""),
            action_type="approval_granted",
            tool_name=next_action,
            command_details={"action": next_action, "args": next_args},
            status="approved",
            approval_required=True,
            approved_by="engineer",
        )

        # Run resume in background thread so HTTP returns immediately
        config["recursion_limit"] = (MAX_STEPS * 2) + 10

        def _resume():
            try:
                _get_graph().invoke(None, config=config)
            except Exception as exc:
                logger.exception("ExecutorAgent resume error: %s", exc)
                _push_event(execution_id, "error", {"message": str(exc)})
                log_execution_audit(
                    execution_id=execution_id,
                    incident_id=state_vals.get("incident_id", ""),
                    action_type="execution_error",
                    status="error",
                    error=str(exc),
                )
            finally:
                snapshot = self._snapshot(execution_id)
                if snapshot and snapshot.get("status") == "waiting_approval":
                    pending = snapshot.get("pending_action") or {}
                    log_execution_audit(
                        execution_id=execution_id,
                        incident_id=state_vals.get("incident_id", ""),
                        action_type="approval_required",
                        tool_name=pending.get("action", ""),
                        command_details=pending,
                        status="pending",
                        approval_required=True,
                    )
                _maybe_learn_from_execution(snapshot)
                _close_stream(execution_id)

        threading.Thread(target=_resume, daemon=True, name=f"executor-resume-{execution_id[:8]}").start()
        return {"execution_id": execution_id, "status": "running"}

    def get(self, execution_id: str) -> dict | None:
        snap = self._snapshot(execution_id)
        if snap is not None:
            return snap
        # Graph is still in-flight (no checkpoint yet) but queue exists
        if execution_id in _event_queues:
            return {"execution_id": execution_id, "status": "running", "scratchpad": [], "pending_action": None}
        return None

    def _snapshot(self, execution_id: str) -> dict | None:
        config = {"configurable": {"thread_id": execution_id}}
        snapshot = _get_graph().get_state(config)
        if not snapshot or not snapshot.values:
            return None

        state = snapshot.values
        # Determine if currently paused at execute_write interrupt
        next_nodes = list(snapshot.next) if snapshot.next else []
        waiting    = "execute_write" in next_nodes
        graph_done = not next_nodes and not waiting

        # Derive final status.
        # If graph terminated without the LLM explicitly setting done=True
        # (loop detection, MAX_STEPS, or invalid action), treat as escalated —
        # "resolved" must only be set when the agent confirmed the fix worked.
        raw_status = state.get("status", "running")
        if graph_done and raw_status == "running":
            raw_status = "escalated"

        pending = None
        if waiting and state.get("next_action"):
            pending = {
                "action":  state["next_action"],
                "args":    state["next_args"],
                "thought": state["last_thought"],
            }

        return {
            "execution_id":   execution_id,
            "incident_id":    state.get("incident_id", ""),
            "alert_name":     state.get("alert_name", ""),
            "namespace":      state.get("namespace", ""),
            "status":         "waiting_approval" if waiting else raw_status,
            "final_summary":  state.get("final_summary", ""),
            "triage_summary": state.get("triage_summary", ""),
            "pods_info":      state.get("pods_info", ""),
            "logs_info":      state.get("logs_info", ""),
            "metrics_info":   state.get("metrics_info", ""),
            "scratchpad":       state.get("scratchpad", []),
            "pending_action":   pending,
            "code_suggestions": state.get("code_suggestions", []),
        }


# Module-level singleton
executor_agent = ExecutorAgent()


def stream_execution_events(execution_id: str):
    """
    Generator for SSE — yields events from the execution queue as they arrive.
    Each event is a JSON line prefixed with 'data: ' per SSE spec.
    The frontend uses EventSource to receive them in real-time.
    """
    q = _event_queues.get(execution_id)
    if q is None:
        yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'Execution not found'}})}\n\n"
        return

    while True:
        try:
            event = q.get(timeout=30)   # 30s timeout — client reconnects if stale
        except queue.Empty:
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
            continue

        if event is None:               # sentinel — stream closed
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            break

        yield f"data: {json.dumps(event)}\n\n"
