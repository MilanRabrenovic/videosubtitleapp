# Subtitle App

## What this app does
- Uploads a video file.
- Generates subtitles using Whisper (with optional language selection).
- Lets users edit subtitle text and timing in a browser.
- Exports subtitles as SRT or VTT.
- Exports a video with burned-in subtitles.
- Exports a karaoke-style video with word-by-word highlighting (ASS).
- Provides styling controls (font, size, colors, outline, background, position).
- Supports curated Google Fonts, system fonts, and per-job custom font uploads.

## User flow (upload -> edit -> export)
1. Upload a video from the upload page.
2. The app transcribes and creates a subtitle job, then redirects to the edit page.
3. Edit subtitle blocks directly in the browser.
4. Save edits to update the burned preview video.
5. Download subtitles or export the final video (karaoke or standard).

## Who this tool is for
- Internal teams who need a simple, reliable subtitle workflow.
- Non-technical users who want to edit subtitles without extra tools.

## Intentionally not included yet
- Authentication and user accounts.
- Databases or cloud storage.
- Advanced editors (timelines, waveform views).
- Background jobs or real-time progress tracking.
