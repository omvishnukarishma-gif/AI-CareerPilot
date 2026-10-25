/**
 * ResumesPage
 *
 * Lists the authenticated user's uploaded resumes and provides a file-picker
 * to upload new PDF or DOCX resumes.  Each row has View and Delete actions.
 *
 * Backend rules enforced / respected:
 *   - Accepted file types: .pdf and .docx only (extension + MIME type)
 *   - Maximum file size: 5 MB (settings.max_upload_size_mb default)
 *   - Upload field name: "file" (matches UploadFile parameter in backend)
 *   - Response shape: ResumeResponse (id, user_id, file_name, file_type,
 *     created_at, updated_at) — content_text is fetched on demand via GET
 *
 * Upload flow:
 *   1. User clicks "Upload resume" → hidden <input type="file"> is opened.
 *   2. File is validated client-side (type, size) for fast feedback.
 *   3. Upload starts; a progress bar tracks the XHR upload percentage.
 *   4. On success the resume list is refreshed automatically.
 *   5. Clear error messages are shown for all backend validation failures.
 *
 * View flow:
 *   1. User clicks "View" on a row → resumeApi.get(id) is called.
 *   2. A modal opens showing file_name, file_type, created_at, and the
 *      full content_text in a scrollable <pre> block.
 *
 * Delete flow:
 *   1. User clicks "Delete" on a row → a confirmation dialog is shown.
 *   2. On confirm, resumeApi.delete(id) is called.
 *   3. On success the list is refreshed.
 */

import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { resumeApi } from "../services/api";
import type { ResumeDetailResponse, ResumeResponse } from "../types/api";

// ---------------------------------------------------------------------------
// Constants — kept in sync with backend settings.max_upload_size_mb = 5
// ---------------------------------------------------------------------------

const MAX_FILE_SIZE_MB = 5;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const ACCEPTED_EXTENSIONS = ["pdf", "docx"];
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
// <input accept="..."> attribute — shows only PDF/DOCX in the file picker
const INPUT_ACCEPT = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ListState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: ResumeResponse[] };

type UploadState =
  | { status: "idle" }
  | { status: "uploading"; progress: number; fileName: string }
  | { status: "success"; fileName: string }
  | { status: "error"; message: string };

/** Modal state for the View action. */
type DetailState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: ResumeDetailResponse };

/** Confirmation dialog state for the Delete action. */
type ConfirmState =
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

function fileTypeBadge(fileType: string): string {
  const upper = fileType.toUpperCase();
  if (upper.includes("PDF")) return "PDF";
  if (upper.includes("DOCX") || upper.includes("WORD")) return "DOCX";
  if (upper.includes("DOC")) return "DOC";
  if (upper.includes("TXT")) return "TXT";
  return upper.slice(0, 6);
}

/** Client-side validation before hitting the network. Returns an error string or null. */
function validateFile(file: File): string | null {
  const ext = file.name.includes(".")
    ? file.name.split(".").pop()?.toLowerCase() ?? ""
    : "";

  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `Unsupported file type ".${ext}". Please upload a PDF or DOCX file.`;
  }

  // Accept generic octet-stream for DOCX since some OS send that
  const mime = file.type.toLowerCase().split(";")[0].trim();
  if (mime && mime !== "application/octet-stream" && !ACCEPTED_MIME_TYPES.includes(mime)) {
    return `Unsupported file type. Please upload a PDF or DOCX file.`;
  }

  if (file.size === 0) {
    return "The selected file is empty. Please choose a different file.";
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return `File exceeds the ${MAX_FILE_SIZE_MB} MB limit. Please choose a smaller file.`;
  }

  return null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ResumesPage() {
  const [listState, setListState] = useState<ListState>({ status: "loading" });
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle" });
  const fileInputRef = useRef<HTMLInputElement>(null);

  // View / detail modal state
  const [detailState, setDetailState] = useState<DetailState>({ status: "idle" });
  const [detailResume, setDetailResume] = useState<ResumeResponse | null>(null);

  // Delete confirmation dialog state
  const [confirmState, setConfirmState] = useState<ConfirmState>({ status: "idle" });
  const [deleteResume, setDeleteResume] = useState<ResumeResponse | null>(null);

  // Load the resume list on mount
  useEffect(() => {
    loadResumes();
  }, []);

  function loadResumes() {
    setListState({ status: "loading" });
    resumeApi
      .list()
      .then((data) => setListState({ status: "success", data }))
      .catch((err: unknown) =>
        setListState({
          status: "error",
          message:
            err instanceof Error ? err.message : "Failed to load resumes.",
        })
      );
  }

  // ── Upload handlers ──

  function handleUploadClick() {
    // Reset the input so selecting the same file again re-triggers onChange
    if (fileInputRef.current) fileInputRef.current.value = "";
    fileInputRef.current?.click();
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side validation for immediate feedback
    const validationError = validateFile(file);
    if (validationError) {
      setUploadState({ status: "error", message: validationError });
      return;
    }

    startUpload(file);
  }

  function startUpload(file: File) {
    setUploadState({ status: "uploading", progress: 0, fileName: file.name });

    resumeApi
      .upload(file, (progress) => {
        setUploadState({ status: "uploading", progress, fileName: file.name });
      })
      .then(() => {
        setUploadState({ status: "success", fileName: file.name });
        // Refresh the list so the newly uploaded resume appears immediately
        loadResumes();
      })
      .catch((err: unknown) => {
        setUploadState({
          status: "error",
          message:
            err instanceof Error ? err.message : "Upload failed. Please try again.",
        });
      });
  }

  function dismissUploadStatus() {
    setUploadState({ status: "idle" });
  }

  // ── View / detail handlers ──

  function handleView(resume: ResumeResponse) {
    setDetailResume(resume);
    setDetailState({ status: "loading" });
    resumeApi
      .get(resume.id)
      .then((data) => setDetailState({ status: "success", data }))
      .catch((err: unknown) =>
        setDetailState({
          status: "error",
          message:
            err instanceof Error ? err.message : "Failed to load resume details.",
        })
      );
  }

  function closeDetail() {
    setDetailState({ status: "idle" });
    setDetailResume(null);
  }

  // ── Delete handlers ──

  function handleDeleteClick(resume: ResumeResponse) {
    setDeleteResume(resume);
    setConfirmState({ status: "idle" });
  }

  function confirmDelete() {
    if (!deleteResume) return;
    setConfirmState({ status: "deleting" });
    resumeApi
      .delete(deleteResume.id)
      .then(() => {
        setConfirmState({ status: "idle" });
        setDeleteResume(null);
        loadResumes();
      })
      .catch((err: unknown) =>
        setConfirmState({
          status: "error",
          message:
            err instanceof Error ? err.message : "Failed to delete resume.",
        })
      );
  }

  function cancelDelete() {
    setConfirmState({ status: "idle" });
    setDeleteResume(null);
  }

  const isUploading = uploadState.status === "uploading";

  return (
    <div className="space-y-6">
      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Resumes</h1>
          <p className="mt-1 text-sm text-slate-500">
            Manage your uploaded resumes.
          </p>
        </div>

        {/* Upload button — disabled while an upload is in progress */}
        <button
          onClick={handleUploadClick}
          disabled={isUploading}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
          aria-busy={isUploading}
        >
          <UploadIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
          {isUploading ? "Uploading…" : "Upload resume"}
        </button>

        {/* Hidden file input — triggered programmatically */}
        <input
          ref={fileInputRef}
          type="file"
          accept={INPUT_ACCEPT}
          className="sr-only"
          aria-hidden="true"
          tabIndex={-1}
          onChange={handleFileChange}
        />
      </div>

      {/* ── Upload status banner ── */}
      {uploadState.status === "uploading" && (
        <UploadProgress
          fileName={uploadState.fileName}
          progress={uploadState.progress}
        />
      )}

      {uploadState.status === "success" && (
        <UploadSuccessBanner
          fileName={uploadState.fileName}
          onDismiss={dismissUploadStatus}
        />
      )}

      {uploadState.status === "error" && (
        <UploadErrorBanner
          message={uploadState.message}
          onDismiss={dismissUploadStatus}
        />
      )}

      {/* ── Resume list ── */}
      <ResumeList
        state={listState}
        onRetry={loadResumes}
        onView={handleView}
        onDelete={handleDeleteClick}
      />

      {/* ── Detail modal ── */}
      {detailResume && (
        <ResumeDetailModal
          resume={detailResume}
          state={detailState}
          onClose={closeDetail}
        />
      )}

      {/* ── Delete confirmation dialog ── */}
      {deleteResume && (
        <DeleteConfirmDialog
          resume={deleteResume}
          state={confirmState}
          onConfirm={confirmDelete}
          onCancel={cancelDelete}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload status sub-components
// ---------------------------------------------------------------------------

function UploadProgress({
  fileName,
  progress,
}: {
  fileName: string;
  progress: number;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`Uploading ${fileName}: ${progress}%`}
      className="rounded-xl border border-indigo-200 bg-indigo-50 p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent"
            aria-hidden="true"
          />
          <span className="text-sm font-medium text-indigo-800 truncate">
            Uploading <span className="font-semibold">{fileName}</span>
          </span>
        </div>
        <span className="ml-4 shrink-0 text-sm font-semibold text-indigo-700">
          {progress}%
        </span>
      </div>
      <div
        className="h-1.5 w-full rounded-full bg-indigo-200"
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-1.5 rounded-full bg-indigo-600 transition-all duration-200"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

function UploadSuccessBanner({
  fileName,
  onDismiss,
}: {
  fileName: string;
  onDismiss: () => void;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-start justify-between rounded-xl border border-green-200 bg-green-50 p-4"
    >
      <div className="flex items-center gap-2 min-w-0">
        <CheckIcon className="h-5 w-5 shrink-0 text-green-600" aria-hidden="true" />
        <p className="text-sm font-medium text-green-800">
          <span className="font-semibold truncate">{fileName}</span> uploaded successfully.
        </p>
      </div>
      <button
        onClick={onDismiss}
        className="ml-4 shrink-0 text-green-600 hover:text-green-800 focus:outline-none"
        aria-label="Dismiss"
      >
        <XIcon className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

function UploadErrorBanner({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start justify-between rounded-xl border border-red-200 bg-red-50 p-4"
    >
      <div className="flex items-start gap-2 min-w-0">
        <ErrorIcon className="mt-0.5 h-5 w-5 shrink-0 text-red-500" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium text-red-800">Upload failed</p>
          <p className="mt-0.5 text-sm text-red-700">{message}</p>
        </div>
      </div>
      <button
        onClick={onDismiss}
        className="ml-4 shrink-0 text-red-500 hover:text-red-700 focus:outline-none"
        aria-label="Dismiss"
      >
        <XIcon className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resume list sub-components
// ---------------------------------------------------------------------------

function ResumeList({
  state,
  onRetry,
  onView,
  onDelete,
}: {
  state: ListState;
  onRetry: () => void;
  onView: (resume: ResumeResponse) => void;
  onDelete: (resume: ResumeResponse) => void;
}) {
  if (state.status === "loading") {
    return (
      <div className="flex items-center justify-center py-24">
        <div
          className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent"
          role="status"
          aria-label="Loading resumes"
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
        <ErrorIcon className="mx-auto mb-3 h-8 w-8 text-red-400" aria-hidden="true" />
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

  if (state.data.length === 0) {
    return <EmptyState />;
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
                File name
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Type
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Uploaded
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
              >
                Updated
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
            {state.data.map((resume) => (
              <ResumeRow
                key={resume.id}
                resume={resume}
                onView={onView}
                onDelete={onDelete}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResumeRow({
  resume,
  onView,
  onDelete,
}: {
  resume: ResumeResponse;
  onView: (resume: ResumeResponse) => void;
  onDelete: (resume: ResumeResponse) => void;
}) {
  return (
    <tr className="hover:bg-slate-50 transition-colors">
      <td className="px-6 py-4">
        <div className="flex items-center gap-3">
          <DocumentIcon className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
          <span className="text-sm font-medium text-slate-900 break-all">
            {resume.file_name}
          </span>
        </div>
      </td>
      <td className="px-6 py-4">
        <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
          {fileTypeBadge(resume.file_type)}
        </span>
      </td>
      <td className="px-6 py-4 text-sm text-slate-500 whitespace-nowrap">
        {formatDate(resume.created_at)}
      </td>
      <td className="px-6 py-4 text-sm text-slate-500 whitespace-nowrap">
        {formatDate(resume.updated_at)}
      </td>
      <td className="px-6 py-4 text-right whitespace-nowrap">
        <div className="inline-flex items-center gap-2">
          <button
            onClick={() => onView(resume)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1"
            aria-label={`View ${resume.file_name}`}
          >
            <EyeIcon className="h-3.5 w-3.5" aria-hidden="true" />
            View
          </button>
          <button
            onClick={() => onDelete(resume)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 hover:border-red-300 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1"
            aria-label={`Delete ${resume.file_name}`}
          >
            <TrashIcon className="h-3.5 w-3.5" aria-hidden="true" />
            Delete
          </button>
        </div>
      </td>
    </tr>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white py-16 text-center">
      <DocumentIcon className="mb-4 h-12 w-12 text-slate-300" aria-hidden="true" />
      <h3 className="text-base font-semibold text-slate-700">No resumes yet</h3>
      <p className="mt-1 max-w-xs text-sm text-slate-500">
        Upload a PDF or DOCX resume to get started. Your resumes will appear here.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------------

function ResumeDetailModal({
  resume,
  state,
  onClose,
}: {
  resume: ResumeResponse;
  state: DetailState;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Resume details"
    >
      <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Modal header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3 min-w-0">
            <DocumentIcon className="h-6 w-6 shrink-0 text-slate-400" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-slate-900 truncate">
              {resume.file_name}
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
                aria-label="Loading resume details"
              />
            </div>
          )}

          {state.status === "error" && (
            <div
              role="alert"
              className="rounded-xl border border-red-200 bg-red-50 p-6 text-center"
            >
              <ErrorIcon className="mx-auto mb-3 h-8 w-8 text-red-400" aria-hidden="true" />
              <p className="text-sm font-medium text-red-700">{state.message}</p>
              <p className="mt-1 text-xs text-red-500">
                Could not load the resume content. Please try again.
              </p>
            </div>
          )}

          {state.status === "success" && (
            <div className="space-y-4">
              {/* Metadata grid */}
              <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    File name
                  </dt>
                  <dd className="mt-1 text-sm font-medium text-slate-900 break-all">
                    {state.data.file_name}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    File type
                  </dt>
                  <dd className="mt-1">
                    <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
                      {fileTypeBadge(state.data.file_type)}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium uppercase tracking-wider text-slate-500">
                    Uploaded
                  </dt>
                  <dd className="mt-1 text-sm text-slate-700">
                    {formatDateTime(state.data.created_at)}
                  </dd>
                </div>
              </dl>

              {/* Extracted text */}
              <div>
                <dt className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
                  Extracted text
                </dt>
                <dd>
                  <pre className="max-h-[50vh] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-800 whitespace-pre-wrap break-words">
                    {state.data.content_text || "No text was extracted from this file."}
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
// Delete confirmation dialog
// ---------------------------------------------------------------------------

function DeleteConfirmDialog({
  resume,
  state,
  onConfirm,
  onCancel,
}: {
  resume: ResumeResponse;
  state: ConfirmState;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const isDeleting = state.status === "deleting";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="alertdialog"
      aria-modal="true"
      aria-label="Delete resume confirmation"
    >
      <div className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl">
        {/* Dialog header */}
        <div className="flex items-start gap-3 px-6 py-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
            <TrashIcon className="h-5 w-5 text-red-600" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-900">
              Delete resume?
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              You are about to delete{" "}
              <span className="font-medium text-slate-900 break-all">
                {resume.file_name}
              </span>
              . This action cannot be undone.
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

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
      />
    </svg>
  );
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
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
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
      />
    </svg>
  );
}

function EyeIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.5}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
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
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
      />
    </svg>
  );
}
