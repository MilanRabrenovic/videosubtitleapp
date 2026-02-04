# Backlog

## Production readiness (Go live)
### P0 — must have
- Add server-side rate limiting and hard upload size limits at the proxy (nginx/caddy).
- Add resource limits per job (CPU/RAM/timeouts) to prevent one job from stalling the app.

### P1 — should have
- Add proxy-level rate limits + hard upload caps (nginx/caddy) on deploy.
- Replace Tailwind CDN with compiled CSS pipeline (PostCSS/CLI) before production.
- Add Terms of Service + Privacy Policy pages (drafts, then legal review before launch).

### P2 — nice to have
- Add progress estimates for transcription/export.
- Add job retry UX (manual retry button, no auto retry).

## Completed (already implemented)
- Real auth + ownership (SQLite users + session cookie).
- File-backed background jobs + Redis/RQ optional workers.
- Health checks (`/health`, `/ready`).
- Per-job logs (stderr captured on failure).
- Safe storage policies (retention, pinned/locked rules).
- Factory Reset with original state backups and re-transcription callback.
- Improved word-based segmentation with silence detection (0.5s threshold).


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
- Fix timeline viewport overflow on some clips (no page horizontal scroll).
- Ensure pills render on short videos consistently and keep word separators on long videos.
- Fix highlight box rendering alignment/visibility (boxes should match word bounds; opacity/color must apply correctly).

## Refactor backlog (maintainability)
### P1 — soon
- Split `app/static/js/subtitles.js` into smaller modules (timeline, editor, presets, exports, toast).
- Extract subtitle edit/save logic from `app/routes/edit_subtitles.py` into services.

### P2 — later
- Split `app/services/tasks.py` into separate task modules (transcribe/preview/export).
- Add lightweight unit tests for subtitle splitting + style normalization.

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
