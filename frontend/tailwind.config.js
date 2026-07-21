/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b1220",
        panel: "#121a2b",
        line: "#243047",
        mist: "#9db0c9",
        signal: "#3dd6c6",
        alert: "#f07178",
        warn: "#e6c07b",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
        body: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
      },
      backgroundImage: {
        grid: "linear-gradient(to right, rgba(36,48,71,0.45) 1px, transparent 1px), linear-gradient(to bottom, rgba(36,48,71,0.45) 1px, transparent 1px)",
        aurora:
          "radial-gradient(ellipse 80% 50% at 20% -10%, rgba(61,214,198,0.18), transparent), radial-gradient(ellipse 60% 40% at 90% 10%, rgba(240,113,120,0.12), transparent)",
      },
      backgroundSize: {
        grid: "48px 48px",
      },
      keyframes: {
        rise: {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        rise: "rise 0.55s ease-out both",
        pulseSoft: "pulseSoft 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
