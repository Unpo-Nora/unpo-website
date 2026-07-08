variable "name_prefix" {
  description = "Prefijo de naming (ej.: unpo-nora-staging)."
  type        = string
}

variable "repository_names" {
  description = "Nombres funcionales de los repos (se prefijan con name_prefix)."
  type        = list(string)
  default     = ["backend", "frontend"]
}

variable "image_tag_mutability" {
  description = "MUTABLE o IMMUTABLE."
  type        = string
  default     = "MUTABLE"
}

variable "scan_on_push" {
  description = "Escaneo de vulnerabilidades al hacer push."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags comunes."
  type        = map(string)
  default     = {}
}
