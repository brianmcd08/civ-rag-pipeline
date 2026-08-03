variable "image_tag" {
  description = "ECR tag to deploy. deploy.sh passes a git SHA so redeploys are visible to Terraform."
  type        = string
}

# No default on purpose. With one, a bare `terraform apply` falls back to
# :latest, compares an unchanged image_uri string, reports no diff, and exits 0
# while Lambda keeps serving the previous image. A required variable is what
# forces every deploy through deploy.sh; a comment would not.

# Existence guard, for the other half of the same failure. Passing a tag that
# was never pushed fails UpdateFunctionCode, but Terraform writes the new
# image_uri into state anyway, so state and the live function disagree and the
# next plan compares the bad tag against itself and finds nothing. Reading the
# image first fails during plan, before anything is written.
data "aws_ecr_image" "app" {
  repository_name = aws_ecr_repository.app.name
  image_tag       = var.image_tag
}

# Created explicitly rather than letting Lambda auto-create it, because the
# auto-created group retains logs forever and quietly accrues storage cost.
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}"
  retention_in_days = 14
}

resource "aws_lambda_function" "api" {
  function_name = var.project_name
  role          = aws_iam_role.lambda.arn

  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  architectures = ["x86_64"]

  # Lambda CPU scales with memory, so this is a latency setting as much as a
  # memory one. The cold path imports LangChain and psycopg, then the FastAPI
  # lifespan opens the Neon pool and builds the agent.
  memory_size = 2048
  timeout     = 60

  environment {
    variables = {
      LLM_PROVIDER           = "bedrock"
      BEDROCK_MODEL_ID       = var.bedrock_model_id
      API_SHARED_SECRET      = var.api_shared_secret
      DATABASE_URL           = var.database_url
      OPENAI_API_KEY         = var.openai_api_key
      PINECONE_API_KEY       = var.pinecone_api_key
      PINECONE_INDEX_NAME_V2 = var.pinecone_index_name_v2
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}