# Jobtracker Status

Last updated: 2026-08-06 (end of session). Pick up here next time.

---

## Milestone 1 — Manual tracker: backend done & deployed, frontend hosting deferred

**Backend: live in AWS, fully verified.**
- Stack name: `jobtracker`
- Region: `us-east-1`
- Account: `<AWS_ACCOUNT_ID>`
- API URL: `https://uku9sxcbl9.execute-api.us-east-1.amazonaws.com`
- DynamoDB table: `JobTrackerTable` (PITR enabled)
- Resources: `JobsFunction`, `AuthFunction`, `AuthorizerFunction` (all Lambda), HTTP API + routes + Lambda authorizer
- Verified end-to-end via smoke test: `/api/auth/setup` → login → create/list/update/delete job, all correct. Table was left clean afterward (no leftover test data/password).

**Frontend: built, tested locally, NOT yet hosted in AWS.**
- Code is done (`frontend/index.html`, `app.js`, `styles.css`, `config.js`) and confirmed working end-to-end against the live API by serving it locally:
  ```
  cd frontend && python3 -m http.server 5500
  ```
  then open `http://localhost:5500`. This works because the deployed API's CORS `FrontendOrigin` parameter is currently set to `http://localhost:5500`.
- **Deliberately deferred**: hosting on S3 + CloudFront. Decided to leave it as local-only until we "get it fully deployed" in one go, rather than doing it piecemeal. Do this next session.
- When we do host it: after CloudFront is up, redeploy the stack with `--parameter-overrides FrontendOrigin=<cloudfront-url>` (see `infra/template.yaml`) so CORS allows the real origin, and update `frontend/config.js`'s `API_BASE_URL` if it ever changes.

---

## Open follow-ups (in rough priority order)

1. **Finish Milestone 1 Step 5**: deploy frontend to S3 + CloudFront (or Amplify Hosting), update `FrontendOrigin` param + redeploy backend stack for CORS.
2. **Narrow the IAM policy.** We're currently running on `jobtracker-claude-code-policy-temp-broad.json` (service-level action wildcards, but resource ARNs still tightly scoped to `jobtracker*`/`JobTrackerTable*`/`role/jobtracker-*`). Plan: pull the actual API calls made during this deploy from CloudTrail (`aws cloudtrail lookup-events --profile claudejobtracker`), fold only what was genuinely used into `jobtracker-claude-code-policy.json` (the narrow target policy — already has the real fixes: SAM transform permission, `aws-sam-cli-managed-default` stack access, API Gateway `/tags/*`), then swap the attached policy back to that.
3. **Milestone 2**: Gmail/LinkedIn ingestion agent (see `jobtracker-plan.md`) — not started.

---

## Practical notes for resuming

- SAM CLI is installed in an isolated venv, **not** on system PATH: `~/.venvs/sam-cli/bin/sam`. (System Python is 3.14; Lambda runtime is 3.12, so builds use `sam build --use-container` via Docker rather than a local 3.12 interpreter.)
- AWS profile: `claudejobtracker` (dedicated IAM user for this project). Verify with:
  ```
  aws sts get-caller-identity --profile claudejobtracker
  ```
- Deploy artifacts bucket: `jobtracker-sam-artifacts-<AWS_ACCOUNT_ID>` (self-managed, not SAM's auto `--resolve-s3` bootstrap — we hit permission issues with that path and switched to an explicit bucket; kept for consistency).
- Deploy command used:
  ```
  AWS_PROFILE=claudejobtracker ~/.venvs/sam-cli/bin/sam deploy \
    --stack-name jobtracker \
    --s3-bucket jobtracker-sam-artifacts-<AWS_ACCOUNT_ID> \
    --s3-prefix jobtracker \
    --capabilities CAPABILITY_IAM \
    --region us-east-1 \
    --parameter-overrides FrontendOrigin=<origin> SessionSecret=<secret> \
    --no-confirm-changeset --no-fail-on-empty-changeset
  ```
- **Session secret**: generated via `openssl rand -hex 32` and passed as a `NoEcho` CloudFormation parameter — intentionally not recorded in this repo. It's not retrievable from AWS after the fact (NoEcho parameters aren't readable via the API/console). If a future deploy needs it and it's been lost, generate a new one — this only invalidates existing login sessions (users just log in again with their existing password; the password hash lives separately in DynamoDB and is unaffected).
- Git: all work through this point is committed on `main` (no remote configured yet). Latest commit: `df97989`.

---

## Reference docs in this repo

- `jobtracker-brief.md` — original spec
- `jobtracker-plan.md` — milestone breakdown (source of truth for what Step X means)
- `jobtracker-claude-code-policy.json` — narrow/target IAM policy for the deploying user
- `jobtracker-claude-code-policy-temp-broad.json` — currently-attached broadened policy (temporary)
