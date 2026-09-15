# IIT Management

Minimal Phase 1 implementation: React, FastAPI, Neon PostgreSQL, Google SSO, student email parsing, teacher approval state, and JWT sessions.

## Local setup

1. Fill in `.env`.
2. Run the API: `cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn api.index:app --reload`.
3. Run the UI: `cd frontend && npm install && npm run dev`.

## Vercel

Create two Vercel projects from this repository. Use `frontend` and `backend` as their respective root directories, then copy the relevant `.env.example` values into each project's environment settings.
