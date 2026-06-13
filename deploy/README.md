# Deploying to real AWS (and tearing it down)

Everything in this repo runs locally with zero AWS spend (ADR-002). This
module exists for one purpose: proving the same Lambdas evaluate for real.
Deploy, watch findings appear, screenshot, **destroy**. It is not designed to
run unattended for weeks.

## What it creates

- 12 Lambda functions (one per custom Config rule, `python3.12`, shared
  execution role: `SecurityAudit` + logs + `config:PutEvaluations`)
- 12 custom Config rules, periodic, `TwentyFour_Hours` frequency
- Config recorder + delivery channel (skippable: `manage_recorder=false` if
  the account already has one — most do, and two recorders is an error)
- Security Hub (skippable: `manage_security_hub=false`), default standards
  disabled so the bus isn't flooded with findings this repo doesn't route
- An evidence S3 bucket (versioned, encrypted, public-access-blocked —
  it has to pass its own controls)

## Runbook

```sh
# 0. prerequisites: terraform >= 1.5, AWS credentials for a sandbox account
cd <repo root>

# 1. stage the lambda zips (handler + vendored shared/)
python scripts/package_lambdas.py

# 2. deploy
cd deploy
terraform init
terraform plan                       # read it — this is someone's AWS bill
terraform apply

# 3. verify (rules evaluate on their schedule; force one immediately:)
aws configservice start-config-rules-evaluation --config-rule-names ccm-07-root-access-keys
aws configservice describe-compliance-by-config-rule --config-rule-names ccm-07-root-access-keys
# findings also appear in Security Hub via the native Config integration

# 4. TEAR DOWN — this is part of the runbook, not an afterthought
terraform destroy
```

## Cost guardrails (why each knob is set the way it is)

| Knob | Setting | Why |
|---|---|---|
| Rule count | 12 | per-evaluation pricing; matches the catalog, no padding |
| Frequency | 24h | demo needs one evaluation cycle, not real-time |
| Recorder scope | `AWS::S3::Bucket` only | recorder bills per configuration item; our rules are periodic and query live APIs, so the recorder exists only because Config requires one |
| Security Hub standards | disabled | default standards generate thousands of findings billed per-finding |
| Bucket | `force_destroy = true` | `terraform destroy` must actually complete |

Left running, this stack costs on the order of single-digit dollars per
month — the guardrail isn't the amount, it's the habit: **infra you aren't
demoing is infra you tear down.**

## Known honest gaps

- `manage_recorder=true` assumes a Config-virgin account. Accounts with
  existing recorders/channels must set it false.
- The Lambdas are deployed exactly as tested under moto; the Config *wire
  plumbing* (event parsing, `put_evaluations`) is what this deploy proves,
  because moto can't (ADR-002).
- No remote state, no CI deploy: this is a prove-it module, and pretending
  otherwise would be resume theater.
