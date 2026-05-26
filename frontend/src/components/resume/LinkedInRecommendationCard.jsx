import { Linkedin, ExternalLink } from "lucide-react";

export function LinkedInRecommendationCard({ rec }) {
  const authorLine = [rec.title, rec.company].filter(Boolean).join(" · ");

  return (
    <figure className="linkedin-rec-card panel-card p-5 h-full flex flex-col">
      <blockquote className="text-sm text-gray-300/95 leading-[1.65] flex-1 italic">
        &ldquo;{rec.text}&rdquo;
      </blockquote>

      <figcaption className="mt-4 pt-3.5 border-t border-sre-border/55">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-white flex items-center gap-2">
              {rec.emoji && (
                <span className="text-base leading-none shrink-0" aria-hidden="true">
                  {rec.emoji}
                </span>
              )}
              {rec.linkedinUrl ? (
                <a
                  href={rec.linkedinUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-teal-300 transition-colors truncate"
                >
                  {rec.author}
                </a>
              ) : (
                rec.author
              )}
            </p>
            {authorLine && (
              <p className="text-xs text-indigo-300/95 mt-0.5 leading-snug">{authorLine}</p>
            )}
            {rec.relationship && (
              <p className="text-[10px] text-gray-500 mt-1.5 leading-relaxed">{rec.relationship}</p>
            )}
          </div>
          {rec.linkedinUrl && (
            <a
              href={rec.linkedinUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 p-1.5 rounded-lg text-blue-400/70 hover:text-blue-300 hover:bg-blue-950/30 transition-colors"
              aria-label={`${rec.author} on LinkedIn`}
              title="View on LinkedIn"
            >
              <Linkedin size={15} />
            </a>
          )}
        </div>
      </figcaption>
    </figure>
  );
}

export function LinkedInRecommendationsSection({ recommendations, linkedin }) {
  if (!recommendations?.length) return null;

  return (
    <section className="linkedin-recommendations">
      <div className="flex flex-wrap items-end justify-between gap-3 mb-4">
        <div>
          <h2
            id="recommendations"
            className="text-[11px] font-bold text-gray-500 uppercase tracking-[0.15em] scroll-mt-24"
          >
            LinkedIn recommendations
          </h2>
          <p className="text-xs text-gray-500 mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="inline-flex items-center gap-1.5 text-blue-400/90">
              <Linkedin size={12} />
              Colleague endorsements
            </span>
            {linkedin?.connections && (
              <>
                <span className="text-gray-600">·</span>
                <span>{linkedin.connections} connections</span>
              </>
            )}
          </p>
        </div>
        {linkedin?.url && (
          <a
            href={linkedin.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-blue-400/90 hover:text-blue-300 px-2.5 py-1.5 rounded-lg border border-blue-500/20 bg-blue-950/20 hover:bg-blue-950/35 transition-colors resume-no-print"
          >
            View on LinkedIn
            <ExternalLink size={11} />
          </a>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {recommendations.map((rec) => (
          <LinkedInRecommendationCard key={rec.author} rec={rec} />
        ))}
      </div>
    </section>
  );
}
