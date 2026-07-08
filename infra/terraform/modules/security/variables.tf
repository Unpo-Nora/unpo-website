variable "name_prefix" {
  description = "Prefijo de naming (ej.: unpo-nora-staging)."
  type        = string
}

variable "vpc_id" {
  description = "ID de la VPC donde crear los security groups."
  type        = string
}

variable "app_port" {
  description = "Puerto de la app (FastAPI backend)."
  type        = number
  default     = 8000
}

variable "db_port" {
  description = "Puerto de la base de datos (PostgreSQL)."
  type        = number
  default     = 5432
}

variable "tags" {
  description = "Tags comunes."
  type        = map(string)
  default     = {}
}
