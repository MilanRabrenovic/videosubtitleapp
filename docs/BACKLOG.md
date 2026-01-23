# Backlog

## Production readiness (Go live)
### P0 — must have
- Add server-side rate limiting and hard upload size limits at the proxy (nginx/caddy).
- Add resource limits per job (CPU/RAM/timeouts) to prevent one job from stalling the app.

### P1 — should have
- Add proxy-level rate limits + hard upload caps (nginx/caddy) on deploy.

### P2 — nice to have
- Add progress estimates for transcription/export.
- Add job retry UX (manual retry button, no auto retry).

## Completed (already implemented)
- Real auth + ownership (SQLite users + session cookie).
- File-backed background jobs + Redis/RQ optional workers.
- Health checks (`/health`, `/ready`).
- Per-job logs (stderr captured on failure).
- Safe storage policies (retention, pinned/locked rules).

## Near-term (Launch hardening)
### Infrastructure & Scaling
- Keep 1 worker for reliability; avoid multi-process until shared queue exists.
- Single worker queue means jobs run sequentially; add multi-worker support when usage grows.
- Add worker concurrency controls and resource limits per job.

### Reliability
- Add job retry policy (manual first, optional auto retry later).
- Add output retention policy per job/user (define default days and caps).

### UX & Product
- Add usage limits/quotas for public users (daily minutes, file size caps).
- Optional: progress estimation for long transcriptions/exports.

## Long-term (Scale + productization)
### Infrastructure & Scaling
- Move to Celery or managed queue for multi-instance scale.
- Add multi-process deployment support with shared job state.

### Security & Ownership
- Add real auth/ownership so jobs, pins, and fonts are per user.
- Restrict access to outputs/uploads to job owners.

### UX & Product
- Add a real jobs history page with filters and search.
- Add billing/subscription enforcement and usage tracking.
