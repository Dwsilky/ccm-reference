# One Lambda per rule, zipped from the staging dirs that
# scripts/package_lambdas.py builds (handler.py + vendored shared/).

data "archive_file" "rule" {
  for_each    = local.rules
  type        = "zip"
  source_dir  = "${path.module}/build/${each.key}"
  output_path = "${path.module}/build/${each.key}.zip"
}

resource "aws_lambda_function" "rule" {
  for_each      = local.rules
  function_name = each.value
  role          = aws_iam_role.rule_lambda.arn
  runtime       = "python3.12"
  handler       = "handler.lambda_handler"
  filename      = data.archive_file.rule[each.key].output_path
  # Hash ties deploys to code content: editing a rule re-deploys exactly
  # that Lambda, nothing else.
  source_code_hash = data.archive_file.rule[each.key].output_base64sha256
  timeout          = 60
  memory_size      = 256 # rules list whole resource populations
}

resource "aws_lambda_permission" "config_invoke" {
  for_each      = local.rules
  statement_id  = "AllowConfigInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rule[each.key].function_name
  principal     = "config.amazonaws.com"
  source_account = data.aws_caller_identity.current.account_id
}
