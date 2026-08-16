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

- [x] Create folder structure:
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
- [x] `infra/template.yaml` (SAM): define `JobTrackerTable` — PK `job_id` (String), on-demand billing.
- [x] **Enable Point-in-Time Recovery (PITR)** on `JobTrackerTable`. This is the "don't lose data" answer:
  - DynamoDB already synchronously replicates every write across 3 Availability Zones, so raw data loss from an AWS-side failure is essentially a non-issue.
  - PITR protects against the more realistic risk — an application bug or a fat-fingered delete — by letting you restore the table to any second within the last 35 days.
  - Cost scales with data size; for a personal job list (probably a few hundred small text records) this is fractions of a cent/month. Worth it for the low effort involved (one flag in the SAM template).
- [x] `backend/jobtracker/db.py`: thin boto3 wrapper —
  - `get_job(job_id)`
  - `put_job(job_item)` (create, dedup-safe via conditional `attribute_not_exists(job_id)`)
  - `list_jobs(is_active: bool)` — GSI on `is_active` or a scan+filter if volume stays low
  - `update_job(job_id, fields)`
  - `delete_job(job_id)`
- [x] `backend/jobtracker/models.py`: `JobItem` dataclass matching the schema in brief Section 3, with a `status` enum and `is_active` derived property.

### Step 2: REST API

- [x] `backend/jobtracker/api.py` (Lambda handler, routed via API Gateway HTTP API):
  - `GET /api/jobs?active=true|false`
  - `POST /api/jobs` (manual entry — brief Section 4.2)
  - `PUT /api/jobs/{id}`
  - `DELETE /api/jobs/{id}`
- [x] `infra/template.yaml`: wire API Gateway routes to the handler, attach the authorizer (Step 3) to every route except the auth endpoints.
- [x] Local test pass with `sam local start-api` + curl for all 4 endpoints.

### Step 3: Auth — set password on first login

Since there's no sensitive data in the tracker, this stays intentionally simple: no expiry, no rotation, no forgot-password flow.

- [x] `backend/jobtracker/auth.py`:
  - `POST /api/auth/setup` — only succeeds if no password hash exists yet. Hashes the submitted password (bcrypt) and stores it as a single item in DynamoDB (or a Secrets Manager value). Locks itself out once set.
  - `POST /api/auth/login` — compares submitted password against the stored hash; on success, issues a signed session token (HMAC, no expiry) as an HTTP-only cookie.
  - Lambda authorizer: validates the session cookie's signature on every `/api/jobs*` request; 401 if missing/invalid.
- [x] Frontend: if `/api/auth/setup` reports no password set yet, show a "Set your password" form instead of a login form; otherwise show login.

### Step 4: Frontend

- [x] `frontend/index.html` + Tailwind (CDN) — login/setup prompt, Active/Non-Active tabs, job table.
- [x] `frontend/app.js`:
  - Login/setup flow (session cookie handles subsequent requests automatically)
  - Fetch + render jobs per active tab
  - Status dropdown → `PUT` on change
  - Edit modal: JD/notes textareas, Save (`PUT`) and Delete (`DELETE` with confirm)
  - "Add Manual Job" form → `POST`
  - This is where "look and feel" gets dialed in — spend time here before moving to Milestone 2.
- [x] Point `app.js` at the deployed API Gateway base URL (config value, not hardcoded — use a small `config.js`).

### Step 5: Deploy & verify

- [x] `sam build && sam deploy --guided` for backend/infra.
- [x] Upload `frontend/` to S3, front with CloudFront (or AWS Amplify Hosting if that's less setup).
- [x] End-to-end check: set password, log in, add a job manually, edit it, change its status, delete it.

---

## Milestone 2 — Gmail ingestion (LinkedIn agent)

Goal: automatically populate the tracker from LinkedIn job-alert emails, on top of the working Milestone 1 system.

Stack decisions for this milestone: dependency management moves to `uv` (`backend/pyproject.toml` + `uv.lock`, exported to `requirements.txt` before `sam build` since SAM's Python build workflow only understands that format); company/role extraction uses LangChain (`langchain-openai`) with structured output instead of regex guessing, since email formatting varies too much for reliable regex parsing. Everything else (sender filter, job-URL regex, dedupe) stays plain Python — deterministic, no reason to route it through an LLM.

- [x] Migrate `backend/requirements.txt` to `backend/pyproject.toml` managed by `uv` (`uv init`/`uv add boto3 bcrypt`), commit `uv.lock`, add a small export step (`uv export --no-hashes -o requirements.txt`) ahead of `sam build`.
- [x] Local `.env` (gitignored) holding `OPENAI_API_KEY` for local dev/testing.
- [x] Register a Google Cloud project, enable Gmail API, create OAuth2 credentials (installed-app flow for personal Gmail — no domain-wide delegation available), run it once locally to get a refresh token.
- [x] One-time local script (`backend/scripts/gmail_auth.py`) to run the OAuth consent flow and print the refresh token.
- [x] Store `client_id`, `client_secret`, `refresh_token`, and `openai_api_key` in AWS Secrets Manager (single secret, JSON blob).
- [x] `backend/jobtracker/gmail_agent.py`:
  - Fetch messages matching `from:jobalerts-noreply@linkedin.com`
  - Regex: `https://www\.linkedin\.com/(?:comm/)?jobs/view/(\d+)`
  - Build `job_id = f"linkedin:{match}"`, dedup via `get_job`
  - LangChain structured-output extraction chain (`ChatOpenAI` + a Pydantic `JobExtraction` model: `company_name`, `role_title`) run on the email subject/body for each new job; falls back to "Needs Review / LinkedIn Job" if extraction is low-confidence or fails
  - Insert via `put_job` if new
  - Structure this as a `BaseEmailDiscoveryAgent` interface so the LinkedIn-specific parts (sender filter, URL regex) can be swapped out for Indeed later without rewriting the extraction or dedupe logic
- [x] `infra/template.yaml`: add the scanning Lambda + EventBridge Scheduler rule (rate: 60 minutes) + IAM permissions (Secrets Manager read, DynamoDB read/write). Heavy deps (LangChain/OpenAI/Google-auth) isolated in a separate Lambda Layer so the Milestone 1 functions stay lean.
- [x] Manual smoke test: ran the deployed Lambda once via `aws lambda invoke` against the live Gmail inbox with real LinkedIn alerts in it (found 5 distinct jobs from 7 matching emails).
- [x] Confirm EventBridge → Lambda → CloudWatch Logs shows scheduled runs firing and finding/skipping jobs correctly.
- [x] End-to-end check: cleared the test data, let the EventBridge schedule fire naturally on its own — same 5 jobs appeared automatically with zero manual invocation, confirmed via CloudWatch and the dashboard.

---

## Out of scope for v1 (per brief Section 4.3)

- Indeed ingestion agent — deferred, but `gmail_agent.py` should be structured so the LinkedIn-specific parsing can be extracted behind a `BaseEmailDiscoveryAgent` interface without a rewrite.
