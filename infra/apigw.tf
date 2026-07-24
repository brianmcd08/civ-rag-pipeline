resource "aws_apigatewayv2_api" "http" {
  name          = var.project_name
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_route" "query" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /query"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  # /query now requires a shared secret, so this is the second brake rather
  # than the only one. Kept low anyway: it caps how fast an unauthenticated
  # caller can burn Lambda invocations on 401s, which the app-level check
  # cannot prevent (the function still has to run to reject the request).
  default_route_settings {
    throttling_rate_limit  = 1
    throttling_burst_limit = 2
  }
}

# API Gateway is a separate service and cannot invoke the function without an
# explicit resource policy on the Lambda side. Omitting this is the single most
# common cause of a 500 from a config that otherwise looks correct.
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "api_base_url" {
  description = "Live base URL. Append /health or /query."
  value       = aws_apigatewayv2_stage.default.invoke_url
}
