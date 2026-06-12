"""Tests for the shared Config-rule plumbing (event parsing, batching, limits)."""

from shared.evaluator import MAX_ANNOTATION, PUT_BATCH, Evaluation, run
from tests.conftest import config_event
from tests.support import FakeSession


class RecordingConfig:
    def __init__(self):
        self.calls = []

    def put_evaluations(self, **kwargs):
        self.calls.append(kwargs)
        return {"FailedEvaluations": []}


def _run(evaluations, params=None):
    config = RecordingConfig()
    count = run(
        config_event(params),
        context=None,
        evaluate_fn=lambda p, s: evaluations,
        session=FakeSession(config=config),
    )
    return count, config


def test_rule_parameters_are_decoded_and_passed_through():
    seen = {}

    def evaluate_fn(params, session):
        seen.update(params)
        return []

    run(
        config_event({"RequireKms": "true"}),
        context=None,
        evaluate_fn=evaluate_fn,
        session=FakeSession(config=RecordingConfig()),
    )
    assert seen == {"RequireKms": "true"}


def test_batches_at_put_evaluations_limit():
    evaluations = [
        Evaluation("AWS::S3::Bucket", f"b{i}", "COMPLIANT", "ok") for i in range(250)
    ]
    count, config = _run(evaluations)
    assert count == 250
    assert [len(c["Evaluations"]) for c in config.calls] == [PUT_BATCH, PUT_BATCH, 50]
    assert all(c["ResultToken"] == "test-token" for c in config.calls)


def test_annotation_truncated_to_config_limit():
    count, config = _run(
        [Evaluation("AWS::::Account", "123", "NON_COMPLIANT", "x" * 1000)]
    )
    wire = config.calls[0]["Evaluations"][0]
    assert len(wire["Annotation"]) == MAX_ANNOTATION


def test_wire_format_fields():
    _, config = _run([Evaluation("AWS::S3::Bucket", "b", "COMPLIANT", "fine")])
    wire = config.calls[0]["Evaluations"][0]
    assert wire == {
        "ComplianceResourceType": "AWS::S3::Bucket",
        "ComplianceResourceId": "b",
        "ComplianceType": "COMPLIANT",
        "Annotation": "fine",
        "OrderingTimestamp": "2026-06-12T00:00:00.000Z",
    }
