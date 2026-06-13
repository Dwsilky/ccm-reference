terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      project = "ccm-reference"
      # Everything this module creates carries this tag so a cost report —
      # or an emergency cleanup — can find all of it.
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  # rule directory name -> Config rule name. One entry per machine-evaluable
  # control; adding CCM-22 here is the entire deploy-side change.
  rules = {
    s3_public_access_block    = "${var.name_prefix}-01-s3-public-access-block"
    s3_bucket_encryption      = "${var.name_prefix}-02-s3-bucket-encryption"
    rds_encryption            = "${var.name_prefix}-03-rds-encryption"
    ebs_encryption            = "${var.name_prefix}-04-ebs-encryption"
    iam_password_policy       = "${var.name_prefix}-05-iam-password-policy"
    iam_user_mfa              = "${var.name_prefix}-06-iam-user-mfa"
    root_access_keys          = "${var.name_prefix}-07-root-access-keys"
    sg_open_ingress           = "${var.name_prefix}-08-sg-open-ingress"
    cloudtrail_enabled        = "${var.name_prefix}-09-cloudtrail-enabled"
    cloudtrail_log_validation = "${var.name_prefix}-10-cloudtrail-log-validation"
    config_recorder_enabled   = "${var.name_prefix}-11-config-recorder-enabled"
    vpc_flow_logs             = "${var.name_prefix}-12-vpc-flow-logs"
  }
}
