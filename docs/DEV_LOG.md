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
