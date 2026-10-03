variable "environment" {
  type        = string
  description = "staging | production"
}

variable "region" {
  type    = string
  default = "fr-par"
}

variable "container_image" {
  type        = string
  description = "Fully qualified image reference (registry/namespace/bibby:sha)"
}

variable "public_base_url" {
  type        = string
  description = "Public URL of the application (used in mails and redirects)"
}

# ---- secrets: provided ONLY via TF_VAR_* from CI secrets, never in tfvars committed to git ----
variable "app_secret" {
  type      = string
  sensitive = true
}

variable "field_encryption_key" {
  type      = string
  sensitive = true
}

variable "database_url" {
  type        = string
  sensitive   = true
  description = "postgresql+asyncpg:// URL of the serverless SQL database (pooler endpoint)"
}

variable "mail_api_key" {
  type      = string
  sensitive = true
}

variable "mail_project_id" {
  type = string
}

variable "mail_sender" {
  type    = string
  default = "noreply@example.org"
}

variable "mail_test_recipient" {
  type    = string
  default = "test@example.org"
}

variable "container_min_scale" {
  type    = number
  default = 1
}

variable "container_max_scale" {
  type    = number
  default = 5
}
