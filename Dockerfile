# ── Stage 1: Build the React frontend ───────────────────────────────────────
FROM node:22-alpine AS frontend-build

WORKDIR /frontend

# Copy lock files first for layer-cache efficiency.
COPY frontend/package*.json ./
RUN npm ci

# Copy the rest of the frontend source and produce a production build.
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Production FastAPI image ────────────────────────────────────────
FROM python:3.13-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    SERVE_FRONTEND=true

WORKDIR /app

# Install the backend package (reads pyproject.toml for dependencies).
# --no-cache-dir keeps the image lean.
COPY backend/ /app/backend/
RUN pip install --no-cache-dir /app/backend

# Copy the Vite production build from the frontend stage.
COPY --from=frontend-build /frontend/dist/ /app/frontend/dist/

# Create the uploads directory so FastAPI can write files on first run.
# On Render, mount a persistent disk at /app/backend/uploads to survive restarts.
RUN mkdir -p /app/backend/uploads

# Render injects $PORT at runtime (default 10000).
EXPOSE 10000

# Run Alembic migrations then start the server.
#
# Render supports a "Pre-Deploy Command" (in the Render dashboard) which is
# the recommended approach — set it to:
#   PYTHONPATH=/app/backend alembic -c /app/backend/alembic.ini upgrade head
#
# If you prefer startup migrations (simpler setup, works without the
# Render pre-deploy feature), the CMD below runs them automatically.
#
# IMPORTANT: Do NOT run this service with more than one instance until the
# migration has completed.  Running alembic upgrade from multiple replicas
# simultaneously can cause a race condition.  Render's zero-downtime deploys
# mean the migration runs once before the new instance starts serving traffic.
#
# --host 0.0.0.0  is required for Docker / Render (not just localhost).
# --app-dir sets the Python working directory so `from app.xxx import ...` resolves.
CMD ["sh", "-c", "alembic -c /app/backend/alembic.ini upgrade head && uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port ${PORT:-10000}"]
