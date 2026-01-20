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
