# GlobalStrat Production Deployment

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  User Browser                                           │
│  https://globalstrat.camdani.com                        │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  Cloudflare (DNS + CDN + SSL)                           │
│  Zone: fafa0995894f903b99c9d9812005e487                 │
│  Domain: globalstrat.camdani.com                        │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  Alibaba ECS — 47.86.57.36                              │
│                                                         │
│  nginx (port 80)                                        │
│  ├─ /           → /var/www/globalstrat/build/ (React)   │
│  └─ /api/       → proxy_pass 127.0.0.1:3006 (FRP)      │
│                                                         │
│  FRP Server (port 7000)                                 │
│  └─ globalstrat-api → port 3006                         │
└──────────────┬──────────────────────────────────────────┘
               │ FRP tunnel (TCP)
               ▼
┌─────────────────────────────────────────────────────────┐
│  Homelab — 192.168.50.5                                 │
│                                                         │
│  Gunicorn (port 8002) — globalstrat.wsgi:application    │
│  FRP Client → ECS:7000 (tunnel 8002 → 3006)            │
│                                                         │
│  PostgreSQL — 192.168.50.38:5432 (globalstrat_db)       │
│  Qdrant     — 192.168.50.186:6333                       │
└─────────────────────────────────────────────────────────┘
```

## Ports & Services

| Service            | Host           | Port | Notes                      |
|--------------------|----------------|------|----------------------------|
| Gunicorn (Django)  | 192.168.50.5   | 8002 | Backend API                |
| FRP Client         | 192.168.50.5   | —    | Tunnels 8002 → ECS:3006   |
| FRP Server         | 47.86.57.36    | 7000 | Accepts tunnel connections |
| nginx (frontend)   | 47.86.57.36    | 80   | Static + API proxy         |
| PostgreSQL         | 192.168.50.38  | 5432 | Database                   |
| Qdrant             | 192.168.50.186 | 6333 | Vector DB for RAG          |

Other platforms on same ECS:
- aib-study → port 3002
- accounting → port 3004
- becsr → port 3005
- mis-project → port 3100
- **globalstrat → port 3006**

---

## Initial Setup (one time)

### 1. Install systemd services on homelab

```bash
cd ~/projects/globalstrat/deploy
sudo bash setup-services.sh
```

This installs and starts:
- `globalstrat-backend.service` — Gunicorn on port 8002
- `globalstrat-frpc.service` — FRP tunnel to ECS

### 2. ECS nginx (already done)

Config installed at `/etc/nginx/sites-enabled/globalstrat`.
To re-apply if needed:

```bash
scp -i ~/.ssh/alibaba2.pem deploy/globalstrat-nginx.conf root@47.86.57.36:/etc/nginx/sites-available/globalstrat
ssh -i ~/.ssh/alibaba2.pem root@47.86.57.36 "ln -sf /etc/nginx/sites-available/globalstrat /etc/nginx/sites-enabled/globalstrat && nginx -t && systemctl reload nginx"
```

### 3. Cloudflare DNS (already done)

`globalstrat.camdani.com` → Cloudflare proxied to ECS (47.86.57.36).
SSL mode: Full (Cloudflare handles TLS termination).

---

## Deploying Updates

### Frontend

```bash
cd ~/projects/globalstrat/frontend
./deploy-frontend.sh
```

Options:
- `./deploy-frontend.sh --skip-build` — deploy existing build/ without rebuilding
- `./deploy-frontend.sh --dry-run` — preview what would happen

The script:
1. Runs `npm run build` in `globalstrat-frontend/`
2. Backs up current ECS version
3. Rsyncs `build/` to ECS `/var/www/globalstrat/build/`
4. Verifies file count and index.html
5. Purges Cloudflare cache

### Backend

After code changes, restart the backend service:

```bash
sudo systemctl restart globalstrat-backend
```

For database migrations:

```bash
cd ~/projects/globalstrat/backend
GLOBALSTRAT_ENV=production python3 manage.py migrate
sudo systemctl restart globalstrat-backend
```

---

## Django Settings

Settings switch between dev and production via `GLOBALSTRAT_ENV` environment variable.

| Setting                 | Development      | Production (`GLOBALSTRAT_ENV=production`) |
|-------------------------|------------------|-------------------------------------------|
| `DEBUG`                 | `True`           | `False`                                   |
| `CORS_ALLOW_ALL_ORIGINS`| `True`           | `False`                                   |
| `CORS_ALLOWED_ORIGINS`  | (all)            | `https://globalstrat.camdani.com`         |
| `CSRF_TRUSTED_ORIGINS`  | —                | `https://globalstrat.camdani.com`         |
| `SESSION_COOKIE_SECURE` | `False`          | `True`                                    |
| `CSRF_COOKIE_SECURE`    | `False`          | `True`                                    |
| `SECURE_SSL_REDIRECT`   | `False`          | `False` (Cloudflare terminates SSL)       |
| `LOGGING level`         | `DEBUG`          | `INFO`                                    |

Environment variables (set in systemd service or shell):
- `GLOBALSTRAT_ENV` — `production` or omit for development
- `DJANGO_SECRET_KEY` — override secret key (optional)
- `DASHSCOPE_API_KEY` — required for AI features
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — override database

To set the DashScope API key in the systemd service:

```bash
sudo systemctl edit globalstrat-backend
```

Add:
```ini
[Service]
Environment=DASHSCOPE_API_KEY=your-key-here
```

Then: `sudo systemctl restart globalstrat-backend`

---

## File Locations

### Homelab (192.168.50.5)

```
~/projects/globalstrat/
├── backend/
│   ├── globalstrat/settings.py      # Django settings
│   ├── gunicorn.conf.py             # Gunicorn config (port 8002, 3 workers)
│   ├── staticfiles/                 # collectstatic output
│   └── manage.py
├── frontend/
│   ├── globalstrat-frontend/
│   │   ├── build/                   # Production React build
│   │   ├── .env.production          # REACT_APP_API_URL=/api
│   │   └── package.json
│   └── deploy-frontend.sh           # Build + deploy to ECS
├── deploy/
│   ├── setup-services.sh            # One-time systemd installer
│   ├── globalstrat-backend.service  # Gunicorn systemd unit
│   ├── globalstrat-frpc.service     # FRP tunnel systemd unit
│   ├── frpc.toml                    # FRP client config
│   └── globalstrat-nginx.conf       # ECS nginx config
└── docs/
    └── DEPLOYMENT.md                # This file
```

### ECS (47.86.57.36)

```
/etc/nginx/sites-enabled/globalstrat   # nginx config
/var/www/globalstrat/build/            # Frontend static files
/etc/frp/frps.toml                     # FRP server (bindPort = 7000)
```

### Systemd Services (after setup)

```
/etc/systemd/system/globalstrat-backend.service
/etc/systemd/system/globalstrat-frpc.service
/etc/frp/frpc-globalstrat.toml
```

---

## Monitoring & Logs

```bash
# Backend logs
journalctl -u globalstrat-backend -f

# FRP tunnel logs
journalctl -u globalstrat-frpc -f

# Service status
systemctl status globalstrat-backend globalstrat-frpc

# nginx access logs (on ECS)
ssh -i ~/.ssh/alibaba2.pem root@47.86.57.36 "tail -f /var/log/nginx/globalstrat.access.log"
```

---

## Rollback

### Frontend rollback

Backups are created automatically by the deploy script at `/var/www/globalstrat-backup-YYYYMMDD-HHMMSS`:

```bash
ssh -i ~/.ssh/alibaba2.pem root@47.86.57.36
rm -rf /var/www/globalstrat/build && mv /var/www/globalstrat-backup-XXXXXXXX-XXXXXX /var/www/globalstrat/build
```

### Backend rollback

Use git to revert code, then restart:

```bash
cd ~/projects/globalstrat/backend
git checkout <previous-commit>
sudo systemctl restart globalstrat-backend
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Frontend loads but API 502 | FRP tunnel down: `systemctl status globalstrat-frpc` |
| Frontend loads but API 504 | Backend not responding: `systemctl status globalstrat-backend` |
| Frontend blank page | Check ECS files: `ssh ... "ls /var/www/globalstrat/build/"` |
| CORS errors | Verify `GLOBALSTRAT_ENV=production` is set in service |
| Database connection refused | Check PostgreSQL on 192.168.50.38: `pg_isready -h 192.168.50.38` |
| "502 Bad Gateway" everywhere | Check nginx on ECS: `ssh ... "nginx -t && systemctl status nginx"` |
| FRP "connection refused" | ECS frps not running: `ssh ... "systemctl status frps"` |
