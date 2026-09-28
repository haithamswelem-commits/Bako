resource "aws_iam_user" "github_actions_ci" {
  name = "bako-github-actions-ci"
}

resource "aws_iam_policy" "github_actions_ecr_push" {
  name = "bako-github-actions-ecr-push"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "GetAuthToken"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "PushPullBakoRepos"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload"
        ]
        Resource = [
          aws_ecr_repository.backend.arn,
          aws_ecr_repository.frontend.arn
        ]
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "github_actions_ecr_push" {
  user       = aws_iam_user.github_actions_ci.name
  policy_arn = aws_iam_policy.github_actions_ecr_push.arn
}

resource "aws_iam_access_key" "github_actions_ci" {
  user = aws_iam_user.github_actions_ci.name
}

output "github_actions_ci_access_key_id" {
  value = aws_iam_access_key.github_actions_ci.id
}

output "github_actions_ci_secret_access_key" {
  value     = aws_iam_access_key.github_actions_ci.secret
  sensitive = true
}