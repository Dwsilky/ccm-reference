# Custom AWS Config rules

Twelve machine-evaluable controls (CCM-01 … CCM-12), each a custom Lambda-backed
Config rule. One directory per rule under `src/`; shared plumbing in `shared/`.

## Why custom rules when managed rules exist?

AWS ships managed rules covering most of these checks
(`s3-bucket-server-side-encryption-enabled`, `iam-user-mfa-enabled`, …), and in
production you should reach for them first: zero code to maintain, and auditors
recognize them. This repo writes them custom anyway, for three honest reasons
and one structural one:

1. **The logic is the learning.** A managed-rule reference proves you can read
   a catalog; writing the evaluation proves you know what the control actually
   asserts. Compare CCM-09's "exists ≠ logging" distinction or CCM-06's
   NOT_APPLICABLE handling — those judgment calls are invisible inside a
   managed rule.
2. **Managed rules don't take your org's position.** CCM-05 deliberately does
   not assert password rotation (800-63B); the managed rule's parameters can't
   express "rotation is opt-in, length is mandatory" as a default posture.
   CCM-08 ships an opinionated sensitive-port list instead of "no open ingress
   at all."
3. **Same price.** Config bills per evaluation identically for managed and
   custom rules; custom costs engineering time, not money.

The structural reason: every rule here returns plain `Evaluation` objects from
a pure `evaluate(params, session)` function, which is what lets the normalizer
(Session 3) treat rule output as just another finding source.

## Anatomy of a rule

```
src/<rule_name>/handler.py
    CONTROL_ID            # CCM-xx, joins to mappings/controls.yaml
    evaluate(params, session) -> list[Evaluation]   # pure logic, unit-tested
    lambda_handler(event, context)                  # one line: shared run()
shared/evaluator.py
    parse_event / run     # Config wire format, annotation limit, batching
```

All rules are **periodic** (ScheduledNotification), not change-triggered: they
query live state via the API instead of trusting the configuration-item
snapshot in the event. Tradeoffs:

- (+) testable against moto with no Config service dependency — this is why
  `pytest` runs with zero AWS credentials;
- (+) immune to the recorder being off (see CCM-11's docstring — a
  change-triggered meta-rule on the recorder is self-defeating);
- (−) detection latency is the schedule interval, not seconds-after-change;
- (−) each run re-lists whole resource populations, which is the cost knob to
  watch at scale (see ADR-001's scale notes).

## Testing strategy

Each rule has compliant / non-compliant / boundary tests in
`tests/config_rules/`, run against moto. Where moto can't represent a state
(root-account access keys), the single API call is faked instead — see
`tests/support.py` and ADR-002. The Config wire format itself (batching,
annotation truncation) is tested once against the shared runner, not per rule.
