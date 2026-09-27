# Codimente Private AI — User Guide

Everything you need to use the platform day to day. Admin tasks
(uploading documents, the audit log) are covered at the end.

---

## Signing in

1. Open your company's Codimente address (for the demo:
   `https://ai.codimentesystems.com`).
2. Enter the **username and password** your administrator gave
   you → **Sign In**.
3. After 20 minutes of inactivity you may be signed out — just
   sign in again; your conversations are kept.

**Forgot your password?** Administrators create accounts and
can reset passwords — contact them. (Failed sign-ins are
recorded in the organisation's audit log, so never share your
credentials.)

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

1. Sidebar → **Manage knowledge** (admins only).
2. Each assistant has its own knowledge section → **+ Upload
   document**.
3. Accepted: **PDF, DOCX, TXT** — up to **20 MB**.
4. The upload returns immediately with status **Pending**:
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

Superusers can manage users, memberships, assistant access and
view the audit trail. Regular users never need it.

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
