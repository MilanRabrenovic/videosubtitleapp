# Deploy (Server Guide)

This app can run on a single server. For production, use a process manager and a reverse proxy.
The checklist below is end-to-end: OS packages → app install → services → proxy → health checks.

## 1) Requirements
- Python 3.11+
- FFmpeg with libass (for subtitle burn-in)
- Redis (optional, for parallel jobs)
- A reverse proxy (Nginx/Caddy) for HTTPS + upload limits
- Enough disk space for uploads/outputs (videos are large)

### Install system packages (Ubuntu example)
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg python3-venv python3-pip
ffmpeg -filters | grep subtitles
```

## 2) Create a dedicated app directory
```bash
mkdir -p /opt/subtitle-app
cd /opt/subtitle-app
```

## 3) App install (virtualenv)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4) Required folders + permissions
These must exist and be writable by the service user:
```
uploads/
outputs/
jobs/
data/
outputs/job-logs/
```

## 5) Environment variables
Set these in your process manager (systemd, Docker, etc.):
```
PYTHONUNBUFFERED=1
REDIS_URL=redis://localhost:6379/0   # optional for multi-worker
```

Optional tuning (defaults are in app/config.py):
```
MAX_UPLOAD_BYTES=600000000
MAX_FONT_UPLOAD_BYTES=20000000
JOB_TIMEOUT_TRANSCRIBE_SECONDS=3600
JOB_TIMEOUT_EXPORT_SECONDS=3600
JOB_TIMEOUT_PREVIEW_SECONDS=1800
```

## 6) Run the web app
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 7) Enable Redis workers (optional but recommended)
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

## 8) Reverse proxy (recommended)
Put Nginx/Caddy in front for:
- TLS/HTTPS
- Hard upload limits
- Rate limiting

### Example Nginx notes
- Set `client_max_body_size` to match `MAX_UPLOAD_BYTES`.
- Add basic rate limits to `/upload` and `/export/*`.
- Forward headers so session cookies work behind HTTPS:
  - `X-Forwarded-Proto`
  - `Host`

### Example Nginx rate limiting (optional)
```
limit_req_zone $binary_remote_addr zone=subtitle_upload:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=subtitle_export:10m rate=20r/m;

server {
  ...
  location /upload {
    limit_req zone=subtitle_upload burst=5 nodelay;
    proxy_pass http://127.0.0.1:8000;
  }

  location /export/ {
    limit_req zone=subtitle_export burst=10 nodelay;
    proxy_pass http://127.0.0.1:8000;
  }
}
```

## 9) Health checks (load balancer)
Use these endpoints for uptime/readiness probes:
- `GET /health` → liveness (always returns ok if the app is running).
- `GET /ready` → readiness (checks folders, auth DB, and Redis if enabled).

Recommended setup:
- Load balancer “health” probe → `/health`
- Load balancer “ready” probe → `/ready`

If Redis is enabled and down, `/ready` returns `status: "degraded"`.

## 10) Files & storage
- `uploads/` stores source videos
- `outputs/` stores previews/exports
- `jobs/` stores job state JSON
- `data/auth.db` stores users + sessions

Cleanup rules will keep disk usage bounded, but you should still monitor disk space.

## 11) First launch checklist
- Start app
- Create a user at `/signup`
- Verify upload → edit → export
- Verify exports are only accessible to logged-in owner

## 12) Systemd examples (Ubuntu)
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
MemoryMax=6G
CPUQuota=200%

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

## 13) Nginx baseline (example)
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

## 14) Operational notes
- Back up `data/auth.db` if you care about users.
- Monitor disk usage (uploads/outputs can grow quickly).
- If running behind HTTPS, keep `Secure` cookies enabled.
