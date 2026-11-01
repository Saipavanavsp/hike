import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { refreshSession } from "@/api/client";
import { AppShell } from "@/components/layout/AppShell";
import { homeFor } from "@/components/layout/nav";
import { Toaster } from "@/components/ui/Toaster";
import { FullPageSkeleton, ProtectedRoute } from "@/routes/ProtectedRoute";
import { useAuth } from "@/stores/auth";

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

function Placeholder({ title }: { title: string }) {
  return <h1 className="text-xl font-semibold">{title}</h1>;
}

const router = createBrowserRouter([
  { path: "/", element: <Home /> },
  { path: "/login", element: <Placeholder title="Sign in" /> },
  {
    element: (
      <ProtectedRoute roles={["seeker", "recruiter", "admin"]}>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [{ path: "/jobs", element: <Placeholder title="Jobs" /> }],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

export default function App() {
  const status = useAuth((s) => s.status);
  useEffect(() => {
    // Restore the session from the refresh cookie on first load.
    if (status === "loading") void refreshSession();
  }, [status]);
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>
  );
}
