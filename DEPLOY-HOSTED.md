# Codimente Private AI — Hosted Demo Deployment (Render + Tiger Cloud + Cloudflare)

Step-by-step guide for hosting the demo at `ai.codimentesystems.com`.

Architecture in one line: **GitHub (VMANYEMU/codimente-ai) → Render web service
(Frankfurt) → Tiger Cloud PostgreSQL (external, free) → Cloudflare DNS**.

> For client on-premises installs, see `DEPLOY-ONPREM.md` instead.
> For the client demo flow itself, see `DEMO-SCRIPT.md`.

---

## Part 1 — Free PostgreSQL on Tiger Cloud (~5 minutes)

Render's single free-database slot is reserved by another project, so the
demo uses an external managed Postgres. Tiger Cloud's free tier: no credit
card, no expiry, 750 MB, pgvector supported.

1. Go to **https://www.tigerdata.com/cloud** and sign up (your own email —
   you own this database).
2. Create a **project**, then a **service**:
   - Region: **EU / Frankfurt** (close to the Render web service)
   - Smallest size is fine
3. When the service is **running**, open its **SQL editor** (or connect with
   `psql` using the connection string) and enable pgvector once:

   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

4. Copy the **connection string** (looks like
   `postgres://tsdbadmin:xxxx@xxxx.cloud.tigerdata.com:xxxxx/tsdb`).
   Keep it ready for Part 2.

---

## Part 2 — Render web service (~5 min setup, ~3 min build)

1. Sign in at **https://dashboard.render.com** using GitHub, as the
   **VMANYEMU** account. Grant Render access to `VMANYEMU/codimente-ai`.
2. **New + → Blueprint** → select the repository `codimente-ai` → Connect.
3. Render reads `render.yaml` (web service only — no Render database) and
   asks for four secrets. Fill them exactly:

   | Variable | Value |
   | --- | --- |
   | `HF_TOKEN` | Hugging Face token with **Make calls to Inference Providers** enabled (huggingface.co → Settings → Access Tokens). Used for BOTH chat and embeddings. |
   | `AI_MODEL` | Leave **empty** (defaults to `openai/gpt-oss-120b:cerebras`) |
   | `SEED_ADMIN_PASSWORD` | A strong password — **this becomes the demo login** (username `admin`). Save it in a password manager. |
   | `DATABASE_URL` | The Tiger Cloud connection string from Part 1 |

4. Click **Apply**.

### What the build does (in order)

1. `pip install -r requirements.txt` — slim dependency set, **no torch**;
   takes ~2–3 minutes (previously 10–15 with the ML stack).
2. `collectstatic` — static files for whitenoise.
3. `migrate` — creates all tables incl. pgvector fields.
4. `seed_organisation --django-admin` — creates the organisation,
   5 assistants (human-resources, finance, procurement, ict-support,
   general), their knowledge bases and the `admin` user — with
   Django `/admin/` access granted (look for
   `Granted Django admin status to 'admin'.` in the log).

### Success looks like

```
Applying core.0003_auditlog... OK
Applying knowledge.0003_document_status... OK
Organisation seeding complete.
Build succeeded 🎉
```

Then verify:

- `https://codimente-ai-xxxx.onrender.com/health/` →
  `{"status": "ok", "database": "ok"}` (proves app + database + pgvector)
- `https://codimente-ai-xxxx.onrender.com/accounts/login/` → sign in as
  `admin` + your seed password.

### The pipeline proof (do once, before any client demo)

Sidebar → **Manage knowledge** → upload a small `.txt` or `.pdf` (a sample
is in `DEMO-SCRIPT.md`) and watch the status badge go:

```
Pending → Processing → Processed
```

If it reaches **Processed**, chat + retrieval + API embeddings all work in
production. If it goes **Failed**, open the **Audit log** — the exact
embedding API error is recorded there.

---

## Part 3 — Cloudflare DNS (2 minutes)

1. Render → service **codimente-ai** → **Settings → Custom Domains →
   Add Custom Domain** → enter `ai.codimentesystems.com`.
2. Render shows a CNAME target like `codimente-ai-xxxx.onrender.com` —
   copy it.
3. Cloudflare → zone **codimentesystems.com** → **DNS → Records →
   Add record**:
   - Type: `CNAME`
   - Name: `ai`
   - Target: the onrender.com value from step 2
   - TTL: Auto
   - **Proxy status: DNS only (grey cloud)** ← critical

**Why grey cloud:** the app forces HTTPS
(`SECURE_SSL_REDIRECT=True`). Cloudflare's proxy with default *Flexible*
SSL reaches Render over HTTP and creates an infinite redirect loop.
DNS-only sends visitors straight to Render's valid certificate.

(If you later want Cloudflare's CDN/WAF: keep the proxy **on** AND set
**SSL/TLS → Overview → Full (strict)** — that combination also works.)

4. Back in Render, wait for the domain to show **Verified** and
   **Certificate active** (a few minutes, automatic).

Then `https://ai.codimentesystems.com` is the demo URL.

---

## Demo-day hygiene

- **Warm up 15 minutes before** a client session: open `/health/`, log in,
  send one chat question. Wakes database connections and the HF router so
  nothing cold happens on stage.
- Add `https://ai.codimentesystems.com/health/` to a free external monitor
  (e.g. UptimeRobot) for email alerts.
- Every `git push` to `main` auto-deploys. Check the Events tab after
  pushing.
- Uploaded documents live on a 1 GB Render disk at `/opt/app/media` and
  survive deploys and restarts.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Build fails at migrate: `connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused` | `DATABASE_URL` not set on the service | Environment tab → set it to the Tiger Cloud connection string → Manual Deploy |
| `could not translate host name "dpg-...-a" to address` | URL still points at a deleted/other-region Render internal database | Use the **Tiger Cloud** external connection string |
| `server does not support SSL, but SSL was required` | URL uses a Render *internal* hostname | Use the external hostname (the settings auto-select sslmode) |
| Runtime: `Ran out of memory (used over 512MB)` | Legacy cause was torch in-process embeddings — now fixed via the HF API; if it recurs, check no stray worker config | Confirm latest `main` is deployed and `EMBEDDINGS_BACKEND` is `api` |
| Chat returns 503 / "could not obtain a response from the AI provider" | `HF_TOKEN` missing/invalid or lacks Inference Providers permission | Regenerate token, update env var, redeploy |
| Document stuck **Failed** | Embedding API error | Audit log → `document.failed` event → `detail.error` has the API response |
| `DisallowedHost` | Host missing from allowlist | `ALLOWED_HOSTS` must be `ai.codimentesystems.com,.onrender.com` |
| 403 on login submit | CSRF origin mismatch | `CSRF_TRUSTED_ORIGINS` must be exactly `https://ai.codimentesystems.com` |
| `permission denied to create extension vector` | Database without pgvector rights/support | Run `CREATE EXTENSION IF NOT EXISTS vector;` as the Tiger admin user (Part 1, step 3) |
| Login forgotten | Seeded admin password lost | Delete + re-apply the blueprint with a new `SEED_ADMIN_PASSWORD`, or run `python manage.py changepassword admin` via Render Shell |
| 403 on `/admin/` with a valid portal login | Django admin needs `is_staff`/`is_superuser` on the user — organisation "admin" rights alone do not grant it (this includes users added via *Add user*, which does not show a Staff status field) | Render Shell → `python manage.py promote_admin --username <name>` (or plain `python manage.py promote_admin` to promote every organisation admin), then sign in again |

---

## Cleanup of the old codimente account (after the new site is green)

1. Old Render account → service `codimente-ai` → Settings → **Delete
   Service** (this also ends the old low-memory warnings).
2. Old GitHub account → repository `codimentebw-commits/codimente-ai` →
   Settings → Danger Zone → **Delete this repository**.

The local clone and `VMANYEMU/codimente-ai` hold the full history; nothing
is lost by deleting the old copies.
