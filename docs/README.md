# Subtitle Studio

A FastAPI web app to generate, edit, and export subtitles from video. Built for speed, clarity, and non‑technical users.

## Key features
- Upload video → auto‑transcribe with Whisper.
- Edit text + timing directly in the browser.
- Timeline with waveform and draggable blocks.
- Export subtitles as SRT or VTT.
- Export burned video (standard or karaoke word highlight).
- Export green‑screen video (subtitles + original audio).
- Preview video updates after every save.
- Styling controls (font, size, colors, outline, background, position).
- Curated Google Fonts, system fonts, and per‑project custom uploads.
- Background jobs with polling, retries, logs, and clean error messages.
- SQLite auth + per‑user ownership.

## User flow
1. Upload a video.
2. Background transcription creates a project and redirects to the editor.
3. Edit subtitles + styling.
4. Save → preview renders in background.
5. Export SRT/VTT or a burned video.

## Quick start (local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000`.

## Requirements
- Python 3.11+
- FFmpeg with libass (`ffmpeg -filters | grep subtitles`)
- Whisper (`openai-whisper`)
- (Optional) Redis for parallel jobs

## Exports
- **SRT / VTT**: Text subtitle files.
- **Word highlight**: Karaoke ASS burned into video.
- **Green screen**: Solid green video with subtitles + original audio.

## Limits & behavior
- Upload size and duration limits are enforced (see `app/config.py`).
- Long videos can be slow to transcribe; the UI warns at 10+ minutes.
- Jobs run sequentially unless Redis workers are enabled.

## Project structure
```
app/
  routes/      # HTTP endpoints
  services/    # transcription, export, jobs, fonts, subtitles
  templates/   # HTML
  static/      # JS
docs/          # design + ops notes
uploads/       # source videos
outputs/       # previews/exports/logs
jobs/          # job state JSON
data/          # auth.db
```

## Docs
- `docs/SETUP.md` – local setup details
- `docs/DEPLOY.md` – production deployment checklist
- `docs/DEV_LOG.md` – chronological changes
- `docs/DECISIONS.md` – architectural choices
- `docs/BACKLOG.md` – upcoming work and refactors

## What’s not included yet
- Full analytics / dashboards
- Real‑time progress bars (only state transitions)
- Multi‑instance scaling (planned via Redis/Celery)

If you want a production‑ready CSS build (instead of Tailwind CDN), add it per `docs/BACKLOG.md`.
