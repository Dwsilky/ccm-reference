# AWS Config: recorder (optional), delivery channel, and the 12 custom rules.
#
# Cost notes, because Config is the bill to watch (ADR-002):
#   * recorder pricing is per configuration item recorded — the recording
#     group below is pinned to a tiny resource-type list rather than
#     all_supported, since our rules are periodic and query live APIs;
#     the recorder exists because Config requires one before rules will run;
#   * rule evaluations bill per evaluation — TwentyFour_Hours frequency and
#     12 rules keeps this in pennies; tear down after demos regardless.

resource "aws_config_configuration_recorder" "this" {
  count    = var.manage_recorder ? 1 : 0
  name     = "default"
  role_arn = aws_iam_role.config_recorder[0].arn
  recording_group {
    all_supported = false
    resource_types = [
      "AWS::S3::Bucket", # cheap to record, and lets CCM-11 see a live recorder
    ]
  }
}

resource "aws_config_delivery_channel" "this" {
  count          = var.manage_recorder ? 1 : 0
  name           = "default"
  s3_bucket_name = aws_s3_bucket.evidence.id
  s3_key_prefix  = "config-history"
  depends_on     = [aws_config_configuration_recorder.this]
}

resource "aws_config_configuration_recorder_status" "this" {
  count      = var.manage_recorder ? 1 : 0
  name       = aws_config_configuration_recorder.this[0].name
  is_enabled = true
  depends_on = [aws_config_delivery_channel.this]
}

resource "aws_config_config_rule" "rule" {
  for_each = local.rules
  name     = each.value

  source {
    owner             = "CUSTOM_LAMBDA"
    source_identifier = aws_lambda_function.rule[each.key].arn
    source_detail {
      event_source                = "aws.config"
      message_type                = "ScheduledNotification"
      maximum_execution_frequency = "TwentyFour_Hours"
    }
  }

  depends_on = [
    aws_lambda_permission.config_invoke,
    aws_config_configuration_recorder_status.this,
  ]
}
