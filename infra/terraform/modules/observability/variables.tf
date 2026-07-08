variable "name_prefix" {
  description = "Prefijo de naming (ej.: unpo-nora-staging)."
  type        = string
}

variable "tags" {
  description = "Tags comunes."
  type        = map(string)
  default     = {}
}
