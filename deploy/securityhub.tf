# The finding bus, for real (ADR-001). Once enabled, the Config -> Security
# Hub native integration forwards rule evaluations automatically — which is
# exactly the production replacement for normalizer/adapters.from_config_evaluation
# (see ADR-004 #3).

resource "aws_securityhub_account" "this" {
  count = var.manage_security_hub ? 1 : 0

  # Consolidated control findings off: this account is a demo bus, not a
  # CSPM; default standards would flood it with findings we don't route.
  enable_default_standards = false
}

output "security_hub_enabled" {
  value = var.manage_security_hub ? "managed by this module" : "pre-existing (unmanaged)"
}

output "evidence_bucket" {
  value = aws_s3_bucket.evidence.id
}

output "config_rules" {
  value = [for r in aws_config_config_rule.rule : r.name]
}
