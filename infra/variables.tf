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
  description = "Fully qualified image reference (registry/namespace/bibby:sha); set by the deploy workflow"
  default     = "placeholder"
}

variable "public_base_url" {
  type        = string
  description = "Public URL of the application (used in mails and redirects); set by the deploy workflow"
  default     = "https://placeholder.invalid"
}

# ---- secrets: provided ONLY via TF_VAR_* from CI secrets, never in tfvars committed to git ----
variable "app_secret" {
  type      = string
  sensitive = true
  default   = "" # set by the deploy workflow via TF_VAR_app_secret
}

variable "field_encryption_key" {
  type      = string
  sensitive = true
  default   = "" # set by the deploy workflow via TF_VAR_field_encryption_key
}

variable "database_url" {
  type        = string
  sensitive   = true
  description = "postgresql+asyncpg:// URL of the serverless SQL database; set by the deploy workflow"
  default     = ""
}

variable "mail_api_key" {
  type      = string
  sensitive = true
  default   = "" # set by the deploy workflow via TF_VAR_mail_api_key
}

variable "mail_project_id" {
  type    = string
  default = ""
}

variable "mail_domain" {
  type        = string
  description = "Sending domain to register in Transactional Email (e.g. example.org). Empty = do not manage a TEM domain."
  default     = ""
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
