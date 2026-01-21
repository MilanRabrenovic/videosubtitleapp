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
