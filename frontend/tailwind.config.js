/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        sre: {
          bg: "#0f1117",
          surface: "#1a1d27",
          border: "#2d3148",
          accent: "#6366f1",
        },
      },
    },
  },
  plugins: [],
};
