import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchJSON, streamDeploy, canApply, needsProdConfirmation } from "../utils/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useAI } from "../context/AIContext.jsx";
import PageHeader from "../components/ui/PageHeader.jsx";
import { Card } from "../components/ui/Card.jsx";
import Button from "../components/ui/Button.jsx";
import { Select } from "../components/ui/Input.jsx";
import StepIndicator from "../components/ui/StepIndicator.jsx";
import Terminal from "../components/ui/Terminal.jsx";
import PipelineStages, { buildInitialStages } from "../components/ui/PipelineStages.jsx";
import Modal, { ModalActions } from "../components/ui/Modal.jsx";
import Badge from "../components/ui/Badge.jsx";
import { Play, AlertTriangle, Shield, CheckCircle2, XCircle, ExternalLink, FileCode } from "lucide-react";

const PLATFORM_REPO = "nareshram5855/infra-platform";
const PLATFORM_BRANCH = "admin/org-bootstrap";

const STEPS = [
  { id: "env", label: "Environment", description: "Select target" },
  { id: "module", label: "Module", description: "Choose resource" },
  { id: "action", label: "Action", description: "Plan or apply" },
  { id: "run", label: "Execute", description: "Review & run" },
];

function mergeStageEvent(stages, event) {
  const idx = stages.findIndex((s) => s.id === event.stage);
  if (idx === -1) return stages;
  const next = [...stages];
  next[idx] = {
    ...next[idx],
    status: event.status,
    duration_ms: event.duration_ms ?? next[idx].duration_ms,
    warning: event.warning ?? next[idx].warning,
  };
  return next;
}

function buildHcl(env, module) {
  const modShort = module.split("/").pop();
  return [
    `include "root" {`,
    `  path = find_in_parent_folders("root.hcl")`,
    `}`,
    ``,
    `terraform {`,
    `  source = "git::https://github.com/${PLATFORM_REPO}.git//terraform/modules/${module}?ref=main"`,
    `}`,
    ``,
    `inputs = {`,
    `  name        = "payments-${modShort}"`,
    `  env         = "${env}"`,
    `  tags = {`,
    `    Team      = "payments"`,
    `    ManagedBy = "stackport"`,
    `    Env       = "${env}"`,
    `  }`,
    `}`,
  ].join("\n");
}

function TerragruntPreview({ env, module }) {
  const modShort = module.split("/").pop();
  const hclPath = `live/${env}/${modShort}/terragrunt.hcl`;
  const repoUrl = `https://github.com/${PLATFORM_REPO}/tree/${PLATFORM_BRANCH}/live/${env}/${modShort}`;
  const hcl = buildHcl(env, module);

  return (
    <div className="rounded-xl border border-[var(--border-subtle)] overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-[var(--bg-muted)] border-b border-[var(--border-subtle)]">
        <div className="flex items-center gap-2">
          <FileCode size={13} className="text-accent shrink-0" />
          <span className="text-[11px] font-mono text-[var(--text-secondary)]">{hclPath}</span>
        </div>
        <a
          href={repoUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-accent hover:underline flex items-center gap-1 shrink-0"
        >
          View in repo <ExternalLink size={10} />
        </a>
      </div>
      <pre className="p-4 text-xs font-mono text-[var(--text-secondary)] bg-[var(--bg-base)] overflow-x-auto leading-relaxed whitespace-pre">
        {hcl}
      </pre>
    </div>
  );
}

export default function Deploy() {
  const { user } = useAuth();
  const { setPageContext, openPanel } = useAI();
  const [searchParams] = useSearchParams();
  const [envs, setEnvs] = useState([]);
  const [envsLoading, setEnvsLoading] = useState(true);
  const [envsError, setEnvsError] = useState(null);
  const [env, setEnv] = useState(searchParams.get("env") ?? "");
  const [module, setModule] = useState("");
  const [action, setAction] = useState("plan");
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [stages, setStages] = useState([]);
  const [result, setResult] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setEnvsLoading(true);
    setEnvsError(null);
    fetchJSON("/modules/environments")
      .then((d) => {
        if (cancelled) return;
        setEnvs(d.environments ?? []);
        setEnvsError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setEnvs([]);
        const msg = String(err?.message ?? err);
        setEnvsError(
          msg.includes("Failed to fetch") || msg.includes("NetworkError")
            ? "Backend unreachable — start the API on port 8081 (see ui/README)."
            : `Could not load environments: ${msg}`
        );
      })
      .finally(() => {
        if (!cancelled) setEnvsLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const preEnv = searchParams.get("env");
    if (preEnv) setEnv(preEnv);
  }, [searchParams]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  useEffect(() => {
    if (!running && !result) {
      setStages(buildInitialStages(action));
    }
  }, [action, running, result]);

  const modules = envs.find((e) => e.env === env)?.modules ?? [];
  const role = user?.role ?? "viewer";
  const actionAllowed = env && action ? canApply(env, role, action) : false;
  const prodGate = needsProdConfirmation(env, action);

  const currentStep = !env ? 0 : !module ? 1 : !action ? 2 : 3;
  const deploySucceeded = result?.status === "success" && result?.exit_code === 0;
  const deployFailed = result && (result.status === "failed" || result.exit_code !== 0);
  const terminalStatus = deployFailed ? "failed" : deploySucceeded ? "success" : result?.status;
  const showPipeline = stages.length > 0 && (running || logs.length > 0 || result);

  async function executeRun(confirmed = false) {
    const initialStages = buildInitialStages(action);
    setLogs([]);
    setResult(null);
    setStages(initialStages);
    setRunning(true);
    setShowConfirm(false);
    await streamDeploy(
      { env, module, action, confirmed, triggered_by: user?.username },
      {
        onLine: (line) => setLogs((prev) => [...prev, line]),
        onStage: (event) => setStages((prev) => mergeStageEvent(prev, event)),
        onDone: (r) => {
          if (r.stages?.length) {
            setStages(
              r.stages.map((s) => ({
                id: s.id,
                label: s.label,
                status: s.status,
                duration_ms: s.duration_ms,
                warning: s.warning,
              }))
            );
          }
          setResult(r);
          setRunning(false);
          const failed = r.status === "failed" || r.exit_code !== 0;
          const isPlan = action === "plan";
          setPageContext({
            page: "deploy", env, module,
            hint: `${env}/${module} ${action} — ${failed ? "FAILED" : "success"}`,
            error: failed ? r._logSnapshot ?? null : null,
            planOutput: isPlan && !failed ? r._logSnapshot ?? null : null,
          });
          if (failed) openPanel("error");
        },
        onError: (err) => {
          setLogs((prev) => [...prev, `ERROR: ${err}`]);
          setRunning(false);
          setPageContext({ page: "deploy", env, module, error: `ERROR: ${err}`, hint: `${env}/${module} ${action} error` });
          openPanel("error");
        },
      }
    );
  }

  function handleRun(e) {
    e.preventDefault();
    if (prodGate || (action === "destroy" && env !== "dev")) {
      setShowConfirm(true);
      return;
    }
    executeRun(false);
  }

  return (
    <div className="p-6 lg:p-8 space-y-8 max-w-4xl animate-fade-in">
      <PageHeader
        title="Deploy Infrastructure"
        description="Run Terraform plan, apply, validate, or destroy on any module in your environments."
      />

      {envsError && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-red-500/30 bg-red-500/10">
          <AlertTriangle size={16} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-xs text-red-200/90 leading-relaxed">{envsError}</p>
        </div>
      )}

      {role === "operator" && (
        <div className="flex items-start gap-3 p-4 rounded-xl border border-amber-500/20 bg-amber-500/5">
          <Shield size={16} className="text-amber-400 shrink-0 mt-0.5" />
          <p className="text-xs text-amber-200/80 leading-relaxed">
            Operators can apply to dev and staging. Production apply and destroy require admin privileges.
          </p>
        </div>
      )}

      <Card>
        <StepIndicator steps={STEPS} currentStep={currentStep} />

        <form onSubmit={handleRun} className="mt-8 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Select
              label="Environment"
              value={env}
              onChange={(v) => { setEnv(v); setModule(""); }}
              placeholder={envsLoading ? "Loading environments…" : "Select environment…"}
              options={envs.map((e) => ({ value: e.env, label: e.env }))}
              required
              disabled={envsLoading}
            />

            <Select
              label="Module"
              value={module}
              onChange={setModule}
              placeholder="Select module…"
              options={modules.map((m) => ({ value: m, label: m }))}
              searchable
              searchPlaceholder="Filter modules…"
              required
              disabled={!env}
            />

            <Select
              label="Action"
              value={action}
              onChange={setAction}
              options={["plan", "apply", "destroy", "validate"]
                .filter((a) => !env || canApply(env, role, a))
                .map((a) => ({ value: a, label: a }))}
            />
          </div>

          {env && module && (
            <div className="flex flex-wrap items-center gap-2 p-3 rounded-lg bg-[var(--bg-muted)] border border-[var(--border-subtle)]">
              <span className="text-xs text-[var(--text-muted)]">Target:</span>
              <Badge variant={env}>{env}</Badge>
              <span className="text-[var(--text-faint)]">/</span>
              <span className="text-xs font-mono text-accent">{module}</span>
              <span className="text-[var(--text-faint)]">→</span>
              <Badge status={action} />
            </div>
          )}

          {/* Terragrunt config preview — shows generated HCL that would go into the user's repo */}
          {env && module && (
            <TerragruntPreview env={env} module={module} />
          )}

          {currentStep >= 3 && stages.length > 0 && (
            <div className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-muted)]/50">
              <p className="text-xs text-[var(--text-muted)] mb-3 uppercase tracking-wide font-medium">
                Pipeline preview
              </p>
              <PipelineStages stages={stages} running={false} />
            </div>
          )}

          <div className="flex items-center gap-4">
            <Button type="submit" icon={Play} loading={running} disabled={running || !env || !module || !actionAllowed}>
              {running ? `Running ${action}…` : `Run ${action}`}
            </Button>
            {!actionAllowed && env && (
              <p className="text-xs text-red-400 flex items-center gap-1.5">
                <AlertTriangle size={12} />
                Role <Badge status={role} className="!inline-flex" /> cannot run {action} on {env}
              </p>
            )}
          </div>
        </form>
      </Card>

      <Modal
        open={showConfirm}
        onClose={() => setShowConfirm(false)}
        title="Confirm production action"
        variant="danger"
        footer={
          <ModalActions
            onCancel={() => setShowConfirm(false)}
            onConfirm={() => executeRun(true)}
            confirmLabel={`Confirm ${action}`}
            confirmVariant="danger"
            loading={running}
          />
        }
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="text-red-400 shrink-0 mt-0.5" size={20} />
          <div className="space-y-2">
            <p className="text-sm text-[var(--text-secondary)]">
              You are about to run <Badge status={action} className="!inline-flex mx-1" /> on{" "}
              <span className="font-mono text-red-300">{env}/{module}</span>.
            </p>
            <p className="text-xs text-[var(--text-muted)]">
              This action requires admin privileges and explicit confirmation. Changes will affect live infrastructure.
            </p>
          </div>
        </div>
      </Modal>

      {showPipeline && (
        <div className="space-y-4">
          {result && (
            <div
              className={`flex items-center gap-2 px-4 py-3 rounded-lg border text-sm ${
                deploySucceeded
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                  : "border-red-500/30 bg-red-500/10 text-red-300"
              }`}
            >
              {deploySucceeded ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
              {deploySucceeded ? "Deployment succeeded" : "Deployment failed"}
              {result.exit_code != null && (
                <span className="text-xs opacity-70 ml-auto font-mono">exit {result.exit_code}</span>
              )}
            </div>
          )}

          <Card className="!p-5">
            <PipelineStages stages={stages} running={running} />
          </Card>

          <Terminal
            ref={logRef}
            title="pipeline output"
            subtitle={`${env}/${module} · ${action}`}
            status={terminalStatus}
            logs={logs}
            running={running}
            maxHeight="24rem"
          />
        </div>
      )}
    </div>
  );
}
