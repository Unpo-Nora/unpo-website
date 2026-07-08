output "name_prefix" {
  description = "Prefijo de naming usado en este entorno."
  value       = local.name_prefix
}

output "region" {
  description = "Región de AWS del entorno."
  value       = var.region
}

# --- Red -------------------------------------------------------------------

output "vpc_id" {
  description = "ID de la VPC."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "IDs de subnets públicas."
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "IDs de subnets privadas."
  value       = module.network.private_subnet_ids
}

# --- Security groups -------------------------------------------------------

output "alb_security_group_id" {
  description = "SG del ALB."
  value       = module.security.alb_security_group_id
}

output "app_security_group_id" {
  description = "SG de la app/ECS."
  value       = module.security.app_security_group_id
}

output "db_security_group_id" {
  description = "SG de la DB."
  value       = module.security.db_security_group_id
}

# --- ECR -------------------------------------------------------------------

output "ecr_repository_urls" {
  description = "URLs de los repos ECR."
  value       = module.ecr.repository_urls
}
