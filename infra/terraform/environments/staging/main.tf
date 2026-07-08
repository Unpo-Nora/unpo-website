###############################################################################
# UNPO / NORA — Infra AWS · Entorno: staging
# 6-C2 — Esqueleto Terraform. NADA aplicado (sin init / plan / apply).
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend remoto de state (S3 + DynamoDB lock) => TAREA 6-C3.
  # Por ahora state LOCAL. NO configurar con valores reales todavía.
  # backend "s3" {
  #   bucket         = "TODO-tfstate-bucket"
  #   key            = "staging/terraform.tfstate"
  #   region         = "TODO-region"
  #   dynamodb_table = "TODO-tflock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = local.common_tags
  }
}

locals {
  name_prefix = "${var.project}-${var.environment}"

  common_tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Scope       = "6-C2-bootstrap"
    },
    var.extra_tags,
  )
}

###############################################################################
# Red base (VPC / subnets / routing / NAT)
###############################################################################
module "network" {
  source = "../../modules/network"

  name_prefix          = local.name_prefix
  vpc_cidr             = var.vpc_cidr
  azs                  = var.azs
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = var.single_nat_gateway
  tags                 = local.common_tags
}

###############################################################################
# Security groups (ALB / app / db)
###############################################################################
module "security" {
  source = "../../modules/security"

  name_prefix = local.name_prefix
  vpc_id      = module.network.vpc_id
  app_port    = var.app_port
  db_port     = var.db_port
  tags        = local.common_tags
}

###############################################################################
# ECR (repos de imágenes backend / frontend)
###############################################################################
module "ecr" {
  source = "../../modules/ecr"

  name_prefix      = local.name_prefix
  repository_names = var.ecr_repository_names
  tags             = local.common_tags
}

###############################################################################
# IAM (esqueleto — roles ECS se completan en 6-C3)
###############################################################################
module "iam" {
  source = "../../modules/iam"

  name_prefix = local.name_prefix
  tags        = local.common_tags
}

###############################################################################
# Observability (esqueleto — log groups / alarmas se completan en 6-C3)
###############################################################################
module "observability" {
  source = "../../modules/observability"

  name_prefix = local.name_prefix
  tags        = local.common_tags
}
