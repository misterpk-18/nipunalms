import type { QueryClient } from "@tanstack/react-query";
import { Link, Navigate, Outlet, createRootRouteWithContext, useRouterState } from "@tanstack/react-router";
import { useAuth } from "@/auth/auth";
import { PUBLIC_PATHS, canOpen, workspaceForPath } from "@/auth/access";
import { AppShell } from "@/components/lms/app-shell";
import { StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootLayout,
  notFoundComponent: NotFound,
});

function RootLayout() {
  return (
    <>
      <Guarded />
      <Toaster richColors position="top-right" />
    </>
  );
}

function Guarded() {
  const path = useRouterState({ select: (s) => s.location.pathname });
  const redirect = useRouterState({ select: (s) => (s.location.search as Record<string, unknown>)["redirect"] as string | undefined });
  const { status, profile, workspaces } = useAuth();

  if (PUBLIC_PATHS.includes(path)) {
    if (status === "authenticated" && profile) {
      // Signing in on /login?redirect=… returns to the page the visitor asked for (same-origin paths only)
      const next = typeof redirect === "string" && redirect.startsWith("/") && !redirect.startsWith("//") ? redirect : profile.home_route;
      return <Navigate to={profile.user.must_change_password ? "/change-password" : next} replace />;
    }
    return <Outlet />;
  }
  if (status === "anonymous") return <Navigate to="/login" search={path === "/" ? {} : { redirect: path }} replace />;
  if (status === "loading" || !profile)
    return (
      <div className="grid min-h-screen place-items-center text-sm text-muted-foreground" aria-busy="true">
        Loading your workspace…
      </div>
    );
  if (profile.user.must_change_password && path !== "/change-password") return <Navigate to="/change-password" replace />;
  if (path === "/change-password") return <Outlet />;
  if (path === "/") return <Navigate to={profile.home_route} replace />;

  return <AppShell>{canOpen(workspaces, workspaceForPath(path)) ? <Outlet /> : <AccessDenied />}</AppShell>;
}

export function AccessDenied() {
  const { profile } = useAuth();
  return (
    <div className="mx-auto max-w-lg py-10">
      <StatusNote state="Permission Restricted">
        Your role ({[...new Set(profile?.scopes.map((s) => s.role_name))].join(" · ")}) cannot open this workspace.{" "}
        <Link className="underline" to={profile?.home_route ?? "/"}>
          Go to your home
        </Link>
        .
      </StatusNote>
    </div>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <h1 className="text-5xl font-bold">404</h1>
      <p className="mt-3 text-sm text-muted-foreground">This page doesn't exist or has moved.</p>
      <Button className="mt-6" asChild>
        <Link to="/">Go home</Link>
      </Button>
    </div>
  );
}
