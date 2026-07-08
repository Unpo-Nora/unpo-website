output "alb_security_group_id" {
  description = "ID del security group del ALB."
  value       = aws_security_group.alb.id
}

output "app_security_group_id" {
  description = "ID del security group de la app/ECS."
  value       = aws_security_group.app.id
}

output "db_security_group_id" {
  description = "ID del security group de la DB."
  value       = aws_security_group.db.id
}
