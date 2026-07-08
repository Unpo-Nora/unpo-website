variable "project" {
  description = "Nombre del proyecto (prefijo de naming)."
  type        = string
  default     = "unpo-nora"
}

variable "environment" {
  description = "Nombre del entorno."
  type        = string
  default     = "staging"
}

variable "region" {
  description = "Región de AWS. sa-east-1 (São Paulo) por latencia AR; se ajusta en 6-C3."
  type        = string
  default     = "sa-east-1"
}

# --- Red -------------------------------------------------------------------

variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability zones (una por subnet)."
  type        = list(string)
  default     = ["sa-east-1a", "sa-east-1b"]
}

variable "public_subnet_cidrs" {
  description = "CIDRs de subnets públicas."
  type        = list(string)
  default     = ["10.20.0.0/24", "10.20.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDRs de subnets privadas."
  type        = list(string)
  default     = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "enable_nat_gateway" {
  description = "Crear NAT gateway para las subnets privadas."
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Una sola NAT compartida (staging = true para bajar costo)."
  type        = bool
  default     = true
}

# --- App / DB --------------------------------------------------------------

variable "app_port" {
  description = "Puerto del backend FastAPI."
  type        = number
  default     = 8000
}

variable "db_port" {
  description = "Puerto de PostgreSQL."
  type        = number
  default     = 5432
}

# --- ECR -------------------------------------------------------------------

variable "ecr_repository_names" {
  description = "Repos de imágenes a crear (se prefijan con project-environment)."
  type        = list(string)
  default     = ["backend", "frontend"]
}

# --- Tags -------------------------------------------------------------------

variable "extra_tags" {
  description = "Tags adicionales a mergear con las comunes."
  type        = map(string)
  default     = {}
}
