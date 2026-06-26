import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchJSON } from "../utils/api.js";
import { useAuth } from "../context/AuthContext.jsx";
import PageHeader from "../components/ui/PageHeader.jsx";
import { Card } from "../components/ui/Card.jsx";
import Badge from "../components/ui/Badge.jsx";
import EmptyState from "../components/ui/EmptyState.jsx";
import Spinner from "../components/ui/Skeleton.jsx";
import StepIndicator from "../components/ui/StepIndicator.jsx";
import {
  GitBranch, Container, Rocket, Server, Cloud, Box, ExternalLink, BookOpen,
} from "lucide-react";

const PLATFORM_WORKFLOWS_URL =
  "https://github.com/nareshram5855/infra-platform/tree/admin/org-bootstrap/.github/workflows";
const PLATFORM_REPO = "nareshram5855/infra-platform";
const PLATFORM_BRANCH = "admin/org-bootstrap";

const TARGET_ICONS = {
  eks: Server,
  ecs: Container,
  lambda: Cloud,
  s3: Box,
};

export default function Pipelines() {
  const { user } = useAuth();
  const [pipelines, setPipelines] = useState([]);
  const [apps, setApps] = useState([]);
  const [overview, setOverview] = useState(null);
  const [deployTargets, setDeployTargets] = useState([]);
  const [sdlcSteps, setSdlcSteps] = useState([]);
  const [loading, setLoading] = useState(true);

  const isOperator = user?.role === "operator" || user?.role === "admin";

  useEffect(() => {
    Promise.all([
      fetchJSON("/pipelines"),
      fetchJSON("/pipelines/apps"),
      fetchJSON("/pipelines/overview"),
    ])
      .then(([p, a, o]) => {
        setPipelines(p.pipelines ?? []);
        setDeployTargets(p.deploy_targets ?? []);
        setSdlcSteps(p.sdlc_steps ?? []);
        setApps(a.apps ?? []);
        setOverview(o);
      })
      .finally(() => setLoading(false));
  }, []);

  const grouped = useMemo(() => {
    return pipelines.reduce((acc, w) => {
      (acc[w.category] = acc[w.category] ?? []).push(w);
      return acc;
    }, {});
  }, [pipelines]);

  if (loading) {
    return (
      <div className="p-6 lg:p-8 flex items-center justify-center min-h-[40vh]">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-8 animate-fade-in">
      <PageHeader
        title="Application CI/CD"
        description="Build, test, scan, and deploy applications alongside IaC — one platform for the full SDLC."
        action={
          <Link
            to="/docs#app-cicd"
            className="inline-flex items-center gap-2 text-sm text-accent hover:underline"
          >
            <BookOpen className="w-4 h-4" />
            Setup guide
          </Link>
        }
      />

      {/* SDLC flow */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">SDLC flow</h2>
          <a
            href={PLATFORM_WORKFLOWS_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-[var(--text-muted)] hover:text-accent transition-colors flex items-center gap-1"
          >
            View workflow templates
            <svg viewBox="0 0 24 24" className="w-3 h-3 fill-none stroke-current" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
          </a>
        </div>
        <StepIndicator
          steps={sdlcSteps.map((s) => ({ id: s.id, label: s.label, description: s.description }))}
          currentStep={sdlcSteps.length}
        />
      </Card>

      {/* Overview stats */}
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "IaC modules", value: overview.iac_module_count },
            { label: "Pipeline templates", value: overview.pipeline_template_count },
            { label: "Sample apps", value: overview.sample_app_count },
            { label: "Deploy targets", value: overview.deploy_targets?.length ?? 4 },
          ].map(({ label, value }) => (
            <Card key={label} className="p-4">
              <p className="text-xs text-[var(--text-muted)] uppercase tracking-wide">{label}</p>
              <p className="text-2xl font-semibold text-[var(--text-primary)] mt-1">{value}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Deploy targets */}
      <section>
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-3">Deploy targets</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {deployTargets.map((t) => {
            const Icon = TARGET_ICONS[t.id] ?? Rocket;
            return (
              <Card key={t.id} className="p-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-accent-muted">
                    <Icon className="w-4 h-4 text-accent" />
                  </div>
                  <div>
                    <p className="font-medium text-[var(--text-primary)]">{t.name}</p>
                    <p className="text-xs text-[var(--text-muted)] mt-1">{t.description}</p>
                    <Badge variant="outline" className="mt-2">{t.id}</Badge>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Workflows */}
      <section>
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-3">Workflow templates</h2>
        {pipelines.length === 0 ? (
          <EmptyState title="No workflows found" description="Add workflows under .github/workflows/" />
        ) : (
          <div className="space-y-6">
            {Object.entries(grouped).map(([category, items]) => (
              <div key={category}>
                <h3 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-faint)] mb-2">
                  {category}
                </h3>
                <div className="grid gap-3">
                  {items.map((w) => {
                    const filename = w.path.replace(".github/workflows/", "");
                    const fileUrl = `https://github.com/${PLATFORM_REPO}/blob/${PLATFORM_BRANCH}/${w.path}`;
                    const actionsUrl = `https://github.com/${PLATFORM_REPO}/actions/workflows/${filename}`;
                    return (
                      <Card key={w.path} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <GitBranch className="w-4 h-4 text-accent shrink-0" />
                            <span className="font-medium text-[var(--text-primary)]">{w.name}</span>
                            {w.callable && <Badge variant="accent">callable</Badge>}
                          </div>
                          <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">{w.path}</p>
                          {w.triggers?.length > 0 && (
                            <p className="text-xs text-[var(--text-faint)] mt-1">
                              Triggers: {w.triggers.join(", ")}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <a
                            href={fileUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-[var(--text-muted)] hover:text-accent hover:underline"
                          >
                            View YAML <ExternalLink className="w-3 h-3" />
                          </a>
                          <a
                            href={actionsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                          >
                            GitHub Actions <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      </Card>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Sample apps */}
      <section>
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-3">Sample applications</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {apps.map((app) => (
            <Card key={app.id} className="p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-[var(--text-primary)]">{app.name}</span>
                <Badge>{app.language}</Badge>
              </div>
              {app.description && (
                <p className="text-xs text-[var(--text-muted)] mb-2">{app.description}</p>
              )}
              <p className="text-xs font-mono text-[var(--text-faint)]">{app.path}</p>
              {app.has_dockerfile && (
                <Badge variant="outline" className="mt-2">Dockerfile</Badge>
              )}
            </Card>
          ))}
        </div>
      </section>

      {/* Operator info */}
      <Card className="p-6 border-accent/20 bg-accent-muted/30">
        <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-2">
          {isOperator ? "Trigger deployments" : "Viewing pipelines"}
        </h2>
        {isOperator ? (
          <div className="text-sm text-[var(--text-muted)] space-y-2">
            <p>
              Application deployments are triggered via GitHub Actions — use workflow dispatch on
              <code className="mx-1 px-1 rounded bg-[var(--bg-hover)]">sdlc-pipeline.yml</code>
              or language-specific app workflows under Actions → Workflows.
            </p>
            <p>
              Promotion path: <strong>dev</strong> (auto on merge) → <strong>staging</strong> → <strong>prod</strong>
              with GitHub Environment approval gates.
            </p>
            <p>
              <a
                href={`https://github.com/${PLATFORM_REPO}/tree/${PLATFORM_BRANCH}/.github/workflows`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline inline-flex items-center gap-1"
              >
                Browse all workflow files on GitHub <ExternalLink className="w-3 h-3" />
              </a>
            </p>
          </div>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">
            You have read-only access to pipeline templates and sample apps. Contact an operator to trigger deployments.
          </p>
        )}
      </Card>
    </div>
  );
}
