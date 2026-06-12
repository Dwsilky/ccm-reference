"""Shared plumbing for custom AWS Config rules.

Each rule module supplies only `evaluate(params, session) -> list[Evaluation]`
— pure compliance logic, no Config API knowledge. This module owns the parts
every rule would otherwise duplicate: parsing the Config invocation event,
annotation limits, batching, and `put_evaluations`.

Deployment note: Lambda has no shared filesystem between functions, so each
rule's zip vendors this package next to its handler (handled in deploy/).
The duplication-in-artifact is the price of single-source-in-repo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import boto3

# AWS Config rejects the whole put_evaluations call if any annotation exceeds
# 256 chars — truncate centrally rather than trusting every rule to remember.
MAX_ANNOTATION = 256

# put_evaluations accepts at most 100 evaluations per call.
PUT_BATCH = 100

COMPLIANT = "COMPLIANT"
NON_COMPLIANT = "NON_COMPLIANT"
NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class Evaluation:
    """One resource's compliance verdict, independent of Config's wire format."""

    resource_type: str
    resource_id: str
    compliance: str  # COMPLIANT | NON_COMPLIANT | NOT_APPLICABLE
    annotation: str = ""


def parse_event(event: dict) -> tuple[dict, dict]:
    """Return (invoking_event, rule_parameters), both as dicts.

    Config delivers both as JSON *strings* inside the event — a classic
    first-time-custom-rule stumbling block.
    """
    invoking_event = json.loads(event["invokingEvent"])
    params = json.loads(event.get("ruleParameters") or "{}")
    return invoking_event, params


def run(event: dict, context, evaluate_fn, session: boto3.Session | None = None) -> int:
    """Lambda entrypoint shared by every rule.

    All rules in this repo are periodic (ScheduledNotification): they query
    live state via the API rather than trusting the configuration item
    snapshot, which keeps each rule testable against moto with zero Config
    service dependency. The `session` parameter exists for tests; Lambda
    always uses the default session.

    Returns the number of evaluations reported.
    """
    invoking_event, params = parse_event(event)
    session = session or boto3.Session()

    evaluations = evaluate_fn(params, session)

    ordering_time = invoking_event["notificationCreationTime"]
    wire = [
        {
            "ComplianceResourceType": e.resource_type,
            "ComplianceResourceId": e.resource_id,
            "ComplianceType": e.compliance,
            "Annotation": e.annotation[:MAX_ANNOTATION] if e.annotation else " ",
            "OrderingTimestamp": ordering_time,
        }
        for e in evaluations
    ]

    config = session.client("config")
    for i in range(0, len(wire), PUT_BATCH):
        config.put_evaluations(
            Evaluations=wire[i : i + PUT_BATCH],
            ResultToken=event["resultToken"],
        )
    return len(wire)
