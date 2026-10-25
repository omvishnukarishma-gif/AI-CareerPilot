/**
 * InterviewHistoryPage
 *
 * Lists all of the current user's past interview-practice sessions.
 * Clicking a session expands it to show the full Q&A transcript and feedback.
 *
 * States:
 *   loading — fetching the list
 *   error   — fetch failed
 *   empty   — no sessions yet
 *   success — list of sessions
 *
 * For each session the user can expand to see the full transcript.
 * The full detail is fetched lazily on first expand (not all at once).
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { interviewApi } from "../services/api";
import type {
  InterviewSessionDetailResponse,
  InterviewSessionResponse,
  TranscriptEntry,
  QuestionOut,
} from "../types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ListState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: InterviewSessionResponse[] };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-green-700";
  if (score >= 40) return "text-amber-600";
  return "text-red-600";
}

function statusBadge(status: string): React.ReactNode {
  const base = "rounded-full px-2.5 py-0.5 text-xs font-semibold";
  if (status === "completed") {
    return <span className={`${base} bg-green-100 text-green-700`}>Completed</span>;
  }
  return <span className={`${base} bg-amber-100 text-amber-700`}>In progress</span>;
}

function categoryLabel(cat: string): string {
  const map: Record<string, string> = {
    behavioral: "Behavioral",
    technical: "Technical",
    role_specific: "Role-specific",
    jd_skill: "Skill focus",
  };
  return map[cat] ?? cat;
}

function categoryBadgeClass(cat: string): string {
  const map: Record<string, string> = {
    behavioral: "bg-violet-100 text-violet-700",
    technical: "bg-blue-100 text-blue-700",
    role_specific: "bg-amber-100 text-amber-700",
    jd_skill: "bg-emerald-100 text-emerald-700",
  };
  return map[cat] ?? "bg-slate-100 text-slate-600";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InterviewHistoryPage() {
  const [listState, setListState] = useState<ListState>({ status: "loading" });

  useEffect(() => {
    interviewApi
      .list()
      .then((data) => setListState({ status: "success", data }))
      .catch((err: unknown) =>
        setListState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load interview history.",
        })
      );
  }, []);

  function retry() {
    setListState({ status: "loading" });
    interviewApi
      .list()
      .then((data) => setListState({ status: "success", data }))
      .catch((err: unknown) =>
        setListState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load interview history.",
        })
      );
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Interview History</h1>
          <p className="mt-1 text-sm text-slate-500">
            Review your past practice sessions and the feedback you received.
          </p>
        </div>
        <Link
          to="/interview"
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          <MicIcon className="h-4 w-4" aria-hidden="true" />
          New session
        </Link>
      </div>

      {/* Content */}
      {listState.status === "loading" && (
        <div className="flex items-center justify-center py-24">
          <div
            className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
            role="status"
            aria-label="Loading interview history"
          />
        </div>
      )}

      {listState.status === "error" && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-700">{listState.message}</p>
          <button
            onClick={retry}
            className="mt-3 rounded-lg bg-red-100 px-4 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {listState.status === "success" && listState.data.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center">
          <MicIcon className="mb-3 h-10 w-10 text-slate-300" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-slate-700">No practice sessions yet</h3>
          <p className="mt-1 text-xs text-slate-500">
            Start a practice session to see your history here.
          </p>
          <Link
            to="/interview"
            className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 transition-colors"
          >
            Start practising
          </Link>
        </div>
      )}

      {listState.status === "success" && listState.data.length > 0 && (
        <div className="space-y-3">
          {listState.data.map((session) => (
            <SessionRow
              key={session.id}
              session={session}
              onDelete={(id) =>
                setListState((prev) =>
                  prev.status === "success"
                    ? { status: "success", data: prev.data.filter((s) => s.id !== id) }
                    : prev
                )
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SessionRow — lazy-loads full detail on expand
// ---------------------------------------------------------------------------

function SessionRow({
  session,
  onDelete,
}: {
  session: InterviewSessionResponse;
  onDelete: (id: number) => void;
}) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<InterviewSessionDetailResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

async function handleDelete() {
  if (deleting) return;

  const confirmed = window.confirm(
    "Are you sure you want to delete this interview session?"
  );

  if (!confirmed) return;

  setDeleting(true);
  setDeleteError(null);

  try {
    await interviewApi.delete(session.id);
    onDelete(session.id);
  } catch (err) {
    setDeleteError(
      err instanceof Error
        ? err.message
        : "Failed to delete interview session."
    );
  } finally {
    setDeleting(false);
  }
}

  async function handleToggle() {
    const willOpen = !open;
    setOpen(willOpen);

    if (willOpen && detail === null && !loadingDetail) {
      setLoadingDetail(true);
      setDetailError(null);
      try {
        const d = await interviewApi.get(session.id);
        setDetail(d);
      } catch (err) {
        setDetailError(err instanceof Error ? err.message : "Failed to load session.");
      } finally {
        setLoadingDetail(false);
      }
    }
  }

  const avgScore =
    detail && detail.transcript.length > 0
      ? Math.round(
          detail.transcript.reduce((s, e) => s + e.feedback.score, 0) /
            detail.transcript.length
        )
      : null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Summary row */}
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full items-center justify-between px-5 py-4 text-left hover:bg-slate-50 transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="shrink-0">
            <MicIcon className="h-5 w-5 text-indigo-500" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900 truncate">
              {session.role_target}
            </p>
            <p className="text-xs text-slate-500">
              {formatDate(session.created_at)} ·{" "}
              {session.answers_given}/{session.question_count} answered
              {avgScore !== null ? (
                <span className={` · avg score: ${scoreColor(avgScore)} font-medium`}>
                  {" "}{avgScore}/100
                </span>
              ) : null}
            </p>
          </div>
        </div>
        <div className="ml-4 flex shrink-0 items-center gap-3">
          {statusBadge(session.status)}
          <ChevronIcon
            className={`h-4 w-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
            aria-hidden="true"
          />
        </div>
      </button>
      
    <div className="flex items-center justify-end gap-3 border-t border-slate-100 px-5 py-2">
      {deleteError && (
        <p role="alert" className="mr-auto text-sm text-red-600">
          {deleteError}
        </p>
      )}

      <button
        type="button"
        onClick={() => void handleDelete()}
        disabled={deleting}
        className="rounded-md px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
        aria-label={`Delete interview session ${session.id}`}
      >
        {deleting ? "Deleting..." : "Delete"}
      </button>
    </div>


      {/* Detail panel */}
      {open && (
        <div className="border-t border-slate-100">
          {loadingDetail && (
            <div className="flex items-center justify-center py-10">
              <div
                className="h-6 w-6 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
                role="status"
                aria-label="Loading session detail"
              />
            </div>
          )}

          {detailError && (
            <div role="alert" className="px-5 py-4 text-sm text-red-600">
              {detailError}
            </div>
          )}

          {detail && !loadingDetail && (
            <TranscriptDetail detail={detail} />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TranscriptDetail — renders the full Q&A transcript
// ---------------------------------------------------------------------------

function TranscriptDetail({ detail }: { detail: InterviewSessionDetailResponse }) {
  if (detail.transcript.length === 0) {
    return (
      <div className="px-5 py-6 text-center text-sm text-slate-500">
        No answers submitted yet.{" "}
        <Link to="/interview" className="text-indigo-600 hover:underline">
          Continue this session
        </Link>
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-100">
      {detail.transcript.map((entry) => {
        const q: QuestionOut | undefined = detail.questions[entry.question_index];
        return (
          <TranscriptEntryRow
            key={entry.question_index}
            entry={entry}
            question={q}
          />
        );
      })}
    </div>
  );
}

function TranscriptEntryRow({
  entry,
  question,
}: {
  entry: TranscriptEntry;
  question: QuestionOut | undefined;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start justify-between px-5 py-3 text-left hover:bg-slate-50 transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-start gap-3 min-w-0">
          <span
            className={`mt-0.5 shrink-0 text-xs font-bold ${scoreColor(entry.feedback.score)}`}
          >
            {Math.round(entry.feedback.score)}
          </span>
          <div className="min-w-0">
            {question && (
              <span
                className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium mb-0.5 ${categoryBadgeClass(question.category)}`}
              >
                {categoryLabel(question.category)}
              </span>
            )}
            <p className="text-sm text-slate-700 truncate">{entry.question_text}</p>
          </div>
        </div>
        <ChevronIcon
          className={`h-4 w-4 shrink-0 text-slate-400 ml-3 mt-0.5 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="px-5 pb-4 space-y-3 bg-slate-50">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-1">
              Your answer
            </p>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{entry.answer}</p>
          </div>

          {entry.feedback.strengths.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-green-600 mb-1">
                Strengths
              </p>
              <ul className="space-y-0.5">
                {entry.feedback.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-slate-700 flex gap-2">
                    <span className="text-green-500 shrink-0">•</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {entry.feedback.improvements.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-600 mb-1">
                Suggestions
              </p>
              <ul className="space-y-0.5">
                {entry.feedback.improvements.map((imp, i) => (
                  <li key={i} className="text-sm text-slate-700 flex gap-2">
                    <span className="text-amber-500 shrink-0">•</span>
                    {imp}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="text-xs text-slate-400 italic">{entry.feedback.note}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function MicIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
    </svg>
  );
}
