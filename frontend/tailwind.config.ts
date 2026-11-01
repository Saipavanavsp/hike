import type { Config } from "tailwindcss";

// Design tokens: one accent (teal), status colours only for status,
// 6px radius (4px for tags), borders over shadows, dense type scale.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "Consolas", "monospace"],
      },
      colors: {
        bg: "#FFFFFF",
        surface: "#F7F8FA",
        border: "#E3E6EB",
        ink: {
          DEFAULT: "#1A1D21",
          secondary: "#5A6270",
        },
        accent: {
          DEFAULT: "#0F766E",
          hover: "#115E59",
          tint: "#F0FDFA",
        },
        status: {
          green: "#15803D",
          "green-bg": "#F0FDF4",
          amber: "#B45309",
          "amber-bg": "#FFFBEB",
          red: "#B91C1C",
          "red-bg": "#FEF2F2",
          grey: "#6B7280",
          "grey-bg": "#F3F4F6",
        },
      },
      borderRadius: {
        DEFAULT: "6px",
        md: "6px",
        sm: "4px",
        tag: "4px",
      },
      fontSize: {
        xs: ["12px", "16px"],
        sm: ["13px", "18px"],
        base: ["14px", "20px"],
        lg: ["16px", "24px"],
        xl: ["18px", "26px"],
        "2xl": ["22px", "30px"],
      },
      height: {
        row: "40px",
      },
      boxShadow: {
        // Only modals and dropdowns get shadows.
        overlay: "0 8px 24px rgba(26, 29, 33, 0.12), 0 1px 2px rgba(26, 29, 33, 0.08)",
      },
      ringColor: {
        DEFAULT: "#0F766E",
      },
    },
  },
  plugins: [],
} satisfies Config;
