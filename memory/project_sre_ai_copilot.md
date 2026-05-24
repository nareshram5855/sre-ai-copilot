---
name: project-sre-ai-copilot
description: SRE AI Copilot — local LLM-powered SRE platform, project goals and phase plan
metadata:
  type: project
---

Building "SRE AI Copilot" — a local AI-powered SRE platform with 5 core features:
1. Intelligent Alert Triage
2. Autonomous Runbook Executor
3. Auto RCA Generator
4. On-Call Knowledge Assistant
5. Proactive Anomaly Predictor

**Tech stack:** Ollama + Mistral 7B, LangChain LCEL, ChromaDB, FastAPI, React 18 + Vite + TailwindCSS

**Why:** Fills SRE gaps using local LLM (no external API), RAG over runbooks/incidents, and autonomous agents

**Phases:**
- Phase 1: Local prototype — COMPLETE (Ollama, RAG, ChromaDB, FastAPI, React, docker-compose)
- Phase 2: LangChain agents, memory, RCA, alert triage intelligence upgrade
- Phase 3: Prometheus, AlertManager, K8s, ServiceNow, Slack integrations
- Phase 4: EKS deployment, Terraform, ArgoCD GitOps, Helm, GitHub Actions, Karpenter

**Current status:** Phase 1 complete. All files written, user needs to run setup commands.

**Project path:** /Users/shivapriya/Downloads/sre-ai/

**Port layout:**
- 11434: Ollama (native macOS)
- 8000: ChromaDB (Docker)
- 8080: FastAPI backend (native Python venv)
- 5173: React frontend (Vite native)

**Key design decisions:**
- Ollama runs NATIVE on macOS (not Docker) — Metal GPU acceleration
- Mistral 7B Q4_K_M (pulled via `ollama pull mistral`) — ~4.1GB, leaves 12GB for stack
- nomic-embed-text for embeddings — 768-dim, reuses Ollama process
- LCEL chains in Phase 1 (not ReAct agents) — agents come in Phase 2
- ChromaDB smart client: HTTP fallback to PersistentClient for dev without Docker
- Sample knowledge base tuned to IAM/CISO domain (PingFederate, SiteMinder, IAM token service)

**How to apply:** When generating code or commands, match production-grade quality. Always explain design decisions in SRE terms.
