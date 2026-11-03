import type { Config } from "tailwindcss";

// Design tokens live as RGB channels in CSS variables (src/index.css), one set per theme,
// so every utility (and opacity modifiers such as border-accent/30) follows light/dark mode.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      colors: {
        canvas: token("canvas"),
        bg: token("bg"),
        surface: token("surface"),
        border: {
          DEFAULT: token("border"),
          strong: token("border-strong"),
        },
        ink: {
          DEFAULT: token("ink"),
          secondary: token("ink-secondary"),
          muted: token("ink-muted"),
        },
        primary: {
          DEFAULT: token("primary"),
          hover: token("primary-hover"),
          fg: token("primary-fg"),
        },
        accent: {
          DEFAULT: token("accent"),
          hover: token("accent-hover"),
          tint: token("accent-tint"),
          brand: token("accent-brand"),
          fg: token("accent-fg"),
        },
        info: {
          DEFAULT: token("info"),
          bg: token("info-bg"),
        },
        status: {
          green: token("green"),
          "green-bg": token("green-bg"),
          amber: token("amber"),
          "amber-bg": token("amber-bg"),
          red: token("red"),
          "red-bg": token("red-bg"),
          grey: token("grey"),
          "grey-bg": token("grey-bg"),
          fg: token("status-fg"),
        },
        sidebar: {
          DEFAULT: token("sidebar"),
          fg: token("sidebar-fg"),
          muted: token("sidebar-muted"),
          hover: token("sidebar-hover"),
          active: token("sidebar-active"),
          border: token("sidebar-border"),
        },
      },
      borderRadius: {
        DEFAULT: "8px",
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        tag: "6px",
      },
      fontSize: {
        "2xs": ["11px", "14px"],
        xs: ["12px", "16px"],
        sm: ["13px", "18px"],
        base: ["14px", "20px"],
        lg: ["16px", "24px"],
        xl: ["18px", "26px"],
        "2xl": ["22px", "30px"],
        "3xl": ["28px", "36px"],
      },
      letterSpacing: {
        tightish: "-0.011em",
      },
      height: {
        row: "44px",
      },
      boxShadow: {
        xs: "0 1px 2px rgb(var(--shadow) / 0.05)",
        card: "0 1px 2px rgb(var(--shadow) / 0.04), 0 1px 3px rgb(var(--shadow) / 0.06)",
        raised: "0 2px 4px rgb(var(--shadow) / 0.04), 0 8px 16px -4px rgb(var(--shadow) / 0.08)",
        overlay:
          "0 16px 40px -8px rgb(var(--shadow) / 0.22), 0 4px 12px -2px rgb(var(--shadow) / 0.08), 0 0 0 1px rgb(var(--border) / 0.6)",
      },
      ringColor: {
        DEFAULT: token("accent"),
      },
      ringOffsetColor: {
        DEFAULT: token("bg"),
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.97) translateY(4px)" },
          to: { opacity: "1", transform: "scale(1) translateY(0)" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "slide-in-left": {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(0)" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 160ms ease-out both",
        "fade-up": "fade-up 220ms cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "scale-in": "scale-in 160ms cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "slide-in-right": "slide-in-right 220ms cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "slide-in-left": "slide-in-left 220ms cubic-bezier(0.2, 0.8, 0.2, 1) both",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
