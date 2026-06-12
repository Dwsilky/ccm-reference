"""CCM-02 — S3 buckets enforce default encryption.

CSF PR.DS-1 / 800-53 SC-28. Bucket: machine-evaluable.

Since Jan 2023 AWS applies SSE-S3 to every new bucket, so "encryption config
exists" is nearly free to pass on modern accounts. The version of this control
that still earns its keep is requiring *customer-managed KMS* (key rotation
and access policy under your control), exposed here as the `RequireKms` rule
parameter. Default is the lenient check so the rule stays meaningful on
legacy buckets that predate the 2023 change.
"""

from botocore.exceptions import ClientError

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-02"


def evaluate(params: dict, session) -> list[Evaluation]:
    require_kms = str(params.get("RequireKms", "false")).lower() == "true"
    s3 = session.client("s3")

    evaluations = []
    for bucket in s3.list_buckets()["Buckets"]:
        name = bucket["Name"]
        try:
            rules = s3.get_bucket_encryption(Bucket=name)["ServerSideEncryptionConfiguration"][
                "Rules"
            ]
        except ClientError as err:
            if err.response["Error"]["Code"] == "ServerSideEncryptionConfigurationNotFoundError":
                evaluations.append(
                    Evaluation(
                        "AWS::S3::Bucket",
                        name,
                        NON_COMPLIANT,
                        f"{CONTROL_ID}: bucket has no default encryption configuration.",
                    )
                )
                continue
            raise

        algorithms = {
            r["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"]
            for r in rules
            if "ApplyServerSideEncryptionByDefault" in r
        }
        if require_kms and not algorithms & {"aws:kms", "aws:kms:dsse"}:
            evaluations.append(
                Evaluation(
                    "AWS::S3::Bucket",
                    name,
                    NON_COMPLIANT,
                    f"{CONTROL_ID}: RequireKms set but bucket uses {sorted(algorithms)}.",
                )
            )
        elif not algorithms:
            evaluations.append(
                Evaluation(
                    "AWS::S3::Bucket",
                    name,
                    NON_COMPLIANT,
                    f"{CONTROL_ID}: encryption config present but no default algorithm set.",
                )
            )
        else:
            evaluations.append(
                Evaluation(
                    "AWS::S3::Bucket",
                    name,
                    COMPLIANT,
                    f"{CONTROL_ID}: default encryption {sorted(algorithms)}.",
                )
            )
    return evaluations


def lambda_handler(event, context):
    return run(event, context, evaluate)
