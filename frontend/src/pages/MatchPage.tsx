/**
 * MatchPage
 *
 * Two-step workflow:
 *   Step 1 — Select a resume and a job description, then click "Run match".
 *   Step 2 — Display the match score, matched skills, missing skills, and
 *            skill-gap recommendations.
 *
 * The page also pre-selects a job description when the URL contains ?jd={id}
 * (deep-linked from JobDescriptionsPage).
 *
 * States for the selector step: loading / error / ready
 * States for the match result: idle / running / error / success
 */

import { type FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { jobDescriptionApi, matchApi, resumeApi } from "../services/api";
import type {
  JobDescriptionResponse,
  MatchDetailResponse,
  ResumeResponse,
} from "../types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready" };

type MatchState =
  | { status: "idle" }
  | { status: "running" }
  | { status: "error"; message: string }
  | { status: "success"; data: MatchDetailResponse };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreColor(score: number): string {
  if (score >= 70) return "text-green-700";
  if (score >= 40) return "text-amber-600";
  return "text-red-600";
}

function scoreBg(score: number): string {
  if (score >= 70) return "bg-green-50 border-green-200";
  if (score >= 40) return "bg-amber-50 border-amber-200";
  return "bg-red-50 border-red-200";
}

function scoreLabel(score: number): string {
  if (score >= 70) return "Strong match";
  if (score >= 40) return "Partial match";
  return "Weak match";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MatchPage() {
  const [searchParams] = useSearchParams();
  const preselectedJdId = searchParams.get("jd");

  const [loadState, setLoadState] = useState<LoadState>({ status: "loading" });
  const [resumes, setResumes] = useState<ResumeResponse[]>([]);
  const [jobDescriptions, setJobDescriptions] = useState<JobDescriptionResponse[]>([]);

  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [selectedJdId, setSelectedJdId] = useState<string>(preselectedJdId ?? "");

  const [matchState, setMatchState] = useState<MatchState>({ status: "idle" });

  useEffect(() => {
    Promise.all([resumeApi.list(), jobDescriptionApi.list()])
      .then(([r, j]) => {
        setResumes(r);
        setJobDescriptions(j);
        setLoadState({ status: "ready" });
        // Auto-select first resume if only one exists
        if (r.length === 1) setSelectedResumeId(String(r[0].id));
        // Pre-select JD from URL if valid
        if (preselectedJdId && j.some((jd) => String(jd.id) === preselectedJdId)) {
          setSelectedJdId(preselectedJdId);
        }
      })
      .catch((err: unknown) =>
        setLoadState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load data.",
        })
      );
  }, [preselectedJdId]);

  async function handleRun(e: FormEvent) {
    e.preventDefault();
    if (!selectedResumeId || !selectedJdId) return;

    setMatchState({ status: "running" });
    try {
      const result = await matchApi.create({
        resume_id: Number(selectedResumeId),
        job_description_id: Number(selectedJdId),
      });
      setMatchState({ status: "success", data: result });
    } catch (err) {
      setMatchState({
        status: "error",
        message: err instanceof Error ? err.message : "Match failed. Please try again.",
      });
    }
  }

  function handleReset() {
    setMatchState({ status: "idle" });
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Match Resume</h1>
        <p className="mt-1 text-sm text-slate-500">
          Compare a resume against a job description to see your match score and skill gaps.
        </p>
      </div>

      {/* Selector / result */}
      {loadState.status === "loading" && (
        <div className="flex items-center justify-center py-24">
          <div
            className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
            role="status"
            aria-label="Loading"
          />
        </div>
      )}

      {loadState.status === "error" && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-700">{loadState.message}</p>
        </div>
      )}

      {loadState.status === "ready" && matchState.status !== "success" && (
        <MatchSelector
          resumes={resumes}
          jobDescriptions={jobDescriptions}
          selectedResumeId={selectedResumeId}
          selectedJdId={selectedJdId}
          onResumeChange={setSelectedResumeId}
          onJdChange={setSelectedJdId}
          onSubmit={handleRun}
          isRunning={matchState.status === "running"}
          error={matchState.status === "error" ? matchState.message : null}
        />
      )}

      {matchState.status === "success" && (
        <MatchResults result={matchState.data} onRunAnother={handleReset} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Selector sub-component
// ---------------------------------------------------------------------------

function MatchSelector({
  resumes,
  jobDescriptions,
  selectedResumeId,
  selectedJdId,
  onResumeChange,
  onJdChange,
  onSubmit,
  isRunning,
  error,
}: {
  resumes: ResumeResponse[];
  jobDescriptions: JobDescriptionResponse[];
  selectedResumeId: string;
  selectedJdId: string;
  onResumeChange: (id: string) => void;
  onJdChange: (id: string) => void;
  onSubmit: (e: FormEvent) => void;
  isRunning: boolean;
  error: string | null;
}) {
  const canRun = selectedResumeId !== "" && selectedJdId !== "" && !isRunning;

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-5"
    >
      <h2 className="text-base font-semibold text-slate-800">Select resume and job description</h2>

      {error && (
        <div role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Resume selector */}
      <div>
        <label htmlFor="sel-resume" className="mb-1 block text-sm font-medium text-slate-700">
          Resume
        </label>
        {resumes.length === 0 ? (
          <p className="text-sm text-slate-500">
            No resumes yet.{" "}
            <a href="/resumes" className="text-indigo-600 hover:underline">
              Upload one first.
            </a>
          </p>
        ) : (
          <select
            id="sel-resume"
            value={selectedResumeId}
            onChange={(e) => onResumeChange(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">— Select a resume —</option>
            {resumes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.file_name} ({r.file_type.toUpperCase()})
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Job description selector */}
      <div>
        <label htmlFor="sel-jd" className="mb-1 block text-sm font-medium text-slate-700">
          Job description
        </label>
        {jobDescriptions.length === 0 ? (
          <p className="text-sm text-slate-500">
            No job descriptions yet.{" "}
            <a href="/job-descriptions" className="text-indigo-600 hover:underline">
              Add one first.
            </a>
          </p>
        ) : (
          <select
            id="sel-jd"
            value={selectedJdId}
            onChange={(e) => onJdChange(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">— Select a job description —</option>
            {jobDescriptions.map((jd) => (
              <option key={jd.id} value={jd.id}>
                {jd.title}{jd.company ? ` — ${jd.company}` : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={!canRun}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {isRunning ? (
            <>
              <span
                className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
                aria-hidden="true"
              />
              Running…
            </>
          ) : (
            "Run match"
          )}
        </button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Results sub-component
// ---------------------------------------------------------------------------

function MatchResults({
  result,
  onRunAnother,
}: {
  result: MatchDetailResponse;
  onRunAnother: () => void;
}) {
  const score = result.match_score;
  const sg = result.skill_gap;

  return (
    <div className="space-y-6">
      {/* Score banner */}
      <div className={`rounded-xl border p-6 ${scoreBg(score)}`}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Match score
            </p>
            <p className={`mt-1 text-5xl font-bold ${scoreColor(score)}`}>
              {score.toFixed(1)}%
            </p>
            <p className={`mt-1 text-sm font-medium ${scoreColor(score)}`}>
              {scoreLabel(score)}
            </p>
          </div>
          <div className="text-sm text-slate-600 space-y-0.5">
            <p>
              <span className="font-medium">Resume:</span>{" "}
              <span className="font-mono text-xs">{result.resume_file_name}</span>
            </p>
            <p>
              <span className="font-medium">Job:</span>{" "}
              {result.job_description_title}
            </p>
            <p>
              <span className="font-medium">Matched:</span>{" "}
              {result.matched_skills.length} skill
              {result.matched_skills.length !== 1 ? "s" : ""}
            </p>
            <p>
              <span className="font-medium">Missing:</span>{" "}
              {result.missing_skills.length} skill
              {result.missing_skills.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      </div>

      {/* Two-column skills grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Matched skills */}
        <div className="rounded-xl border border-green-200 bg-green-50 p-5">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-green-800">
            <CheckCircleIcon className="h-4 w-4" aria-hidden="true" />
            Matched skills ({result.matched_skills.length})
          </h3>
          {result.matched_skills.length === 0 ? (
            <p className="text-xs text-green-700">No matched skills found.</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {result.matched_skills.map((s) => (
                <li
                  key={s}
                  className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800"
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Missing skills */}
        <div className="rounded-xl border border-red-200 bg-red-50 p-5">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-800">
            <XCircleIcon className="h-4 w-4" aria-hidden="true" />
            Not found in resume ({result.missing_skills.length})
          </h3>
          {result.missing_skills.length === 0 ? (
            <p className="text-xs text-red-700">All required skills found!</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {result.missing_skills.map((s) => (
                <li
                  key={s}
                  className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800"
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Recommendations */}
      {sg && sg.recommendations.length > 0 && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <h3 className="mb-3 text-sm font-semibold text-indigo-800">
            Recommendations
          </h3>
          <ul className="space-y-2">
            {sg.recommendations.map((rec, i) => (
              <li key={i} className="flex gap-2 text-sm text-indigo-900">
                <span className="mt-0.5 shrink-0 text-indigo-400">•</span>
                <span>{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Run another */}
      <div className="flex justify-end">
        <button
          onClick={onRunAnother}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          Run another match
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
