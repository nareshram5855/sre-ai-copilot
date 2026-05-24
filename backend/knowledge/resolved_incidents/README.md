# Resolved Incidents (auto-learned)

This directory is a placeholder for the `resolved_incidents` knowledge domain.

Successful ExecutorAgent resolutions are embedded directly into the
`sre_resolved_incidents` ChromaDB collection by `LearningAgent` — they do
not originate from static markdown files here.

After three successful resolutions for the same alert type, an auto-runbook
is promoted to `runbooks/auto/`.
