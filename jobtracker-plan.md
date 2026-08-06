# Jobtracker Implementation Plan

Derived from `jobtracker-brief.md`. Organized into two milestones: get a working tracker with manual entry and a solid UI first, then layer in Gmail scanning.

---

## 0. Decisions to confirm before starting

| Decision | Options | Recommendation |
| :--- | :--- | :--- |
| Language | Python 3.12 vs Node.js | Python (boto3 + Gmail API are both mature; simpler Lambda packaging with SAM) |
| IaC tool | AWS SAM vs CDK vs raw Boto3 script | SAM — least boilerplate for a Lambda + API Gateway + DynamoDB app this size |
| Frontend | React/Vite vs vanilla HTML/JS | Vanilla HTML/JS + Tailwind (via CDN) — no build step, fine for a single-user app |
| Auth | First-login sets a password | See Milestone 1, Step 3 below |
| Repo layout | Monorepo (backend + frontend + infra together) | Yes, single repo, three top-level folders |

---

## Milestone 1 — Manual tracker (storage, API, UI, auth)

Goal: a fully working, deployed job tracker — add/edit/delete/status-change jobs by hand — with no Gmail dependency yet.

### Step 1: Repo scaffolding & storage

- [ ] Create folder structure:
  ```
  jobtracker/
    infra/            # SAM template, DynamoDB definition
    backend/
      jobtracker/
        db.py          # get_job, put_job, list_jobs, update_job, delete_job
        models.py       # JobItem schema/validation
        auth.py         # password setup/login/session logic
      requirements.txt
    frontend/
      index.html
      app.js
      styles.css
    jobtracker-brief.md
    jobtracker-plan.md
  ```
- [ ] `infra/template.yaml` (SAM): define `JobTrackerTable` — PK `job_id` (String), on-demand billing.
- [ ] **Enable Point-in-Time Recovery (PITR)** on `JobTrackerTable`. This is the "don't lose data" answer:
  - DynamoDB already synchronously replicates every write across 3 Availability Zones, so raw data loss from an AWS-side failure is essentially a non-issue.
  - PITR protects against the more realistic risk — an application bug or a fat-fingered delete — by letting you restore the table to any second within the last 35 days.
  - Cost scales with data size; for a personal job list (probably a few hundred small text records) this is fractions of a cent/month. Worth it for the low effort involved (one flag in the SAM template).
- [ ] `backend/jobtracker/db.py`: thin boto3 wrapper —
  - `get_job(job_id)`
  - `put_job(job_item)` (create, dedup-safe via conditional `attribute_not_exists(job_id)`)
  - `list_jobs(is_active: bool)` — GSI on `is_active` or a scan+filter if volume stays low
  - `update_job(job_id, fields)`
  - `delete_job(job_id)`
- [ ] `backend/jobtracker/models.py`: `JobItem` dataclass matching the schema in brief Section 3, with a `status` enum and `is_active` derived property.

### Step 2: REST API

- [ ] `backend/jobtracker/api.py` (Lambda handler, routed via API Gateway HTTP API):
  - `GET /api/jobs?active=true|false`
  - `POST /api/jobs` (manual entry — brief Section 4.2)
  - `PUT /api/jobs/{id}`
  - `DELETE /api/jobs/{id}`
- [ ] `infra/template.yaml`: wire API Gateway routes to the handler, attach the authorizer (Step 3) to every route except the auth endpoints.
- [ ] Local test pass with `sam local start-api` + curl for all 4 endpoints.

### Step 3: Auth — set password on first login

Since there's no sensitive data in the tracker, this stays intentionally simple: no expiry, no rotation, no forgot-password flow.

- [ ] `backend/jobtracker/auth.py`:
  - `POST /api/auth/setup` — only succeeds if no password hash exists yet. Hashes the submitted password (bcrypt) and stores it as a single item in DynamoDB (or a Secrets Manager value). Locks itself out once set.
  - `POST /api/auth/login` — compares submitted password against the stored hash; on success, issues a signed session token (HMAC, no expiry) as an HTTP-only cookie.
  - Lambda authorizer: validates the session cookie's signature on every `/api/jobs*` request; 401 if missing/invalid.
- [ ] Frontend: if `/api/auth/setup` reports no password set yet, show a "Set your password" form instead of a login form; otherwise show login.

### Step 4: Frontend

- [ ] `frontend/index.html` + Tailwind (CDN) — login/setup prompt, Active/Non-Active tabs, job table.
- [ ] `frontend/app.js`:
  - Login/setup flow (session cookie handles subsequent requests automatically)
  - Fetch + render jobs per active tab
  - Status dropdown → `PUT` on change
  - Edit modal: JD/notes textareas, Save (`PUT`) and Delete (`DELETE` with confirm)
  - "Add Manual Job" form → `POST`
  - This is where "look and feel" gets dialed in — spend time here before moving to Milestone 2.
- [ ] Point `app.js` at the deployed API Gateway base URL (config value, not hardcoded — use a small `config.js`).

### Step 5: Deploy & verify

- [ ] `sam build && sam deploy --guided` for backend/infra.
- [ ] Upload `frontend/` to S3, front with CloudFront (or AWS Amplify Hosting if that's less setup).
- [ ] End-to-end check: set password, log in, add a job manually, edit it, change its status, delete it.

---

## Milestone 2 — Gmail ingestion (LinkedIn agent)

Goal: automatically populate the tracker from LinkedIn job-alert emails, on top of the working Milestone 1 system.

- [ ] Register a Google Cloud project, enable Gmail API, create OAuth2 credentials (installed-app flow for personal Gmail — no domain-wide delegation available), run it once locally to get a refresh token.
- [ ] One-time local script (`backend/scripts/gmail_auth.py`) to run the OAuth consent flow and print the refresh token.
- [ ] Store `client_id`, `client_secret`, `refresh_token` in AWS Secrets Manager (single secret, JSON blob).
- [ ] `backend/jobtracker/gmail_agent.py`:
  - Fetch messages matching `from:jobalerts-noreply@linkedin.com`
  - Regex: `https://www\.linkedin\.com/(?:comm/)?jobs/view/(\d+)`
  - Build `job_id = f"linkedin:{match}"`, dedup via `get_job`, insert via `put_job` if new
  - Best-effort parse of company/role from subject or body; fallback to "Needs Review / LinkedIn Job"
- [ ] `infra/template.yaml`: add the scanning Lambda + EventBridge Scheduler rule (rate: 60 minutes) + IAM permissions (Secrets Manager read, DynamoDB read/write).
- [ ] Manual smoke test: run the Lambda once locally (`sam local invoke`) against a live Gmail inbox with a real LinkedIn alert in it.
- [ ] Confirm EventBridge → Lambda → CloudWatch Logs shows scheduled runs firing and finding/skipping jobs correctly.
- [ ] End-to-end check: trigger a real LinkedIn alert email, wait for next scheduled run (or invoke manually), confirm it appears in the dashboard as `new`.

---

## Out of scope for v1 (per brief Section 4.3)

- Indeed ingestion agent — deferred, but `gmail_agent.py` should be structured so the LinkedIn-specific parsing can be extracted behind a `BaseEmailDiscoveryAgent` interface without a rewrite.
