# Subtitle App

## What this app does
- Uploads a video file.
- Generates subtitles (placeholder for now).
- Lets users edit subtitle text and timing in a browser.
- Exports subtitles as SRT or VTT.
- Exports a video with burned-in subtitles (placeholder for now).

## User flow (upload -> edit -> export)
1. Upload a video from the upload page.
2. The app creates a subtitle job and redirects to the edit page.
3. Edit subtitle blocks directly in the browser.
4. Save edits and download subtitles or export a video with subtitles.

## Who this tool is for
- Internal teams who need a simple, reliable subtitle workflow.
- Non-technical users who want to edit subtitles without extra tools.

## Intentionally not included yet
- Authentication and user accounts.
- Databases or cloud storage.
- Advanced editors (timelines, waveform views).
- Subtitle styling or live previews.
- Whisper and FFmpeg wiring (placeholders only).
