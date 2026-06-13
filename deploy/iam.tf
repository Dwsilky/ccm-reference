# One execution role shared by all 12 rule Lambdas: they are deliberately
# read-only-plus-PutEvaluations, so per-rule roles would be 12 copies of the
# same statement. SecurityAudit is AWS's curated read-only audit policy —
# broader than any single rule needs, but maintained by AWS as services
# change, which beats hand-curating 12 minimal policies that rot.

resource "aws_iam_role" "rule_lambda" {
  name = "${var.name_prefix}-config-rule-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "audit_readonly" {
  role       = aws_iam_role.rule_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/SecurityAudit"
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.rule_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "put_evaluations" {
  name = "put-evaluations"
  role = aws_iam_role.rule_lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "config:PutEvaluations"
      Resource = "*"
    }]
  })
}

# Recorder service role (only when this module manages the recorder).
resource "aws_iam_role" "config_recorder" {
  count = var.manage_recorder ? 1 : 0
  name  = "${var.name_prefix}-config-recorder"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "config.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "config_recorder" {
  count      = var.manage_recorder ? 1 : 0
  role       = aws_iam_role.config_recorder[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}
