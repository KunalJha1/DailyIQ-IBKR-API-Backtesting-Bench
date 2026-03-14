import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0D1117",
        panel: "#161B22",
        hover: "#1C2128",
        "border-default": "#21262D",
        "border-active": "#1A56DB",
        "text-primary": "#E6EDF3",
        "text-secondary": "#8B949E",
        "text-muted": "#484F58",
        green: "#00C853",
        red: "#FF3D71",
        amber: "#F59E0B",
        blue: "#1A56DB",
        purple: "#8B5CF6",
        navy: "#0f172a",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "monospace"],
        sans: ["Geist Sans", "Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        input: "4px",
        btn: "6px",
        panel: "0px",
      },
    },
  },
  plugins: [],
} satisfies Config;
