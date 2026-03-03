import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: "#0a0a0f",
          50: "#0f0f18",
          100: "#141420",
          200: "#1a1a2e",
          300: "#22223a",
        },
        accent: {
          green: "#00f5a0",
          red: "#ff4757",
          blue: "#00d2ff",
          yellow: "#ffd93d",
          purple: "#a855f7",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
