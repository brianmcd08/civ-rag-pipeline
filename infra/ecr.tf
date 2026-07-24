resource "aws_ecr_repository" "app" {
  name = var.project_name

  # Redeploys overwrite the same :latest tag, so tags must be mutable.
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  # Lets `terraform destroy` remove the repo even with images still in it.
  force_delete = true
}

# Every redeploy leaves the previous image behind. Storage is billed per GB,
# and this image will not be small, so cap how many accumulate.
resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire all but the 3 most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = { type = "expire" }
      }
    ]
  })
}

output "ecr_repository_url" {
  description = "Push target for the deploy script"
  value       = aws_ecr_repository.app.repository_url
}