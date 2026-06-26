import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Github, ExternalLink, Workflow, GitPullRequest, AlertCircle,
  ChevronRight, Filter, Sparkles, X,
} from "lucide-react";
import { fetchJSON } from "../utils/api.js";
import { formatRelativeTime } from "../utils/format.js";
import PageHeader from "../components/ui/PageHeader.jsx";
import { Card } from "../components/ui/Card.jsx";
import Badge from "../components/ui/Badge.jsx";
import Button from "../components/ui/Button.jsx";
import EmptyState from "../components/ui/EmptyState.jsx";
import WorkflowLoading from "../components/ui/WorkflowLoading.jsx";
import { Table, TableHead, TableHeader, TableBody, TableRow, TableCell } from "../components/ui/Table.jsx";
import PipelineStages from "../components/ui/PipelineStages.jsx";
import Terminal from "../components/ui/Terminal.jsx";
import MarkdownResponse from "../components/ai/MarkdownResponse.jsx";

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "failed", label: "Failed" },
  { value: "success", label: "Success" },
];

function workflowStatusVariant(run) {
  if (run.status === "in_progress" || run.status === "queued") return "warning";
  if (run.conclusion === "success") return "success";
  if (run.conclusion === "failure") return "failed";
  return "default";
}

function jobStepStatus(step) {
  if (step.status === "in_progress") return "running";
  if (step.conclusion === "success") return "success";
  if (step.conclusion === "failure") return "failed";
  if (step.conclusion === "skipped") return "skipped";
  return "pending";
}

function jobsToStages(jobs) {
  return (jobs ?? []).flatMap((job) =>
    (job.steps ?? []).map((step, i) => ({
      id: `${job.id}-${step.number ?? i}`,
      label: `${job.name}: ${step.name}`,
      status: jobStepStatus(step),
      error: step.conclusion === "failure" ? `${job.name} — ${step.name}` : undefined,
    }))
  );
}

const _API_BASE = import.meta.env.VITE_API_BASE || "/api";

async function streamRunHelp(runId, body, { onChunk, onDone, onError }) {
  const token = sessionStorage.getItem("infra_platform_token");
  try {
    const res = await fetch(`${_API_BASE}/team/runs/${runId}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const msg = await res.text();
      onError(res.status === 503 ? "AI not available — check ai_enabled and provider config." : msg);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop();
      for (const part of parts) {
        if (!part.startsWith("data: ")) continue;
        const data = part.slice(6);
        if (data === "[DONE]") { onDone(); return; }
        onChunk(data);
      }
    }
    onDone();
  } catch (e) {
    onError(e.message);
  }
}

function RunDetailPanel({ run, projectId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aiAnswer, setAiAnswer] = useState("");
  const [aiStreaming, setAiStreaming] = useState(false);
  const [aiError, setAiError] = useState(null);

  useEffect(() => {
    if (!run?.id || !projectId) return;
    setLoading(true);
    fetchJSON(`/team/runs/${run.id}/detail?project_id=${projectId}`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false));
  }, [run?.id, projectId]);

  const stages = useMemo(() => jobsToStages(detail?.jobs), [detail?.jobs]);
  const isFailed = run?.conclusion === "failure" || detail?.conclusion === "failure";

  async function handleAskStackport() {
    setAiAnswer("");
    setAiError(null);
    setAiStreaming(true);
    await streamRunHelp(run.id, { project_id: projectId }, {
      onChunk: (chunk) => setAiAnswer((prev) => prev + chunk),
      onDone: () => setAiStreaming(false),
      onError: (err) => { setAiError(err); setAiStreaming(false); },
    });
  }

  return (
    <Card className="border-accent/25">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-[var(--text-primary)] truncate">
            {run.name}
          </p>
          <p className="text-xs text-[var(--text-muted)] mt-0.5 font-mono">
            {run.repo} · {run.head_branch ?? "—"}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <a href={run.url} target="_blank" rel="noreferrer">
            <Button variant="outline" size="sm" icon={ExternalLink}>Open in GitHub</Button>
          </a>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
            aria-label="Close run detail"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {loading ? (
        <WorkflowLoading preset="cicd" compact title="Loading run detail" />
      ) : detail ? (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge status={detail.conclusion || detail.status} variant={workflowStatusVariant(detail)} dot />
            <span className="text-xs text-[var(--text-muted)]">
              Started {formatRelativeTime(detail.created_at)}
            </span>
          </div>

          {detail.failed_step && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2">
              <p className="text-xs font-medium text-red-300">
                Failed step: {detail.failed_job?.name} → {detail.failed_step.name}
              </p>
            </div>
          )}

          {stages.length > 0 && (
            <PipelineStages stages={stages} />
          )}

          {detail.log_excerpt && (
            <Terminal
              title="Job log excerpt"
              subtitle={detail.failed_job?.name}
              status={isFailed ? "failed" : undefined}
              logs={[detail.log_excerpt]}
              maxHeight="16rem"
            />
          )}

          {detail.log_error && !detail.log_excerpt && (
            <p className="text-xs text-amber-300/80">{detail.log_error}</p>
          )}

          {isFailed && (
            <div className="space-y-3 pt-2 border-t border-[var(--border-subtle)]">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">
                  Stackport assistant
                </p>
                <Button
                  size="sm"
                  icon={Sparkles}
                  onClick={handleAskStackport}
                  disabled={aiStreaming}
                >
                  {aiStreaming ? "Thinking…" : "Ask Stackport"}
                </Button>
              </div>
              {aiError && (
                <p className="text-xs text-red-400">{aiError}</p>
              )}
              {(aiAnswer || aiStreaming) && (
                <MarkdownResponse content={aiAnswer} streaming={aiStreaming} />
              )}
            </div>
          )}
        </div>
      ) : (
        <EmptyState
          icon={AlertCircle}
          title="Could not load run detail"
          description="The run may have been deleted or GitHub credentials lack access."
        />
      )}
    </Card>
  );
}

export default function MyTeam() {
  const [searchParams] = useSearchParams();
  const [workspace, setWorkspace] = useState(null);
  const [runs, setRuns] = useState([]);
  const [statusFilter, setStatusFilter] = useState(() => {
    const s = searchParams.get("status");
    return s === "failed" || s === "success" ? s : "all";
  });
  const [loading, setLoading] = useState(true);
  const [runsLoading, setRunsLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState(null);

  const loadWorkspace = useCallback(() => {
    return fetchJSON("/team/workspace").then(setWorkspace);
  }, []);

  const loadRuns = useCallback((status) => {
    setRunsLoading(true);
    return fetchJSON(`/team/runs?status=${status}&limit=50`)
      .then((data) => setRuns(data.runs ?? []))
      .finally(() => setRunsLoading(false));
  }, []);

  useEffect(() => {
    const s = searchParams.get("status");
    if (s === "failed" || s === "success" || s === "all") {
      setStatusFilter(s);
    }
  }, [searchParams]);

  useEffect(() => {
    Promise.all([loadWorkspace(), loadRuns("all")]).finally(() => setLoading(false));
  }, [loadWorkspace, loadRuns]);

  useEffect(() => {
    if (!loading) loadRuns(statusFilter);
  }, [statusFilter, loadRuns, loading]);

  function handleSelectRun(run) {
    setSelectedRun(run);
  }

  if (loading) {
    return (
      <div className="p-6 lg:p-8">
        <WorkflowLoading preset="iac" title="Loading My Team" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-8 animate-fade-in">
      <PageHeader
        title="My Team"
        description="GitHub Actions pipelines, IaC requests, and run diagnostics for your onboarded team repos."
        actions={
          workspace?.projects?.length > 0 && (
            <Badge variant="info">{workspace.projects.length} repo{workspace.projects.length === 1 ? "" : "s"}</Badge>
          )
        }
      />

      {workspace?.scope_note && (
        <Card className="border-amber-500/25 bg-amber-500/5">
          <p className="text-xs text-[var(--text-muted)]">{workspace.scope_note}</p>
        </Card>
      )}

      {!workspace?.configured ? (
        <Card className="border-amber-500/25 bg-amber-500/5">
          <EmptyState
            icon={Github}
            title="GitHub not connected"
            description={workspace?.message ?? "Set GITHUB_TOKEN on the backend or run gh auth login."}
          />
        </Card>
      ) : workspace?.projects?.length === 0 ? (
        <Card>
          <EmptyState
            icon={GitPullRequest}
            title="No team repos yet"
            description="Onboard an Infra Deploy or application repo to see pipelines and IaC requests here."
            action={
              <Link to="/onboard">
                <Button size="sm">Onboard a project</Button>
              </Link>
            }
          />
        </Card>
      ) : (
        <>
          {/* Overview */}
          <section>
            <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">Overview</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
              <Card>
                <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] mb-1">Open IaC requests</p>
                <p className="text-2xl font-bold text-[var(--text-primary)]">{workspace.open_iac_issues_count ?? 0}</p>
              </Card>
              <Card>
                <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] mb-1">Recent runs</p>
                <p className="text-2xl font-bold text-[var(--text-primary)]">{workspace.recent_runs?.length ?? 0}</p>
              </Card>
              <Card>
                <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] mb-1">Failed runs</p>
                <p className="text-2xl font-bold text-red-400">{workspace.failed_runs_count ?? 0}</p>
              </Card>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <Card padding={false}>
                <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Open IaC requests</p>
                  <Badge variant="info">{workspace.open_iac_issues?.length ?? 0}</Badge>
                </div>
                {(workspace.open_iac_issues?.length ?? 0) === 0 ? (
                  <div className="p-6 text-sm text-[var(--text-muted)]">No open IaC requests.</div>
                ) : (
                  <Table>
                    <TableHead>
                      <TableHeader>Repo</TableHeader>
                      <TableHeader>Request</TableHeader>
                      <TableHeader />
                    </TableHead>
                    <TableBody>
                      {workspace.open_iac_issues.slice(0, 5).map((issue) => (
                        <TableRow key={`${issue.repo}-${issue.number}`}>
                          <TableCell className="text-xs font-mono text-[var(--text-muted)]">{issue.repo}</TableCell>
                          <TableCell>
                            <p className="text-sm truncate max-w-[200px]">{issue.title}</p>
                          </TableCell>
                          <TableCell>
                            <a href={issue.url} target="_blank" rel="noreferrer" className="text-accent text-xs inline-flex items-center gap-1">
                              View <ExternalLink size={12} />
                            </a>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </Card>

              <Card padding={false}>
                <div className="px-4 py-3 border-b border-[var(--border-subtle)] flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">Recent runs</p>
                  <Badge variant="default">{workspace.recent_runs?.length ?? 0}</Badge>
                </div>
                {(workspace.recent_runs?.length ?? 0) === 0 ? (
                  <div className="p-6 text-sm text-[var(--text-muted)]">No recent workflow runs.</div>
                ) : (
                  <Table>
                    <TableHead>
                      <TableHeader>Workflow</TableHeader>
                      <TableHeader>Result</TableHeader>
                      <TableHeader />
                    </TableHead>
                    <TableBody>
                      {workspace.recent_runs.slice(0, 5).map((run) => (
                        <TableRow
                          key={`${run.repo}-${run.id}`}
                          className="cursor-pointer hover:bg-[var(--bg-hover)]"
                          onClick={() => handleSelectRun(run)}
                        >
                          <TableCell>
                            <div className="flex items-center gap-1.5">
                              <Workflow size={12} className="text-[var(--text-faint)]" />
                              <span className="text-sm truncate max-w-[180px]">{run.name}</span>
                            </div>
                            <p className="text-[10px] font-mono text-[var(--text-faint)] mt-0.5">{run.repo}</p>
                          </TableCell>
                          <TableCell>
                            <Badge status={run.conclusion || run.status} variant={workflowStatusVariant(run)} dot />
                          </TableCell>
                          <TableCell>
                            <ChevronRight size={14} className="text-[var(--text-faint)]" />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </Card>
            </div>
          </section>

          {/* Pipelines & runs */}
          <section>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">Pipelines & runs</h2>
              <div className="flex items-center gap-1.5">
                <Filter size={14} className="text-[var(--text-faint)]" />
                {STATUS_FILTERS.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setStatusFilter(value)}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                      statusFilter === value
                        ? "bg-accent/15 text-accent border border-accent/30"
                        : "text-[var(--text-muted)] hover:bg-[var(--bg-hover)] border border-transparent"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {selectedRun && (
              <div className="mb-4">
                <RunDetailPanel
                  run={selectedRun}
                  projectId={selectedRun.project_id}
                  onClose={() => setSelectedRun(null)}
                />
              </div>
            )}

            <Card padding={false}>
              {runsLoading ? (
                <div className="p-6">
                  <WorkflowLoading preset="cicd" compact title="Refreshing workflow runs" />
                </div>
              ) : runs.length === 0 ? (
                <EmptyState
                  icon={Workflow}
                  title="No runs match this filter"
                  description={`No ${statusFilter === "all" ? "" : statusFilter + " "}workflow runs found across team repos.`}
                />
              ) : (
                <Table>
                  <TableHead>
                    <TableHeader>Repo</TableHeader>
                    <TableHeader>Workflow</TableHeader>
                    <TableHeader>Branch</TableHeader>
                    <TableHeader>Result</TableHeader>
                    <TableHeader>Started</TableHeader>
                    <TableHeader />
                  </TableHead>
                  <TableBody>
                    {runs.map((run) => (
                      <TableRow
                        key={`${run.repo}-${run.id}`}
                        className="cursor-pointer hover:bg-[var(--bg-hover)]"
                        onClick={() => handleSelectRun(run)}
                      >
                        <TableCell className="text-xs font-mono text-[var(--text-muted)]">{run.repo}</TableCell>
                        <TableCell className="text-sm">{run.name}</TableCell>
                        <TableCell className="text-xs text-[var(--text-muted)]">{run.head_branch ?? "—"}</TableCell>
                        <TableCell>
                          <Badge status={run.conclusion || run.status} variant={workflowStatusVariant(run)} dot />
                        </TableCell>
                        <TableCell className="text-xs text-[var(--text-muted)]">
                          {formatRelativeTime(run.created_at)}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <a
                            href={run.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-accent text-xs inline-flex items-center gap-1"
                          >
                            GitHub <ExternalLink size={12} />
                          </a>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </Card>
          </section>
        </>
      )}

      {workspace?.message && workspace.configured && (
        <p className="text-xs text-amber-300/80">{workspace.message}</p>
      )}
    </div>
  );
}
