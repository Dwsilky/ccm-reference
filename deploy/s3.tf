# Evidence bucket — and a chance to eat our own dog food: this bucket must
# itself pass CCM-01 (account PAB is separate) and CCM-02 (KMS not required
# here; SSE-S3 with versioning is the demo posture).

resource "aws_s3_bucket" "evidence" {
  bucket        = "${var.name_prefix}-evidence-${data.aws_caller_identity.current.account_id}"
  force_destroy = true # demo bucket: terraform destroy must actually work
}

resource "aws_s3_bucket_versioning" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence" {
  bucket = aws_s3_bucket.evidence.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "evidence" {
  bucket                  = aws_s3_bucket.evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Config's delivery channel needs explicit permission to write history here.
resource "aws_s3_bucket_policy" "evidence_config_delivery" {
  count  = var.manage_recorder ? 1 : 0
  bucket = aws_s3_bucket.evidence.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSConfigBucketCheck"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = ["s3:GetBucketAcl", "s3:ListBucket"]
        Resource  = aws_s3_bucket.evidence.arn
      },
      {
        Sid       = "AWSConfigBucketDelivery"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.evidence.arn}/config-history/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" }
        }
      }
    ]
  })
}
