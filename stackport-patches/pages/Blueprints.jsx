import { useEffect, useMemo, useState } from "react";
import {
  Boxes, Server, Database, Cloud, Layers, Globe, DollarSign,
  Shield, ChevronRight, X, Copy, CheckCheck,
} from "lucide-react";
import { fetchJSON, postJSONBody } from "../utils/api.js";
import PageHeader from "../components/ui/PageHeader.jsx";
import { Card } from "../components/ui/Card.jsx";
import Badge from "../components/ui/Badge.jsx";
import EmptyState from "../components/ui/EmptyState.jsx";
import { SearchInput } from "../components/ui/Input.jsx";
import Input from "../components/ui/Input.jsx";
import Select from "../components/ui/Select.jsx";
import Button from "../components/ui/Button.jsx";
import Modal from "../components/ui/Modal.jsx";
import Spinner from "../components/ui/Skeleton.jsx";
import { useAI } from "../context/AIContext.jsx";

const CATEGORY_ICONS = {
  compute: Server,
  data: Database,
  serverless: Cloud,
  static: Globe,
  default: Layers,
};

function getCategoryIcon(category) {
  const key = (category ?? "").toLowerCase();
  for (const [k, Icon] of Object.entries(CATEGORY_ICONS)) {
    if (key.includes(k)) return Icon;
  }
  return CATEGORY_ICONS.default;
}

// ── Blueprint catalog card ─────────────────────────────────────────────────

function BlueprintCard({ bp, onDeploy }) {
  const Icon = getCategoryIcon(bp.category);
  const costRange = bp.estimated_cost_min && bp.estimated_cost_max
    ? `$${bp.estimated_cost_min}–$${bp.estimated_cost_max}/mo`
    : null;

  return (
    <Card hover padding={false} className="overflow-hidden flex flex-col">
      <div className="px-5 pt-5 pb-4 flex-1">
        <div className="flex items-start gap-3 mb-3">
          <div className="p-2.5 rounded-xl bg-accent-muted border border-accent/20 shrink-0">
            <Icon size={18} className="text-accent" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-[var(--text-primary)] leading-tight">{bp.name}</p>
            <p className="text-[11px] text-[var(--text-muted)] mt-0.5 capitalize">{bp.category}</p>
          </div>
          {costRange && (
            <div className="flex items-center gap-1 text-[11px] text-emerald-400 shrink-0">
              <DollarSign size={11} />
              <span className="font-medium">{costRange}</span>
            </div>
          )}
        </div>

        <p className="text-xs text-[var(--text-muted)] leading-relaxed mb-3">{bp.description}</p>

        {/* Tags */}
        {bp.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {bp.tags.map((t) => (
              <span key={t} className="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-muted)] text-[var(--text-faint)] border border-[var(--border-subtle)]">
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Compliance */}
        {bp.compliance?.length > 0 && (
          <div className="flex items-center gap-1.5">
            <Shield size={11} className="text-[var(--text-faint)]" />
            {bp.compliance.map((c) => (
              <Badge key={c} variant="info" className="text-[9px]">{c}</Badge>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-5 py-3 border-t border-[var(--border-subtle)] flex items-center justify-between bg-[var(--bg-elevated)]/50">
        <span className="text-[11px] text-[var(--text-faint)]">
          {bp.module_count} module{bp.module_count !== 1 ? "s" : ""}
        </span>
        <Button size="sm" variant="outline" icon={ChevronRight} onClick={() => onDeploy(bp)}>
          Deploy
        </Button>
      </div>
    </Card>
  );
}

// ── Deploy wizard modal ────────────────────────────────────────────────────

const ENV_OPTIONS = [
  { value: "dev", label: "dev" },
  { value: "staging", label: "staging" },
  { value: "prod", label: "prod" },
];

const REGION_OPTIONS = [
  { value: "us-east-1", label: "us-east-1 (N. Virginia)" },
  { value: "us-west-2", label: "us-west-2 (Oregon)" },
  { value: "eu-west-1", label: "eu-west-1 (Ireland)" },
  { value: "ap-southeast-1", label: "ap-southeast-1 (Singapore)" },
];

function DeployWizard({ bp, onClose }) {
  const [step, setStep] = useState(0); // 0 = params, 1 = preview
  const [params, setParams] = useState({ env: "dev", region: "us-east-1" });
  const [rendered, setRendered] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(null);
  const [errors, setErrors] = useState({});

  function setParam(key, val) {
    setParams((p) => ({ ...p, [key]: val }));
    setErrors((e) => { const n = { ...e }; delete n[key]; return n; });
  }

  function validate() {
    const errs = {};
    for (const p of bp.params ?? []) {
      if (p.required && !params[p.name]?.trim()) {
        errs[p.name] = "Required";
      }
    }
    return errs;
  }

  async function handlePreview() {
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setLoading(true);
    try {
      const result = await postJSONBody(`/blueprints/${bp.id}/render`, { params });
      setRendered(result);
      setStep(1);
    } catch (e) {
      setErrors({ _global: e.message ?? "Render failed" });
    } finally {
      setLoading(false);
    }
  }

  function copyFile(content, idx) {
    navigator.clipboard.writeText(content);
    setCopied(idx);
    setTimeout(() => setCopied(null), 2000);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={step === 0 ? `Deploy — ${bp.name}` : `Preview — ${rendered?.blueprint_name}`}
      size="xl"
      footer={
        step === 0 ? (
          <>
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
            <Button loading={loading} onClick={handlePreview}>Generate files</Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={() => setStep(0)}>Back</Button>
            <Button variant="secondary" onClick={onClose}>Done</Button>
          </>
        )
      }
    >
      {step === 0 ? (
        <div className="space-y-4">
          <p className="text-xs text-[var(--text-muted)] leading-relaxed">{bp.description}</p>

          {errors._global && (
            <div className="px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
              {errors._global}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Select
              label="Environment"
              value={params.env}
              onChange={(v) => setParam("env", v)}
              options={ENV_OPTIONS}
            />
            <Select
              label="Region"
              value={params.region}
              onChange={(v) => setParam("region", v)}
              options={REGION_OPTIONS}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {(bp.params ?? []).map((p) => (
              <Input
                key={p.name}
                label={p.label ?? p.name}
                placeholder={p.placeholder ?? ""}
                value={params[p.name] ?? ""}
                onChange={(e) => setParam(p.name, e.target.value)}
                error={errors[p.name]}
                hint={p.description}
              />
            ))}
          </div>

          {/* Cost estimate */}
          {bp.estimated_cost_min && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-emerald-500/5 border border-emerald-500/15 text-xs text-emerald-400">
              <DollarSign size={13} />
              <span>Estimated cost: <strong>${bp.estimated_cost_min}–${bp.estimated_cost_max}/mo</strong></span>
              {bp.cost_note && <span className="text-[var(--text-faint)] ml-1">— {bp.cost_note}</span>}
            </div>
          )}

          {/* Module list */}
          {bp.modules?.length > 0 && (
            <div>
              <p className="text-[11px] font-medium text-[var(--text-muted)] mb-2 uppercase tracking-wide">
                Modules included
              </p>
              <div className="flex flex-col gap-1">
                {bp.modules.map((m) => (
                  <div key={m} className="flex items-center gap-2 text-xs font-mono text-[var(--text-faint)]">
                    <Boxes size={11} className="text-accent/60 shrink-0" />
                    {m}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-[var(--text-muted)]">
            Generated <strong className="text-[var(--text-primary)]">{rendered.files.length}</strong> files for{" "}
            <strong className="text-[var(--text-primary)]">{rendered.team}/{rendered.app}</strong> ({rendered.env}).
            Copy each file into your team&apos;s Terragrunt repo.
          </p>

          {rendered.files.map((f, idx) => (
            <div key={idx} className="rounded-lg border border-[var(--border-subtle)] overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg-muted)] border-b border-[var(--border-subtle)]">
                <span className="text-[11px] font-mono text-accent">{f.path}</span>
                {f.module && (
                  <span className="text-[10px] text-[var(--text-faint)]">{f.module}</span>
                )}
                <button
                  onClick={() => copyFile(f.content, idx)}
                  className="flex items-center gap-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors ml-3"
                >
                  {copied === idx ? <CheckCheck size={13} className="text-emerald-400" /> : <Copy size={13} />}
                  {copied === idx ? "Copied" : "Copy"}
                </button>
              </div>
              <pre className="px-4 py-3 text-[11px] font-mono text-[var(--text-secondary)] overflow-x-auto whitespace-pre leading-relaxed max-h-48 overflow-y-auto">
                {f.content}
              </pre>
            </div>
          ))}
        </div>
      )}
    </Modal>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function Blueprints() {
  const [blueprints, setBlueprints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [deploying, setDeploying] = useState(null);
  const { setPageContext } = useAI();

  useEffect(() => {
    setPageContext({ page: "blueprints", hint: "Browsing stack blueprint catalog" });
  }, []);

  useEffect(() => {
    fetchJSON("/blueprints")
      .then(setBlueprints)
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(
    () => [...new Set(blueprints.map((b) => b.category))].sort(),
    [blueprints]
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return blueprints.filter((b) => {
      const matchSearch = !q
        || b.name.toLowerCase().includes(q)
        || b.description.toLowerCase().includes(q)
        || b.tags?.some((t) => t.toLowerCase().includes(q));
      const matchCat = !categoryFilter || b.category === categoryFilter;
      return matchSearch && matchCat;
    });
  }, [blueprints, search, categoryFilter]);

  if (loading) {
    return (
      <div className="p-6 lg:p-8 flex items-center justify-center min-h-[40vh]">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 animate-fade-in">
      <PageHeader
        title="Stack Blueprints"
        description={`${blueprints.length} pre-built, production-ready stacks. Fill in your team, app, and env — get Terragrunt files instantly.`}
      />

      {/* Filter bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <SearchInput
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search blueprints…"
          className="flex-1"
        />
        <Select
          value={categoryFilter}
          onChange={setCategoryFilter}
          placeholder="All categories"
          options={[
            { value: "", label: "All categories" },
            ...categories.map((c) => ({ value: c, label: c })),
          ]}
          className="min-w-[160px]"
        />
      </div>

      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon={Boxes}
            title="No blueprints found"
            description="Try adjusting your search or category filter."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((bp) => (
            <BlueprintCard key={bp.id} bp={bp} onDeploy={setDeploying} />
          ))}
        </div>
      )}

      {deploying && (
        <DeployWizard bp={deploying} onClose={() => setDeploying(null)} />
      )}
    </div>
  );
}
