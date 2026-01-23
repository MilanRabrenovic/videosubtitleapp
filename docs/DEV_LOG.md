# Dev Log

## 2026-01-16
- Implemented: Project scaffold, FastAPI app wiring, upload/edit/export routes, stub subtitle storage, and basic templates/JS.
- Incomplete: Whisper transcription, FFmpeg video export, real subtitle timing validation, and UI polish.
- Next action: Wire Whisper transcription to replace stub subtitles and persist real timestamps.

## 2026-01-16
- Implemented: Whisper transcription with the `base` model, conversion to canonical subtitle JSON, and SRT persistence on upload/edit.
- Incomplete: FFmpeg video export, subtitle timing validation, and UI polish.
- Known limitations: Transcription speed depends on CPU; accuracy may vary on noisy audio; no language selection yet.
- Next action: Add a transcription progress indicator and basic timing validation feedback in the editor.

## 2026-01-16
- Implemented: Upload submit now shows a processing message and disables the submit button.
- Incomplete: Transcription is still synchronous and blocks during processing.
- Next action: Add a lightweight status view in the edit page to confirm subtitle save success without reload.

## 2026-01-16
- Implemented: Inline save confirmation that appears briefly after subtitles are saved without reloading the page.
- Why: A small confirmation improves user trust that edits were persisted during long sessions.
- Next action: Add a basic validation hint for timestamp formatting errors.

## 2026-01-16
- Implemented: Advisory timestamp format hint on save; warnings show without blocking saves.
- Why: This keeps editing flow smooth while nudging users toward export-safe timestamps.
- Next action: Add a lightweight cue in the editor when SRT export is generated from the latest edits.

## 2026-01-16
- Implemented: Export freshness cue that confirms when SRT reflects the latest saved edits.
- Why: A small, UX-only signal improves confidence without adding backend state.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: FFmpeg-based burn-in export using `ffmpeg -i input -vf subtitles=... -c:a copy output`.
- Known limitations: Hard subtitles are permanent; export is synchronous and may be slow on large videos.
- Assumptions: Uses the latest saved SRT from the editor as the export source.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Experimental playback view with word-level transcript highlighting synced to video playback.
- Why: This is a UX exploration separate from subtitles and exports; timing is advisory and may drift.
- Known limitations: Word timings can be imprecise with punctuation and fast speech.
- Next action: Add a link from the editor to the playback view for quick access.

## 2026-01-16
- Implemented: ASS karaoke export using word timings with FFmpeg `ass` filter for burned word highlighting.
- Why: ASS is required for per-word highlight timing; SRT cannot express karaoke effects.
- Known limitations: Highlight timing is approximate; punctuation grouping is basic; output is hard subtitles.
- Next action: Add a minimal UI button to trigger karaoke export alongside the existing export.

## 2026-01-16
- Implemented: Editor preview panel with an inline video player to validate edits before exporting.
- Why: Quick in-browser playback reduces context switching and improves confidence in timing.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Burned-in preview video generation on upload/save and preview refresh in the editor.
- Why: Matches the final burned export more closely during review.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Preview burn-in now uses ASS karaoke highlighting when word timings exist.
- Why: Preview matches the karaoke export output instead of plain subtitles.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Karaoke preview/export now aligns word text to edited subtitles, with fallback timings when counts differ.
- Why: Ensures edited text appears in burned previews and karaoke exports.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Styling controls in the editor (font, colors, position, background) applied to preview and exports.
- Why: Lets users match brand/style needs while keeping export output consistent.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Single-line toggle that collapses subtitle text to one line for burned previews and exports.
- Why: Keeps on-screen captions consistent and avoids multi-line blocks when desired.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Word-count based line wrapping for burned subtitles with configurable max words per line.
- Why: Prevents off-screen overflow while keeping layout predictable.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Subtitle blocks now split into multiple timed blocks based on max words per line.
- Why: Ensures long lines are broken into readable chunks and burned preview reflects the split.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Word-timing-based splitting to improve subtitle timing precision.
- Why: Uses actual word timestamps for more accurate block start/end times.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Word timing smoothing with min/max duration clamps and overlap prevention.
- Why: Makes karaoke highlights feel more natural for short/long words.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-16
- Implemented: Upload language selector to pass explicit language to Whisper.
- Why: Improves accuracy and avoids mis-detection for non-English videos.
- Next action: Add a lightweight undo for the last edit block to speed minor fixes.

## 2026-01-19
- Implemented: Burned preview video generation on upload/save with karaoke ASS; export for standard and karaoke; word-level alignment improvements.
- Implemented: Subtitle styling controls (fonts, colors, outline, background, padding, position, line height, max words per line), plus line splitting with word-timed blocks.
- Implemented: Font system with curated Google fonts cache, system fonts, per-job custom uploads with license confirmation, and delete custom font action.
- Implemented: Upload validation (size, type, duration), streamed uploads, FFmpeg subprocess timeouts, and storage cleanup by size cap with job touch.
- Implemented: Sup/sub rendering with font-metric vertical positioning and stable horizontal placement.
- Incomplete: Background jobs/progress tracking and user-facing job management.
- Next action: Evaluate background processing and progress indicators for long transcriptions/exports.

## 2026-01-19
- Implemented: File-backed job queue with persistent JSON state, worker threads, and job status polling.
- Implemented: Transcription, preview rendering, and export now run in background jobs (no blocking requests).
- Implemented: Job status endpoint and minimal UI polling for processing/preview/export states.
- Tradeoffs: Single-process worker, polling instead of realtime; easy to replace with Redis/Celery later.
- Next action: Add auth/usage limits for public access and harden job retention policies.

## 2026-01-20
- Implemented: Save edits now always queues a fresh preview job so the UI doesn’t lag one edit behind.
- Implemented: UI polling wired to preview job IDs returned by save, so updates appear without page refresh.
- Next action: Review multi-user throughput and decide on worker concurrency limits.

## 2026-01-22
- Implemented: Job lifecycle fields (last_accessed_at, pinned, locked, expires_at) with access tracking.
- Implemented: Recent jobs list on upload page and `/jobs/recent` endpoint.
- Implemented: Conservative cleanup rules (skip pinned/locked, honor expires_at, delete in batches).
- Implemented: Pin toggle in editor and editor lock heartbeats.
- Next action: Add auth/ownership so recent jobs are scoped per user.

## 2026-01-22
- Implemented: Structured error payloads for failed jobs (code/message/hint).
- Implemented: Whisper/FFmpeg failures now map to user-friendly messages and hints.
- Implemented: UI now shows clean failure copy during processing, preview, and export.
- Next action: Add retry UX for failed jobs and scope errors per user.

## 2026-01-22
- Implemented: Step-level job timeline (upload, transcribe, preview_render, export_standard, export_karaoke).
- Implemented: Job failures now record the failing step and expose it in status polling.
- Implemented: Minimal UI copy now includes “Failed during …” without exposing timestamps.
- Not tracked: user behavior analytics, transcripts, or media content.
- Next action: Add retry UX or support tooling for step-level diagnostics.

## 2026-01-22
- Implemented: Session-scoped job ownership via cookie (subtitle_session_id).
- Implemented: “My recent jobs” list now shows only jobs from the current browser session.
- Implemented: Jobs now store owner_session_id; legacy jobs remain unowned.
- Next action: Add real auth and owner-scoped job access once accounts exist.

## 2026-01-23
- Implemented: Tailwind-based UI refresh (light theme), reorganized subtitle styling controls, sticky preview + export panel.
- Implemented: Drag-and-drop upload zone with centered CTA; recent-jobs delete buttons with confirmation and toast feedback.
- Implemented: Bottom-center toast system for all user messages (save/export/preview/pin/upload).
- Implemented: Karaoke alignment improvements for hyphenated tokens and better word-duration fidelity.
- Next action: Validate highlight timing on long words across more clips and refine alignment if needed.

## 2026-01-23
- Implemented: SQLite-backed auth (signup/login/logout) with secure session cookies and password hashing.
- Implemented: Project ownership enforced by user_id across edit/export/playback/jobs routes.
- Implemented: Protected media endpoints for uploads/outputs and removed direct static access.
- Next action: Add rate limiting and proxy-level upload caps before public launch.

## 2026-01-23
- Implemented: In-app rate limiting for upload/edit/export endpoints with per-IP limits.
- Implemented: Early request size checks for video and font uploads (reject large uploads before processing).
- Next action: Add proxy-level limits (nginx/caddy) when deploying to production.
