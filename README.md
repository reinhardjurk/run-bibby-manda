# Bibby Multi-Org – Laufevent-Plattform für mehrere Organisationen

Neuentwicklung der Laufevent-Anwendung „Bibby" als **Mandantenplattform**: mehrere
Organisationen (Vereine/Veranstalter) verwalten ihre Läufe vollständig getrennt voneinander,
ein **Super-Admin** verwaltet die Plattform. Öffentliche Seiten sind über den Slug der
Organisation adressiert (`/{slug}/teilnahme`, `/{slug}/ergebnisse`, `/{slug}/manage?token=…`),
der interne Bereich unter `/{slug}/team`, die Plattformverwaltung unter `/platform`.

| Bereich | Technik |
| --- | --- |
| Backend | Python 3.11, FastAPI, async SQLAlchemy 2 + asyncpg, Alembic, Pydantic-Settings, WeasyPrint, httpx, bcrypt, Fernet |
| Frontend | React + Vite + TypeScript, react-router, eigene i18n (DE/EN) |
| Datenbank | PostgreSQL 16 (Migrationen additiv & idempotent; Row-Level-Security als zweite Verteidigungslinie) |
| Hosting | Serverless Container + Serverless SQL + Object Storage + Transactional E-Mail (Scaleway), OpenTofu, manuell ausgelöster Deploy-Workflow |

## Repository-Struktur

```
backend/        FastAPI-Anwendung (fachliche Pakete: registrations/, timing/, results/, payments/,
                sponsors/, stats/, mail/, settings/, sepa/, users/, events/, auth/, platform/)
backend/alembic Migrationen – einzige Quelle der Wahrheit fürs Schema
backend/tests   Unit-, API- und Isolationstests (pytest, echte PostgreSQL-Testdatenbank)
backend/tools   Lasttests (seed/registration/timing/cleanup) und Zielfoto-CLI
frontend/       SPA (öffentliche Seiten, Team-Bereich, Kiosk-Zeiterfassung, Plattform-Admin)
infra/          OpenTofu (Scaleway)
docs/           Architektur, Rotations-Runbook, Deployment, Lasttests
.github/        CI (Lint, Typen, Tests, Secret-Scan, Build) und manueller Deploy
```

## Lokale Entwicklung

Voraussetzungen: Python 3.11, [uv](https://docs.astral.sh/uv/), Node 22, PostgreSQL 16, die
WeasyPrint-Systembibliotheken (pango, harfbuzz).

```bash
# Datenbanken
createdb bibby && createdb bibby_test     # Benutzer bibby/bibby (siehe backend/.env.example)

# Backend
cd backend
cp .env.example .env                       # Werte anpassen (nie committen)
uv sync --extra dev
uv run alembic upgrade head
uv run python -m app.cli create-platform-admin root@example.org 'ein-langes-passwort'
uv run uvicorn app.main:app --reload --port 8000

# Frontend (zweites Terminal)
cd frontend
npm ci
npm run dev                                # http://localhost:5173, proxied /api → :8000
```

Erster Schritt im Browser: `http://localhost:5173/platform` → als Super-Admin anmelden →
Organisation mit Slug und erstem Org-Admin anlegen → `http://localhost:5173/{slug}/team/login`.

## Qualitätssicherung

```bash
cd backend
uv run ruff check app tests tools && uv run ruff format --check app tests tools
uv run mypy app
uv run pytest -q                           # Unit + API + Isolationstests (Testdatenbank bibby_test)
cd ../frontend && npm run typecheck && npm run lint && npm run build
```

Die CI-Pipeline (`.github/workflows/ci.yml`) führt auf jedem Push Secret-Scan (gitleaks), Lint,
Typprüfung (mypy/tsc), Tests und den Frontend-/Container-Build aus. Deploys erfolgen nur manuell
aus einer grünen Pipeline (`deploy.yml`). Lokal: `pre-commit install` aktiviert gitleaks, ruff und
die Standard-Hooks.

## Dokumentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) – Mandantenmodell, Isolation, Auth, Abläufe
- [docs/ROTATION_RUNBOOK.md](docs/ROTATION_RUNBOOK.md) – Rotation aller Secrets inkl. Folgen
- [docs/DEPLOY.md](docs/DEPLOY.md) – Umgebungen, Secrets, Migrationen, Deploy
- [docs/LOADTEST.md](docs/LOADTEST.md) – Lasttests und Aufräumen
- [docs/FINISH_PHOTOS.md](docs/FINISH_PHOTOS.md) – Zielfoto-Werkzeug
