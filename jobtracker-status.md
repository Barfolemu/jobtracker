# Jobtracker Status

Last updated: 2026-08-07 (end of session). Pick up here next time.

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

1. **Narrow the IAM policy.** Currently running on `jobtracker-claude-code-policy-temp-broad.json` (service-level action wildcards, but resource ARNs still tightly scoped to `jobtracker*`/`JobTrackerTable*`/`role/jobtracker-*`). This session added 4 more CloudFront actions to it (`GetOriginAccessControl`, `UpdateOriginAccessControl`, `DeleteOriginAccessControl`, `ListOriginAccessControls`) after hitting an `AccessDenied` creating the frontend's Origin Access Control — CloudFormation needs to read the OAC's `Id` right after creating it. Plan: pull the actual API calls made from CloudTrail (`aws cloudtrail lookup-events --profile claudejobtracker`), fold only what was genuinely used into `jobtracker-claude-code-policy.json` (the narrow target policy), then swap the attached policy back to that.
2. **Custom domain.** Ashley bought `ashleycjones.com` and is building a separate personal homepage there (different project). Plan discussed: put that homepage at the root/apex, and once it exists, point a subdomain (e.g. `jobtracker.ashleycjones.com`) at this CloudFront distribution via Route 53 + an ACM cert + a CloudFront alternate domain name. Not started — revisit once the homepage project exists.
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
- **Session secret**: generated via `openssl rand -hex 32` and passed as a `NoEcho` CloudFormation parameter — intentionally not recorded in this repo. It's not retrievable from AWS after the fact (NoEcho parameters aren't readable via the API/console). If a future deploy needs it and it's been lost, generate a new one — this only invalidates existing login sessions (users just log in again with their existing password; the password hash lives separately in DynamoDB and is unaffected). Confirmed this session: on `sam deploy` to an *existing* stack, omitting a parameter from `--parameter-overrides` preserves its current value rather than erroring — so `SessionSecret` doesn't need to be re-passed on every deploy, only `FrontendOrigin` (or whatever actually changed).
- **AWS CLI session expiry**: the `claudejobtracker` profile's credentials can expire mid-session (`Your session has expired. Please reauthenticate using 'aws login'`). `aws login --profile claudejobtracker` opens a browser-based flow — has to be run by Ashley directly (via `! aws login --profile claudejobtracker` in chat), not by the agent, since it needs a real browser/terminal.
- Git: all work through this point is committed on `main` (no remote configured yet).

---

## Reference docs in this repo

- `jobtracker-brief.md` — original spec
- `jobtracker-plan.md` — milestone breakdown (source of truth for what Step X means)
- `jobtracker-claude-code-policy.json` — narrow/target IAM policy for the deploying user
- `jobtracker-claude-code-policy-temp-broad.json` — currently-attached broadened policy (temporary)
