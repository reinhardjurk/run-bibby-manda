# Deployment

## Umgebungen

GitHub-Environments `staging` und `production` mit jeweils eigenen Secrets/Variablen:

| Art | Name | Inhalt |
| --- | --- | --- |
| Secret | `SCW_ACCESS_KEY`, `SCW_SECRET_KEY` | IAM-API-Key für Registry, Container, SDB, Object Storage |
| Secret | `BIBBY_DATABASE_URL` | `postgresql+asyncpg://…` (App-Rolle, Pooler-Endpoint) |
| Secret | `BIBBY_DATABASE_URL_MIGRATIONS` | Eigentümer-Rolle für `alembic upgrade head` |
| Secret | `BIBBY_APP_SECRET`, `BIBBY_FIELD_ENCRYPTION_KEY`, `BIBBY_MAIL_API_KEY` | siehe Runbook |
| Variable | `SCW_REGISTRY`, `SCW_NAMESPACE`, `SCW_PROJECT_ID`, `SCW_ORGANIZATION_ID`, `TF_STATE_BUCKET`, `PUBLIC_BASE_URL` | unkritische Konfiguration |

## Ablauf (`.github/workflows/deploy.yml`, manuell)

1. **verify-ci** – der Commit braucht einen erfolgreichen `CI`-Lauf (Lint, Typen, Tests,
   Secret-Scan, Frontend-Build, Container-Build).
2. **build-push** – ein Image aus `backend/Dockerfile` (Frontend wird im Multi-Stage-Build
   erzeugt und unter `/app/static` ausgeliefert; `GIT_SHA` landet in `/version`).
3. **migrate** – `alembic upgrade head` als eigener Schritt gegen die Datenbank. Migrationen sind
   additiv/idempotent; der Container startet **nie** mit Migrationen.
4. **deploy** – `tofu apply` in `infra/` (Serverless Container, SDB, Buckets, TEM), danach
   Smoke-Test auf `/health` und `/version`.

## Erstinbetriebnahme

1. Scaleway-Projekt, IAM-Key (Registry, Container, SDB, Object Storage, TEM), State-Bucket und
   Registry-Namespace anlegen; Mail-Domain in Transactional Email verifizieren.
2. **Datenbank einmalig lokal anlegen** – der Deploy-Workflow führt Migrationen vor `tofu apply`
   aus, die Datenbank muss also vorher existieren. Alle Variablen außer `environment` haben
   Platzhalter-Defaults, die der Workflow später überschreibt:

   ```bash
   cd infra
   export SCW_ACCESS_KEY=… SCW_SECRET_KEY=… SCW_DEFAULT_PROJECT_ID=… SCW_DEFAULT_ORGANIZATION_ID=…
   export AWS_ACCESS_KEY_ID=$SCW_ACCESS_KEY AWS_SECRET_ACCESS_KEY=$SCW_SECRET_KEY   # S3-State-Backend
   tofu init -backend-config="bucket=<state-bucket>" -backend-config="key=bibby/production.tfstate"
   tofu apply -var environment=production \
     -target=scaleway_sdb_sql_database.bibby -target=scaleway_object_bucket.finish_photos
   tofu output -raw database_endpoint
   ```

   Serverless SQL authentifiziert mit dem IAM-Key; die URL für beide DB-Secrets lautet
   `postgresql+asyncpg://<ACCESS_KEY>:<SECRET_KEY>@<endpoint-host>:5432/bibby-production?ssl=require`.
   Eigene PostgreSQL-Rollen sind dort nicht möglich, die RLS-Policies bleiben deshalb inaktiv
   (primäre Verteidigung ist die getestete Scoping-Schicht).
3. Environments in GitHub befüllen (Tabelle oben) und den Deploy-Workflow ausführen. Beim
   ersten Lauf schlägt nur der abschließende Smoke-Test fehl, weil `PUBLIC_BASE_URL` noch nicht
   die Container-Domain ist: Domain aus dem Tofu-Output `container_url` übernehmen, Variable
   setzen, erneut deployen.
4. Super-Admin anlegen: entweder einmalig `BIBBY_BOOTSTRAP_PLATFORM_ADMIN_EMAIL/PASSWORD` als
   Container-Secrets setzen (Bootstrap beim Start, idempotent) oder
   `python -m app.cli create-platform-admin` in einer Container-Shell ausführen. Danach die
   Bootstrap-Variablen wieder entfernen.
5. Unter `/platform` die erste Organisation samt Org-Admin anlegen.

## Datenbankrollen (RLS)

```sql
CREATE ROLE bibby_app LOGIN PASSWORD '…';          -- kein BYPASSRLS, nicht Eigentümer
GRANT USAGE ON SCHEMA public TO bibby_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bibby_app;
ALTER DEFAULT PRIVILEGES FOR ROLE bibby_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO bibby_app;
```

Die App verbindet sich als `bibby_app`, Migrationen laufen als Eigentümer (`bibby_owner`).
Plattform-Endpoints (Super-Admin) lesen über alle Mandanten; dafür ist die Plattformrolle in der
App zuständig – RLS-Policies lassen Mandantentabellen nur mit gesetztem `app.organization_id`
lesen, weshalb die Plattformübersicht ausschließlich Aggregationen über eine Verbindung mit
`BYPASSRLS`-Recht (oder die Eigentümer-Rolle) benötigt, falls RLS für die App-Rolle aktiv ist.
Wird nur die primäre Scoping-Schicht genutzt (eine Rolle), greifen die Policies nicht.
