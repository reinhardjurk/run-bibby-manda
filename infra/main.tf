# Serverless container + serverless SQL + object storage + transactional e-mail (Scaleway).

resource "scaleway_container_namespace" "bibby" {
  name        = "bibby-${var.environment}"
  description = "Bibby Multi-Org (${var.environment})"
}

resource "scaleway_sdb_sql_database" "bibby" {
  name    = "bibby-${var.environment}"
  min_cpu = 0
  max_cpu = 4
}

resource "scaleway_object_bucket" "finish_photos" {
  name = "bibby-${var.environment}-finish-photos"
  # Objects are uploaded public-read individually by the photo CLI; the bucket itself has NO
  # public listing, so folders can only be reached with the HMAC-derived name.
}

resource "scaleway_object_bucket" "sponsor_logos" {
  name = "bibby-${var.environment}-sponsor-logos"
}

resource "scaleway_object_bucket_acl" "sponsor_logos" {
  bucket = scaleway_object_bucket.sponsor_logos.id
  acl    = "public-read"
}

resource "scaleway_tem_domain" "mail" {
  count      = var.environment == "production" ? 1 : 0
  name       = replace(replace(var.public_base_url, "https://", ""), "/", "")
  accept_tos = true
}

resource "scaleway_container" "app" {
  name           = "bibby-app"
  namespace_id   = scaleway_container_namespace.bibby.id
  registry_image = var.container_image
  port           = 8080
  cpu_limit      = 1000
  memory_limit   = 1024
  min_scale      = var.container_min_scale
  max_scale      = var.container_max_scale
  timeout        = 120
  privacy        = "public"
  protocol       = "http1"
  deploy         = true
  http_option    = "redirected"

  environment_variables = {
    BIBBY_ENV                 = var.environment
    BIBBY_PUBLIC_BASE_URL     = var.public_base_url
    BIBBY_CORS_ORIGINS        = jsonencode([var.public_base_url])
    BIBBY_COOKIE_SECURE       = "true"
    BIBBY_MAIL_PROJECT_ID     = var.mail_project_id
    BIBBY_MAIL_DEFAULT_SENDER = var.mail_sender
    BIBBY_MAIL_TEST_RECIPIENT = var.mail_test_recipient
    BIBBY_PAYMENT_PROVIDER    = "sumup"
    BIBBY_PDF_WORKERS         = "2"
  }

  secret_environment_variables = {
    BIBBY_DATABASE_URL         = var.database_url
    BIBBY_APP_SECRET           = var.app_secret
    BIBBY_FIELD_ENCRYPTION_KEY = var.field_encryption_key
    BIBBY_MAIL_API_KEY         = var.mail_api_key
  }

  health_check {
    http {
      path = "/health"
    }
    interval          = "30s"
    failure_threshold = 3
  }
}

output "container_url" {
  value = scaleway_container.app.domain_name
}

output "database_endpoint" {
  value     = scaleway_sdb_sql_database.bibby.endpoint
  sensitive = true
}

output "finish_photo_bucket" {
  value = scaleway_object_bucket.finish_photos.endpoint
}
