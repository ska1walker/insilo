import type { Config } from "tailwindcss";

export default {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        white: "#FFFFFF",
        black: "#0A0A0A",
        gold: {
          DEFAULT: "#C9A961",
          light: "#E6D4A3",
          deep: "#9C8147",
          faint: "#F5EDD9",
        },
        surface: {
          soft: "#FAFAF7",
          warm: "#F5F3EE",
        },
        border: {
          subtle: "#E8E6E1",
          strong: "#D4D1CA",
        },
        text: {
          primary: "#0A0A0A",
          secondary: "#4A4842",
          meta: "#737065",
          disabled: "#A8A599",
        },
        recording: "#C84A3F",
        success: "#4A7C59",
        warning: "#B8893C",
        error: "#A33A2F",
      },
      fontFamily: {
        display: ['"Lexend Deca"', "sans-serif"],
        body: ['"Inter"', "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      spacing: {
        "0.5": "0.125rem",
        "1": "0.25rem",
        "2": "0.5rem",
        "3": "0.75rem",
        "4": "1rem",
        "6": "1.5rem",
        "8": "2rem",
        "12": "3rem",
        "16": "4rem",
        "24": "6rem",
        "32": "8rem",
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
        full: "9999px",
      },
      boxShadow: {
        xs: "0 1px 2px rgba(10, 10, 10, 0.04)",
        sm: "0 2px 4px rgba(10, 10, 10, 0.05)",
        md: "0 4px 12px rgba(10, 10, 10, 0.06)",
        lg: "0 8px 24px rgba(10, 10, 10, 0.08)",
        gold: "0 4px 16px rgba(201, 169, 97, 0.15)",
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      animation: {
        "pulse-line": "pulse-line 2.4s ease-in-out infinite",
        "pulse-gold": "pulse-gold 2s ease-in-out infinite",
      },
      keyframes: {
        "pulse-line": {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "1" },
        },
        "pulse-gold": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(201, 169, 97, 0.4)" },
          "50%": { boxShadow: "0 0 0 16px rgba(201, 169, 97, 0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
