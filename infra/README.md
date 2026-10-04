# Infrastructure (OpenTofu / Terraform, Scaleway)

Resources: container namespace + serverless container (backend incl. built SPA), serverless SQL
database (PostgreSQL), object storage buckets (finish photos without public listing, sponsor
logos public-read) and, when `mail_domain` is set, a transactional e-mail domain (its DNS records
appear in the output `mail_domain_dns`).

Applied exclusively by the manual `Deploy` GitHub workflow after a green CI run. State is stored in
an Object Storage bucket (`-backend-config`). All secrets are injected via `TF_VAR_*` from GitHub
environment secrets; `*.tfvars` files are git-ignored (only `*.example` is committed).

Migrations run as a separate workflow step (`alembic upgrade head`) **before** the container is
redeployed – never at container start (serverless pooler).
