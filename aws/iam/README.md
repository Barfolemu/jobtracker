# IAM policy files

`jobtracker-claude-code-policy-temp-broad.json` is the policy attached to
`jobtracker-dev-role-broad` — the role the `jobtracker` AWS CLI profile
assumes (via the `ashley-dev` base user). Despite the "temp-broad" name,
it's the permanent policy: action wildcards were broadened per-service
(`s3:*`, `lambda:*`, etc.) to unblock iteration, but resource ARNs stay
tightly scoped to `jobtracker*`-prefixed resources, so the blast radius is
still contained. Decision made 2026-08-08 not to pursue narrowing further
for this project — see `jobtracker-status.md` in the repo root.

Account ID in this file is scrubbed to `<AWS_ACCOUNT_ID>`. To get a real,
pasteable copy:

```
sed "s/<AWS_ACCOUNT_ID>/$(grep -oP '(?<=AWS_ACCOUNT_ID=).*' ../../.env)/g" jobtracker-claude-code-policy-temp-broad.json
```

An earlier, narrower draft policy (`jobtracker-claude-code-policy.json`)
existed before this one and has been removed — this project uses IAM
roles rather than a standalone user, so there's no reason to maintain two
policy variants.
