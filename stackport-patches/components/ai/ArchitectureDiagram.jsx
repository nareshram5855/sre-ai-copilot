/**
 * Renders an architecture diagram.
 *
 * Props:
 *   svgDef          — raw SVG string from the Python aws_diagram module (preferred)
 *   mermaidDef      — Mermaid diagram string (fallback when svgDef absent)
 *   architectureName — used for the filename when downloading
 */
import { useEffect, useState } from "react";
import { ZoomIn, ZoomOut, Download, Maximize2, Minimize2 } from "lucide-react";

// ── Mermaid lazy-loader ───────────────────────────────────────────────────────

let _mermaidReady = false;
let _mermaid = null;

async function getMermaid() {
  if (_mermaidReady) return _mermaid;
  const m = await import("mermaid");
  _mermaid = m.default;
  _mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    themeVariables: {
      background: "#0a0a0c",
      primaryColor: "#1e3a5f",
      primaryTextColor: "#93c5fd",
      lineColor: "#475569",
      secondaryColor: "#14532d",
      tertiaryColor: "#3b0764",
      edgeLabelBackground: "#1e293b",
      clusterBkg: "#0f172a",
      clusterBorder: "#334155",
      fontFamily: "JetBrains Mono, ui-monospace, monospace",
      fontSize: "13px",
    },
    flowchart: { curve: "basis", padding: 20, htmlLabels: true },
    securityLevel: "loose",
  });
  _mermaidReady = true;
  return _mermaid;
}

// ── Parse SVG viewBox for accurate fit-zoom calculation ───────────────────────

function getSvgDims(svgStr) {
  const m = (svgStr || "").match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  return m ? { w: parseFloat(m[1]), h: parseFloat(m[2]) } : { w: 900, h: 700 };
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ArchitectureDiagram({ svgDef, mermaidDef, architectureName }) {
  const [renderedSvg, setRenderedSvg] = useState("");
  const [error, setError]             = useState("");
  const [zoom, setZoom]               = useState(1);
  const [fitZoom, setFitZoom]         = useState(1);
  const [fullscreen, setFullscreen]   = useState(false);

  // Prefer svgDef; fall back to mermaid rendering
  useEffect(() => {
    if (svgDef) {
      setRenderedSvg(svgDef);
      setError("");
      return;
    }
    if (!mermaidDef) return;
    let cancelled = false;
    (async () => {
      try {
        const m  = await getMermaid();
        const id = `mermaid-${Date.now()}`;
        const { svg: out } = await m.render(id, mermaidDef);
        if (!cancelled) { setRenderedSvg(out); setError(""); }
      } catch (e) {
        if (!cancelled) setError(e.message || "Diagram render failed");
      }
    })();
    return () => { cancelled = true; };
  }, [svgDef, mermaidDef]);

  // Escape key closes fullscreen
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e) => { if (e.key === "Escape") exitFullscreen(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  function enterFullscreen() {
    const svg = renderedSvg || svgDef || "";
    const { w, h } = getSvgDims(svg);
    // 64px horizontal padding + 52px toolbar + 48px breathing room
    const fz = Math.min(
      (window.innerWidth  - 64) / w,
      (window.innerHeight - 100) / h,
      1   // never scale UP past 100% on entry
    );
    const clamped = Math.max(fz, 0.2);
    setFitZoom(clamped);
    setZoom(clamped);
    setFullscreen(true);
  }

  function exitFullscreen() {
    setFullscreen(false);
    setZoom(1);
  }

  function download() {
    const content = svgDef || renderedSvg;
    const blob = new Blob([content], { type: "image/svg+xml" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `${architectureName || "architecture"}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!svgDef && !mermaidDef) return null;

  // ── Shared toolbar (used in both inline and fullscreen) ────────────────────
  const toolbar = (
    <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] shrink-0">
      <div className="flex items-center gap-1.5">
        <div className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
        <div className="w-2.5 h-2.5 rounded-full bg-amber-500/60" />
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/60" />
        <span className="ml-3 text-[11px] font-mono text-[var(--text-muted)]">
          {architectureName || "architecture"}.svg
        </span>
        {svgDef && (
          <span className="ml-2 text-[9px] font-semibold px-1.5 py-0.5 rounded-full bg-[#FF9900]/10 text-[#FF9900] border border-[#FF9900]/20 uppercase tracking-wider">
            AWS
          </span>
        )}
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => setZoom(z => Math.max(0.2, +(z - 0.1).toFixed(2)))}
          className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-faint)] hover:text-[var(--text-secondary)] transition-colors"
          title="Zoom out">
          <ZoomOut size={13} />
        </button>

        {/* Clicking the % label resets to fit-zoom (fullscreen) or 100% (inline) */}
        <button
          onClick={() => setZoom(fullscreen ? fitZoom : 1)}
          className="text-[10px] text-[var(--text-faint)] w-10 text-center font-mono hover:text-[var(--text-secondary)] transition-colors"
          title="Reset zoom">
          {Math.round(zoom * 100)}%
        </button>

        <button
          onClick={() => setZoom(z => Math.min(3, +(z + 0.1).toFixed(2)))}
          className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-faint)] hover:text-[var(--text-secondary)] transition-colors"
          title="Zoom in">
          <ZoomIn size={13} />
        </button>

        <button
          onClick={download}
          className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-faint)] hover:text-[var(--text-secondary)] transition-colors"
          title="Download SVG">
          <Download size={13} />
        </button>

        {fullscreen ? (
          <button
            onClick={exitFullscreen}
            className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-faint)] hover:text-[var(--text-secondary)] transition-colors"
            title="Exit fullscreen (Esc)">
            <Minimize2 size={13} />
          </button>
        ) : (
          <button
            onClick={enterFullscreen}
            className="p-1.5 rounded hover:bg-[var(--bg-hover)] text-[var(--text-faint)] hover:text-[var(--text-secondary)] transition-colors"
            title="Fullscreen — auto-fits diagram">
            <Maximize2 size={13} />
          </button>
        )}
      </div>
    </div>
  );

  // ── Diagram canvas ─────────────────────────────────────────────────────────
  const canvas = (
    <div
      className="overflow-auto bg-[#0d1525] flex-1"
      style={fullscreen ? { minHeight: 0 } : { minHeight: "300px", maxHeight: "540px" }}
    >
      {error ? (
        <div className="p-4 text-xs text-red-400 font-mono">{error}</div>
      ) : renderedSvg ? (
        <div
          className="p-4 flex items-start justify-center min-h-full"
          style={{
            transform:       `scale(${zoom})`,
            transformOrigin: "top center",
            transition:      "transform 0.15s ease",
          }}
          dangerouslySetInnerHTML={{ __html: renderedSvg }}
        />
      ) : (
        <div className="flex items-center justify-center h-40 text-[var(--text-faint)] text-sm">
          <span className="animate-pulse">Rendering diagram…</span>
        </div>
      )}
    </div>
  );

  // ── Fullscreen: single fixed overlay, no double-render ────────────────────
  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-[200] bg-[#0a0a0c] flex flex-col">
        {toolbar}
        {canvas}
      </div>
    );
  }

  // ── Inline card ────────────────────────────────────────────────────────────
  return (
    <div className="rounded-xl border border-[var(--border-subtle)] overflow-hidden">
      {toolbar}
      {canvas}
    </div>
  );
}
