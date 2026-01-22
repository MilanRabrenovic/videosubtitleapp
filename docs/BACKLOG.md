# Backlog

## Infrastructure & Scaling
- Evaluate Redis/Celery migration for background jobs.
- Add worker concurrency controls and resource limits per job.
- Add job retry policy and failure diagnostics.
- Add lightweight ownership (cookie token) so recent jobs/pin are per user before full auth.

## Reliability
- Add job ownership tokens or auth before public launch.
- Improve error surfacing in the UI for failed jobs.
- Add job cleanup policies for outputs (retention per user/job).

## UX & Product
- Add a minimal job list/history for recent uploads.
- Add progress estimation for long transcriptions/exports (optional).
- Add usage limits or quotas for public users.
