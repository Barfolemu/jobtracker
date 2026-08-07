# Jobtracker Status

Last updated: 2026-08-07 (end of session). Pick up here next time.

---

## Milestone 2 — Gmail/LinkedIn ingestion: DONE, verified via natural scheduled run

Auto-populates the tracker from LinkedIn job-alert emails. Stack decisions: `uv` for backend dependency management (see below), LangChain (`langchain-openai`, model `gpt-4o-mini`) for company/role extraction instead of regex, since email formatting varies too much for reliable regex parsing.

**Code structure** (source of truth for "what does the agent do" — see `jobtracker-plan.md` Milestone 2 for the original spec):
- `backend/jobtracker/gmail_agent.py` — Lambda handler/orchestrator. Loads creds from Secrets Manager, runs each source agent, writes new jobs to DynamoDB.
- `backend/jobtracker/email_discovery/base.py` — `BaseEmailDiscoveryAgent` interface: `identify()` (cheap/deterministic — is this a job alert?) and `enrich()` (may call an LLM — only for jobs confirmed new, so re-scanning already-known emails never costs an OpenAI call).
- `backend/jobtracker/email_discovery/linkedin.py` — `LinkedInJobAgent`: job-URL regex (`https://www\.linkedin\.com/(?:comm/)?jobs/view/(\d+)`), fallback text ("Needs Review" / "LinkedIn Job") for low-confidence extractions.
- `backend/jobtracker/email_discovery/extraction.py` — LangChain structured-output chain (prompt + `ChatOpenAI` + `JobExtraction` Pydantic model: company_name, role_title, confidence).
- `backend/jobtracker/email_discovery/gmail_client.py` — thin Gmail REST wrapper (OAuth token refresh via `google-auth`, search/fetch, MIME body parsing). Deliberately *not* using `google-api-python-client` — it bundles a 99MB static discovery-doc cache for every Google API, not just Gmail.
- Gmail search is bounded to `newer_than:2d` (see `_RECENCY_WINDOW` in `gmail_agent.py`) — a 2-day rolling overlap so a missed hourly run can't let an email fall out of the window before being processed; DynamoDB dedup (`get_job` before enrich/write) makes reprocessing already-seen emails cheap and safe.

**Dependency isolation**: the three Milestone 1 Lambdas (`AuthFunction`, `AuthorizerFunction`, `JobsFunction`) share one `CodeUri`/`requirements.txt` (lean: `boto3`, `bcrypt` — now managed via `uv`, see below). `GmailAgentFunction` uses the *same* `CodeUri` (so it can import `jobtracker.db` etc.) but gets LangChain/OpenAI/Google-auth (~90MB) via a separate Lambda Layer (`GmailAgentDepsLayer`, `backend/layers/gmail_agent_deps/`), so the hot-path Authorizer (runs on every API request) isn't bloated by deps it never uses. Verified: all three Milestone 1 functions stayed at 32MB after this change; `GmailAgentFunction` is 32MB own code + 90MB layer, well under Lambda's 250MB unzipped limit.

**uv migration**: `backend/pyproject.toml` + `uv.lock` (main functions: `boto3`, `bcrypt`) and `backend/layers/gmail_agent_deps/pyproject.toml` + `uv.lock` (Gmail-only: `langchain`, `langchain-openai`, `google-auth`, `google-auth-oauthlib`, `requests`) are the source of truth for deps now — `sam build` still needs plain `requirements.txt` (no native uv support in SAM's Python build workflow), so each is exported via `uv export --no-hashes --no-dev -o requirements.txt` before building. Re-run that export after any `uv add`/`uv remove` in either directory. `backend/scripts/gmail_auth.py` (one-time OAuth consent script) uses `uv run --script` with inline PEP 723 metadata instead, so it doesn't need either project's venv.

**Google Cloud OAuth**: project `jobtracker-504817`, OAuth client is a Desktop-app type (installed-app flow), consent screen in Testing mode with Ashley's Gmail as the only test user. Downloaded `client_secret_*.json` is gitignored (pattern added this session) and redundant with `.env` — same values in both, can be deleted anytime. Refresh token has no expiry as long as the app stays in Testing mode with the same test user.

**Secrets**: `jobtracker-gmail-agent` (Secrets Manager, JSON blob: `google_client_id`, `google_client_secret`, `google_refresh_token`, `openai_api_key`) — defined as a stack resource in `infra/template.yaml`, values passed as `NoEcho` parameters at deploy time from `.env`, same pattern as `SessionSecret`.

**Verified via manual `aws lambda invoke` and twice via the EventBridge Scheduler firing naturally** on its own 60-minute rate schedule (`jobtracker-gmail-scan`) with zero manual intervention. Confirmed the dedupe design is safe even under an accidental duplicate invocation (AWS CLI retried mid-cold-start during the first manual test; the retry correctly saw everything as already-written and wrote nothing twice).

**Bug found and fixed post-verification**: LinkedIn's job-alert emails are actually digests bundling several distinct job postings into one message (each in its own dashed-line-delimited "card" with its own `View job:` link), not one job per email as originally assumed. `identify()` used a single `.search()` call, so it only ever captured the first job per email — verified against real inbox data this was silently dropping ~3 out of every 4 postings LinkedIn actually sent. Fixed: `identify()` now splits each email into its individual job cards (`LinkedInJobAgent` in `linkedin.py`) and returns one candidate per card; `enrich()` runs the LangChain extraction on each card's isolated text instead of the whole email, so company/role can't get confused across unrelated postings bundled in the same message. Re-verified via a natural scheduled run after the fix: 16 additional correctly-extracted jobs appeared (3 fewer than a same-day dry run found, because the oldest source email aged out of the 2-day recency window in the interim — expected behavior, not a bug).

---

## Milestone 1 — Manual tracker: DONE, backend + frontend both live in AWS

**Backend: live in AWS, fully verified.**
- Stack name: `jobtracker`
- Region: `us-east-1`
- Account: `<AWS_ACCOUNT_ID>`
- API URL: `https://uku9sxcbl9.execute-api.us-east-1.amazonaws.com`
- DynamoDB table: `JobTrackerTable` (PITR enabled)
- Resources: `JobsFunction`, `AuthFunction`, `AuthorizerFunction` (all Lambda), HTTP API + routes + Lambda authorizer
- Verified end-to-end via smoke test: `/api/auth/setup` → login → create/list/update/delete job, all correct.

**Frontend: hosted on S3 + CloudFront, verified end-to-end.**
- Live URL: **`https://d1uufm32urh929.cloudfront.net`** — this is what to use day-to-day to track jobs (no custom domain yet).
- Infra: `FrontendBucket` (private S3, `jobtracker-frontend-<AWS_ACCOUNT_ID>`) served through `FrontendDistribution` (CloudFront) via Origin Access Control — bucket is not publicly readable directly, only through CloudFront. Defined in `infra/template.yaml`.
- Deploy flow for future frontend changes:
  ```
  aws s3 sync frontend/ s3://jobtracker-frontend-<AWS_ACCOUNT_ID>/ --delete --profile claudejobtracker
  ```
  (No CloudFront invalidation needed unless caching becomes an issue — default cache behavior is `CachingOptimized`.)
- Backend's `FrontendOrigin` CORS parameter is now set to the CloudFront URL (was `http://localhost:5500` during local dev). If the CloudFront domain ever changes (e.g. distribution recreated), redeploy backend with `--parameter-overrides FrontendOrigin=<new-url>`.
- Verified via browser: loaded the CloudFront URL, confirmed session cookie from earlier testing still worked (sessions have no expiry), added a manual job, saw it in the Active list, deleted it directly via DynamoDB afterward (the in-app delete button uses a native `confirm()` dialog that browser automation avoids triggering) to leave the table clean. Table still has the pre-existing "test"/"manager" entry from earlier manual testing — left untouched, not created by this session.

---

## Open follow-ups (in rough priority order)

1. **Narrow the IAM policy.** Currently running on `jobtracker-claude-code-policy-temp-broad.json` (service-level action wildcards, but resource ARNs still tightly scoped to `jobtracker*`/`JobTrackerTable*`/`role/jobtracker-*`). Two rounds of additions so far: 4 CloudFront actions for the frontend's Origin Access Control (`GetOriginAccessControl`, `UpdateOriginAccessControl`, `DeleteOriginAccessControl`, `ListOriginAccessControls`), and a `LambdaLayersBroad` statement for the Gmail agent's dependency layer (`lambda:*` on the separate `layer:jobtracker-*` ARN namespace, which the existing function-scoped statement didn't cover). Plan: pull the actual API calls made from CloudTrail (`aws cloudtrail lookup-events --profile claudejobtracker`), fold only what was genuinely used into `jobtracker-claude-code-policy.json` (the narrow target policy), then swap the attached policy back to that.
2. **Custom domain.** Ashley bought `ashleycjones.com` and is building a separate personal homepage there (different project). Plan discussed: put that homepage at the root/apex, and once it exists, point a subdomain (e.g. `jobtracker.ashleycjones.com`) at this CloudFront distribution via Route 53 + an ACM cert + a CloudFront alternate domain name. Not started — revisit once the homepage project exists.
3. **Extend ingestion beyond LinkedIn.** The `BaseEmailDiscoveryAgent` interface (`backend/jobtracker/email_discovery/base.py`) was built specifically so an Indeed (or other source) agent can be added without touching `gmail_agent.py`'s orchestration or the dedupe logic — just a new `identify()`/`enrich()` implementation plus registering it in the `agents` list in `gmail_agent.py`. Not started.
4. **Model/prompt tuning.** Extraction currently uses `gpt-4o-mini` with a fairly minimal prompt (`backend/jobtracker/email_discovery/extraction.py`) and a flat 0.4 confidence threshold for falling back to "Needs Review". Worked cleanly on real LinkedIn alerts in testing, but hasn't been stress-tested against edge cases (unusual formatting, non-English postings, etc.) — revisit if "Needs Review" shows up often in practice.

---

## Practical notes for resuming

- SAM CLI is installed in an isolated venv, **not** on system PATH: `~/.venvs/sam-cli/bin/sam`. (System Python is 3.14; Lambda runtime is 3.12, so builds use `sam build --use-container` via Docker rather than a local 3.12 interpreter.)
- AWS profile: `claudejobtracker` (dedicated IAM user for this project). Verify with:
  ```
  aws sts get-caller-identity --profile claudejobtracker
  ```
- Deploy artifacts bucket: `jobtracker-sam-artifacts-<AWS_ACCOUNT_ID>` (self-managed, not SAM's auto `--resolve-s3` bootstrap — we hit permission issues with that path and switched to an explicit bucket; kept for consistency).
- Deploy command used (now includes the Gmail agent params, sourced from `.env`; `SessionSecret` omitted since it's preserved automatically — see below):
  ```
  cd infra
  set -a; source ../.env; set +a
  AWS_PROFILE=claudejobtracker ~/.venvs/sam-cli/bin/sam deploy \
    --stack-name jobtracker \
    --s3-bucket jobtracker-sam-artifacts-<AWS_ACCOUNT_ID> \
    --s3-prefix jobtracker \
    --capabilities CAPABILITY_IAM \
    --region us-east-1 \
    --parameter-overrides \
      FrontendOrigin=<origin> \
      GoogleClientId="$GOOGLE_CLIENT_ID" \
      GoogleClientSecret="$GOOGLE_CLIENT_SECRET" \
      GoogleRefreshToken="$GOOGLE_REFRESH_TOKEN" \
      OpenAiApiKey="$OPENAI_API_KEY" \
    --no-confirm-changeset --no-fail-on-empty-changeset
  ```
  `.env` (gitignored, repo root) holds `OPENAI_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` — the latter comes from running `uv run backend/scripts/gmail_auth.py` once.
- **`aws lambda invoke` can double-invoke on a slow cold start.** Hit this manually testing `GmailAgentFunction`: the CLI retried mid-flight while the first call was still cold-starting (~16s: init + Gmail/OpenAI calls), and the response actually returned was from the redundant second (fast, warm) call. Both invocations really ran server-side — check CloudWatch for multiple `RequestId`s in one log stream if a result looks suspiciously different from what you expect. Not a bug in our code; it's exactly why `gmail_agent.py`'s dedupe-before-write design matters — the duplicate call correctly saw everything as already-written and wrote nothing twice.
- **Session secret**: generated via `openssl rand -hex 32` and passed as a `NoEcho` CloudFormation parameter — intentionally not recorded in this repo. It's not retrievable from AWS after the fact (NoEcho parameters aren't readable via the API/console). If a future deploy needs it and it's been lost, generate a new one — this only invalidates existing login sessions (users just log in again with their existing password; the password hash lives separately in DynamoDB and is unaffected). Confirmed this session: on `sam deploy` to an *existing* stack, omitting a parameter from `--parameter-overrides` preserves its current value rather than erroring — so `SessionSecret` doesn't need to be re-passed on every deploy, only `FrontendOrigin` (or whatever actually changed).
- **AWS CLI session expiry**: the `claudejobtracker` profile's credentials can expire mid-session (`Your session has expired. Please reauthenticate using 'aws login'`). `aws login --profile claudejobtracker` opens a browser-based flow — has to be run by Ashley directly (via `! aws login --profile claudejobtracker` in chat), not by the agent, since it needs a real browser/terminal.
- Git: all work through this point is committed on `main` (no remote configured yet). Latest commit: `0a34d52`.

---

## Reference docs in this repo

- `jobtracker-brief.md` — original spec
- `jobtracker-plan.md` — milestone breakdown (source of truth for what Step X means)
- `jobtracker-claude-code-policy.json` — narrow/target IAM policy for the deploying user
- `jobtracker-claude-code-policy-temp-broad.json` — currently-attached broadened policy (temporary)
