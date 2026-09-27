# Codimente Private AI — User Guide

Everything you need to use the platform day to day. Admin tasks
(uploading documents, the audit log) are covered at the end.

---

## Signing in

1. Open your company's Codimente address (for the demo:
   `https://ai.codimentesystems.com`).
2. Enter the **username and password** your administrator gave
   you → **Sign In**.
3. You stay signed in on that browser until you sign out (or
   the session expires) — your conversations are always kept.

**Forgot your password?** Administrators create accounts and
can reset passwords — contact them. (Failed sign-ins are
recorded in the organisation's audit log, so never share your
credentials.)

---

## What to do after you sign in

The chat screen shows these steps right on the welcome panel:

1. **Pick an assistant** in the left sidebar — each one answers
   only from its own approved documents.
2. **Type your question** at the bottom and press **Enter**.
3. **Open the Sources** under the answer to verify it against
   the original document.

Or click one of the example questions (the chips under the
welcome panel) — it fills the box and sends for you.

**Administrators** also see a tip on the welcome panel: use
**Manage knowledge** in the sidebar to upload the documents
your team asks about. The full upload sequence is in the
administrator section below.

**Looking for `/admin/`?** That is the separate Django
administration site for user accounts and permissions — see
the note in the administrator section below. Everyday use
needs nothing from it.

---

## Asking questions

1. Pick an assistant in the left sidebar. Each one answers
   **only from its own approved documents**:
   - **Human Resources** — leave, benefits, conduct, HR policy
   - **Finance** — budgets, expenses, payments, financial policy
   - **Procurement** — suppliers, purchasing, tenders
   - **ICT Support** — systems, accounts, hardware, IT procedures
   - **General Assistant** — questions across all departments
2. Type your question at the bottom and press **Enter** (or the
   ➤ button). Use **Shift+Enter** for a new line.
3. The answer appears with **Sources** beneath it — the exact
   document (and page, for PDFs) the answer came from.
   **Always verify important decisions against that source.**

### Good questions

- "How many annual leave days am I entitled to?"
- "What is the per diem for international travel?"
- "How many quotations do we need for a KES 300,000 purchase?"

### What the assistant will NOT do

If the answer is not in your organisation's approved documents,
it says so instead of guessing. That is deliberate — trust the
refusals as much as the answers.

---

## Conversations

- **Start over:** *+ New conversation* resets the screen; the
  next message begins a fresh thread.
- **Continue later:** conversations are saved per assistant in
  the sidebar. Click one to reopen it with all messages and
  sources, and keep chatting — the assistant remembers the
  thread's context.
- **Follow-ups work:** "and what about part-time staff?" is
  understood as referring to the previous question.
- Conversations belong to **you alone** — no other user (in any
  organisation) can open them, even with the link.

---

## Multiple organisations (if enabled for you)

If you belong to more than one organisation, the sidebar shows
**Organisations** with a *"Switch to …"* link. The assistants,
documents and history you see always belong to the active
organisation — switching is instantaneous and fully separated.

---

## For administrators

### Uploading knowledge (Manage knowledge)

**Quick reference — the upload sequence:**

1. Sidebar → **Manage knowledge** (admins only).
2. Find the assistant's section → **+ Upload document**.
3. Choose the file (**PDF, DOCX or TXT**, max **20 MB**) and
   give it a clear title, e.g. *"HR Handbook 2026"* — users
   see this title in the sources of answers.
4. Click **Upload and process** → the status badge runs
   **Pending → Processing → Processed** by itself (a couple of
   minutes for a large PDF).
5. **Test it**: ask the assistant a question the document
   answers — the reply must cite it under **Sources**.
6. Only when the badge says **Processed** is the document live
   for users.

The same steps are shown on the upload page itself. More
detail:
   - **Processing** → the document is being split into chunks
     and embedded (live, no refresh needed)
   - **Processed** → the assistant can now answer from it
   - **Failed** → see the audit log for the error; fix and use
     **Reprocess**
5. **Delete** removes a document *and* all of its knowledge
   chunks permanently (you will be asked to confirm).

Best practice: upload the current, approved version of a
policy. To replace one, upload the new file and delete the old
one.

### Reading the audit log

Sidebar → **Audit log** shows the last 200 organisation events:
sign-ins (including failed attempts), assistant access changes,
organisation switches, and every document upload, processing
result and deletion — with actor, time and details. Entries are
**append-only**: nobody can edit or delete history, not even in
the admin interface.

### Django admin (`/admin/`)

`/admin/` is Django's own administration site — separate from
the portal. It manages **users, passwords and Django
permissions** (things the portal deliberately does not
expose). Regular users never need it.

> **Getting `403 Forbidden` on `/admin/`?** That is expected
> without *Django staff status*. There are two unrelated
> admin layers:
>
> | Layer | Grants | Where it is given |
> | --- | --- | --- |
> | **Organisation admin** | Manage knowledge, audit log | Portal — memberships (org role "admin") |
> | **Django admin** | `/admin/` pages | `is_staff` + `is_superuser` on the user |
>
> An organisation admin **does not** automatically get
> `/admin/`, and "Staff status" is a checkbox on the user page
> in `/admin/` itself (a superuser without it still gets 403).
>
> **Fix from the command line** (Render Shell →
> `python manage.py promote_admin --username guest`), or
> promote all organisation admins at once with
> `python manage.py promote_admin`. Users already in `/admin/`
> can instead tick **Staff status** and **Superuser status**
> on the user's page and save.
>
> **Signed into the portal but `/chat/` itself returns 403?**
> That is the other gate: portal access needs an organisation
> membership **and** assistant access rows, and neither is
> created by adding a user in `/admin/`. Re-running
> `python manage.py seed_organisation --django-admin
> --admin-username <name>` wires all of it up idempotently
> (it never resets the password), or add a membership with
> role **Administrator** plus **assistant access** entries in
> `/admin/` by hand.

---

## Troubleshooting

| Problem | What to do |
| --- | --- |
| "Invalid username or password" | Check for typos; if it persists, ask an admin — repeated failures are audited |
| Answer says knowledge "does not provide enough information" | The document hasn't been uploaded (or processed) for that assistant — check Manage knowledge |
| Document stuck on **Pending/Processing** | Large PDFs take a minute or two; if far longer, press **Reprocess** |
| Document **Failed** | Usually a scanned/image-only PDF with no readable text — upload a text-based version |
| Answer looks wrong or outdated | Open the cited source; if the document is old, upload the newer version and delete the stale one |
| Page behaves oddly after an update | Hard-refresh with **Ctrl+F5** to fetch the new styles |
| `/admin/` shows **403 Forbidden** despite a valid login | The account lacks Django staff status (see the admin section above) | An existing superuser ticks **Staff status** on the user, or run `python manage.py promote_admin --username <name>` |
