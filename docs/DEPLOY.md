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

1. Scaleway-Projekt, IAM-Key, State-Bucket anlegen; Environments in GitHub befüllen.
2. Deploy ausführen; Datenbank-URL aus dem Tofu-Output (`database_endpoint`) in die Secrets
   übernehmen und erneut deployen.
3. Super-Admin anlegen: entweder einmalig `BIBBY_BOOTSTRAP_PLATFORM_ADMIN_EMAIL/PASSWORD` als
   Container-Secrets setzen (Bootstrap beim Start, idempotent) oder
   `python -m app.cli create-platform-admin` in einer Container-Shell ausführen. Danach die
   Bootstrap-Variablen wieder entfernen.
4. Unter `/platform` die erste Organisation samt Org-Admin anlegen.

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
