/**
 * App.tsx — root application component.
 *
 * Sets up the full routing tree:
 *
 *   /              → LandingPage (public)
 *   /login         → LoginPage  (public)
 *   /register      → RegisterPage (public)
 *   /dashboard     → DashboardPage (protected, inside AppLayout)
 *   /resumes       → ResumesPage   (protected, inside AppLayout)
 *   /job-descriptions → JobDescriptionsPage (protected, inside AppLayout)
 *   /applications  → JobApplicationsPage (protected, inside AppLayout)
 *   /match         → MatchPage (protected, inside AppLayout)
 *   /interview     → InterviewPage (protected, inside AppLayout)
 *   /interview/history → InterviewHistoryPage (protected, inside AppLayout)
 *   /settings      → ProfileSettingsPage (protected, inside AppLayout)
 *   *              → redirect to /dashboard
 *
 * AuthProvider wraps the whole tree so every component can call useAuth().
 * BrowserRouter is in main.tsx so this file stays easily testable.
 */

import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ResumesPage } from "./pages/ResumesPage";
import { JobDescriptionsPage } from "./pages/JobDescriptionsPage";
import { JobApplicationsPage } from "./pages/JobApplicationsPage";
import { MatchPage } from "./pages/MatchPage";
import { InterviewPage } from "./pages/InterviewPage";
import { InterviewHistoryPage } from "./pages/InterviewHistoryPage";
import { ProfileSettingsPage } from "./pages/ProfileSettingsPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* ── Public routes ── */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* ── Protected routes (require auth) ── */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/resumes" element={<ResumesPage />} />
            <Route path="/job-descriptions" element={<JobDescriptionsPage />} />
            <Route path="/applications" element={<JobApplicationsPage />} />
            <Route path="/match" element={<MatchPage />} />
            <Route path="/interview" element={<InterviewPage />} />
            <Route path="/interview/history" element={<InterviewHistoryPage />} />
            <Route path="/settings" element={<ProfileSettingsPage />} />
          </Route>
        </Route>

        {/* ── Default / 404 ── */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthProvider>
  );
}
