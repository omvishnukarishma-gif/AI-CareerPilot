/**
 * Shared API types.
 *
 * These mirror the backend Pydantic schemas exactly so the TypeScript
 * compiler catches mismatches at build time rather than at runtime.
 *
 * Backend source of truth:
 *   backend/app/schemas/auth.py
 *   backend/app/schemas/resume.py
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

/** POST /api/v1/auth/register — request body */
export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

/** POST /api/v1/auth/login — request body */
export interface LoginRequest {
  email: string;
  password: string;
}

/** GET /api/v1/auth/me — response (also returned by register) */
export interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
}

/** POST /api/v1/auth/login — response */
export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}

/** PUT /api/v1/auth/me — request body */
export interface UserUpdate {
  full_name?: string;
  current_password?: string;
  new_password?: string;
}

// ---------------------------------------------------------------------------
// Resumes
// ---------------------------------------------------------------------------

/** GET /api/v1/resumes — list item (excludes content_text) */
export interface ResumeResponse {
  id: number;
  user_id: number;
  file_name: string;
  file_type: string;
  created_at: string;
  updated_at: string;
}

/** GET /api/v1/resumes/{id} — full detail (includes content_text) */
export interface ResumeDetailResponse extends ResumeResponse {
  content_text: string;
  parsed_data: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// Error shape returned by FastAPI
// ---------------------------------------------------------------------------

/** FastAPI default error response body */
export interface ApiError {
  detail: string | { msg: string; type: string }[];
}

// ---------------------------------------------------------------------------
// Job Descriptions
// ---------------------------------------------------------------------------

/** POST /api/v1/job-descriptions — request body */
export interface JobDescriptionCreate {
  title: string;
  company?: string | null;
  description_text: string;
}

/** GET /api/v1/job-descriptions — list item (excludes description_text) */
export interface JobDescriptionResponse {
  id: number;
  user_id: number;
  title: string;
  company: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /api/v1/job-descriptions/{id} — full detail */
export interface JobDescriptionDetailResponse extends JobDescriptionResponse {
  description_text: string;
}

// ---------------------------------------------------------------------------
// Matches
// ---------------------------------------------------------------------------

/** POST /api/v1/matches — request body */
export interface MatchCreate {
  resume_id: number;
  job_description_id: number;
}

/** Skill-gap sub-object embedded in MatchDetailResponse */
export interface SkillGapResponse {
  id: number;
  matched_skills: string[];
  missing_skills: string[];
  recommendations: string[];
  created_at: string;
  updated_at: string;
}

/** GET /api/v1/matches — list item */
export interface MatchResponse {
  id: number;
  resume_id: number;
  job_description_id: number;
  match_score: number;
  matched_skills: string[];
  missing_skills: string[];
  created_at: string;
  updated_at: string;
}

/** GET /api/v1/matches/{id} — full detail with skill-gap */
export interface MatchDetailResponse extends MatchResponse {
  skill_gap: SkillGapResponse | null;
  job_description_title: string;
  resume_file_name: string;
}

// ---------------------------------------------------------------------------
// Job Applications
// ---------------------------------------------------------------------------

/** Allowed status values for job applications */
export type JobApplicationStatus =
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "archived";

/** POST /api/v1/job-applications — request body */
export interface JobApplicationCreate {
  company_name: string;
  role_title: string;
  status?: JobApplicationStatus;
  job_url?: string | null;
  notes?: string | null;
  deadline?: string | null;
}

/** PUT /api/v1/job-applications/{id} — request body (all fields optional) */
export interface JobApplicationUpdate {
  company_name?: string;
  role_title?: string;
  status?: JobApplicationStatus;
  job_url?: string | null;
  notes?: string | null;
  deadline?: string | null;
}

/** GET /api/v1/job-applications — list item and detail response */
export interface JobApplicationResponse {
  id: number;
  user_id: number;
  company_name: string;
  role_title: string;
  status: JobApplicationStatus;
  job_url: string | null;
  notes: string | null;
  deadline: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Interview Sessions
// ---------------------------------------------------------------------------

/** POST /api/v1/interview-sessions — request body */
export interface InterviewSessionCreate {
  role_target: string;
  job_description_id?: number | null;
  resume_id?: number | null;
}

/** POST /api/v1/interview-sessions/{id}/answers — request body */
export interface AnswerSubmit {
  question_index: number;
  answer: string;
}

/** A single question returned by the API (expected_keywords omitted) */
export interface QuestionOut {
  text: string;
  category: string;
  skill_ref: string | null;
}

/** Structured feedback for one answer */
export interface FeedbackOut {
  score: number;
  strengths: string[];
  improvements: string[];
  note: string;
}

/** One answered question in the session transcript */
export interface TranscriptEntry {
  question_index: number;
  question_text: string;
  answer: string;
  feedback: FeedbackOut;
}

/** GET /api/v1/interview-sessions — list item (lean, no questions/transcript) */
export interface InterviewSessionResponse {
  id: number;
  user_id: number;
  role_target: string;
  status: "started" | "completed";
  job_description_id: number | null;
  resume_id: number | null;
  question_count: number;
  answers_given: number;
  created_at: string;
  updated_at: string;
}

/** GET /api/v1/interview-sessions/{id} — full detail */
export interface InterviewSessionDetailResponse {
  id: number;
  user_id: number;
  role_target: string;
  status: "started" | "completed";
  job_description_id: number | null;
  resume_id: number | null;
  questions: QuestionOut[];
  transcript: TranscriptEntry[];
  created_at: string;
  updated_at: string;
}
