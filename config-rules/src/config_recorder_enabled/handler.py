"""CCM-11 — AWS Config recorder enabled and recording (meta-control).

CSF DE.CM-1 / 800-53 CM-8. Bucket: machine-evaluable.

The monitoring system watching itself. This works as a *periodic* Config rule
because scheduled evaluations fire from the Config service directly — they do
not depend on the recorder that this rule is checking. A change-triggered
version would be self-defeating: recorder off means no configuration items,
means the rule never fires, means permanent silence reads as permanent green.

Failing this control means every change-triggered rule in the account is
blind — severity-wise it outranks any single resource finding.
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-11"


def evaluate(params: dict, session) -> list[Evaluation]:
    config = session.client("config")
    account_id = session.client("sts").get_caller_identity()["Account"]

    recorders = config.describe_configuration_recorders()["ConfigurationRecorders"]
    if not recorders:
        return [
            Evaluation(
                "AWS::::Account",
                account_id,
                NON_COMPLIANT,
                f"{CONTROL_ID}: no Config recorder exists; change-triggered rules "
                "are blind.",
            )
        ]

    statuses = config.describe_configuration_recorder_status()[
        "ConfigurationRecordersStatus"
    ]
    recording = [s["name"] for s in statuses if s.get("recording")]
    if recording:
        return [
            Evaluation(
                "AWS::::Account",
                account_id,
                COMPLIANT,
                f"{CONTROL_ID}: recorder '{recording[0]}' is recording.",
            )
        ]
    return [
        Evaluation(
            "AWS::::Account",
            account_id,
            NON_COMPLIANT,
            f"{CONTROL_ID}: recorder exists but is stopped (StopConfigurationRecorder).",
        )
    ]


def lambda_handler(event, context):
    return run(event, context, evaluate)
