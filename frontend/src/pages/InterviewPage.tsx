/**
 * InterviewPage
 *
 * Three-step workflow:
 *   Step 1 — Setup form: enter role, optionally pick a JD and resume.
 *   Step 2 — Q&A flow: answer one question at a time, see feedback after each.
 *   Step 3 — Summary: view all answers, scores, and recommendations.
 *
 * The page links to /interview/history so users can review past sessions.
 *
 * States:
 *   setup   — initial form (loads resumes + JDs in the background)
 *   loading — waiting for session creation API call
 *   active  — answering questions one by one
 *   done    — all questions answered, full transcript shown
 *   error   — top-level error (setup load failure)
 */

import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { interviewApi, jobDescriptionApi, resumeApi } from "../services/api";
import type {
  InterviewSessionDetailResponse,
  JobDescriptionResponse,
  QuestionOut,
  ResumeResponse,
  TranscriptEntry,
} from "../types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PageState =
  | { stage: "setup" }
  | { stage: "loading" }
  | { stage: "active"; session: InterviewSessionDetailResponse; currentIndex: number; submitting: boolean; answerError: string | null }
  | { stage: "done"; session: InterviewSessionDetailResponse }
  | { stage: "error"; message: string };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function scoreColor(score: number): string {
  if (score >= 70) return "text-green-700";
  if (score >= 40) return "text-amber-600";
  return "text-red-600";
}

function scoreRingClass(score: number): string {
  if (score >= 70) return "border-green-400";
  if (score >= 40) return "border-amber-400";
  return "border-red-400";
}

function avgScore(entries: TranscriptEntry[]): number {
  if (entries.length === 0) return 0;
  return Math.round(entries.reduce((s, e) => s + e.feedback.score, 0) / entries.length);
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function InterviewPage() {
  const [pageState, setPageState] = useState<PageState>({ stage: "setup" });
  const [resumes, setResumes] = useState<ResumeResponse[]>([]);
  const [jobDescriptions, setJobDescriptions] = useState<JobDescriptionResponse[]>([]);
  const [loadingData, setLoadingData] = useState(true);

  // Setup form fields
  const [roleTarget, setRoleTarget] = useState("");
  const [selectedJdId, setSelectedJdId] = useState<string>("");
  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [setupError, setSetupError] = useState<string | null>(null);

  // Q&A answer textarea
  const [answerText, setAnswerText] = useState("");
  const answerRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    Promise.all([resumeApi.list(), jobDescriptionApi.list()])
      .then(([r, j]) => {
        setResumes(r);
        setJobDescriptions(j);
      })
      .catch((err: unknown) => {
        // Non-fatal — user can still practice without JD/resume
        console.warn("Could not load resumes/JDs:", err);
      })
      .finally(() => setLoadingData(false));
  }, []);

  // Focus the answer textarea when a new question becomes active
  useEffect(() => {
    if (pageState.stage === "active") {
      answerRef.current?.focus();
    }
  }, [pageState.stage, pageState.stage === "active" ? pageState.currentIndex : null]);

  async function handleStart(e: FormEvent) {
    e.preventDefault();
    if (!roleTarget.trim()) {
      setSetupError("Please enter a role target.");
      return;
    }
    setSetupError(null);
    setPageState({ stage: "loading" });
    try {
      const session = await interviewApi.create({
        role_target: roleTarget.trim(),
        job_description_id: selectedJdId ? Number(selectedJdId) : null,
        resume_id: selectedResumeId ? Number(selectedResumeId) : null,
      });
      setPageState({ stage: "active", session, currentIndex: 0, submitting: false, answerError: null });
      setAnswerText("");
    } catch (err) {
      setPageState({
        stage: "error",
        message: err instanceof Error ? err.message : "Failed to start session.",
      });
    }
  }

  async function handleSubmitAnswer(e: FormEvent) {
    e.preventDefault();
    if (pageState.stage !== "active") return;
    const { session, currentIndex } = pageState;

    if (answerText.trim().length < 3) {
      setPageState({ ...pageState, answerError: "Please write at least a few words." });
      return;
    }

    setPageState({ ...pageState, submitting: true, answerError: null });
    try {
      const updated = await interviewApi.submitAnswer(session.id, {
        question_index: currentIndex,
        answer: answerText.trim(),
      });
      setAnswerText("");

      if (updated.status === "completed") {
        setPageState({ stage: "done", session: updated });
      } else {
        setPageState({
          stage: "active",
          session: updated,
          currentIndex: currentIndex + 1,
          submitting: false,
          answerError: null,
        });
      }
    } catch (err) {
      setPageState({
        ...pageState,
        submitting: false,
        answerError: err instanceof Error ? err.message : "Failed to submit answer.",
      });
    }
  }

  function handleRestart() {
    setPageState({ stage: "setup" });
    setRoleTarget("");
    setSelectedJdId("");
    setSelectedResumeId("");
    setAnswerText("");
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Interview Practice</h1>
          <p className="mt-1 text-sm text-slate-500">
            Practice answering interview questions and get instant structured feedback.
          </p>
        </div>
        <Link
          to="/interview/history"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
        >
          <ClockIcon className="h-4 w-4" aria-hidden="true" />
          History
        </Link>
      </div>

      {/* Feedback banner for error stage */}
      {pageState.stage === "error" && (
        <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
          <p className="text-sm font-medium text-red-700">{pageState.message}</p>
          <button
            onClick={handleRestart}
            className="mt-3 rounded-lg bg-red-100 px-4 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 transition-colors"
          >
            Try again
          </button>
        </div>
      )}

      {/* Setup form */}
      {(pageState.stage === "setup" || pageState.stage === "loading") && (
        <SetupForm
          loadingData={loadingData}
          resumes={resumes}
          jobDescriptions={jobDescriptions}
          roleTarget={roleTarget}
          selectedJdId={selectedJdId}
          selectedResumeId={selectedResumeId}
          onRoleChange={setRoleTarget}
          onJdChange={setSelectedJdId}
          onResumeChange={setSelectedResumeId}
          onSubmit={handleStart}
          isStarting={pageState.stage === "loading"}
          error={setupError}
        />
      )}

      {/* Active Q&A */}
      {pageState.stage === "active" && (
        <ActiveSession
          session={pageState.session}
          currentIndex={pageState.currentIndex}
          answerText={answerText}
          answerRef={answerRef}
          onAnswerChange={setAnswerText}
          onSubmit={handleSubmitAnswer}
          submitting={pageState.submitting}
          answerError={pageState.answerError}
        />
      )}

      {/* Done / Summary */}
      {pageState.stage === "done" && (
        <SessionSummary session={pageState.session} onPracticeAgain={handleRestart} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SetupForm sub-component
// ---------------------------------------------------------------------------

function SetupForm({
  loadingData,
  resumes,
  jobDescriptions,
  roleTarget,
  selectedJdId,
  selectedResumeId,
  onRoleChange,
  onJdChange,
  onResumeChange,
  onSubmit,
  isStarting,
  error,
}: {
  loadingData: boolean;
  resumes: ResumeResponse[];
  jobDescriptions: JobDescriptionResponse[];
  roleTarget: string;
  selectedJdId: string;
  selectedResumeId: string;
  onRoleChange: (v: string) => void;
  onJdChange: (v: string) => void;
  onResumeChange: (v: string) => void;
  onSubmit: (e: FormEvent) => void;
  isStarting: boolean;
  error: string | null;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-1 text-base font-semibold text-slate-800">Start a practice session</h2>
      <p className="mb-5 text-sm text-slate-500">
        Enter the role you are preparing for. Optionally link a job description to get
        skill-focused questions.
      </p>

      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        {error && (
          <div role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Role target */}
        <div>
          <label htmlFor="role-target" className="mb-1 block text-sm font-medium text-slate-700">
            Target role <span className="text-red-500">*</span>
          </label>
          <input
            id="role-target"
            type="text"
            required
            value={roleTarget}
            onChange={(e) => onRoleChange(e.target.value)}
            placeholder="e.g. Senior Python Developer"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {loadingData ? (
          <div className="flex items-center gap-2 text-sm text-slate-400">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" aria-hidden="true" />
            Loading your resumes and job descriptions…
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Job description */}
            <div>
              <label htmlFor="jd-select" className="mb-1 block text-sm font-medium text-slate-700">
                Job description <span className="text-slate-400 text-xs">(optional)</span>
              </label>
              {jobDescriptions.length === 0 ? (
                <p className="text-xs text-slate-500">
                  No job descriptions yet.{" "}
                  <Link to="/job-descriptions" className="text-indigo-600 hover:underline">
                    Add one
                  </Link>{" "}
                  for tailored questions.
                </p>
              ) : (
                <select
                  id="jd-select"
                  value={selectedJdId}
                  onChange={(e) => onJdChange(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">— None —</option>
                  {jobDescriptions.map((jd) => (
                    <option key={jd.id} value={jd.id}>
                      {jd.title}{jd.company ? ` — ${jd.company}` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Resume */}
            <div>
              <label htmlFor="resume-select" className="mb-1 block text-sm font-medium text-slate-700">
                Resume <span className="text-slate-400 text-xs">(optional)</span>
              </label>
              {resumes.length === 0 ? (
                <p className="text-xs text-slate-500">
                  No resumes yet.{" "}
                  <Link to="/resumes" className="text-indigo-600 hover:underline">
                    Upload one
                  </Link>{" "}
                  to focus on skill gaps.
                </p>
              ) : (
                <select
                  id="resume-select"
                  value={selectedResumeId}
                  onChange={(e) => onResumeChange(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">— None —</option>
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.file_name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        )}

        {/* Limitations notice */}
        <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-800">
          <strong>Note:</strong> Questions and feedback are generated using deterministic keyword
          matching — not an AI language model. Scores reflect keyword coverage and answer
          structure, not actual quality.
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isStarting || !roleTarget.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {isStarting ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" aria-hidden="true" />
                Starting…
              </>
            ) : (
              <>
                <MicIcon className="h-4 w-4" aria-hidden="true" />
                Start practice
              </>
            )}
          </button>
        </div>
      </form>
    </section>
  );
}

// ---------------------------------------------------------------------------
// ActiveSession sub-component
// ---------------------------------------------------------------------------

function ActiveSession({
  session,
  currentIndex,
  answerText,
  answerRef,
  onAnswerChange,
  onSubmit,
  submitting,
  answerError,
}: {
  session: InterviewSessionDetailResponse;
  currentIndex: number;
  answerText: string;
  answerRef: React.RefObject<HTMLTextAreaElement | null>;
  onAnswerChange: (v: string) => void;
  onSubmit: (e: FormEvent) => void;
  submitting: boolean;
  answerError: string | null;
}) {
  const question: QuestionOut = session.questions[currentIndex];
  const total = session.questions.length;
  const answeredSoFar = session.transcript.length;
  const progress = Math.round((answeredSoFar / total) * 100);

  return (
    <div className="space-y-5">
      {/* Progress bar */}
      <div>
        <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
          <span>
            Question {currentIndex + 1} of {total}
          </span>
          <span>{progress}% complete</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </div>

      {/* Question card */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${categoryBadgeClass(question.category)}`}
          >
            {categoryLabel(question.category)}
          </span>
          {question.skill_ref && (
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
              {question.skill_ref}
            </span>
          )}
        </div>

        <p className="text-base font-medium text-slate-900 leading-relaxed">
          {question.text}
        </p>
      </div>

      {/* Previous answers (accordion — collapsed by default) */}
      {session.transcript.length > 0 && (
        <PreviousAnswers transcript={session.transcript} questions={session.questions} />
      )}

      {/* Answer form */}
      <form onSubmit={onSubmit} className="space-y-3">
        {answerError && (
          <div role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {answerError}
          </div>
        )}

        <div>
          <label htmlFor="answer-text" className="mb-1 block text-sm font-medium text-slate-700">
            Your answer
          </label>
          <textarea
            id="answer-text"
            ref={answerRef}
            rows={6}
            value={answerText}
            onChange={(e) => onAnswerChange(e.target.value)}
            placeholder="Type your answer here. Aim for at least 2–3 sentences with a specific example."
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-y"
            aria-describedby="answer-hint"
          />
          <p id="answer-hint" className="mt-1 text-xs text-slate-400">
            Tip: for behavioral questions use the STAR method (Situation, Task, Action, Result).
          </p>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={submitting || answerText.trim().length < 3}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? (
              <>
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" aria-hidden="true" />
                Submitting…
              </>
            ) : currentIndex + 1 === total ? (
              "Submit & finish"
            ) : (
              "Submit & next →"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PreviousAnswers sub-component (collapsible list)
// ---------------------------------------------------------------------------

function PreviousAnswers({
  transcript,
  questions,
}: {
  transcript: TranscriptEntry[];
  questions: QuestionOut[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-5 py-3 text-sm font-medium text-slate-600 hover:text-slate-900"
        aria-expanded={open}
      >
        <span>Previous answers ({transcript.length})</span>
        <ChevronIcon className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>

      {open && (
        <div className="divide-y divide-slate-200 border-t border-slate-200">
          {transcript.map((entry) => {
            const q = questions[entry.question_index];
            return (
              <div key={entry.question_index} className="px-5 py-4 space-y-2">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Q{entry.question_index + 1} · {q ? categoryLabel(q.category) : ""}
                </p>
                <p className="text-sm text-slate-700">{entry.question_text}</p>
                <p className="text-sm text-slate-500 italic">{entry.answer}</p>
                <FeedbackPill score={entry.feedback.score} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SessionSummary sub-component
// ---------------------------------------------------------------------------

function SessionSummary({
  session,
  onPracticeAgain,
}: {
  session: InterviewSessionDetailResponse;
  onPracticeAgain: () => void;
}) {
  const avg = avgScore(session.transcript);

  return (
    <div className="space-y-6">
      {/* Header banner */}
      <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-indigo-900">Practice complete!</h2>
            <p className="mt-1 text-sm text-indigo-700">
              {session.role_target} · {session.transcript.length} question
              {session.transcript.length !== 1 ? "s" : ""} answered
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
              Avg score
            </p>
            <p className={`text-4xl font-bold ${scoreColor(avg)}`}>{avg}</p>
          </div>
        </div>
      </div>

      {/* Per-question cards */}
      <div className="space-y-4">
        {session.transcript.map((entry) => {
          const q = session.questions[entry.question_index];
          return (
            <TranscriptCard
              key={entry.question_index}
              entry={entry}
              question={q}
              index={entry.question_index}
            />
          );
        })}
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <Link
          to="/interview/history"
          className="text-sm font-medium text-indigo-600 hover:underline"
        >
          View session history →
        </Link>
        <button
          onClick={onPracticeAgain}
          className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-colors"
        >
          Practice again
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TranscriptCard sub-component
// ---------------------------------------------------------------------------

function TranscriptCard({
  entry,
  question,
  index,
}: {
  entry: TranscriptEntry;
  question: QuestionOut | undefined;
  index: number;
}) {
  const [open, setOpen] = useState(true);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start justify-between px-5 py-4 text-left hover:bg-slate-50 transition-colors"
        aria-expanded={open}
      >
        <div className="flex items-start gap-3 min-w-0">
          <div
            className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${scoreRingClass(entry.feedback.score)} ${scoreColor(entry.feedback.score)}`}
          >
            {Math.round(entry.feedback.score)}
          </div>
          <div className="min-w-0">
            {question && (
              <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium mb-1 ${categoryBadgeClass(question.category)}`}>
                {categoryLabel(question.category)}
              </span>
            )}
            <p className="text-sm font-medium text-slate-900">
              Q{index + 1}: {entry.question_text}
            </p>
          </div>
        </div>
        <ChevronIcon className={`h-4 w-4 shrink-0 text-slate-400 transition-transform mt-1 ml-2 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>

      {/* Body */}
      {open && (
        <div className="border-t border-slate-100 px-5 py-4 space-y-4">
          {/* Answer */}
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Your answer
            </p>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{entry.answer}</p>
          </div>

          {/* Strengths */}
          {entry.feedback.strengths.length > 0 && (
            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-green-600">
                <CheckCircleIcon className="h-3.5 w-3.5" aria-hidden="true" />
                Strengths
              </p>
              <ul className="space-y-1">
                {entry.feedback.strengths.map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="shrink-0 text-green-500 mt-0.5">•</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Improvements */}
          {entry.feedback.improvements.length > 0 && (
            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-600">
                <LightbulbIcon className="h-3.5 w-3.5" aria-hidden="true" />
                Suggestions
              </p>
              <ul className="space-y-1">
                {entry.feedback.improvements.map((imp, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="shrink-0 text-amber-500 mt-0.5">•</span>
                    <span>{imp}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Note */}
          <p className="text-xs text-slate-400 italic">{entry.feedback.note}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// FeedbackPill — compact score badge
// ---------------------------------------------------------------------------

function FeedbackPill({ score }: { score: number }) {
  return (
    <span className={`text-xs font-semibold ${scoreColor(score)}`}>
      Score: {Math.round(score)}/100
    </span>
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

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
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

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function LightbulbIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
    </svg>
  );
}
