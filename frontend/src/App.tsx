import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { refreshSession } from "@/api/client";
import type { Role } from "@/api/types";
import { AppShell } from "@/components/layout/AppShell";
import { homeFor } from "@/components/layout/nav";
import { TextSkeleton } from "@/components/ui/Skeleton";
import { Toaster } from "@/components/ui/Toaster";
import LoginPage from "@/pages/LoginPage";
import ApplicationsPage from "@/pages/seeker/ApplicationsPage";
import JobDetailPage from "@/pages/seeker/JobDetailPage";
import JobsPage from "@/pages/seeker/JobsPage";
import ProfilePage from "@/pages/seeker/ProfilePage";
import ResumePage from "@/pages/seeker/ResumePage";
import SavedJobsPage from "@/pages/seeker/SavedJobsPage";
import { FullPageSkeleton, ProtectedRoute } from "@/routes/ProtectedRoute";
import { hasSessionHint, useAuth } from "@/stores/auth";

// Recruiter and admin screens pull in dnd-kit and Recharts; load them on demand.
const PipelinePage = lazy(() => import("@/pages/recruiter/PipelinePage"));
const MyJobsPage = lazy(() => import("@/pages/recruiter/MyJobsPage"));
const JobFormPage = lazy(() => import("@/pages/recruiter/JobFormPage"));
const AdminUsersPage = lazy(() => import("@/pages/admin/AdminUsersPage"));
const AdminJobsPage = lazy(() => import("@/pages/admin/AdminJobsPage"));
const AdminApplicationsPage = lazy(() => import("@/pages/admin/AdminApplicationsPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15_000 },
  },
});

function Home() {
  const { status, user } = useAuth();
  if (status === "loading") return <FullPageSkeleton />;
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

function guard(roles: Role[], page: ReactNode) {
  return (
    <ProtectedRoute roles={roles}>
      <Suspense fallback={<TextSkeleton lines={8} />}>{page}</Suspense>
    </ProtectedRoute>
  );
}

const router = createBrowserRouter([
  { path: "/", element: <Home /> },
  { path: "/login", element: <LoginPage /> },
  {
    element: (
      <ProtectedRoute roles={["seeker", "recruiter", "admin"]}>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { path: "/jobs", element: guard(["seeker"], <JobsPage />) },
      { path: "/jobs/:id", element: guard(["seeker", "recruiter", "admin"], <JobDetailPage />) },
      { path: "/applications", element: guard(["seeker"], <ApplicationsPage />) },
      { path: "/saved", element: guard(["seeker"], <SavedJobsPage />) },
      { path: "/profile", element: guard(["seeker"], <ProfilePage />) },
      { path: "/resume", element: guard(["seeker"], <ResumePage />) },
      { path: "/recruiter", element: guard(["recruiter", "admin"], <PipelinePage />) },
      { path: "/recruiter/jobs", element: guard(["recruiter", "admin"], <MyJobsPage />) },
      { path: "/recruiter/jobs/new", element: guard(["recruiter", "admin"], <JobFormPage />) },
      { path: "/recruiter/jobs/:id/edit", element: guard(["recruiter", "admin"], <JobFormPage />) },
      { path: "/recruiter/jobs/:id", element: guard(["recruiter", "admin"], <PipelinePage />) },
      { path: "/admin/users", element: guard(["admin"], <AdminUsersPage />) },
      { path: "/admin/jobs", element: guard(["admin"], <AdminJobsPage />) },
      { path: "/admin/applications", element: guard(["admin"], <AdminApplicationsPage />) },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

export default function App() {
  const status = useAuth((s) => s.status);
  useEffect(() => {
    // Restore the session from the refresh cookie on first load.
    if (status !== "loading") return;
    if (hasSessionHint()) void refreshSession();
    else useAuth.getState().clear();
  }, [status]);
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>
  );
}
