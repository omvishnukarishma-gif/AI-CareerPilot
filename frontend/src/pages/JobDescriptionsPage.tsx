/**
 * JobDescriptionsPage
 *
 * Lets users paste a job description and save it for matching.
 * Lists all previously saved job descriptions below the form.
 *
 * Each card has View, Edit, and Delete actions.
 *
 * States:
 *   - Create Form: idle / submitting / error
 *   - List: loading / error / empty / success
 *   - Detail modal: idle / loading / error / success
 *   - Edit form: idle / submitting / error
 *   - Delete dialog: idle / deleting / error
 */

import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { jobDescriptionApi } from "../services/api";
import type {
  JobDescriptionDetailResponse,
  JobDescriptionResponse,
} from "../types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ListState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: JobDescriptionResponse[] };

type FormState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "error"; message: string };

/** Modal state for the View action. */
type DetailState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: JobDescriptionDetailResponse };

/** Edit modal state. */
type EditState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "submitting" };

/** Delete confirmation dialog state. */
type DeleteState =
  | { status: "idle" }
  | { status: "deleting" }
  | { status: "error"; message: string };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function formatDateTime(iso: string): string {
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

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function JobDescriptionsPage() {
  const [listState, setListState] = useState<ListState>({ status: "loading" });
  const [formState, setFormState] = useState<FormState>({ status: "idle" });

  // Create form fields
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [descriptionText, setDescriptionText] = useState("");

  // View modal state
  const [detailState, setDetailState] = useState<DetailState>({ status: "idle" });
  const [detailJd, setDetailJd] = useState<JobDescriptionResponse | null>(null);

  // Edit modal state
  const [editState, setEditState] = useState<EditState>({ status: "idle" });
  const [editJd, setEditJd] = useState<JobDescriptionResponse | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editCompany, setEditCompany] = useState("");
  const [editDescriptionText, setEditDescriptionText] = useState("");

  // Delete dialog state
  const [deleteState, setDeleteState] = useState<DeleteState>({ status: "idle" });
  const [deleteJd, setDeleteJd] = useState<JobDescriptionResponse | null>(null);

  useEffect(() => {
    loadList();
  }, []);

  function loadList() {
    setListState({ status: "loading" });
    jobDescriptionApi
      .list()
      .then((data) => setListState({ status: "success", data }))
      .catch((err: unknown) =>
        setListState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load job descriptions.",
        })
      );
  }

  // ── Create form ──

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (descriptionText.trim().length < 20) {
      setFormState({
        status: "error",
        message: "Job description must be at least 20 characters.",
      });
      return;
    }

    setFormState({ status: "submitting" });
    try {
      await jobDescriptionApi.create({
        title: title.trim(),
        company: company.trim() || null,
        description_text: descriptionText.trim(),
      });
      // Reset form and reload list
      setTitle("");
      setCompany("");
      setDescriptionText("");
      setFormState({ status: "idle" });
      loadList();
    } catch (err) {
      setFormState({
        status: "error",
        message: err instanceof Error ? err.message : "Failed to save job description.",
      });
    }
  }

  // ── View / detail ──

  function handleView(jd: JobDescriptionResponse) {
    setDetailJd(jd);
    setDetailState({ status: "loading" });
    jobDescriptionApi
      .get(jd.id)
      .then((data) => setDetailState({ status: "success", data }))
      .catch((err: unknown) =>
        setDetailState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load job description.",
        })
      );
  }

  function closeDetail() {
    setDetailState({ status: "idle" });
    setDetailJd(null);
  }

  // ── Edit ──

  function handleEdit(jd: JobDescriptionResponse) {
    setEditJd(jd);
    setEditState({ status: "loading" });
    // Pre-populate fields from the list item (title, company) and fetch the
    // full description_text which is not present in the list response.
    setEditTitle(jd.title);
    setEditCompany(jd.company ?? "");
    jobDescriptionApi
      .get(jd.id)
      .then((data) => {
        setEditDescriptionText(data.description_text);
        setEditState({ status: "idle" });
      })
      .catch((err: unknown) =>
        setEditState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to load job description for editing.",
        })
      );
  }

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault();
    if (!editJd) return;
    if (editDescriptionText.trim().length < 20) {
      setEditState({
        status: "error",
        message: "Job description must be at least 20 characters.",
      });
      return;
    }

    setEditState({ status: "submitting" });
    try {
      await jobDescriptionApi.update(editJd.id, {
        title: editTitle.trim(),
        company: editCompany.trim() || null,
        description_text: editDescriptionText.trim(),
      });
      setEditState({ status: "idle" });
      setEditJd(null);
      loadList();
    } catch (err) {
      setEditState({
        status: "error",
        message: err instanceof Error ? err.message : "Failed to update job description.",
      });
    }
  }

  function closeEdit() {
    setEditState({ status: "idle" });
    setEditJd(null);
  }

  // ── Delete ──

  function handleDeleteClick(jd: JobDescriptionResponse) {
    setDeleteJd(jd);
    setDeleteState({ status: "idle" });
  }

  function confirmDelete() {
    if (!deleteJd) return;
    setDeleteState({ status: "deleting" });
    jobDescriptionApi
      .delete(deleteJd.id)
      .then(() => {
        setDeleteState({ status: "idle" });
        setDeleteJd(null);
        loadList();
      })
      .catch((err: unknown) =>
        setDeleteState({
          status: "error",
          message: err instanceof Error ? err.message : "Failed to delete job description.",
        })
      );
  }

  function cancelDelete() {
    setDeleteState({ status: "idle" });
    setDeleteJd(null);
  }

  const isSubmitting = formState.status === "submitting";

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Job Descriptions</h1>
        <p className="mt-1 text-sm text-slate-500">
          Paste a job description to save it, then match it against one of your resumes.
        </p>
      </div>

      {/* Create form */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-base font-semibold text-slate-800">
          Add a job description
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {formState.status === "error" && (
            <div role="alert" className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
              {formState.message}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Title */}
            <div>
              <label
                htmlFor="jd-title"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Job title <span className="text-red-500">*</span>
              </label>
              <input
                id="jd-title"
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Senior Python Developer"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Company */}
            <div>
              <label
                htmlFor="jd-company"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Company <span className="text-slate-400 text-xs">(optional)</span>
              </label>
              <input
                id="jd-company"
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="e.g. Acme Corp"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Description text */}
          <div>
            <label
              htmlFor="jd-text"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Job description <span className="text-red-500">*</span>
            </label>
            <textarea
              id="jd-text"
              required
              rows={8}
              value={descriptionText}
              onChange={(e) => setDescriptionText(e.target.value)}
              placeholder="Paste the full job description here…"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-y"
            />
            <p className="mt-1 text-xs text-slate-400">
              Minimum 20 characters. The more detail you include, the more accurate the skill match.
            </p>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isSubmitting || !title.trim() || !descriptionText.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? "Saving…" : "Save job description"}
            </button>
          </div>
        </form>
      </section>

      {/* Job description list */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-slate-700">
          Saved job descriptions
        </h2>
        <JobDescriptionList
          state={listState}
          onRetry={loadList}
          onView={handleView}
          onEdit={handleEdit}
          onDelete={handleDeleteClick}
        />
      </section>

      {/* ── Detail modal ── */}
      {detailJd && (
        <JdDetailModal
          jd={detailJd}
          state={detailState}
          onClose={closeDetail}
        />
      )}

      {/* ── Edit modal ── */}
      {editJd && (
        <JdEditModal
          state={editState}
          editTitle={editTitle}
          editCompany={editCompany}
          editDescriptionText={editDescriptionText}
          onTitleChange={setEditTitle}
          onCompanyChange={setEditCompany}
          onDescriptionChange={setEditDescriptionText}
          onSubmit={handleEditSubmit}
          onClose={closeEdit}
        />
      )}

      {/* ── Delete confirmation dialog ── */}
      {deleteJd && (
        <DeleteConfirmDialog
          jd={deleteJd}
          state={deleteState}
          onConfirm={confirmDelete}
          onCancel={cancelDelete}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// List sub-component
// ---------------------------------------------------------------------------

function JobDescriptionList({
  state,
  onRetry,
  onView,
  onEdit,
  onDelete,
}: {
  state: ListState;
  onRetry: () => void;
  onView: (jd: JobDescriptionResponse) => void;
  onEdit: (jd: JobDescriptionResponse) => void;
  onDelete: (jd: JobDescriptionResponse) => void;
}) {
  if (state.status === "loading") {
    return (
      <div className="flex items-center justify-center py-16">
        <div
          className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
          role="status"
          aria-label="Loading job descriptions"
        />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-sm font-medium text-red-700">{state.message}</p>
        <button
          onClick={onRetry}
          className="mt-3 rounded-lg bg-red-100 px-4 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (state.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center">
        <BriefcaseIcon className="mb-3 h-10 w-10 text-slate-300" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-slate-700">No job descriptions yet</h3>
        <p className="mt-1 text-xs text-slate-500">
          Paste a job description above to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {state.data.map((jd) => (
        <JobDescriptionCard
          key={jd.id}
          jd={jd}
          onView={onView}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

function JobDescriptionCard({
  jd,
  onView,
  onEdit,
  onDelete,
}: {
  jd: JobDescriptionResponse;
  onView: (jd: JobDescriptionResponse) => void;
  onEdit: (jd: JobDescriptionResponse) => void;
  onDelete: (jd: JobDescriptionResponse) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm hover:border-indigo-200 transition-colors">
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-900 truncate">{jd.title}</p>
        <p className="mt-0.5 text-xs text-slate-500">
          {jd.company ? `${jd.company} · ` : ""}Added {formatDate(jd.created_at)}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {/* View */}
        <button
          onClick={() => onView(jd)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
          aria-label={`View ${jd.title}`}
        >
          <EyeIcon className="h-3.5 w-3.5" aria-hidden="true" />
          View
        </button>

        {/* Edit */}
        <button
          onClick={() => onEdit(jd)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
          aria-label={`Edit ${jd.title}`}
        >
          <PencilIcon className="h-3.5 w-3.5" aria-hidden="true" />
          Edit
        </button>

        {/* Delete */}
        <button
          onClick={() => onDelete(jd)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1"
          aria-label={`Delete ${jd.title}`}
        >
          <TrashIcon className="h-3.5 w-3.5" aria-hidden="true" />
          Delete
        </button>

        {/* Match resume link — kept from original */}
        <Link
          to={`/match?jd=${jd.id}`}
          className="ml-1 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
        >
          <ChartIcon className="h-3.5 w-3.5" aria-hidden="true" />
          Match
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------------

function JdDetailModal({
  jd,
  state,
  onClose,
}: {
  jd: JobDescriptionResponse;
  state: DetailState;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Job description details"
    >
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Modal header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3 min-w-0">
            <BriefcaseIcon className="h-6 w-6 shrink-0 text-slate-400" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-slate-900 truncate">
              {jd.title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="ml-4 shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Close"
          >
            <XIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Modal body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {state.status === "loading" && (
            <div className="flex items-center justify-center py-16">
              <div
                className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
                role="status"
                aria-label="Loading job description"
              />
            </div>
          )}

          {state.status === "error" && (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 p-6 text-center"
            >
              <p className="text-sm font-medium text-red-700">{state.message}</p>
              <p className="mt-1 text-xs text-red-500">
                Could not load the job description. Please try again.
              </p>
            </div>
          )}

          {state.status === "success" && (
            <div className="space-y-4">
              {/* Metadata grid */}
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    Title
                  </dt>
                  <dd className="mt-1 text-sm font-medium text-slate-900">
                    {state.data.title}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    Company
                  </dt>
                  <dd className="mt-1 text-sm text-slate-700">
                    {state.data.company || "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    Added
                  </dt>
                  <dd className="mt-1 text-sm text-slate-700">
                    {formatDateTime(state.data.created_at)}
                  </dd>
                </div>
              </dl>

              {/* Full description text */}
              <div>
                <dt className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Description
                </dt>
                <dd>
                  <pre className="max-h-[50vh] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-800 whitespace-pre-wrap break-words">
                    {state.data.description_text || "No description text available."}
                  </pre>
                </dd>
              </div>
            </div>
          )}
        </div>

        {/* Modal footer */}
        <div className="flex justify-end border-t border-slate-200 px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Edit modal
// ---------------------------------------------------------------------------

function JdEditModal({
  state,
  editTitle,
  editCompany,
  editDescriptionText,
  onTitleChange,
  onCompanyChange,
  onDescriptionChange,
  onSubmit,
  onClose,
}: {
  state: EditState;
  editTitle: string;
  editCompany: string;
  editDescriptionText: string;
  onTitleChange: (v: string) => void;
  onCompanyChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onSubmit: (e: FormEvent) => void;
  onClose: () => void;
}) {
  const isLoading = state.status === "loading";
  const isSubmitting = state.status === "submitting";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Edit job description"
    >
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Modal header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3 min-w-0">
            <PencilIcon className="h-6 w-6 shrink-0 text-indigo-500" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-slate-900 truncate">
              Edit job description
            </h2>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="ml-4 shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-60"
            aria-label="Close"
          >
            <XIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Modal body */}
        <form onSubmit={onSubmit} className="flex flex-1 flex-col overflow-hidden" noValidate>
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {state.status === "error" && (
              <div role="alert" className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
                {state.message}
              </div>
            )}

            {isLoading ? (
              <div className="flex items-center justify-center py-16">
                <div
                  className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
                  role="status"
                  aria-label="Loading job description for editing"
                />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  {/* Title */}
                  <div>
                    <label
                      htmlFor="edit-jd-title"
                      className="mb-1 block text-sm font-medium text-slate-700"
                    >
                      Job title <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="edit-jd-title"
                      type="text"
                      required
                      value={editTitle}
                      onChange={(e) => onTitleChange(e.target.value)}
                      placeholder="e.g. Senior Python Developer"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>

                  {/* Company */}
                  <div>
                    <label
                      htmlFor="edit-jd-company"
                      className="mb-1 block text-sm font-medium text-slate-700"
                    >
                      Company <span className="text-slate-400 text-xs">(optional)</span>
                    </label>
                    <input
                      id="edit-jd-company"
                      type="text"
                      value={editCompany}
                      onChange={(e) => onCompanyChange(e.target.value)}
                      placeholder="e.g. Acme Corp"
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                {/* Description text */}
                <div>
                  <label
                    htmlFor="edit-jd-text"
                    className="mb-1 block text-sm font-medium text-slate-700"
                  >
                    Job description <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    id="edit-jd-text"
                    required
                    rows={8}
                    value={editDescriptionText}
                    onChange={(e) => onDescriptionChange(e.target.value)}
                    placeholder="Paste the full job description here…"
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-y"
                  />
                  <p className="mt-1 text-xs text-slate-400">
                    Minimum 20 characters. The more detail you include, the more accurate the skill match.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Modal footer */}
          <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || isLoading || !editTitle.trim() || !editDescriptionText.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? (
                <>
                  <div
                    className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
                    aria-hidden="true"
                  />
                  Saving…
                </>
              ) : (
                "Save changes"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Delete confirmation dialog
// ---------------------------------------------------------------------------

function DeleteConfirmDialog({
  jd,
  state,
  onConfirm,
  onCancel,
}: {
  jd: JobDescriptionResponse;
  state: DeleteState;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const isDeleting = state.status === "deleting";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="alertdialog"
      aria-modal="true"
      aria-label="Delete job description confirmation"
    >
      <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Dialog header */}
        <div className="flex items-start gap-3 px-6 py-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
            <TrashIcon className="h-5 w-5 text-red-600" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-900">
              Delete job description?
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              You are about to delete{" "}
              <span className="font-medium text-slate-900">
                {jd.title}
              </span>
              {jd.company ? ` at ${jd.company}` : ""}. This action cannot be undone.
            </p>
          </div>
        </div>

        {/* Error message */}
        {state.status === "error" && (
          <div role="alert" className="mx-6 mb-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {state.message}
          </div>
        )}

        {/* Dialog footer */}
        <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 transition-colors disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
          >
            {isDeleting ? (
              <>
                <div
                  className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
                  aria-hidden="true"
                />
                Deleting…
              </>
            ) : (
              "Delete"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline SVG icons
// ---------------------------------------------------------------------------

function BriefcaseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M20.25 14.15v4.073a2.25 2.25 0 01-2.25 2.25h-12a2.25 2.25 0 01-2.25-2.25V7.5a2.25 2.25 0 012.25-2.25h1.5m9 0h1.5a2.25 2.25 0 012.25 2.25v.75M9 7.5V6a3 3 0 013-3h0a3 3 0 013 3v1.5M9 7.5h6" />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
    </svg>
  );
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
