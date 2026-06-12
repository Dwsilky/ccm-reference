"""CCM-10 — CloudTrail log-file validation enabled.

CSF PR.DS-6 / 800-53 AU-9. Bucket: machine-evaluable.

Per-trail verdict (unlike CCM-09): integrity protection is a property of each
trail's output, and an unvalidated trail is a tampering blind spot even when
another trail is validated.

With no trails at all this rule reports NOT_APPLICABLE rather than failing —
the absence of trails is CCM-09's finding, and double-failing one root cause
creates two tickets for one fix.
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, NOT_APPLICABLE, Evaluation, run

CONTROL_ID = "CCM-10"


def evaluate(params: dict, session) -> list[Evaluation]:
    cloudtrail = session.client("cloudtrail")
    trails = cloudtrail.describe_trails()["trailList"]

    if not trails:
        account_id = session.client("sts").get_caller_identity()["Account"]
        return [
            Evaluation(
                "AWS::::Account",
                account_id,
                NOT_APPLICABLE,
                f"{CONTROL_ID}: no trails exist; absence of CloudTrail is CCM-09's finding.",
            )
        ]

    evaluations = []
    for trail in trails:
        if trail.get("LogFileValidationEnabled"):
            evaluations.append(
                Evaluation(
                    "AWS::CloudTrail::Trail",
                    trail["Name"],
                    COMPLIANT,
                    f"{CONTROL_ID}: log-file validation enabled.",
                )
            )
        else:
            evaluations.append(
                Evaluation(
                    "AWS::CloudTrail::Trail",
                    trail["Name"],
                    NON_COMPLIANT,
                    f"{CONTROL_ID}: log-file validation disabled; log integrity is "
                    "unverifiable.",
                )
            )
    return evaluations


def lambda_handler(event, context):
    return run(event, context, evaluate)
