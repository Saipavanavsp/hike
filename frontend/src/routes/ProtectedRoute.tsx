import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import type { Role } from "@/api/types";
import { homeFor } from "@/components/layout/nav";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/stores/auth";

export function FullPageSkeleton() {
  return (
    <div className="flex min-h-screen" role="status" aria-label="Loading">
      <div className="hidden w-[240px] border-r border-border bg-surface md:block" />
      <div className="flex-1">
        <div className="h-12 border-b border-border" />
        <div className="space-y-3 p-4">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    </div>
  );
}

export function ProtectedRoute({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullPageSkeleton />;
  if (status === "anonymous" || !user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}
