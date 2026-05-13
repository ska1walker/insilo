import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{ts,tsx,mdx}",
    "./app/**/*.{ts,tsx,mdx}",
    "./components/**/*.{ts,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primärfarben — sparsam nutzen
        white: "#FFFFFF",
        black: "#0A0A0A",
        gold: {
          DEFAULT: "#C9A961",
          light: "#E6D4A3",
          deep: "#9C8147",
          faint: "#F5EDD9",
        },

        // Flächen
        surface: {
          soft: "#FAFAF7",
          warm: "#F5F3EE",
        },

        // Borders
        border: {
          subtle: "#E8E6E1",
          strong: "#D4D1CA",
        },

        // Text-Hierarchie
        text: {
          primary: "#0A0A0A",
          secondary: "#4A4842",
          meta: "#737065",
          disabled: "#A8A599",
        },

        // Status
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

      fontSize: {
        // Type-Skala aus docs/DESIGN.md
        "h1": ["clamp(2.5rem, 5vw, 3.5rem)", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        "h2": ["2rem", { lineHeight: "1.2", letterSpacing: "-0.015em" }],
        "h3": ["1.5rem", { lineHeight: "1.3", letterSpacing: "-0.01em" }],
        "h4": ["1.125rem", { lineHeight: "1.4" }],
        "body-lg": ["1.0625rem", { lineHeight: "1.6" }],
        "body": ["1rem", { lineHeight: "1.6" }],
        "body-sm": ["0.875rem", { lineHeight: "1.5" }],
        "meta": ["0.8125rem", { lineHeight: "1.4", letterSpacing: "0.01em" }],
        "label": ["0.6875rem", { lineHeight: "1.2", letterSpacing: "0.08em" }],
      },

      spacing: {
        // 8px-Grid (Tailwind nutzt 4px-Grid; wir mappen entsprechend)
      },

      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },

      boxShadow: {
        xs: "0 1px 2px rgba(10, 10, 10, 0.04)",
        sm: "0 2px 4px rgba(10, 10, 10, 0.05)",
        md: "0 4px 12px rgba(10, 10, 10, 0.06)",
        lg: "0 8px 24px rgba(10, 10, 10, 0.08)",
        gold: "0 4px 16px rgba(201, 169, 97, 0.15)",
      },

      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },

      transitionDuration: {
        fast: "150ms",
        medium: "250ms",
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
          "0%, 100%": { transform: "scale(1)", boxShadow: "0 4px 16px rgba(201, 169, 97, 0.15)" },
          "50%": { transform: "scale(1.02)", boxShadow: "0 4px 20px rgba(201, 169, 97, 0.3)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
