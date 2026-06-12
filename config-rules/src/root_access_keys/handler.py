"""CCM-07 — Root account has no access keys.

CSF PR.AC-4 / 800-53 AC-6. Bucket: machine-evaluable.

Uses GetAccountSummary rather than the credential report: the summary is a
single synchronous call, while the credential report needs a generate/poll
cycle that adds latency and a failure mode for exactly the same bit of
information (AccountAccessKeysPresent).
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-07"


def evaluate(params: dict, session) -> list[Evaluation]:
    account_id = session.client("sts").get_caller_identity()["Account"]
    summary = session.client("iam").get_account_summary()["SummaryMap"]

    keys_present = summary.get("AccountAccessKeysPresent", 0)
    if keys_present:
        return [
            Evaluation(
                "AWS::::Account",
                account_id,
                NON_COMPLIANT,
                f"{CONTROL_ID}: root account has {keys_present} active access key(s); "
                "delete them — root API access should not exist.",
            )
        ]
    return [
        Evaluation(
            "AWS::::Account",
            account_id,
            COMPLIANT,
            f"{CONTROL_ID}: root account has no access keys.",
        )
    ]


def lambda_handler(event, context):
    return run(event, context, evaluate)
