/**
 * API service layer.
 *
 * All network requests go through this module so that:
 *   - The base URL is configured once (via Vite env vars).
 *   - Auth tokens are attached automatically when present.
 *   - Error responses are normalised into thrown Error instances.
 *
 * The Vite dev server proxies /api/* to the backend (see vite.config.ts),
 * so in development we use a relative base URL.  In production the same
 * proxy or a reverse-proxy handles routing.
 *
 * Endpoints:
 *   POST /api/v1/auth/register
 *   POST /api/v1/auth/login
 *   GET  /api/v1/auth/me
 *   POST /api/v1/resumes        (multipart/form-data)
 *   GET  /api/v1/resumes
 *   GET  /api/v1/resumes/{id}
 *   POST /api/v1/job-descriptions
 *   GET  /api/v1/job-descriptions
 *   GET  /api/v1/job-descriptions/{id}
 *   POST /api/v1/matches
 *   GET  /api/v1/matches
 *   GET  /api/v1/matches/{id}
 *   POST /api/v1/interview-sessions
 *   GET  /api/v1/interview-sessions
 *   GET  /api/v1/interview-sessions/{id}
 *   POST /api/v1/interview-sessions/{id}/answers
 *   POST /api/v1/job-applications
 *   GET  /api/v1/job-applications
 *   GET  /api/v1/job-applications/{id}
 *   PUT  /api/v1/job-applications/{id}
 *   DELETE /api/v1/job-applications/{id}
 *   DELETE /api/v1/resumes/{id}
 *   PUT  /api/v1/job-descriptions/{id}
 *   DELETE /api/v1/job-descriptions/{id}
 */

import type {
  JobApplicationCreate,
  JobApplicationResponse,
  JobApplicationUpdate,
  JobDescriptionCreate,
  JobDescriptionDetailResponse,
  JobDescriptionResponse,
  LoginRequest,
  MatchCreate,
  MatchDetailResponse,
  MatchResponse,
  RegisterRequest,
  ResumeDetailResponse,
  ResumeResponse,
  TokenResponse,
  UserResponse,
  UserUpdate,
  AnswerSubmit,
  InterviewSessionCreate,
  InterviewSessionDetailResponse,
  InterviewSessionResponse,
} from "../types/api";

// ---------------------------------------------------------------------------
// Base URL
// ---------------------------------------------------------------------------

// VITE_API_URL is set in .env / .env.example.
// Falls back to the same origin so the Vite proxy works with no config.
const BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

// ---------------------------------------------------------------------------
// Token storage helpers (localStorage — fine for a dev-phase SPA)
// ---------------------------------------------------------------------------

const TOKEN_KEY = "careerpilot_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Core fetch wrapper — JSON requests
// ---------------------------------------------------------------------------

/**
 * Thin wrapper around fetch that:
 *   - Prepends BASE_URL
 *   - Sets Content-Type: application/json for bodies
 *   - Attaches Bearer token from localStorage when present
 *   - Throws a descriptive Error for non-2xx responses
 */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail))
        detail = body.detail.map((e: { msg: string }) => e.msg).join("; ");
    } catch {
      // response body was not JSON — keep the status text
    }
    throw new Error(detail);
  }

  // 204 No Content — return undefined cast to T
  if (response.status === 204) return undefined as unknown as T;

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Multipart fetch wrapper — FormData / file uploads
// ---------------------------------------------------------------------------

/**
 * Like request(), but for multipart/form-data uploads.
 *
 * Content-Type is intentionally NOT set — the browser must set it
 * automatically so it can include the correct multipart boundary string.
 * Manually setting it (even to "multipart/form-data") breaks the boundary
 * and causes the server to reject the request with a 422.
 */
async function requestFormData<T>(
  path: string,
  body: FormData,
  onProgress?: (percent: number) => void
): Promise<T> {
  const token = getStoredToken();

  // Use XMLHttpRequest when a progress callback is supplied so we can track
  // upload bytes.  Otherwise fall back to a plain fetch call.
  if (onProgress) {
    return new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE_URL}${path}`);

      if (token) {
        xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      }

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText) as T);
          } catch {
            reject(new Error("Invalid JSON in server response"));
          }
        } else {
          let detail = `${xhr.status} ${xhr.statusText}`;
          try {
            const body = JSON.parse(xhr.responseText) as {
              detail?: string | { msg: string }[];
            };
            if (typeof body.detail === "string") detail = body.detail;
            else if (Array.isArray(body.detail))
              detail = body.detail.map((e) => e.msg).join("; ");
          } catch {
            // keep status text
          }
          reject(new Error(detail));
        }
      });

      xhr.addEventListener("error", () =>
        reject(new Error("Network error during upload"))
      );
      xhr.addEventListener("abort", () =>
        reject(new Error("Upload aborted"))
      );

      xhr.send(body);
    });
  }

  // No progress tracking — plain fetch is simpler
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers,
    body,
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const errBody = await response.json();
      if (typeof errBody.detail === "string") detail = errBody.detail;
      else if (Array.isArray(errBody.detail))
        detail = errBody.detail.map((e: { msg: string }) => e.msg).join("; ");
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------------

export const authApi = {
  register(body: RegisterRequest): Promise<UserResponse> {
    return request<UserResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  login(body: LoginRequest): Promise<TokenResponse> {
    return request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  me(): Promise<UserResponse> {
    return request<UserResponse>("/auth/me");
  },

  updateMe(body: UserUpdate): Promise<UserResponse> {
    return request<UserResponse>("/auth/me", {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },
};

// ---------------------------------------------------------------------------
// Resume endpoints
// ---------------------------------------------------------------------------

export const resumeApi = {
  list(): Promise<ResumeResponse[]> {
    return request<ResumeResponse[]>("/resumes");
  },

  get(id: number): Promise<ResumeDetailResponse> {
    return request<ResumeDetailResponse>(`/resumes/${id}`);
  },

  /** DELETE /api/v1/resumes/{id} — deletes DB record + physical file. */
  delete(id: number): Promise<void> {
    return request<void>(`/resumes/${id}`, { method: "DELETE" });
  },

  /**
   * Upload a resume file (PDF or DOCX, max 5 MB).
   *
   * Uses FormData so the browser sets the correct Content-Type boundary.
   * The backend field name is "file" — changing it breaks the endpoint.
   *
   * @param file       The File object selected by the user.
   * @param onProgress Optional callback receiving 0–100 upload percent.
   */
  upload(file: File, onProgress?: (percent: number) => void): Promise<ResumeResponse> {
    const form = new FormData();
    form.append("file", file);
    return requestFormData<ResumeResponse>("/resumes", form, onProgress);
  },
};

// ---------------------------------------------------------------------------
// Job Description endpoints
// ---------------------------------------------------------------------------

export const jobDescriptionApi = {
  create(body: JobDescriptionCreate): Promise<JobDescriptionDetailResponse> {
    return request<JobDescriptionDetailResponse>("/job-descriptions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  list(): Promise<JobDescriptionResponse[]> {
    return request<JobDescriptionResponse[]>("/job-descriptions");
  },

  get(id: number): Promise<JobDescriptionDetailResponse> {
    return request<JobDescriptionDetailResponse>(`/job-descriptions/${id}`);
  },

  /** PUT /api/v1/job-descriptions/{id} — full replacement update. */
  update(id: number, body: JobDescriptionCreate): Promise<JobDescriptionDetailResponse> {
    return request<JobDescriptionDetailResponse>(`/job-descriptions/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  /** DELETE /api/v1/job-descriptions/{id} */
  delete(id: number): Promise<void> {
    return request<void>(`/job-descriptions/${id}`, { method: "DELETE" });
  },
};

// ---------------------------------------------------------------------------
// Match endpoints
// ---------------------------------------------------------------------------

export const matchApi = {
  create(body: MatchCreate): Promise<MatchDetailResponse> {
    return request<MatchDetailResponse>("/matches", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  list(): Promise<MatchResponse[]> {
    return request<MatchResponse[]>("/matches");
  },

  get(id: number): Promise<MatchDetailResponse> {
    return request<MatchDetailResponse>(`/matches/${id}`);
  },
};

// ---------------------------------------------------------------------------
// Interview Session endpoints
// ---------------------------------------------------------------------------

export const interviewApi = {
  /**
   * Start a new interview-practice session.
   * Generates questions based on role, optional JD, and optional resume.
   */
  create(body: InterviewSessionCreate): Promise<InterviewSessionDetailResponse> {
    return request<InterviewSessionDetailResponse>("/interview-sessions", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** List all sessions for the current user (lean, no questions/transcript). */
  list(): Promise<InterviewSessionResponse[]> {
    return request<InterviewSessionResponse[]>("/interview-sessions");
  },

  /** Get full session detail including questions and transcript. */
  get(id: number): Promise<InterviewSessionDetailResponse> {
    return request<InterviewSessionDetailResponse>(`/interview-sessions/${id}`);
  },

  /**
   * Submit an answer for one question in a session.
   * Returns the updated session detail (with new transcript entry + feedback).
   */
  submitAnswer(
    sessionId: number,
    body: AnswerSubmit
  ): Promise<InterviewSessionDetailResponse> {
    return request<InterviewSessionDetailResponse>(
      `/interview-sessions/${sessionId}/answers`,
      { method: "POST", body: JSON.stringify(body) }
    );
  },

  /** DELETE /api/v1/interview-sessions/{id} */
  delete(id: number): Promise<void> {
    return request<void>(`/interview-sessions/${id}`, { method: "DELETE" });
  },
};

// ---------------------------------------------------------------------------
// Job Application endpoints
// ---------------------------------------------------------------------------

export const jobApplicationApi = {
  create(body: JobApplicationCreate): Promise<JobApplicationResponse> {
    return request<JobApplicationResponse>("/job-applications", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  list(): Promise<JobApplicationResponse[]> {
    return request<JobApplicationResponse[]>("/job-applications");
  },

  get(id: number): Promise<JobApplicationResponse> {
    return request<JobApplicationResponse>(`/job-applications/${id}`);
  },

  update(id: number, body: JobApplicationUpdate): Promise<JobApplicationResponse> {
    return request<JobApplicationResponse>(`/job-applications/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  delete(id: number): Promise<void> {
    return request<void>(`/job-applications/${id}`, { method: "DELETE" });
  },
};
