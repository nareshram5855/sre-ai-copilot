import { useEffect, useId, useRef, useState } from "react";

let mermaidPromise;

function loadMermaid() {
  if (!mermaidPromise) {
    mermaidPromise = import("mermaid").then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        securityLevel: "strict",
        themeVariables: {
          primaryColor: "#6366f1",
          primaryTextColor: "#e5e7eb",
          primaryBorderColor: "#4f46e5",
          lineColor: "#6366f1",
          secondaryColor: "#1a1d27",
          tertiaryColor: "#0f1117",
          background: "#1a1d27",
          mainBkg: "#1a1d27",
          nodeBorder: "#2d3148",
          clusterBkg: "#0f1117",
          titleColor: "#f3f4f6",
          edgeLabelBackground: "#1a1d27",
          fontFamily: "Inter, system-ui, sans-serif",
        },
        flowchart: { curve: "basis", padding: 16 },
        sequence: { actorMargin: 48, messageMargin: 40 },
      });
      return mermaid;
    });
  }
  return mermaidPromise;
}

export function MermaidDiagram({ chart, title, caption }) {
  const containerRef = useRef(null);
  const renderId = useId().replace(/:/g, "");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      if (!containerRef.current || !chart?.trim()) return;
      setLoading(true);
      setError(null);

      try {
        const mermaid = await loadMermaid();
        if (cancelled) return;

        const { svg } = await mermaid.render(`mmd-${renderId}`, chart.trim());
        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = svg;
        const svgEl = containerRef.current.querySelector("svg");
        if (svgEl) {
          svgEl.style.maxWidth = "100%";
          svgEl.style.height = "auto";
          svgEl.removeAttribute("height");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err?.message || "Failed to render diagram");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    render();
    return () => {
      cancelled = true;
    };
  }, [chart, renderId]);

  return (
    <figure className="panel-card overflow-hidden">
      {title && (
        <div className="px-4 py-3 border-b border-sre-border flex items-center justify-between gap-2">
          <h4 className="text-sm font-semibold text-white">{title}</h4>
          {loading && (
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Rendering…</span>
          )}
        </div>
      )}
      <div
        className="p-4 overflow-x-auto bg-sre-bg/40 min-h-[120px] flex items-center justify-center arch-mermaid-canvas"
      >
        {error ? (
          <pre className="text-xs text-red-400 whitespace-pre-wrap font-mono p-3 w-full">{error}</pre>
        ) : (
          <div ref={containerRef} className="w-full [&_svg]:mx-auto" aria-label={title || "Architecture diagram"} />
        )}
      </div>
      {caption && (
        <figcaption className="px-4 py-2.5 border-t border-sre-border text-xs text-gray-500 leading-relaxed">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
