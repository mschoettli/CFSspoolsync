# Non-Docker Installation (Linux)

This guide installs CFSspoolsync without Docker:
- backend via Python + `systemd`
- frontend as static files served by Nginx

## 1) Prerequisites

- Linux host with:
  - Python 3.11+ (3.12 recommended)
  - Node.js 20+
  - Nginx
  - `tesseract-ocr`, `tesseract-ocr-eng`, `tesseract-ocr-deu`
- `git`
- `sudo` access

Example package install (Debian/Ubuntu):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm nginx \
  tesseract-ocr tesseract-ocr-eng tesseract-ocr-deu git
```

## 2) Checkout and environment file

```bash
sudo mkdir -p /opt/cfsspoolsync
sudo chown -R "$USER":"$USER" /opt/cfsspoolsync
cd /opt/cfsspoolsync
git clone https://github.com/mschoettli/CFSspoolsync.git .
cp .env.example .env
```

Set your values in `.env` (prefix is `CFS_` for backend runtime settings).

Important fields:
- `CFS_MOONRAKER_HOST` (empty = simulator mode)
- `CFS_MOONRAKER_PORT` (usually `7125`)
- `CFS_OPENAI_API_KEY` / `CFS_ANTHROPIC_API_KEY` (optional)

## 3) Backend setup (venv)

```bash
cd /opt/cfsspoolsync/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create data directory:

```bash
mkdir -p /opt/cfsspoolsync/backend/data
```

## 4) Backend systemd service

Create `/etc/systemd/system/cfsspoolsync-backend.service`:

```ini
[Unit]
Description=CFSspoolsync Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/cfsspoolsync/backend
EnvironmentFile=/opt/cfsspoolsync/.env
ExecStart=/opt/cfsspoolsync/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now cfsspoolsync-backend
sudo systemctl status cfsspoolsync-backend --no-pager
```

## 5) Frontend build

```bash
cd /opt/cfsspoolsync/frontend
npm ci
npm run build
```

The build output is in:
- `/opt/cfsspoolsync/frontend/dist`

## 6) Nginx config (frontend + backend proxy)

Create `/etc/nginx/sites-available/cfsspoolsync.conf`:

```nginx
server {
    listen 8088;
    server_name _;
    client_max_body_size 12m;

    root /opt/cfsspoolsync/frontend/dist;
    index index.html;

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        try_files $uri =404;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Enable and reload:

```bash
sudo ln -sf /etc/nginx/sites-available/cfsspoolsync.conf /etc/nginx/sites-enabled/cfsspoolsync.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 7) Validation

```bash
curl -I http://127.0.0.1:8088/
curl -I http://127.0.0.1:8088/api/health
```

Expected:
- `HTTP/1.1 200 OK` for `/`
- `HTTP/1.1 200 OK` for `/api/health`

## 8) Updates

```bash
cd /opt/cfsspoolsync
git pull

cd /opt/cfsspoolsync/backend
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart cfsspoolsync-backend

cd /opt/cfsspoolsync/frontend
npm ci
npm run build
sudo systemctl reload nginx
```
