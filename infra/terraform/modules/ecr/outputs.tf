output "repository_urls" {
  description = "Map nombre_funcional -> URL del repo ECR."
  value       = { for k, r in aws_ecr_repository.this : k => r.repository_url }
}

output "repository_arns" {
  description = "Map nombre_funcional -> ARN del repo ECR."
  value       = { for k, r in aws_ecr_repository.this : k => r.arn }
}
