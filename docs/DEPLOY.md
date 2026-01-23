# Deploy (Server Guide)

This app can run on a single server. For production, use a process manager and a reverse proxy.

## 1) Requirements
- Python 3.11+
- FFmpeg with libass
- Redis (optional, for parallel jobs)
- A reverse proxy (Nginx/Caddy) for HTTPS + upload limits

### Install FFmpeg (Ubuntu example)
```bash
sudo apt-get update
sudo apt-get install ffmpeg
ffmpeg -filters | grep subtitles
```

## 2) Environment variables
Set these in your process manager (systemd, Docker, etc.):

```
REDIS_URL=redis://localhost:6379/0   # optional for multi-worker
PYTHONUNBUFFERED=1
```

## 3) Run the web app
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 4) Enable Redis workers (optional but recommended)
If you want multiple jobs to run in parallel:

```bash
sudo apt-get install redis-server
sudo systemctl enable redis
sudo systemctl start redis
```

Then run 1–4 workers:
```bash
export REDIS_URL=redis://localhost:6379/0
python -m app.worker
```

## 5) Reverse proxy (recommended)
Put Nginx/Caddy in front for:
- TLS/HTTPS
- Hard upload limits
- Rate limiting

### Example Nginx notes
- Set `client_max_body_size` to match `MAX_UPLOAD_BYTES`.
- Add basic rate limits to `/upload` and `/export/*`.

## 6) Files & storage
- `uploads/` stores source videos
- `outputs/` stores previews/exports
- `jobs/` stores job state JSON
- `data/auth.db` stores users + sessions

Cleanup rules will keep disk usage bounded, but you should still monitor disk space.

## 7) First launch checklist
- Start app
- Create a user at `/signup`
- Verify upload → edit → export
- Verify exports are only accessible to logged-in owner

## 8) Systemd examples (Ubuntu)
Create a service for the web app:
```
[Unit]
Description=Subtitle Studio Web
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/subtitle-app
Environment=PYTHONUNBUFFERED=1
Environment=REDIS_URL=redis://localhost:6379/0
ExecStart=/path/to/subtitle-app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Worker service (run 2–4 copies):
```
[Unit]
Description=Subtitle Studio Worker
After=network.target redis.service

[Service]
User=ubuntu
WorkingDirectory=/path/to/subtitle-app
Environment=PYTHONUNBUFFERED=1
Environment=REDIS_URL=redis://localhost:6379/0
ExecStart=/path/to/subtitle-app/.venv/bin/python -m app.worker
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable services:
```
sudo systemctl enable subtitle-studio.service
sudo systemctl start subtitle-studio.service
sudo systemctl enable subtitle-studio-worker@1.service
sudo systemctl start subtitle-studio-worker@1.service
```

## 9) Nginx baseline (example)
```
server {
  listen 80;
  server_name your-domain.com;

  client_max_body_size 600M;

  location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }
}
```
