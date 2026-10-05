locals {
  eks_oidc_provider_url = replace(aws_iam_openid_connect_provider.eks.url, "https://", "")
}

resource "aws_iam_role" "external_secrets" {
  name = "bako-external-secrets-irsa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.eks.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${local.eks_oidc_provider_url}:sub" = "system:serviceaccount:external-secrets:external-secrets"
            "${local.eks_oidc_provider_url}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "external_secrets_read_rds_secret" {
  name = "bako-external-secrets-read-rds-secret"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = aws_secretsmanager_secret.bako_db.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "external_secrets_read_rds_secret" {
  role       = aws_iam_role.external_secrets.name
  policy_arn = aws_iam_policy.external_secrets_read_rds_secret.arn
}

output "external_secrets_role_arn" {
  value = aws_iam_role.external_secrets.arn
}