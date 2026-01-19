# Setup

## Requirements
- Python 3.10+
- FFmpeg installed and available on PATH (needed for video export later)

## Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally
```bash
uvicorn app.main:app --reload
```
Then open `http://127.0.0.1:8000`.
