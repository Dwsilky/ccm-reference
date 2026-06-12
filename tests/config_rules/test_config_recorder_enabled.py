import boto3
from moto import mock_aws

from src.config_recorder_enabled.handler import evaluate

RECORDER = {
    "name": "default",
    "roleARN": "arn:aws:iam::123456789012:role/config-role",
    "recordingGroup": {"allSupported": True, "includeGlobalResourceTypes": True},
}


def _recorder(session, started):
    config = session.client("config")
    config.put_configuration_recorder(ConfigurationRecorder=RECORDER)
    if started:
        # Config refuses to start a recorder without a delivery channel.
        session.client("s3").create_bucket(Bucket="config-delivery")
        config.put_delivery_channel(
            DeliveryChannel={"name": "default", "s3BucketName": "config-delivery"}
        )
        config.start_configuration_recorder(ConfigurationRecorderName="default")


@mock_aws
def test_no_recorder_is_non_compliant():
    [result] = evaluate({}, boto3.Session())
    assert result.compliance == "NON_COMPLIANT"
    assert "no Config recorder" in result.annotation


@mock_aws
def test_stopped_recorder_is_non_compliant():
    session = boto3.Session()
    _recorder(session, started=False)
    [result] = evaluate({}, session)
    assert result.compliance == "NON_COMPLIANT"
    assert "stopped" in result.annotation


@mock_aws
def test_recording_recorder_is_compliant():
    session = boto3.Session()
    _recorder(session, started=True)
    [result] = evaluate({}, session)
    assert result.compliance == "COMPLIANT"
