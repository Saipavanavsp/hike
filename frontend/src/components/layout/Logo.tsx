import { Link } from "react-router-dom";

export function Logo({ to = "/" }: { to?: string }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-2 text-ink hover:text-ink"
      aria-label="Hike home"
    >
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="6" fill="#0F766E" />
        <path d="M10 8v16M22 8v16M10 16h12" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <span className="text-base font-semibold tracking-tight">Hike</span>
    </Link>
  );
}
