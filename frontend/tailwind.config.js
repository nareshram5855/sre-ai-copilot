/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        sre: {
          bg: "#0f1117",
          surface: "#1a1d27",
          border: "#2d3148",
          accent: "#6366f1",
          success: "#22c55e",
          warning: "#eab308",
          danger: "#ef4444",
        },
        recruiter: {
          navy: "#0c1222",
          slate: "#131a2e",
          teal: "#2dd4bf",
          violet: "#a78bfa",
          amber: "#fbbf24",
        },
      },
      animation: {
        "recruiter-shimmer": "recruiter-shimmer 2.4s ease-in-out infinite",
        "recruiter-glow": "recruiter-glow 2s ease-in-out infinite",
        "recruiter-success": "recruiter-success 1.2s ease-out forwards",
        "recruiter-chip-pop": "recruiter-chip-pop 0.35s ease-out",
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.04) inset",
      },
    },
  },
  plugins: [],
};
