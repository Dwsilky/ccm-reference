# Control coverage matrix

_Generated from `mappings/controls.yaml` by `scripts/gen_matrix.py` on 2026-06-12. Do not edit by hand._

**21 controls** across the three buckets — **4 implemented**, 17 planned.

## Machine-evaluable (4/12 implemented)

_Config state we can compute a pass/fail on. Fully automated._

| ID | Control | CSF | 800-53 | Collection method | Source | Status |
|---|---|---|---|---|---|---|
| CCM-01 | S3 account public-access block enabled | PR.DS-5 | SC-7 | Custom Config rule (periodic Lambda) | `config-rules/src/s3_public_access_block` | ✅ implemented |
| CCM-02 | S3 buckets enforce default encryption | PR.DS-1 | SC-28 | Custom Config rule (periodic Lambda) | `config-rules/src/s3_bucket_encryption` | ✅ implemented |
| CCM-03 | RDS instances encrypted at rest | PR.DS-1 | SC-28 | Custom Config rule (periodic Lambda) | `config-rules/src/rds_encryption` | ⬜ planned |
| CCM-04 | EBS volumes encrypted | PR.DS-1 | SC-28 | Custom Config rule (periodic Lambda) | `config-rules/src/ebs_encryption` | ⬜ planned |
| CCM-05 | IAM password policy meets standard | PR.AC-1 | IA-5 | Custom Config rule (periodic Lambda) | `config-rules/src/iam_password_policy` | ✅ implemented |
| CCM-06 | MFA enabled for console users | PR.AC-7 | IA-2(1) | Custom Config rule (periodic Lambda) | `config-rules/src/iam_user_mfa` | ⬜ planned |
| CCM-07 | Root account has no access keys | PR.AC-4 | AC-6 | Custom Config rule (periodic Lambda) | `config-rules/src/root_access_keys` | ✅ implemented |
| CCM-08 | No 0.0.0.0/0 ingress on sensitive ports | PR.AC-5 | SC-7 | Custom Config rule (periodic Lambda) | `config-rules/src/sg_open_ingress` | ⬜ planned |
| CCM-09 | CloudTrail enabled, multi-region | PR.PT-1 | AU-2 | Custom Config rule (periodic Lambda) | `config-rules/src/cloudtrail_enabled` | ⬜ planned |
| CCM-10 | CloudTrail log-file validation enabled | PR.DS-6 | AU-9 | Custom Config rule (periodic Lambda) | `config-rules/src/cloudtrail_log_validation` | ⬜ planned |
| CCM-11 | Config recorder enabled (meta-control) | DE.CM-1 | CM-8 | Custom Config rule (periodic Lambda) | `config-rules/src/config_recorder_enabled` | ⬜ planned |
| CCM-12 | VPC flow logs enabled | DE.AE-3 | AU-12 | Custom Config rule (periodic Lambda) | `config-rules/src/vpc_flow_logs` | ⬜ planned |

## Evidence-attestable (0/4 implemented)

_No computable pass/fail, but the artifact proving the process ran can be pulled on a schedule._

| ID | Control | CSF | 800-53 | Collection method | Source | Status |
|---|---|---|---|---|---|---|
| CCM-13 | Quarterly access review occurred | PR.AC-4 | AC-2(3) | Collector — GitHub Issues API, assert a labeled review ticket closed this quarter | `collectors/access_review.py` | ⬜ planned |
| CCM-14 | Backup restore test succeeded | PR.IP-4 | CP-9 | Collector — parse backup-job logs, evidence a successful restore test | `collectors/backup_restore.py` | ⬜ planned |
| CCM-15 | Vulnerability remediation SLAs met | RS.MI-3 | RA-5, SI-2 | Collector — scanner findings, compute time-to-remediate per severity | `collectors/vuln_sla.py` | ⬜ planned |
| CCM-16 | Change approvals enforced on merges | PR.IP-3 | CM-3 | Collector — GitHub API, merged PRs carried a required approval | `collectors/change_approval.py` | ⬜ planned |

## Human-judgment (0/5 implemented)

_Not automatable. We automate only the reminder and the tracking of the attestation._

| ID | Control | CSF | 800-53 | Collection method | Source | Status |
|---|---|---|---|---|---|---|
| CCM-17 | Security policy review / adequacy | ID.GV-1 | PL-1 | Judgment tracker — attestation cadence in judgment-register.yaml | `router/judgment_tracker.py` | ⬜ planned |
| CCM-18 | Risk acceptances current (expiry tracked) | ID.RA-6 | CA-5 | Judgment tracker — attestation cadence in judgment-register.yaml | `router/judgment_tracker.py` | ⬜ planned |
| CCM-19 | Vendor risk assessments performed | ID.SC-2 | SA-9 | Judgment tracker — attestation cadence in judgment-register.yaml | `router/judgment_tracker.py` | ⬜ planned |
| CCM-20 | IR plan tabletop exercised | PR.IP-10 | IR-3 | Judgment tracker — attestation cadence in judgment-register.yaml | `router/judgment_tracker.py` | ⬜ planned |
| CCM-21 | Data classification reviewed | ID.AM-5 | RA-2 | Judgment tracker — attestation cadence in judgment-register.yaml | `router/judgment_tracker.py` | ⬜ planned |

