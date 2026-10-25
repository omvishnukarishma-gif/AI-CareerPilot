/**
 * NotFoundPage — shown for any unrecognised route.
 */

import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function NotFoundPage() {
  const { user } = useAuth();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 dark:bg-slate-900 px-4">
      <p className="text-8xl font-extrabold text-slate-200 dark:text-slate-700 select-none">
        404
      </p>
      <h1 className="mt-4 text-2xl font-bold text-slate-800 dark:text-slate-100">
        Page not found
      </h1>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 text-center max-w-sm">
        The page you were looking for doesn&apos;t exist or has been moved.
      </p>
      <Link
        to={user ? "/dashboard" : "/"}
        className="mt-6 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
      >
        {user ? "Go to dashboard" : "Go home"}
      </Link>
    </div>
  );
}
