# Setup

## Requirements
- Python 3.11+
- FFmpeg with libass available on PATH (required for burned subtitles)
- Whisper (`openai-whisper`) and its dependencies

## Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Install FFmpeg (macOS example)
```bash
brew install ffmpeg-full
```
Verify the subtitles filter is available:
```bash
ffmpeg -filters | grep subtitles
```

## Run locally
```bash
uvicorn app.main:app --reload
```
Then open `http://127.0.0.1:8000`.

## Optional: Redis queue (for parallel jobs)
If you want multiple jobs to run in parallel, use Redis + RQ.

```bash
export REDIS_URL=redis://localhost:6379/0
```

Start a worker:
```bash
python -m app.worker
```

The app will still run without Redis; it falls back to the single in-process worker.
