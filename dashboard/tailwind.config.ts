import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#23312f",
        paper: "#f5f0e7",
        line: "#e3d9c9",
        moss: "#2f7a62",
        signal: "#a33b42",
        steel: "#44758f",
      },
    },
  },
  plugins: [],
};

export default config;
