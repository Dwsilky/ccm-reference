"""CCM-09 — CloudTrail enabled, multi-region, actively logging.

CSF PR.PT-1 / 800-53 AU-2. Bucket: machine-evaluable.

Account-level verdict, not per-trail: the control is "API activity is being
recorded everywhere", which one multi-region trail satisfies regardless of
how many single-region or stopped trails also exist. Grading trails
individually would mark an account with one good trail and three abandoned
ones as 75% failing — noise, not signal.

"Exists" is not "logging": a trail with StopLogging called still shows up in
DescribeTrails, so the rule also requires IsLogging from GetTrailStatus.
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-09"


def evaluate(params: dict, session) -> list[Evaluation]:
    cloudtrail = session.client("cloudtrail")
    account_id = session.client("sts").get_caller_identity()["Account"]

    trails = cloudtrail.describe_trails()["trailList"]
    multi_region = [t for t in trails if t.get("IsMultiRegionTrail")]

    logging_trail = None
    for trail in multi_region:
        status = cloudtrail.get_trail_status(Name=trail["TrailARN"])
        if status.get("IsLogging"):
            logging_trail = trail
            break

    if logging_trail:
        return [
            Evaluation(
                "AWS::::Account",
                account_id,
                COMPLIANT,
                f"{CONTROL_ID}: multi-region trail '{logging_trail['Name']}' is logging.",
            )
        ]

    if multi_region:
        detail = "multi-region trail(s) exist but none are logging (StopLogging?)"
    elif trails:
        detail = f"{len(trails)} trail(s) exist but none are multi-region"
    else:
        detail = "no CloudTrail trails exist"
    return [
        Evaluation(
            "AWS::::Account",
            account_id,
            NON_COMPLIANT,
            f"{CONTROL_ID}: {detail}.",
        )
    ]


def lambda_handler(event, context):
    return run(event, context, evaluate)
