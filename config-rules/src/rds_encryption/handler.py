"""CCM-03 — RDS instances encrypted at rest.

CSF PR.DS-1 / 800-53 SC-28. Bucket: machine-evaluable.

Detection here is the easy half: an unencrypted RDS instance can't be flipped
in place — remediation is snapshot → copy-with-KMS → restore, with downtime.
That asymmetry is why the annotation states the remediation path: the finding
lands in a ticket (see router/) and the assignee shouldn't need to research
why "just enable encryption" isn't a thing.

Scope: DB instances only. Aurora encryption lives on the cluster object and
would silently evade an instance-level check — out of scope until a cluster
rule exists, and saying so beats false assurance.
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-03"


def evaluate(params: dict, session) -> list[Evaluation]:
    rds = session.client("rds")

    evaluations = []
    for page in rds.get_paginator("describe_db_instances").paginate():
        for db in page["DBInstances"]:
            name = db["DBInstanceIdentifier"]
            if db.get("StorageEncrypted"):
                evaluations.append(
                    Evaluation(
                        "AWS::RDS::DBInstance",
                        name,
                        COMPLIANT,
                        f"{CONTROL_ID}: storage encrypted (KMS key attached).",
                    )
                )
            else:
                evaluations.append(
                    Evaluation(
                        "AWS::RDS::DBInstance",
                        name,
                        NON_COMPLIANT,
                        f"{CONTROL_ID}: storage not encrypted; remediation requires "
                        "snapshot -> encrypted copy -> restore.",
                    )
                )
    return evaluations


def lambda_handler(event, context):
    return run(event, context, evaluate)
