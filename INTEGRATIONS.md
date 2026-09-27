# Codimente Private AI — Integration Guide

How to connect **any external system** — an intranet portal, HR
system, Teams/Slack bot, mobile app or backend service — to
Codimente Private AI and ask questions of its organisational
knowledge.

The connection is a plain HTTPS API. Nothing about your system
matters to Codimente except: it can send an HTTPS request with
one header. No SDK is required, no cookies, no browser.

```
Your system ── HTTPS + API token ──▶ Codimente Private AI ──▶ grounded answer + sources
```

---

## 1. How access works (read this first)

Every request is authorised through the same chain, whether it
comes from the web portal or from your system:

**user → organisation → assistant**

An integration is represented by an **API token** that bundles
all three:

| Token property | Meaning |
| --- | --- |
| **User** | The account your system acts as. Conversations it creates belong to this user. |
| **Organisation** | The one organisation the token operates in. Knowledge and assistants of other organisations are invisible to it. |
| **Assistants** | Only the assistants the user has been granted access to can be asked. |

A token is a **secret** — anyone holding it can read the
organisation's knowledge through the assistant. Treat it like a
password: it is shown **exactly once** when created, stored only
as a SHA-256 hash, and can be revoked at any moment.

---

## 2. One-time setup (done by the Codimente administrator)

Do these steps **in the target deployment** — the hosted demo
(`https://ai.codimentesystems.com`) or the client's on-prem
installation.

### Step 1 — Create a service user

In `/admin/` → **Users** → **Add user**: a dedicated account for
the integration, e.g. `svc-intranet`. Using a dedicated user
(meaning: not a human's account) keeps audit-log entries and
conversation history attributable to the integration itself.

### Step 2 — Give it organisation access

In `/admin/` → **Organisation memberships** → **Add**:
organisation = the target organisation, user = the service user,
role = `user` (an integration never needs `admin`), active ✓.

### Step 3 — Choose the assistants it may use

In `/admin/` → **Assistant accesses** → **Add**: membership =
the service user's membership, assistant = one assistant.
Repeat for every assistant the system should be able to ask.
**Less is safer** — grant only what the integration really
answers questions about.

### Step 4 — Issue the API token

In `/admin/` → **API tokens** → **Add**:

- **Name** — what connects through it, e.g. `Intranet portal`
  (unique per organisation)
- **User** — the service user from step 1
- **Organisation** — the organisation from step 2
- **Expires at** — optional; set a review date for high-value
  integrations

On save, the admin page shows the key **once**, in the format:

```
codai_xJ9k2...  (~50 characters)
```

Copy it immediately into your system's secret store — leaving
the page is the last time anyone can see it. Creation is
recorded in the organisation's audit log.

### Step 5 — Verify the credential (your first request)

```bash
curl https://YOUR-CODIMENTE-HOST/api/v1/whoami/ \
  -H "Authorization: Token codai_YOUR_KEY"
```

Success (HTTP 200) tells you exactly what the token can reach —
use this as your integration's startup health check:

```json
{
  "user": "svc-intranet",
  "organisation": "Codimente Demo Organisation",
  "organisation_id": 1,
  "token_name": "Intranet portal",
  "token_prefix": "codai_xJ9k2",
  "assistants": [
    {"slug": "human-resources", "name": "Human Resources"},
    {"slug": "general", "name": "General Assistant"}
  ]
}
```

The `assistants[].slug` values are what you pass as `assistant`
in every chat request.

---

## 3. The API

Base URL: **`https://YOUR-CODIMENTE-HOST/api/v1/`**

All endpoints require the header:

```
Authorization: Token codai_YOUR_KEY
```

(`Bearer` is accepted as a synonym for `Token`.)

### 3.1 Ask a question — `POST /api/v1/chat/`

```bash
curl -X POST https://YOUR-CODIMENTE-HOST/api/v1/chat/ \
  -H "Authorization: Token codai_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "How many annual leave days do we get?",
    "assistant": "human-resources"
  }'
```

| Field | Required | Meaning |
| --- | --- | --- |
| `message` | yes | The question text |
| `assistant` | no | Assistant slug; defaults to `general` |
| `conversation_id` | no | Continue an existing conversation (see 3.3) |

**Response `200`:**

```json
{
  "message": "How many annual leave days do we get?",
  "answer": "Full-time employees receive 27 working days of annual leave per year...",
  "assistant": "Human Resources",
  "provider": "huggingface",
  "conversation_id": 42,
  "sources": [
    {
      "title": "HR Handbook 2026",
      "page": 1,
      "knowledge_base": "Human Resources Knowledge",
      "chunk_index": 3,
      "similarity": 0.8631
    }
  ]
}
```

Display `answer` and the `sources` together — showing where an
answer comes from is the product's core promise to its users.

**Grounding behaviour (important for integrators):** the
assistant answers **only** from the approved documents of that
assistant. When the knowledge does not contain the answer, the
API still returns 200 — with a refusal text such as *"the
available organisational knowledge does not provide enough
information…"* and an **empty `sources` array**. That is not an
error; do not retry. Detect it via empty `sources` if your UI
needs to distinguish it.

### 3.2 Multi-turn conversations — `conversation_id`

Pass the returned `conversation_id` back on the next request to
keep context (follow-ups like *"and for part-time staff?"* work
across turns):

```json
{
  "message": "What happens if I do not use all my days?",
  "assistant": "human-resources",
  "conversation_id": 42
}
```

A conversation belongs to the token's user, organisation and
assistant — the same `conversation_id` with a different
`assistant` returns **404**.

### 3.3 List conversations — `GET /api/v1/conversations/`

Optional `?assistant=<slug>` filter. Returns the most recent 20
conversations of the token's user in its organisation:

```json
{
  "conversations": [
    {
      "id": 42,
      "title": "How many annual leave days do we get?",
      "assistant": "human-resources",
      "updated_at": "2026-09-27T10:14:03.512Z"
    }
  ]
}
```

### 3.4 Fetch a conversation — `GET /api/v1/conversations/<id>/`

Returns the full message history with sources for each
assistant message — for rendering transcripts in your system:

```json
{
  "conversation_id": 42,
  "title": "How many annual leave days do we get?",
  "assistant": {"id": 1, "name": "Human Resources", "slug": "human-resources"},
  "messages": [
    {
      "id": 101,
      "role": "user",
      "content": "How many annual leave days do we get?",
      "sources": null,
      "created_at": "2026-09-27T10:12:55.004Z"
    },
    {
      "id": 102,
      "role": "assistant",
      "content": "Full-time employees receive 27 working days...",
      "sources": [{"title": "HR Handbook 2026", "page": 1}],
      "created_at": "2026-09-27T10:12:58.330Z"
    }
  ]
}
```

---

## 4. Connecting your system — step by step

1. **Store the token** in your secret store (environment
   variable, vault). Never in source code, never in a mobile
   app or browser frontend — the token grants knowledge access,
   so only **server-side** code may hold it.
2. **At startup or deploy**, call `GET /api/v1/whoami/` and
   fail fast if the token is invalid, and (optionally) verify
   the expected assistant slugs are present.
3. **Send questions** with `POST /api/v1/chat/`. Use a client
   timeout of **at least 60 seconds** — grounded answers can
   take several seconds (up to ~30 s cold).
4. **Keep the thread**: store the returned `conversation_id`
   per user-conversation in your system and send it on
   follow-ups. Start a new conversation simply by omitting it.
5. **Render answer + sources.** Show `answer` as text (it is
   generated as Markdown), and list `sources[].title` /
   `sources[].page` as the provenance.
6. **Handle the failure modes** in §5 — especially 401 after a
   token revocation (re-fetch config / alert) and 429 by
   queuing, not hammering.

### Minimal examples

**Python (requests):**

```python
import os
import requests

CODEMENTE_URL = "https://YOUR-CODIMENTE-HOST"
API_TOKEN = os.environ["CODEMENTE_API_TOKEN"]

def ask(message, assistant, conversation_id=None):
    response = requests.post(
        f"{CODEMENTE_URL}/api/v1/chat/",
        headers={"Authorization": f"Token {API_TOKEN}"},
        json={
            "message": message,
            "assistant": assistant,
            "conversation_id": conversation_id,
        },
        timeout=90,
    )
    response.raise_for_status()
    return response.json()

result = ask(
    "How many annual leave days do we get?",
    assistant="human-resources",
)
print(result["answer"])
print([s["title"] for s in result["sources"]])
```

**JavaScript (Node 18+, fetch):**

```javascript
const CODEMENTE_URL = "https://YOUR-CODIMENTE-HOST";
const API_TOKEN = process.env.CODEMENTE_API_TOKEN;

async function ask(message, assistant, conversationId) {
  const response = await fetch(
    `${CODEMENTE_URL}/api/v1/chat/`,
    {
      method: "POST",
      headers: {
        "Authorization": `Token ${API_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        assistant,
        conversation_id: conversationId,
      }),
    }
  );

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(`Codimente ${response.status}: ${body.error}`);
  }

  return response.json();
}
```

---

## 5. Error responses — what to build for

All errors are JSON: `{"error": "human-readable reason"}`.

| HTTP | Meaning | What your system should do |
| --- | --- | --- |
| **400** | Malformed request (empty message, bad `conversation_id` type) | Fix the request; log the `error` text |
| **401** | Missing / invalid / deactivated / expired token, or deactivated user | Stop and alert: the credential was revoked or expired. Do not retry blindly |
| **403** | Token's user has no active membership in the token's organisation, or no access to the requested assistant | Configuration error: the admin must grant membership / assistant access (§2 steps 2–3) |
| **404** | No such conversation **for this token** (foreign or deleted) | Treat as "start a new conversation" — never retry the id |
| **429** | More than **30 chat requests per minute** for the token's user | Queue and retry after ~60 s with backoff |
| **503** | The AI provider failed to answer | Safe to retry once after a short pause; nothing was persisted |

Unknown or disabled assistants and knowledge of other
organisations are deliberately indistinguishable from
non-existent ones (403/404) — the API never confirms the
existence of anything the token may not see.

---

## 6. Operating the integration (administrator reference)

| Task | Where |
| --- | --- |
| See which token is used how | `/admin/` → **API tokens** → `last_used_at` |
| Revoke a leaked or retired token | `/admin/` → **API tokens** → edit → untick **Active** (deactivation is audited; deletion is disabled so audit history stays intact) |
| Rotate a token | Deactivate the old one, create a new one, update the secret in your system — both tokens can coexist briefly for a zero-downtime switch |
| Change what a token can ask | Grant/revoke **Assistant accesses** for its user — takes effect on the next request |
| Investigate an integration | **Audit log** (portal) + conversation history under the service user |

**Rate limit:** 30 chat requests per minute per token user.
Request more integrations as separate service users with their
own tokens if a system legitimately needs more throughput.

**On-prem deployments:** everything in this guide applies
unchanged — point the base URL at the client's own host. The
token, its organisation and its access are created inside *that*
installation; nothing is shared with the hosted demo.

---

## 7. Security rules of thumb

1. **One token per system.** Compromised or retired
   integrations can then be cut off individually without
   touching the others.
2. **Server-side only.** Never ship the token in browser code,
   mobile apps or public repositories. If a frontend needs the
   AI, let your backend proxy the call.
3. **Least privilege.** Grant the fewest assistants; use a
   `user` role, never `admin`.
4. **Expiry for high-value integrations.** `expires_at` forces a
   periodic rotation conversation.
5. **Watch `last_used_at`.** A token that should be busy but is
   silent — or one that is busy when it should be silent — is
   worth investigating in the audit log.
