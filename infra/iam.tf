data "aws_caller_identity" "current" {}

locals {
  # The profile the app names at runtime via BEDROCK_MODEL_ID.
  bedrock_profile_arn = "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/${var.bedrock_model_id}"

  # The global profile forwards to the underlying foundation model in whichever
  # region has capacity, so the model ARN must be allowed in any region too.
  # Verified with: aws bedrock get-inference-profile --inference-profile-identifier global.anthropic.claude-sonnet-4-6
  bedrock_model_arn = "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-6"
}

# Trust policy: only the Lambda service may assume this role.
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.project_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# CloudWatch Logs write access. AWS-managed, and the only reason a traceback
# from a failed invocation is visible anywhere.
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "bedrock_invoke" {
  statement {
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]

    resources = [
      local.bedrock_profile_arn,
      local.bedrock_model_arn,
    ]
  }
}

resource "aws_iam_role_policy" "bedrock_invoke" {
  name   = "${var.project_name}-bedrock-invoke"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.bedrock_invoke.json
}