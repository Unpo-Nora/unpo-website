variable "name_prefix" {
  description = "Prefijo de naming (ej.: unpo-nora-staging)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
}

variable "azs" {
  description = "Availability zones a usar (una por subnet)."
  type        = list(string)
}

variable "public_subnet_cidrs" {
  description = "CIDRs de las subnets públicas."
  type        = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDRs de las subnets privadas."
  type        = list(string)
}

variable "enable_nat_gateway" {
  description = "Crear NAT gateway para salida de las subnets privadas."
  type        = bool
  default     = true
}

variable "single_nat_gateway" {
  description = "Usar una sola NAT compartida (staging = true para bajar costo)."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags comunes."
  type        = map(string)
  default     = {}
}
