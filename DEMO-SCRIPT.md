# Codimente Private AI — Client Demo Script

A 30-minute, copy-paste-ready demo flow. The trick that sells
RAG: every answer contains facts that **do not exist in any
language model's training data** — they come only from the
documents you uploaded minutes earlier.

## Before the client arrives (10 min prep)

1. Deploy is live and `https://ai.codimentesystems.com/health/`
   says `{"status": "ok"}`.
2. Log in as `admin`.
3. Create the four demo documents below (Notepad → plain
   `.txt` files — uploads accept TXT, PDF and DOCX).
4. Upload each document to its assistant via **Manage
   knowledge**, and wait for every badge to turn **Processed**.
5. Send one test question per assistant so no live demo starts
   with a cold first request.
6. Have a second browser window (or incognito) open on the
   login page for the security moment in act 3.

> Text files keep the demo simple. For clients who want to see
> "real" documents, convert the same content to PDF — page
> numbers then appear in the source cards, which looks even
> better.

## The demo documents

Save each block as its own `.txt` file. The numbers are
deliberately invented — that is the whole point.

**`hr-handbook-2026.txt`** → upload to *Human Resources*

```
Codimente Systems — HR Handbook 2026

Annual leave: Full-time employees receive 27 working days of
annual leave per year. Leave must be taken before 31 March of
the following year; untaken days lapse unless written approval
from the HR Director is obtained.

Sick leave: 10 days per year on full pay, certified by a
registered medical practitioner.

Probation: The first 4 months of employment are probationary.
During probation, notice is 7 days on either side.

Remote work: Employees may work remotely up to 3 days per week
with supervisor approval recorded in the HR portal.
```

**`finance-policy-2026.txt`** → upload to *Finance*

```
Codimente Systems — Finance Policy 2026

Expense reimbursement: Claims must be submitted within 21 days
of the expense date. Claims older than 21 days require CFO
sign-off.

Per diem: Regional travel KES 6,500 per night; international
travel USD 220 per night.

Petty cash: Limited to KES 15,000 per transaction and KES
40,000 per month per department.

Purchase approvals: Expenditure above KES 250,000 requires two
approvals — the department head and the Finance Director.
```

**`procurement-manual-2026.txt`** → upload to *Procurement*

```
Codimente Systems — Procurement Manual 2026

Quotations: Purchases between KES 100,000 and KES 500,000
require 3 written quotations. Above KES 500,000, a full tender
with a 5-member evaluation committee is required.

Supplier onboarding: New suppliers must provide a valid tax
certificate and bank letter. Onboarding takes 10 working days.

Framework agreements run for 24 months and may be extended
once, by 6 months, with Procurement Committee approval.
```

**`ict-runbook-2026.txt`** → upload to *ICT Support*

```
Codimente Systems — ICT Runbook 2026

Password reset: Staff password resets are handled via the
self-service portal; locked accounts auto-unlock after 15
minutes.

VPN: Access requests require department head approval and are
reviewed every 6 months.

Backup: Daily incremental at 22:00, full backup each Sunday.
Restoration requests are fulfilled within 4 working hours.
```

## The flow (30 minutes)

### Act 1 — The story (5 min, no screen)

- "Every company has answers buried in PDFs nobody can find.
  Generic chatbots don't know your policies — and worse, they
  invent plausible ones. Codimente AI answers **only** from
  documents your organisation approves, and shows the source."

### Act 2 — The grounded answers (12 min)

Sign in, then for each assistant: ask, let the answer render,
**point at the source card** ("Page 1, HR Handbook 2026").

The welcome screen's three numbered steps (pick an assistant →
ask → verify the source) mirror this exact flow — and the
suggestion chips under it are live: clicking one sends a real
question, handy for hands-on client moments.

| Ask (exact wording works well) | The fact it must cite |
| --- | --- |
| HR: "How many annual leave days do we get, and what happens if I don't use them?" | 27 days; lapses 31 March unless HR Director approves |
| HR: "I'm 3 months in, how much notice do I need to give?" | 7 days (probation) — the model must reason from the handbook, not general law |
| Finance: "I travelled to Kampala last week. What's my per diem and when must I claim?" | USD 220/night; within 21 days |
| Finance: "We need a laptop worth KES 300,000 — who signs?" | Two approvals: department head + Finance Director |
| Procurement: "We're buying something worth KES 450,000 — how do we buy it?" | 3 written quotations |
| ICT: "A user is locked out — how long until they're back in?" | Auto-unlock after 15 minutes |

**The killer follow-up** (any assistant):
> "What does the policy say about lunch allowances?"

Expected: *"The available organisational knowledge does not
provide enough information to answer that."* — **this is the
most important answer of the demo.** A generic chatbot would
invent something. Ours refuses. That's the trust story.

### Act 3 — The security story (8 min)

1. In the second browser, attempt a wrong password.
2. Back in admin: sidebar → **Audit log** — the failed login is
   on screen, timestamped. Scroll: logins, uploads, switches,
   deletions are all there. "Every security-relevant event is
   recorded and visible to admins."
3. **Manage knowledge** → upload a tiny document live and watch
   the badge go **Pending → Processing → Processed**. "It's
   chunked, embedded, and searchable in seconds — on your
   infrastructure."
4. Optional flourish: open Django admin (`/admin/`) briefly to
   show the append-only audit trail (no edit/delete buttons).

### Act 4 — The close (5 min)

- "This hosted site is our demo. **Your deployment never
  touches our cloud** — one server on your premises:
  PostgreSQL with vector search, the AI layer, and your
  documents. See `DEPLOY-ONPREM.md` — it's a half-day install
  with your IT team."
- "Nothing leaves your network except the language model call —
  and for air-gapped clients we swap in a local model. The
  product was designed for that from day one."
- **The API moment** (lands well with technical clients): any
  system they own can ask the same assistants with one HTTP
  call — no SDK, no cookies:

  ```bash
  curl https://ai.codimentesystems.com/api/v1/chat/ \
    -H "Authorization: Token codai_..." \
    -H "Content-Type: application/json" \
    -d '{"message": "How many annual leave days do we get?",
         "assistant": "human-resources"}'
  ```

  The answer arrives grounded, with the same source cards —
  "this is how your intranet or HR portal embeds Codimente.
  Full guide: `INTEGRATIONS.md`."
- Leave-behind: send the client the source cards' titles or a
  screenshot pack after the meeting.

## If something misbehaves

| Symptom | Say | Do |
| --- | --- | --- |
| Answer is slow (>20 s) | "First request warms the model — watch the thinking indicator, then it's instant" | Ask the follow-up, it will be fast |
| 503 on chat | "The model provider hiccuped — the system is designed to fail clean" | Retry once; nothing was saved, nothing corrupted |
| Answer cites nothing | The question drifted off-document | Use the *lunch allowance* line above deliberately |
| Upload stuck on Pending | Processing thread is busy | Click **Reprocess** and continue talking — badge will settle |

## Do NOT demo

- Multi-organisation switching (needs a second org seeded —
  only set it up if the client scenario calls for it).
- The Django admin beyond a glance (staff tooling, not polish).
- Deleting the seeded assistants or renaming slugs — demo
  questions are tied to them.
