# Vendored Prowler sample output

`findings.ocsf.json` is sample output in Prowler v4's OCSF JSON format
(`prowler aws --output-formats json-ocsf`), vendored so the adapter and its
tests run with no scanner installed and no AWS account.

**Provenance:** structure follows Prowler v4's OCSF output; objects are
abridged to the fields `adapters.from_prowler` consumes (`metadata.event_code`,
`status_code`, `status_detail`, `severity`, `cloud.*`, `resources[]`,
`finding_info.*`) plus enough context to stay readable. Account ID and ARNs
are synthetic. If Prowler's schema drifts, this file is the fixture to update
— the adapter's tests will say exactly which field moved.

Three findings chosen on purpose:

| event_code | status | why it's here |
|---|---|---|
| `cloudtrail_multi_region_enabled` | FAIL | maps to CCM-09 via the catalog |
| `s3_account_level_public_access_blocks` | PASS | maps to CCM-01; proves PASS findings normalize too |
| `ec2_instance_imdsv2_enabled` | FAIL | deliberately NOT in the catalog — exercises the unmapped path |
