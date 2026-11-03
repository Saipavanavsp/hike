// Recharts takes colours as strings: these read the theme's CSS variables (src/index.css),
// so charts follow light and dark mode without re-rendering.
const SANS = '"Inter Variable", Inter, system-ui, sans-serif';

export const CHART = {
  axis: { fontSize: 11, fill: "var(--chart-axis)", fontFamily: SANS },
  label: { fontSize: 12, fill: "var(--chart-label)", fontFamily: SANS, fontWeight: 600 },
  grid: "var(--chart-grid)",
  cursor: "var(--chart-cursor)",
  series: "var(--chart-1)",
  tooltip: {
    background: "rgb(var(--bg))",
    color: "rgb(var(--ink))",
    border: "1px solid rgb(var(--border))",
    borderRadius: 8,
    fontSize: 12,
    boxShadow: "0 8px 24px -6px rgb(var(--shadow) / 0.18)",
  },
  tooltipLabel: { color: "rgb(var(--ink-secondary))", marginBottom: 2 },
  tooltipItem: { color: "rgb(var(--ink))" },
} as const;
