import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#f5f4ed",
        ink: "#1f2421",
        accent: "#165b33",
        accentSoft: "#d6ecd9",
        warn: "#b84b2d"
      },
      fontFamily: {
        heading: ["Space Grotesk", "ui-sans-serif", "sans-serif"],
        body: ["IBM Plex Sans", "ui-sans-serif", "sans-serif"]
      },
      boxShadow: {
        panel: "0 10px 40px rgba(12, 52, 30, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
