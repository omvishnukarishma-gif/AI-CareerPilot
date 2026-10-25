/**
 * ProfileSettingsPage
 *
 * Allows the user to update their display name and change their password.
 * Also shows appearance (dark mode) and application info sections.
 */

import { type FormEvent, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { authApi } from "../services/api";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-700 pb-3 last:border-0 last:pb-0">
      <span className="text-sm font-medium text-slate-500 dark:text-slate-400">
        {label}
      </span>
      <span className="text-sm font-semibold text-slate-900 dark:text-slate-200">
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ProfileSettingsPage() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();

  // --- Edit name state ---
  const [nameValue, setNameValue] = useState(user?.full_name ?? "");
  const [nameStatus, setNameStatus] = useState<
    "idle" | "saving" | "success" | "error"
  >("idle");
  const [nameError, setNameError] = useState("");

  // --- Change password state ---
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwStatus, setPwStatus] = useState<
    "idle" | "saving" | "success" | "error"
  >("idle");
  const [pwError, setPwError] = useState("");

  async function handleNameSave(e: FormEvent) {
    e.preventDefault();
    if (!nameValue.trim()) return;
    setNameStatus("saving");
    setNameError("");
    try {
      await authApi.updateMe({ full_name: nameValue.trim() });
      setNameStatus("success");
    } catch (err) {
      setNameError(err instanceof Error ? err.message : "Failed to update name.");
      setNameStatus("error");
    }
  }

  async function handlePasswordSave(e: FormEvent) {
    e.preventDefault();
    if (!currentPw || !newPw) return;
    setPwStatus("saving");
    setPwError("");
    try {
      await authApi.updateMe({ current_password: currentPw, new_password: newPw });
      setPwStatus("success");
      setCurrentPw("");
      setNewPw("");
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "Failed to change password.");
      setPwStatus("error");
    }
  }

  return (
    <div className="space-y-8">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
          Profile &amp; Settings
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your account and preferences.
        </p>
      </div>

      {/* Account info (read-only) */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200">
          Account
        </h2>
        <div className="space-y-4">
          <InfoRow label="Email" value={user?.email ?? "—"} />
          <InfoRow label="Status" value={user?.is_active ? "Active" : "Inactive"} />
        </div>
      </section>

      {/* Edit display name */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200">
          Display name
        </h2>
        <form onSubmit={handleNameSave} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label
              htmlFor="full_name"
              className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1"
            >
              Full name
            </label>
            <input
              id="full_name"
              type="text"
              value={nameValue}
              onChange={(e) => { setNameValue(e.target.value); setNameStatus("idle"); }}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              minLength={1}
              maxLength={255}
              required
            />
          </div>
          <button
            type="submit"
            disabled={nameStatus === "saving"}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
            {nameStatus === "saving" ? "Saving…" : "Save"}
          </button>
        </form>
        {nameStatus === "success" && (
          <p className="mt-2 text-sm text-green-600 dark:text-green-400">Name updated.</p>
        )}
        {nameStatus === "error" && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">{nameError}</p>
        )}
      </section>

      {/* Change password */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200">
          Change password
        </h2>
        <form onSubmit={handlePasswordSave} className="space-y-3">
          <div>
            <label
              htmlFor="current_password"
              className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1"
            >
              Current password
            </label>
            <input
              id="current_password"
              type="password"
              value={currentPw}
              onChange={(e) => { setCurrentPw(e.target.value); setPwStatus("idle"); }}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              required
            />
          </div>
          <div>
            <label
              htmlFor="new_password"
              className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1"
            >
              New password
            </label>
            <input
              id="new_password"
              type="password"
              value={newPw}
              onChange={(e) => { setNewPw(e.target.value); setPwStatus("idle"); }}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100"
              minLength={8}
              required
            />
          </div>
          <button
            type="submit"
            disabled={pwStatus === "saving"}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
            {pwStatus === "saving" ? "Saving…" : "Change password"}
          </button>
        </form>
        {pwStatus === "success" && (
          <p className="mt-2 text-sm text-green-600 dark:text-green-400">Password changed.</p>
        )}
        {pwStatus === "error" && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">{pwError}</p>
        )}
      </section>

      {/* Appearance */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200">
          Appearance
        </h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Dark mode
            </p>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              Toggle between light and dark themes. Your preference is saved.
            </p>
          </div>
          <button
            onClick={toggleTheme}
            role="switch"
            aria-checked={theme === "dark"}
            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${
              theme === "dark" ? "bg-indigo-600" : "bg-slate-200"
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                theme === "dark" ? "translate-x-5" : "translate-x-0"
              }`}
            />
          </button>
        </div>
      </section>

      {/* About */}
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="mb-4 text-base font-semibold text-slate-800 dark:text-slate-200">
          About
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          AI CareerPilot is an intelligent career and job application platform.
          Resume analysis, job matching, interview practice, and application
          tracking — all in one place.
        </p>
        <p className="mt-2 text-xs text-slate-400">
          Set LLM_API_KEY in the backend .env to enable AI-powered features.
          Without a key, all analysis uses deterministic heuristics.
        </p>
      </section>
    </div>
  );
}
