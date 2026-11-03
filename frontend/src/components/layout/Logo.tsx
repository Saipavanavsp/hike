import { Link } from "react-router-dom";
import { cn } from "@/lib/cn";

export function LogoMark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="8" className="fill-accent-brand" />
      <path
        d="M10.5 8.5v15M21.5 8.5v15M10.5 16h11"
        stroke="#fff"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Logo({ to = "/", className }: { to?: string; className?: string }) {
  return (
    <Link
      to={to}
      className={cn("inline-flex items-center gap-2.5 text-ink hover:text-ink", className)}
      aria-label="Hike home"
    >
      <LogoMark />
      <span className="text-[17px] font-semibold tracking-tight">Hike</span>
    </Link>
  );
}
