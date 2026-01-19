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

## Tradeoffs accepted for simplicity
- No authentication or multi-user support.
- Local filesystem storage only.
- Minimal UI polish until the core flow is stable.
- No video preview or advanced editing widgets.
