/** "₹12–18 LPA" style salary range from annual INR amounts. */
export function formatLpa(amount: number): string {
  const lpa = amount / 100_000;
  return Number.isInteger(lpa) ? String(lpa) : lpa.toFixed(1).replace(/\.0$/, "");
}

export function formatSalaryRange(min: number, max: number): string {
  if (min === max) return `₹${formatLpa(min)} LPA`;
  return `₹${formatLpa(min)}–${formatLpa(max)} LPA`;
}

export function formatExperience(min: number, max: number): string {
  if (min === 0 && max === 0) return "Fresher";
  return `${min}–${max} yrs`;
}

const UNITS: [number, string][] = [
  [60, "s"],
  [60, "m"],
  [24, "h"],
  [7, "d"],
  [4.35, "w"],
  [12, "mo"],
  [Number.POSITIVE_INFINITY, "y"],
];

/** Compact relative time: "just now", "5m ago", "3d ago", "2w ago". */
export function relativeTime(iso: string, now: Date = new Date()): string {
  let value = (now.getTime() - new Date(iso).getTime()) / 1000;
  if (value < 45) return "just now";
  for (const [size, unit] of UNITS) {
    if (Math.abs(value) < size) return `${Math.floor(value)}${unit} ago`;
    value /= size;
  }
  return "";
}

export function absoluteDate(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export const REMOTE_LABELS: Record<string, string> = {
  onsite: "On-site",
  hybrid: "Hybrid",
  remote: "Remote",
};

export const ROLE_LABELS: Record<string, string> = {
  backend: "Backend",
  frontend: "Frontend",
  fullstack: "Full-Stack",
  data_ml: "Data/ML",
  devops: "DevOps",
  mobile: "Mobile",
  qa: "QA",
};

export const STATUS_LABELS: Record<string, string> = {
  applied: "Applied",
  shortlisted: "Shortlisted",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (
    (parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")
  ).toUpperCase();
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
