"""CCM-04 — EBS volumes encrypted.

CSF PR.DS-1 / 800-53 SC-28. Bucket: machine-evaluable.

Emits two kinds of evaluation from one rule on purpose:

- per-volume: is each *existing* volume encrypted (the audit population), and
- account-level: is EBS encryption-by-default on (whether *future* volumes
  will be).

Checking only existing volumes is whack-a-mole — the account default is the
part that stops the backlog from regrowing, so it's asserted as its own
resource rather than buried in an annotation.
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-04"


def evaluate(params: dict, session) -> list[Evaluation]:
    ec2 = session.client("ec2")
    account_id = session.client("sts").get_caller_identity()["Account"]

    evaluations = []
    if ec2.get_ebs_encryption_by_default()["EbsEncryptionByDefault"]:
        evaluations.append(
            Evaluation(
                "AWS::::Account",
                account_id,
                COMPLIANT,
                f"{CONTROL_ID}: EBS encryption-by-default enabled; new volumes are covered.",
            )
        )
    else:
        evaluations.append(
            Evaluation(
                "AWS::::Account",
                account_id,
                NON_COMPLIANT,
                f"{CONTROL_ID}: EBS encryption-by-default is off — every new volume "
                "starts unencrypted.",
            )
        )

    for page in ec2.get_paginator("describe_volumes").paginate():
        for vol in page["Volumes"]:
            if vol.get("Encrypted"):
                evaluations.append(
                    Evaluation(
                        "AWS::EC2::Volume",
                        vol["VolumeId"],
                        COMPLIANT,
                        f"{CONTROL_ID}: volume encrypted.",
                    )
                )
            else:
                evaluations.append(
                    Evaluation(
                        "AWS::EC2::Volume",
                        vol["VolumeId"],
                        NON_COMPLIANT,
                        f"{CONTROL_ID}: volume not encrypted; remediation is "
                        "snapshot -> encrypted copy -> swap, not in-place.",
                    )
                )
    return evaluations


def lambda_handler(event, context):
    return run(event, context, evaluate)
