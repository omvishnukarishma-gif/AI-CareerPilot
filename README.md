# AI CareerPilot

**Intelligent Career & Job Application Platform**

A full-stack web application that helps students and job seekers:
- Analyze resumes with AI
- Compare resumes with job descriptions
- Identify skill gaps
- Prepare for interviews using AI
- Track job applications

---

## Tech Stack

| Layer       | Technology                              |
|-------------|-----------------------------------------|
| Frontend    | React 19, TypeScript, Vite, Tailwind CSS |
| Backend    | Python 3.11+, FastAPI, Pydantic          |
| Database   | PostgreSQL 16                           |
| AI          | LLM API integration (Phase 2+)           |
| Testing    | pytest (backend), Vitest (frontend)     |

---

## Project Structure

```text
AI-CareerPilot/
|-- frontend/          # React + TypeScript + Vite frontend
|-- backend/           # FastAPI + SQLAlchemy backend
|-- docker-compose.yml # PostgreSQL via Docker
|-- .gitignore
|-- README.md
```

---
## Prerequisites

Install the following on your Windows machine:

1. **Python 3.11 or later** - <https://www.python.org/downloads/windows/>
   - Verify: `py --version`

2. **Node.js 20 or later** (with npm) - <https://nodejs.org/>
   - Verify: `node --version` and `npm --version`

3. **PostgreSQL** - choose **one** of the options below.

4. **Git** - <https://git-scm.com/download/win>
   - Verify: `git --version`

---

## Database Setup

### Option A: PostgreSQL via Docker (recommended if you have Docker)

If you have Docker Desktop installed:

```powershell
# Start the PostgreSQL container
docker-compose up -d

# Verify it's running
docker-compose ps
```

The database will be available at `localhost:5432` with these defaults:
- User: `careerpilot`
- Password: Set locally using the POSTGRES_PASSWORD environment variable.
- Database: `careerpilot_dev`

### Option B: Local PostgreSQL installation

If you do NOT have Docker:

1. Download PostgreSQL from <https://www.postgresql.org/download/windows/>
2. During installation, set a password for the `postgres` user.
3. After installation, open **pgAdmin** or use **SQL Shell (psql)**:

```powershell
# Create a dedicated database and user for this project
psql -U postgres -c "CREATE USER careerpilot WITH PASSWORD 'careerpilot_dev';"
psql -U postgres -c "CREATE DATABASE careerpilot_dev OWNER careerpilot;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE careerpilot_dev TO careerpilot;"
```

4. Update `backend/.env` with your connection string if needed.

---

## Backend Setup (FastAPI)

```powershell
# 1. Navigate to the backend directory
cd backend

# 2. Create a virtual environment
py -3.13 -m venv .venv

# 3. Activate it (PowerShell)
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -e ".[dev]"

# 5. Copy the env template and fill in your values
Copy-Item .env.example .env

# 6. Run the backend server (with auto-reload)
uvicorn app.main:app --reload

# The API will be available at http://127.0.0.1:8000
# Interactive API docs: http://127.0.0.1:8000/docs
```

### Backend Tests

```powershell
# Make sure you're in the backend/ directory with the venv activated
pytest -v
```

---

## Frontend Setup (React + Vite)

```powershell
# 1. Navigate to the frontend directory (open a new terminal)
cd frontend

# 2. Install dependencies
npm install

# 3. Copy the env template
Copy-Item .env.example .env

# 4. Start the dev server
npm run dev

# The frontend will be available at http://localhost:5173
```

> **API URL in development:** `VITE_API_URL` in `.env` should be left **empty** (the default).
> The Vite dev server proxies all `/api/*` requests to the backend at `http://127.0.0.1:8000`
> (see `vite.config.ts`), so no direct backend URL is needed and CORS is not involved.
>
> **API URL in production / Docker:** set `VITE_API_URL` to the full backend base URL, e.g.
> `VITE_API_URL=https://api.myapp.com/api/v1`. When this variable is set the frontend
> bypasses the proxy and calls the backend directly.

### Frontend Build

```powershell
# Production build
npm run build

# Preview the production build
npm run preview
```

### Frontend Tests

```powershell
# Run tests once (CI mode)
npm run test:run

# Run tests in watch mode (development)
npm run test
```

---

## Running Both Together

Open two terminals:

**Terminal 1 (backend):**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

**Terminal 2 (frontend):**
```powershell
cd frontend
npm run dev
```

Then open `http://localhost:5173` in your browser.

---

## API Endpoints (Phase 0-4)

All API routes are prefixed with `/api/v1`.

### Infrastructure & Auth

| Method | Endpoint                | Description                               |
|--------|-------------------------|-------------------------------------------|
| GET    | `/api/v1/health`        | Health check - returns status             |
| GET    | `/`                     | Root - links to API docs                  |
| GET    | `/docs`                 | Swagger UI (interactive docs)             |
| POST   | `/api/v1/auth/register` | Create a new user account                 |
| POST   | `/api/v1/auth/login`    | Log in and receive a JWT token            |
| GET    | `/api/v1/auth/me`       | Get the current authenticated user       |

### Resumes

| Method | Endpoint               | Description                               |
|--------|------------------------|-------------------------------------------|
| POST   | `/api/v1/resumes`      | Upload a PDF or DOCX resume               |
| GET    | `/api/v1/resumes`      | List the current user's resumes           |
| GET    | `/api/v1/resumes/{id}` | Get one resume (includes extracted text)  |

### Job Descriptions (Phase 3)

| Method | Endpoint                        | Description                                      |
|--------|---------------------------------|--------------------------------------------------|
| POST   | `/api/v1/job-descriptions`      | Create / save a job description                  |
| GET    | `/api/v1/job-descriptions`      | List the current user's job descriptions         |
| GET    | `/api/v1/job-descriptions/{id}` | Get one job description with full text           |

### Resume Job Matching & Skill Gaps (Phase 3)

| Method | Endpoint              | Description                                      |
|--------|-----------------------|--------------------------------------------------|
| POST   | `/api/v1/matches`     | Run a resume job match and compute skill gaps    |
| GET    | `/api/v1/matches`     | List the current user's matches                  |
| GET    | `/api/v1/matches/{id}`| Get one match with embedded skill-gap analysis   |

### Interview Preparation (Phase 4)

| Method | Endpoint                                    | Description                                        |
|--------|---------------------------------------------|----------------------------------------------------|
| POST   | `/api/v1/interview-sessions`                | Start a new practice session (generates questions) |
| GET    | `/api/v1/interview-sessions`                | List the current user's sessions (lean)            |
| GET    | `/api/v1/interview-sessions/{id}`           | Get full session detail (questions + transcript)   |
| POST   | `/api/v1/interview-sessions/{id}/answers`   | Submit one answer â€” returns feedback + score       |

All endpoints except `/health`, `/`, `/docs`, `/auth/register`, and `/auth/login` require a Bearer JWT token.

---

## Interview Preparation â€” Usage

1. Navigate to **Interview Prep** in the sidebar.
2. Enter the role you are practising for (e.g. "Senior Python Developer").
3. Optionally select a saved job description to get skill-focused questions.
4. Optionally select a resume to focus questions on skills missing from it.
5. Click **Start practice** â€” a session is created and questions are generated.
6. Answer each question in the text area and click **Submit & next**.
7. After the last answer the session summary is shown with per-question scores and feedback.
8. Click **History** to review all past sessions.

### How questions are generated

Questions are chosen from a curated bank by category:

| Category      | Source                                         | Count |
|---------------|------------------------------------------------|-------|
| `behavioral`  | Fixed STAR-method situational questions        | 3     |
| `technical`   | Fixed software-engineering fundamentals        | 3     |
| `role_specific` | Matched to keywords in the role target (Python, React, backend, â€¦) | 0â€“2 |
| `jd_skill`    | One question per skill extracted from the JD text (prioritises skills missing from the resume) | 0â€“4 |

### How answers are scored

Feedback is produced by a deterministic, offline heuristic â€” **no LLM or paid API is used**.

- **Keyword coverage (50%)** â€” how many of the question's expected concepts appear in the answer.
- **Length (25%)** â€” answers under 30 words score poorly; answers over 80 words score full marks.
- **Structure (25%)** â€” behavioral questions check for STAR-method markers; technical questions check for example markers.

The score (0â€“100) is a self-reflection aid, not a hiring signal. It cannot assess answer quality, depth, or domain accuracy.

---

## Development Phases

| Phase | Description                          | Status       |
|-------|--------------------------------------|-------------|
| 0     | Project setup and infrastructure     | âœ… Complete |
| 1     | Authentication system               | âœ… Complete |
| 2     | Resume upload and AI parsing         | âœ… Complete |
| 3     | Job match and skill gap analysis     | âœ… Complete |
| 4     | AI interview preparation             | âœ… Complete |
| 5     | Application tracker                  | Not started |
| 6     | Dashboard and polish                 | Not started |
| 7     | Deployment preparation               | Not started |

---

## Notes

- **Never commit `.env` files.** They contain secrets and are in `.gitignore`.
- The `.env.example` files are templates with fake values â€” safe to commit.
- AI API keys are loaded only on the backend and never exposed to the frontend.
- Backend tests use mocked AI responses â€” no real API calls during testing.
