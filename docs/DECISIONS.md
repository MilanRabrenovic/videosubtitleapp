# Decisions

## Why FastAPI
FastAPI is simple to set up, fast to iterate on, and supports async workflows for long-running processing later.

## Why server-rendered HTML
Server-rendered pages keep the stack minimal and reliable while still allowing small JS enhancements.

## Why manual subtitle editing is required
Auto-transcription is rarely perfect; manual editing is essential for accuracy and usability.

## Whisper model choice (base)
The `base` model is the smallest reasonable default that balances speed and accuracy for an MVP without heavy hardware requirements.

## Timestamp format
Canonical subtitle timestamps are stored as `HH:MM:SS,mmm` for SRT compatibility; VTT output converts commas to dots on export.

## Why hard subtitles for export
Hard subtitles are the simplest, most predictable way to ensure the exported video matches the edited text without needing player support.

## Why export is synchronous
Synchronous export keeps the system simple and avoids background job infrastructure for the MVP.

## Why word-level transcript is separate from subtitles
Word-level timing is experimental and for playback context only; keeping it separate avoids polluting the subtitle edit/export flow.

## Why ASS is required for word highlighting
ASS karaoke tags allow per-word timing and color transitions that SRT and VTT cannot represent.

## Why karaoke export is separate from web playback captions
Burned karaoke subtitles are for finalized video delivery; playback highlights remain a lightweight editor aid.

## Why we cache Google Fonts locally
Google Fonts are downloaded on first use and cached to avoid repeated downloads and keep exports deterministic.

## Why custom fonts are job-scoped
Uploaded fonts are tied to a specific job to reduce licensing risk and keep storage isolated.

## Why we use a storage cap cleanup
A size-based cleanup keeps local disk usage bounded without introducing a database or job scheduler.

## Why file-backed jobs
JSON files in a `jobs/` directory keep job state persistent across restarts without extra infrastructure.

## Why polling instead of WebSockets
Polling keeps the implementation minimal and reliable; it can be replaced with real-time updates later.

## Why background jobs are required for public users
Transcription and exports can take minutes; background jobs prevent request timeouts and let users return later.

## Why single-worker FIFO by default
One worker keeps CPU usage predictable and avoids overload on small servers; concurrency can be increased later.

## Why jobs are retained for a fixed window
Job JSON files are kept for a limited time to balance reliability with storage limits.

## Tradeoffs accepted for simplicity
- No authentication or multi-user support.
- Local filesystem storage only.
- Minimal UI polish until the core flow is stable.
- No video preview or advanced editing widgets.
