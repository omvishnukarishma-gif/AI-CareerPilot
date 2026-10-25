/**
 * ProtectedRoute
 *
 * Wraps routes that require authentication.  While the initial auth check
 * is loading, shows a full-screen spinner so there is no flash of the
 * login page for users who are already logged in.  Once loading is done,
 * unauthenticated visitors are redirected to /login.
 */

import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div
          className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
          role="status"
          aria-label="Loading"
        />
      </div>
    );
  }

  if (!user) {
    // Preserve the attempted URL so we can redirect back after login.
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
