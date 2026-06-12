"""CCM-12 — VPC flow logs enabled on every VPC.

CSF DE.AE-3 / 800-53 AU-12. Bucket: machine-evaluable.

Per-VPC verdict: flow logs can also attach at subnet/ENI level, but
VPC-level attachment is the only one that can't be quietly bypassed by the
next subnet. A flow log must be ACTIVE to count — a flow log whose delivery
is failing (bad IAM role, deleted bucket) still exists in the API while
producing nothing.

The default VPC is evaluated like any other: unused-but-present default VPCs
are exactly where unmonitored traffic hides.
"""

from shared.evaluator import COMPLIANT, NON_COMPLIANT, Evaluation, run

CONTROL_ID = "CCM-12"


def evaluate(params: dict, session) -> list[Evaluation]:
    ec2 = session.client("ec2")

    active_by_vpc: set[str] = set()
    for page in ec2.get_paginator("describe_flow_logs").paginate():
        for fl in page["FlowLogs"]:
            if fl.get("FlowLogStatus") == "ACTIVE":
                active_by_vpc.add(fl["ResourceId"])

    evaluations = []
    for page in ec2.get_paginator("describe_vpcs").paginate():
        for vpc in page["Vpcs"]:
            vpc_id = vpc["VpcId"]
            if vpc_id in active_by_vpc:
                evaluations.append(
                    Evaluation(
                        "AWS::EC2::VPC",
                        vpc_id,
                        COMPLIANT,
                        f"{CONTROL_ID}: active VPC-level flow log attached.",
                    )
                )
            else:
                evaluations.append(
                    Evaluation(
                        "AWS::EC2::VPC",
                        vpc_id,
                        NON_COMPLIANT,
                        f"{CONTROL_ID}: no active VPC-level flow log.",
                    )
                )
    return evaluations


def lambda_handler(event, context):
    return run(event, context, evaluate)
