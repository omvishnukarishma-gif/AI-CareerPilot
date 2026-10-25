/**
 * JobApplicationsPage
 *
 * A job-application tracker.  Lets the user create, edit, delete, search,
 * filter and sort their job applications.
 *
 * States:
 *   - List: loading / error / empty / success
 *   - Create form: idle / submitting / error (inline expandable section)
 *   - Edit: modal overlay with its own form state
 *   - Delete: confirmation dialog (modal)
 *
 * Backend endpoints (all require auth):
 *   POST   /api/v1/job-applications
 *   GET    /api/v1/job-applications
 *   GET    /api/v1/job-applications/{id}
 *   PUT    /api/v1/job-applications/{id}
 *   DELETE /api/v1/job-applications/{id}
 */

import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";
import { jobApplicationApi } from "../services/api";
import type {
  JobApplicationCreate,
  JobApplicationResponse,
  JobApplicationStatus,
  JobApplicationUpdate,
} from "../types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ListState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: JobApplicationResponse[] };

type FormState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "error"; message: string };

type SortOrder = "newest" | "oldest";

type StatusFilter = "all" | JobApplicationStatus;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_OPTIONS: JobApplicationStatus[] = [
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "archived",
];

const STATUS_LABELS: Record<JobApplicationStatus, string> = {
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
  archived: "Archived",
};

const STATUS_BADGE_CLASSES: Record<JobApplicationStatus, string> = {
  applied: "bg-blue-100 text-blue-700",
  interviewing: "bg-amber-100 text-amber-700",
  offer: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
  archived: "bg-slate-100 text-slate-600",
};

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

function formatDateInput(iso: string | null): string {
  if (!iso) return "";
  try {
    // The API returns ISO strings; the <input type="date"> expects yyyy-mm-dd.
    return new Date(iso).toISOString().slice(0, 10);
  } catch {
    return "";
  }
}

function statusBadgeClass(status: JobApplicationStatus): string {
  return `inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE_CLASSES[status]}`;
}

// ---------------------------------------------------------------------------
// Form field shape (shared by create and edit forms)
// ---------------------------------------------------------------------------

interface FormFields {
  company_name: string;
  role_title: string;
  status: JobApplicationStatus;
  job_url: string;
  notes: string;
  deadline: string; // yyyy-mm-dd from <input type="date">, "" if empty
}

const EMPTY_FORM: FormFields = {
  company_name: "",
  role_title: "",
  status: "applied",
  job_url: "",
  notes: "",
  deadline: "",
};

function applicationToForm(app: JobApplicationResponse): FormFields {
  return {
    company_name: app.company_name,
    role_title: app.role_title,
    status: app.status,
    job_url: app.job_url ?? "",
    notes: app.notes ?? "",
    deadline: formatDateInput(app.deadline),
  };
}

function fieldsToCreate(fields: FormFields): JobApplicationCreate {
  return {
    company_name: fields.company_name.trim(),
    role_title: fields.role_title.trim(),
    status: fields.status,
    job_url: fields.job_url.trim() || null,
    notes: fields.notes.trim() || null,
    deadline: fields.deadline || null,
  };
}

function fieldsToUpdate(fields: FormFields): JobApplicationUpdate {
  return {
    company_name: fields.company_name.trim(),
    role_title: fields.role_title.trim(),
    status: fields.status,
    job_url: fields.job_url.trim() || null,
    notes: fields.notes.trim() || null,
    deadline: fields.deadline || null,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function JobApplicationsPage() {
  // List state
  const [listState, setListState] = useState<ListState>({ status: "loading" });

  // Create form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState<FormFields>(EMPTY_FORM);
  const [createFormState, setCreateFormState] = useState<FormState>({ status: "idle" });

  // Edit state — which application is being edited (modal)
  const [editing, setEditing] = useState<JobApplicationResponse | null>(null);
  const [editForm, setEditForm] = useState<FormFields>(EMPTY_FORM);
  const [editFormState, setEditFormState] = useState<FormState>({ status: "idle" });

  // Delete confirmation state
  const [deleteTarget, setDeleteTarget] = useState<JobApplicationResponse | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Toolbar state
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("newest");

  // -------------------------------------------------------------------------
  // Data loading
  // -------------------------------------------------------------------------

  useEffect(() => {
    loadList();
  }, []);

  function loadList() {
    setListState({ status: "loading" });
    jobApplicationApi
      .list()
      .then((data) => setListState({ status: "success", data }))
      .catch((err: unknown) =>
        setListState({
          status: "error",
          message:
            err instanceof Error ? err.message : "Failed to load job applications.",
        })
      );
  }

  // -------------------------------------------------------------------------
  // Create form handlers
  // -------------------------------------------------------------------------

  function handleCreateFieldChange(
    e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) {
    const { name, value } = e.target;
    setCreateForm((prev) => ({ ...prev, [name]: value }));
  }

  async function handleCreateSubmit(e: FormEvent) {
    e.preventDefault();
    if (!createForm.company_name.trim() || !createForm.role_title.trim()) {
      setCreateFormState({
        status: "error",
        message: "Company name and role title are required.",
      });
      return;
    }

    setCreateFormState({ status: "submitting" });
    try {
      await jobApplicationApi.create(fieldsToCreate(createForm));
      setCreateForm(EMPTY_FORM);
      setCreateFormState({ status: "idle" });
      setShowCreateForm(false);
      loadList();
    } catch (err) {
      setCreateFormState({
        status: "error",
        message:
          err instanceof Error ? err.message : "Failed to create application.",
      });
    }
  }

  function handleCreateCancel() {
    setShowCreateForm(false);
    setCreateForm(EMPTY_FORM);
    setCreateFormState({ status: "idle" });
  }

  // -------------------------------------------------------------------------
  // Edit handlers
  // -------------------------------------------------------------------------

  function openEdit(app: JobApplicationResponse) {
    setEditing(app);
    setEditForm(applicationToForm(app));
    setEditFormState({ status: "idle" });
  }

  function handleEditFieldChange(
    e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) {
    const { name, value } = e.target;
    setEditForm((prev) => ({ ...prev, [name]: value }));
  }

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    if (!editForm.company_name.trim() || !editForm.role_title.trim()) {
      setEditFormState({
        status: "error",
        message: "Company name and role title are required.",
      });
      return;
    }

    setEditFormState({ status: "submitting" });
    try {
      await jobApplicationApi.update(editing.id, fieldsToUpdate(editForm));
      closeEdit();
      loadList();
    } catch (err) {
      setEditFormState({
        status: "error",
        message:
          err instanceof Error ? err.message : "Failed to update application.",
      });
    }
  }

  function closeEdit() {
    setEditing(null);
    setEditForm(EMPTY_FORM);
    setEditFormState({ status: "idle" });
  }

  // -------------------------------------------------------------------------
  // Delete handlers
  // -------------------------------------------------------------------------

  function openDelete(app: JobApplicationResponse) {
    setDeleteTarget(app);
    setDeleting(false);
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await jobApplicationApi.delete(deleteTarget.id);
      setDeleteTarget(null);
      setDeleting(false);
      loadList();
    } catch (err) {
      setDeleting(false);
      // Keep the dialog open but surface the error
      console.error(
        "Delete failed:",
        err instanceof Error ? err.message : "Unknown error"
      );
    }
  }

  function cancelDelete() {
    setDeleteTarget(null);
    setDeleting(false);
  }

  // -------------------------------------------------------------------------
  // Filtered + sorted list (client-side)
  // -------------------------------------------------------------------------

  const visibleApplications = useMemo(() => {
    if (listState.status !== "success") return [];

    const term = search.trim().toLowerCase();

    return listState.data
      .filter((app) => {
        // Status filter
        if (statusFilter !== "all" && app.status !== statusFilter) return false;
        // Search filter (company or role)
        if (term) {
          const haystack =
            `${app.company_name} ${app.role_title}`.toLowerCase();
          if (!haystack.includes(term)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const dateA = new Date(a.created_at).getTime();
        const dateB = new Date(b.created_at).getTime();
        return sortOrder === "newest" ? dateB - dateA : dateA - dateB;
      });
  }, [listState, search, statusFilter, sortOrder]);

  const hasFilters = search.trim() !== "" || statusFilter !== "all";

  function clearFilters() {
    setSearch("");
    setStatusFilter("all");
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Job Applications</h1>
          <p className="mt-1 text-sm text-slate-500">
            Track your job applications, deadlines and statuses.
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm((v) => !v)}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition-colors"
        >
          <PlusIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
          {showCreateForm ? "Close form" : "Add application"}
        </button>
      </div>

      {/* Create form — inline expandable section */}
      {showCreateForm && (
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-slate-800">
            Add a new application
          </h2>
          <form onSubmit={handleCreateSubmit} className="space-y-4" noValidate>
            {createFormState.status === "error" && (
              <div
                role="alert"
                className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700"
              >
                {createFormState.message}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              {/* Company name */}
              <div>
                <label
                  htmlFor="create-company-name"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Company name <span className="text-red-500">*</span>
                </label>
                <input
                  id="create-company-name"
                  name="company_name"
                  type="text"
                  required
                  value={createForm.company_name}
                  onChange={handleCreateFieldChange}
                  placeholder="e.g. Acme Corp"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Role title */}
              <div>
                <label
                  htmlFor="create-role-title"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Role title <span className="text-red-500">*</span>
                </label>
                <input
                  id="create-role-title"
                  name="role_title"
                  type="text"
                  required
                  value={createForm.role_title}
                  onChange={handleCreateFieldChange}
                  placeholder="e.g. Senior Python Developer"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {/* Status */}
              <div>
                <label
                  htmlFor="create-status"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Status
                </label>
                <select
                  id="create-status"
                  name="status"
                  value={createForm.status}
                  onChange={handleCreateFieldChange}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
              </div>

              {/* Job URL */}
              <div>
                <label
                  htmlFor="create-job-url"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Job URL{" "}
                  <span className="text-xs text-slate-400">(optional)</span>
                </label>
                <input
                  id="create-job-url"
                  name="job_url"
                  type="url"
                  value={createForm.job_url}
                  onChange={handleCreateFieldChange}
                  placeholder="https://…"
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              {/* Deadline */}
              <div>
                <label
                  htmlFor="create-deadline"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Deadline{" "}
                  <span className="text-xs text-slate-400">(optional)</span>
                </label>
                <input
                  id="create-deadline"
                  name="deadline"
                  type="date"
                  value={createForm.deadline}
                  onChange={handleCreateFieldChange}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Notes */}
            <div>
              <label
                htmlFor="create-notes"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Notes{" "}
                <span className="text-xs text-slate-400">(optional)</span>
              </label>
              <textarea
                id="create-notes"
                name="notes"
                rows={3}
                value={createForm.notes}
                onChange={handleCreateFieldChange}
                placeholder="Any notes about this application…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-y"
              />
            </div>

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={handleCreateCancel}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createFormState.status === "submitting"}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
              >
                {createFormState.status === "submitting"
                  ? "Saving…"
                  : "Save application"}
              </button>
            </div>
          </form>
        </section>
      )}

      {/* Toolbar — search, filter, sort */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {/* Search */}
        <div className="relative flex-1">
          <SearchIcon
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by company or role…"
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
        </div>

        {/* Status filter */}
        <div>
          <label htmlFor="status-filter" className="sr-only">
            Filter by status
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="all">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </div>

        {/* Sort toggle */}
        <button
          type="button"
          onClick={() =>
            setSortOrder((prev) => (prev === "newest" ? "oldest" : "newest"))
          }
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          aria-label={`Sort by created date, currently ${sortOrder}`}
        >
          <SortIcon className="h-4 w-4 text-slate-400" aria-hidden="true" />
          {sortOrder === "newest" ? "Newest first" : "Oldest first"}
        </button>
      </div>

      {/* Application list / states */}
      <ApplicationList
        state={listState}
        visible={visibleApplications}
        hasFilters={hasFilters}
        onRetry={loadList}
        onClearFilters={clearFilters}
        onEdit={openEdit}
        onDelete={openDelete}
      />

      {/* Edit modal */}
      {editing && (
        <EditModal
          app={editing}
          form={editForm}
          formState={editFormState}
          onChange={handleEditFieldChange}
          onSubmit={handleEditSubmit}
          onCancel={closeEdit}
        />
      )}

      {/* Delete confirmation modal */}
      {deleteTarget && (
        <DeleteDialog
          app={deleteTarget}
          deleting={deleting}
          onConfirm={confirmDelete}
          onCancel={cancelDelete}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ApplicationList — handles loading / error / empty / success states
// ---------------------------------------------------------------------------

function ApplicationList({
  state,
  visible,
  hasFilters,
  onRetry,
  onClearFilters,
  onEdit,
  onDelete,
}: {
  state: ListState;
  visible: JobApplicationResponse[];
  hasFilters: boolean;
  onRetry: () => void;
  onClearFilters: () => void;
  onEdit: (app: JobApplicationResponse) => void;
  onDelete: (app: JobApplicationResponse) => void;
}) {
  if (state.status === "loading") {
    return (
      <div className="flex items-center justify-center py-24">
        <div
          className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
          role="status"
          aria-label="Loading job applications"
        />
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div
        role="alert"
        className="rounded-xl border border-red-200 bg-red-50 p-6 text-center"
      >
        <ErrorIcon
          className="mx-auto mb-3 h-8 w-8 text-red-400"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-red-700">{state.message}</p>
        <p className="mt-1 text-xs text-red-500">
          Make sure the backend is running and you&apos;re logged in.
        </p>
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg bg-red-100 px-4 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (visible.length === 0) {
    return hasFilters ? (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white py-12 text-center">
        <SearchIcon
          className="mb-3 h-10 w-10 text-slate-300"
          aria-hidden="true"
        />
        <h3 className="text-sm font-semibold text-slate-700">No matches found</h3>
        <p className="mt-1 text-xs text-slate-500">
          No applications match your search or filter.
        </p>
        <button
          onClick={onClearFilters}
          className="mt-4 rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700 transition-colors"
        >
          Clear filters
        </button>
      </div>
    ) : (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center">
        <BriefcaseIcon
          className="mb-4 h-12 w-12 text-slate-300"
          aria-hidden="true"
        />
        <h3 className="text-base font-semibold text-slate-700">
          No applications yet
        </h3>
        <p className="mt-1 max-w-xs text-sm text-slate-500">
          Click “Add application” to start tracking your job applications.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead>
            <tr className="bg-slate-50">
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Company
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Role
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Status
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Deadline
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Added
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visible.map((app) => (
              <ApplicationRow
                key={app.id}
                app={app}
                onEdit={onEdit}
                onDelete={onDelete}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ApplicationRow — a single table row
// ---------------------------------------------------------------------------

function ApplicationRow({
  app,
  onEdit,
  onDelete,
}: {
  app: JobApplicationResponse;
  onEdit: (app: JobApplicationResponse) => void;
  onDelete: (app: JobApplicationResponse) => void;
}) {
  return (
    <tr className="hover:bg-slate-50 transition-colors">
      <td className="px-6 py-4">
        <div className="flex items-center gap-2">
          <BuildingIcon
            className="h-4 w-4 shrink-0 text-slate-400"
            aria-hidden="true"
          />
          <span className="text-sm font-medium text-slate-900 break-words">
            {app.company_name}
          </span>
        </div>
      </td>
      <td className="px-6 py-4">
        <span className="text-sm text-slate-700 break-words">
          {app.role_title}
        </span>
        {app.job_url && (
          <a
            href={app.job_url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 inline-flex items-center text-indigo-600 hover:text-indigo-800 hover:underline"
            aria-label="Open job posting"
          >
            <ExternalLinkIcon className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        )}
      </td>
      <td className="px-6 py-4">
        <span className={statusBadgeClass(app.status)}>
          {STATUS_LABELS[app.status]}
        </span>
      </td>
      <td className="px-6 py-4 text-sm text-slate-500">
        {app.deadline ? formatDate(app.deadline) : "—"}
      </td>
      <td className="px-6 py-4 text-sm text-slate-500">
        {formatDate(app.created_at)}
      </td>
      <td className="px-6 py-4 text-right whitespace-nowrap">
        <button
          type="button"
          onClick={() => onEdit(app)}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-50 transition-colors"
          aria-label={`Edit ${app.company_name} application`}
        >
          <PencilIcon className="h-3.5 w-3.5" aria-hidden="true" />
          Edit
        </button>
        <button
          type="button"
          onClick={() => onDelete(app)}
          className="ml-2 inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors"
          aria-label={`Delete ${app.company_name} application`}
        >
          <TrashIcon className="h-3.5 w-3.5" aria-hidden="true" />
          Delete
        </button>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// EditModal — overlay with the edit form
// ---------------------------------------------------------------------------

function EditModal({
  app,
  form,
  formState,
  onChange,
  onSubmit,
  onCancel,
}: {
  app: JobApplicationResponse;
  form: FormFields;
  formState: FormState;
  onChange: (
    e: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => void;
  onSubmit: (e: FormEvent) => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Edit application for ${app.company_name}`}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/50"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Modal panel */}
      <div className="relative w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-800">
            Edit application
          </h2>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            aria-label="Close edit dialog"
          >
            <XIcon className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {formState.status === "error" && (
            <div
              role="alert"
              className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {formState.message}
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Company name */}
            <div>
              <label
                htmlFor="edit-company-name"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Company name <span className="text-red-500">*</span>
              </label>
              <input
                id="edit-company-name"
                name="company_name"
                type="text"
                required
                value={form.company_name}
                onChange={onChange}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Role title */}
            <div>
              <label
                htmlFor="edit-role-title"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Role title <span className="text-red-500">*</span>
              </label>
              <input
                id="edit-role-title"
                name="role_title"
                type="text"
                required
                value={form.role_title}
                onChange={onChange}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            {/* Status */}
            <div>
              <label
                htmlFor="edit-status"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Status
              </label>
              <select
                id="edit-status"
                name="status"
                value={form.status}
                onChange={onChange}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </option>
                ))}
              </select>
            </div>

            {/* Job URL */}
            <div>
              <label
                htmlFor="edit-job-url"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Job URL{" "}
                <span className="text-xs text-slate-400">(optional)</span>
              </label>
              <input
                id="edit-job-url"
                name="job_url"
                type="url"
                value={form.job_url}
                onChange={onChange}
                placeholder="https://…"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            {/* Deadline */}
            <div>
              <label
                htmlFor="edit-deadline"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Deadline{" "}
                <span className="text-xs text-slate-400">(optional)</span>
              </label>
              <input
                id="edit-deadline"
                name="deadline"
                type="date"
                value={form.deadline}
                onChange={onChange}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Notes */}
          <div>
            <label
              htmlFor="edit-notes"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Notes{" "}
              <span className="text-xs text-slate-400">(optional)</span>
            </label>
            <textarea
              id="edit-notes"
              name="notes"
              rows={3}
              value={form.notes}
              onChange={onChange}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-y"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={formState.status === "submitting"}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
            >
              {formState.status === "submitting" ? "Saving…" : "Save changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DeleteDialog — confirmation modal
// ---------------------------------------------------------------------------

function DeleteDialog({
  app,
  deleting,
  onConfirm,
  onCancel,
}: {
  app: JobApplicationResponse;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Confirm deletion"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-slate-900/50"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Modal panel */}
      <div className="relative w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-xl text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
          <TrashIcon className="h-6 w-6 text-red-600" aria-hidden="true" />
        </div>
        <h2 className="text-base font-semibold text-slate-900">
          Delete application?
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          Are you sure you want to delete the application for{" "}
          <span className="font-medium text-slate-700">{app.company_name}</span> —{" "}
          <span className="font-medium text-slate-700">{app.role_title}</span>?
          This action cannot be undone.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={deleting}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={deleting}
            className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
          >
            {deleting ? (
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

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 4.5v15m7.5-7.5h-15"
      />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
      />
    </svg>
  );
}

function SortIcon({ className }: { className?: string }) {
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
        d="M3 7.5L7.5 3m0 0L12 7.5M7.5 3v18M21 16.5L16.5 21m0 0L12 16.5m4.5 4.5V3"
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

function BuildingIcon({ className }: { className?: string }) {
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
        d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21"
      />
    </svg>
  );
}

function ExternalLinkIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
      />
    </svg>
  );
}

function PencilIcon({ className }: { className?: string }) {
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
        d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125"
      />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
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
        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m7.228 0V5a2.25 2.25 0 012.25-2.25h2a2.25 2.25 0 012.25 2.25v.75M6.75 5.79v-.75A2.25 2.25 0 019 3h6a2.25 2.25 0 012.25 2.25v.75"
      />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function ErrorIcon({ className }: { className?: string }) {
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
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
      />
    </svg>
  );
}
