# Codimente Private AI — On-Premises Deployment Guide

This guide installs Codimente Private AI on your own servers.
Nothing leaves your network except (optionally) the language
model API call — see *Air-gapped installations* below for the
fully offline setup.

```
┌──────────────────────────  Your server  ──────────────────────────┐
│                                                                   │
│  nginx (TLS 443) ──► gunicorn ──► Django application              │
│                                       │        │                  │
│                              PostgreSQL +      └─ worker thread   │
│                              pgvector          (document          │
│                                                 processing)      │
│  /var/codimente/media  ← uploaded knowledge documents            │
└───────────────────────────────────────────────────────────────────┘
```

## 1. Requirements

| Component | Minimum | Notes |
| --- | --- | --- |
| OS | Ubuntu 22.04+ / Debian 12+ | any Linux with systemd works |
| RAM | 8 GB | 16 GB recommended |
| Disk | 40 GB | grows with your document library |
| Python | 3.13 | |
| PostgreSQL | 16+ with the **pgvector** extension | packages: `postgresql`, `libpq-dev` |
| Reverse proxy | nginx (or IIS/Apache) | terminates TLS |

The machine does **not** need a GPU. Text embedding runs on CPU
(all-MiniLM-L6-v2, 384 dimensions).

## 2. System preparation

```bash
sudo apt update
sudo apt install -y python3.13 python3.13-venv postgresql nginx build-essential libpq-dev
sudo -u postgres createuser codimente --pwprompt
sudo -u postgres createdb codimente_ai --owner=codimente
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;" -d codimente_ai
```

If `CREATE EXTENSION` fails, install the pgvector package first
(`apt install postgresql-16-pgvector`, or build from source —
https://github.com/pgvector/pgvector).

## 3. Application installation

```bash
sudo mkdir -p /var/codimente/media
sudo adduser --system --group codimente
sudo git clone <your-repo-url> /opt/codimente
cd /opt/codimente
python3.13 -m venv venv
venv/bin/pip install -r requirements.txt
```

Create `/opt/codimente/.env`:

```
SECRET_KEY=<generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=codimente.internal.yourcompany.com
CSRF_TRUSTED_ORIGINS=https://codimente.internal.yourcompany.com
DB_NAME=codimente_ai
DB_USER=codimente
DB_PASSWORD=<the password from step 2>
DB_HOST=localhost
DB_PORT=5432
HF_TOKEN=<Hugging Face token, see section 6>
MEDIA_ROOT=/var/codimente/media
```

```bash
sudo chown codimente:codimente /opt/codimente/.env
sudo chown -R codimente:codimente /var/codimente/media
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py seed_organisation \
    --organisation "Your Company" \
    --admin-username admin \
    --admin-password "<choose-a-strong-password>"
```

`seed_organisation` is idempotent and creates the organisation,
its departmental assistants, one knowledge base per assistant
and the admin user.

## 4. Run as a service

`/etc/systemd/system/codimente.service`:

```ini
[Unit]
Description=Codimente Private AI
After=network.target postgresql.service

[Service]
User=codimente
Group=codimente
WorkingDirectory=/opt/codimente
Environment="DJANGO_SETTINGS_MODULE=codimente_ai.settings"
ExecStart=/opt/codimente/venv/bin/gunicorn codimente_ai.wsgi:application \
    --workers 2 --threads 4 --timeout 120 \
    --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now codimente
```

## 5. nginx + TLS

`/etc/nginx/sites-available/codimente`:

```nginx
server {
    listen 443 ssl http2;
    server_name codimente.internal.yourcompany.com;

    ssl_certificate     /etc/ssl/codimente/fullchain.pem;
    ssl_certificate_key /etc/ssl/codimente/privkey.pem;

    client_max_body_size 25M;   # uploads are limited to 20 MB

    location /static/ {
        alias /opt/codimente/staticfiles/;
    }

    location /media/ {
        alias /var/codimente/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/codimente /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

For an internal certificate authority or Let's Encrypt — both
work; the application only needs the `X-Forwarded-Proto https`
header to arrive.

Open `https://codimente.internal.yourcompany.com/accounts/login/`
and sign in with the admin credentials from step 3.

## 6. The AI provider

By default the assistant calls the **Hugging Face Inference
Router** (`HostedProvider`), which needs one outbound HTTPS
connection and an `HF_TOKEN`. Documents, conversations, users
and embeddings never leave your network in this mode.

**Air-gapped installations:** add an `OllamaProvider` to
`ai/providers/` (Ollama, vLLM or any OpenAI-compatible local
server) and point the settings at it. The provider abstraction
was designed for exactly this swap — no application code
changes. Contact Codimente for the on-prem model bundle.

**Embeddings:** by default these also travel to the Hugging
Face API. For a fully offline install, add the local
embedding model to the venv and switch backends:

```bash
venv/bin/pip install sentence-transformers
```

```
# .env
EMBEDDINGS_BACKEND=local
```

Both backends produce identical 384-dimensional vectors, so
existing pgvector data stays valid either way.

## 7. Updating

```bash
cd /opt/codimente
sudo -u codimente git pull
sudo -u codimente venv/bin/pip install -r requirements.txt
sudo -u codimente venv/bin/python manage.py migrate
sudo -u codimente venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart codimente
```

## 8. Health check and monitoring

`GET /health/` returns `200 {"status": "ok"}` when the
application and database are reachable, `503` otherwise. Point
Zabbix/Nagios/Uptime-Kuma at it — no authentication required.

## 9. Backups

Everything stateful lives in two places:

```bash
# Database (conversations, users, audit log, embeddings)
sudo -u postgres pg_dump codimente_ai | gzip > codimente_$(date +%F).sql.gz

# Uploaded documents
tar czf media_$(date +%F).tar.gz /var/codimente/media
```

Embeddings are reproducible from the uploaded documents, so a
database + media restore is always sufficient.

## 10. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `permission denied to create extension vector` | pgvector not installed for your Postgres version — see step 2 |
| 503 from the chat endpoint | `HF_TOKEN` missing/invalid, or the firewall blocks the router — check `journalctl -u codimente` |
| Login returns 403 | `CSRF_TRUSTED_ORIGINS` must exactly match `https://your-host` |
| `DisallowedHost` | add the host to `ALLOWED_HOSTS` |
| Upload stuck on "Pending" | the worker thread runs inside the web process — a restart (`systemctl restart codimente`) re-runs nothing; check the log for the failure and use the Reprocess button |
| Uploaded file disappears after update | `MEDIA_ROOT` must point to `/var/codimente/media`, not the repo directory |
