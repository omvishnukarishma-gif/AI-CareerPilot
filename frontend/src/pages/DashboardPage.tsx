/**
 * DashboardPage
 *
 * Shows a personalised welcome and a quick-stats overview.
 * Currently fetches the user's resume count from the backend so the card
 * has real data.  Subsequent phases will add job-match stats, application
 * counts, etc.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { interviewApi, jobApplicationApi, matchApi, resumeApi } from "../services/api";
import type { InterviewSessionResponse, JobApplicationResponse, MatchResponse, ResumeResponse } from "../types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type FetchState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: T };

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DashboardPage() {
  const { user } = useAuth();
  const [resumeState, setResumeState] = useState<FetchState<ResumeResponse[]>>(
    { status: "loading" }
  );
  const [matchState, setMatchState] = useState<FetchState<MatchResponse[]>>(
    { status: "loading" }
  );
  const [interviewState, setInterviewState] = useState<FetchState<InterviewSessionResponse[]>>(
    { status: "loading" }
  );
  const [applicationState, setApplicationState] = useState<FetchState<JobApplicationResponse[]>>(
    { status: "loading" }
  );

  useEffect(() => {
    resumeApi
      .list()
      .then((data) => setResumeState({ status: "success", data }))
      .catch((err: unknown) =>
        setResumeState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load resumes.",
        })
      );
    matchApi
      .list()
      .then((data) => setMatchState({ status: "success", data }))
      .catch((err: unknown) =>
        setMatchState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load matches.",
        })
      );
    interviewApi
      .list()
      .then((data) => setInterviewState({ status: "success", data }))
      .catch((err: unknown) =>
        setInterviewState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load interview sessions.",
        })
      );
    jobApplicationApi
      .list()
      .then((data) => setApplicationState({ status: "success", data }))
      .catch((err: unknown) =>
        setApplicationState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load applications.",
        })
      );
  }, []);

  const firstName = user?.full_name?.split(" ")[0] ?? "there";

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">
          Welcome back, {firstName}!
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Here&apos;s an overview of your career progress.
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Resume count card */}
        <StatCard
          title="Resumes"
          icon={<DocumentIcon className="h-6 w-6 text-indigo-600" />}
          state={resumeState}
          renderValue={(data) => (
            <div>
              <p className="text-3xl font-bold text-slate-900">{data.length}</p>
              {data.length === 0 ? (
                <p className="mt-1 text-sm text-slate-500">
                  No resumes yet.{" "}
                  <Link to="/resumes" className="text-indigo-600 hover:underline">
                    Upload your first
                  </Link>
                </p>
              ) : (
                <p className="mt-1 text-sm text-slate-500">
                  <Link to="/resumes" className="text-indigo-600 hover:underline">
                    View all resumes →
                  </Link>
                </p>
              )}
            </div>
          )}
        />

        {/* Job Matches card — real count from backend */}
        <StatCard
          title="Job Matches"
          icon={<BriefcaseIcon className="h-6 w-6 text-violet-600" />}
          state={matchState}
          renderValue={(data) => (
            <div>
              <p className="text-3xl font-bold text-slate-900">{data.length}</p>
              {data.length === 0 ? (
                <p className="mt-1 text-sm text-slate-500">
                  No matches yet.{" "}
                  <Link to="/match" className="text-indigo-600 hover:underline">
                    Run your first match
                  </Link>
                </p>
              ) : (
                <p className="mt-1 text-sm text-slate-500">
                  <Link to="/match" className="text-indigo-600 hover:underline">
                    Run another match →
                  </Link>
                </p>
              )}
            </div>
          )}
        />

        {/* Interview Prep card — real count from backend */}
        <StatCard
          title="Interview Prep"
          icon={<ChatIcon className="h-6 w-6 text-emerald-600" />}
          state={interviewState}
          renderValue={(data) => (
            <div>
              <p className="text-3xl font-bold text-slate-900">{data.length}</p>
              {data.length === 0 ? (
                <p className="mt-1 text-sm text-slate-500">
                  No sessions yet.{" "}
                  <Link to="/interview" className="text-indigo-600 hover:underline">
                    Start practising
                  </Link>
                </p>
              ) : (
                <p className="mt-1 text-sm text-slate-500">
                  <Link to="/interview/history" className="text-indigo-600 hover:underline">
                    View history →
                  </Link>
                </p>
              )}
            </div>
          )}
        />

        {/* Job Applications card — real count from backend */}
        <StatCard
          title="Applications"
          icon={<BriefcaseIcon className="h-6 w-6 text-amber-600" />}
          state={applicationState}
          renderValue={(data) => (
            <div>
              <p className="text-3xl font-bold text-slate-900">{data.length}</p>
              {data.length === 0 ? (
                <p className="mt-1 text-sm text-slate-500">
                  No applications yet.{" "}
                  <Link to="/applications" className="text-indigo-600 hover:underline">
                    Track your first
                  </Link>
                </p>
              ) : (
                <p className="mt-1 text-sm text-slate-500">
                  <Link to="/applications" className="text-indigo-600 hover:underline">
                    View all →
                  </Link>
                </p>
              )}
            </div>
          )}
        />
      </div>

      {/* Quick links */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-slate-700">
          Quick actions
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <QuickLink
            to="/resumes"
            icon={<DocumentIcon className="h-5 w-5 text-indigo-600" />}
            label="Manage resumes"
            description="Upload, view, and manage your resumes."
          />
          <QuickLink
            to="/job-descriptions"
            icon={<BriefcaseIcon className="h-5 w-5 text-violet-600" />}
            label="Job descriptions"
            description="Paste and save job descriptions for matching."
          />
          <QuickLink
            to="/match"
            icon={<ChartIcon className="h-5 w-5 text-emerald-600" />}
            label="Match resume"
            description="See your match score and skill gaps."
          />
          <QuickLink
            to="/interview"
            icon={<ChatIcon className="h-5 w-5 text-indigo-600" />}
            label="Interview practice"
            description="Practice with tailored interview questions."
          />
          <QuickLink
            to="/applications"
            icon={<BriefcaseIcon className="h-5 w-5 text-amber-600" />}
            label="Job applications"
            description="Track and manage your job applications."
          />
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** A stat card that shows a loading spinner, an error, or real data. */
function StatCard<T>({
  title,
  icon,
  state,
  renderValue,
}: {
  title: string;
  icon: React.ReactNode;
  state: FetchState<T>;
  renderValue: (data: T) => React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-slate-50 p-2">{icon}</div>
        <span className="text-sm font-semibold text-slate-700">{title}</span>
      </div>

      <div className="mt-4">
        {state.status === "loading" && (
          <div
            className="h-6 w-6 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
            role="status"
            aria-label={`Loading ${title}`}
          />
        )}
        {state.status === "error" && (
          <p className="text-sm text-red-600">{state.message}</p>
        )}
        {state.status === "success" && renderValue(state.data)}
      </div>
    </div>
  );
}

/** A quick-action link card. */
function QuickLink({
  to,
  icon,
  label,
  description,
}: {
  to: string;
  icon: React.ReactNode;
  label: string;
  description: string;
}) {
  return (
    <Link
      to={to}
      className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-indigo-300 hover:bg-indigo-50"
    >
      <div className="mt-0.5 shrink-0 rounded-lg bg-slate-50 p-1.5">{icon}</div>
      <div>
        <p className="text-sm font-medium text-slate-900">{label}</p>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
      />
    </svg>
  );
}

function BriefcaseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M20.25 14.15v4.073a2.25 2.25 0 01-2.25 2.25h-12a2.25 2.25 0 01-2.25-2.25V7.5a2.25 2.25 0 012.25-2.25h1.5m9 0h1.5a2.25 2.25 0 012.25 2.25v.75M9 7.5V6a3 3 0 013-3h0a3 3 0 013 3v1.5M9 7.5h6"
      />
    </svg>
  );
}

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
      />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
      />
    </svg>
  );
}
