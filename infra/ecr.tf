resource "aws_ecr_repository" "app" {
  name = var.project_name

  # deploy.sh tags with the short commit SHA, so redeploying an unchanged
  # commit (a rebuild after a base-image or dependency bump, a re-apply after a
  # failed deploy) pushes that same tag again. An immutable repository rejects
  # that push. Only the -dirty-<timestamp> variants are guaranteed unique.
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