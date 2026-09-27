# Codimente Private AI

An organisation-aware, permission-controlled RAG platform.
Companies deploy Codimente with their own documents, departments,
users and assistants. It is not a chatbot — every answer is
grounded in the organisation's approved knowledge, with source
attribution and strict departmental isolation.

> Deploying for a client on their own servers? See
> **[DEPLOY-ONPREM.md](DEPLOY-ONPREM.md)** — a step-by-step
> on-premises installation guide.
>
> Hosting the public demo on Render (with Tiger Cloud Postgres
> and Cloudflare DNS)? See **[DEPLOY-HOSTED.md](DEPLOY-HOSTED.md)**.
>
> End-user instructions live in **[USER-GUIDE.md](USER-GUIDE.md)** —
> share it with everyone you onboard.
>
> Connecting another system (intranet, HR portal, bot, mobile
> app) to ask questions through the API? See
> **[INTEGRATIONS.md](INTEGRATIONS.md)**.

## Architecture

```
Organisation
├── Users
├── AI Assistants
│   ├── Human Resources
│   ├── Finance
│   ├── Procurement
│   ├── ICT Support
│   └── General Assistant
├── Organisational Knowledge
│   ├── Policies
│   ├── Procedures
│   ├── Manuals
│   └── Other documents
└── Conversations
    ├── User
    ├── Assistant
    ├── Messages
    └── Sources
```

- **AI layer** — provider-based (`ai/providers/`). The default
  `HostedProvider` calls the Hugging Face Inference Router
  (GPT-OSS). Swapping in an `OllamaProvider` later requires no
  application changes.
- **Data** — PostgreSQL + pgvector. Embeddings use
  `all-MiniLM-L6-v2` (384 dimensions) through the Hugging Face
  Inference API by default, which keeps the web process small
  and fast to deploy; on-premises installs can generate them
  in-process instead with `EMBEDDINGS_BACKEND=local`.
- **Retrieval** — hybrid semantic (0.75) + keyword (0.25) scoring
  with a relevance threshold, so unrelated questions do not
  receive the mathematically closest chunk.
- **Security** — authentication, organisation scoping,
  assistant-level permissions (`AssistantAccess`),
  cross-organisation validation, CSRF protection, DOMPurify for
  rendered AI markdown, and a backend-enforced security chain on
  every conversation endpoint:

```
Conversation
  ↓ belongs to logged-in user?
  ↓ belongs to user's organisation?
  ↓ user has access to its assistant?
YES → messages returned
```

## Administration features

- **Organisation switching** — users belonging to several
  organisations can switch the active one from the chat sidebar
  (`organisations/<id>/switch/`). The choice is stored in the
  session and every query (assistants, conversations, knowledge,
  audit) is scoped to it.
- **Audit log** — an append-only, organisation-scoped trail
  (`/audit/`, admins only, also browsable read-only in Django
  admin). Recorded events include logins, failed login attempts,
  logouts, assistant access grants/revocations, organisation
  switches, document uploads, processing completions/failures,
  reprocess requests and deletions.
- **Background document processing** — uploads return
  immediately with a `pending` status; a worker thread owns the
  transitions `pending → processing → processed | failed` and
  the knowledge page polls the `document-status` endpoint every
  4 s so progress is visible without a manual refresh. The
  worker module is deliberately isolated: moving to Celery or a
  Render Background Worker later requires no changes to views
  or templates.

## Conversations

Conversations are persistent and per-assistant:

- The sidebar shows each assistant's own history.
- Clicking a conversation restores its messages and sources from
  PostgreSQL and sets `conversationId`, so new messages continue
  the same thread.
- Multi-turn memory: the model receives recent conversation
  history, and retrieval is contextualised with that history so
  vague follow-ups ("What happens to the rest?") retrieve the
  right material.
- Failed AI provider calls persist nothing — no orphan user
  messages — so a retry is always clean.

## Local development

1. Create a PostgreSQL database and user, and add them to `.env`:

   ```
   DB_NAME=codimente_ai
   DB_USER=codimente_ai_user
   DB_PASSWORD=...
   DB_HOST=localhost
   DB_PORT=5432
   HF_TOKEN=...
   ```

   Enable pgvector once (the migration also does this on fresh
   databases): `CREATE EXTENSION IF NOT EXISTS vector;`

2. Install and run:

   ```
   python -m venv venv
   venv/Scripts/pip install -r requirements.txt
   venv/Scripts/python manage.py migrate
   venv/Scripts/python manage.py runserver
   ```

3. Seed the demo organisation, assistants, knowledge bases
   and an admin user (idempotent — safe to re-run):

   ```
   venv/Scripts/python manage.py seed_organisation --admin-password "your-password"
   ```

   Add `--django-admin` to also grant the seeded user access to
   Django's `/admin/` site.

4. Optional: grant the DB role permission to run the test
   suite (tests create a temporary database):

   ```sql
   ALTER ROLE codimente_ai_user CREATEDB;
   ```

## Deployment to Render (ai.codimentesystems.com)

The repository ships with `render.yaml` (blueprint) and
`build.sh`.

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint** and select the
   repository. Render provisions:
   - PostgreSQL 17 database (pgvector available by default)
   - Web service running gunicorn
3. Set the remaining environment variables when prompted:
   - `HF_TOKEN` — Hugging Face token for the inference router
   - `AI_MODEL` — optional, defaults to
     `openai/gpt-oss-120b:cerebras`
   - `SEED_ADMIN_PASSWORD` — password for the organisation
     admin user created automatically on deploy
     (username: `admin`)
4. Add your custom domain `ai.codimentesystems.com` to the web
   service and create the CNAME at your DNS provider.
5. Deploy. `build.sh` installs dependencies, collects static
   files (whitenoise), applies migrations — including the
   `CREATE EXTENSION vector` step — and seeds the default
   organisation, departmental assistants and admin user
   automatically.

### Environment variables (production)

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Generated by Render from the blueprint |
| `DEBUG` | `False` in production |
| `ALLOWED_HOSTS` | `ai.codimentesystems.com,.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://ai.codimentesystems.com` |
| `DATABASE_URL` | Injected by Render automatically |
| `HF_TOKEN` | Hugging Face router token |
| `SEED_ADMIN_PASSWORD` | Password for the seeded admin user |

Production hardening activates automatically when `DEBUG=False`:
HSTS, secure/CSRF cookies, SSL redirect, `X_FRAME_OPTIONS=DENY`.

> **Note on uploads:** the blueprint attaches a small (1 GB)
> persistent disk at `/opt/app/media`, so uploaded documents
> survive deploys and restarts. This hosted instance is a demo:
> paying client deployments run on the client's own premises,
> where the same architecture (web process + worker thread +
> local disk) runs unchanged on a single server.

### Monitoring the demo

The service exposes an unauthenticated `GET /health/` endpoint:
`200 {"status": "ok"}` when the application and its database
are reachable, `503 {"status": "degraded"}` when the database
cannot be reached. Render's `healthCheckPath` is wired to it
(failed checks restart the service automatically), and any free
external monitor (e.g. UptimeRobot) can watch the same URL and
email you if the demo goes down.

## What is complete

- AI chat with a real LLM via a provider abstraction
- PostgreSQL + pgvector semantic RAG with hybrid retrieval
- Local embedding generation
- Departmental knowledge isolation per assistant
- Source attribution stored with assistant messages
- Grounding controls against hallucination
- Authentication, organisation membership, assistant permissions
- Cross-organisation protection (model-level validation)
- Persistent conversations, multi-turn memory, contextual RAG
- Conversation history with click-to-open, sources restored
- Organisation switching with session-scoped active membership
- Append-only audit log with admin UI
- Asynchronous document processing with live status polling
- `/health/` endpoint for uptime monitoring and Render health checks
- Production deployment configuration for Render
