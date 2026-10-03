# Lasttests

Werkzeuge in `backend/tools/loadtest/` arbeiten ausschließlich über die öffentliche API gegen
eine laufende Umgebung (auch Produktion). Testdaten sind markiert: E-Mail-Domain
`loadtest.example.org`, Event-/Gerätenamen mit Präfix `LOADTEST`, Startnummern ab `90001`.
Vor jedem Lauf wird der Mailmodus der Organisation auf `off` erzwungen (und geprüft).

```bash
cd backend
export BIBBY_LOADTEST_BASE_URL=https://lauf.example.org
export BIBBY_LOADTEST_SLUG=testverein
export BIBBY_LOADTEST_EMAIL=admin@example.org
export BIBBY_LOADTEST_PASSWORD='…'

uv run tools/loadtest/run_all.sh                      # seed → Anmeldungen → Zeiterfassung → cleanup
# einzeln:
uv run python -m tools.loadtest.seed
BIBBY_LOADTEST_CONCURRENCY=50 BIBBY_LOADTEST_TOTAL=500 uv run python -m tools.loadtest.registration_load
BIBBY_LOADTEST_DEVICES=6 BIBBY_LOADTEST_BATCHES=100 uv run python -m tools.loadtest.timing_load
uv run python -m tools.loadtest.cleanup
```

Geprüft wird: keine Fehler, **Eindeutigkeit der Startnummern unter Nebenläufigkeit**,
Idempotenz der Offline-Queue (Wiederholungen erhöhen nur `duplicates`), p50/p95-Latenzen.
Jeder Verstoß endet mit Exit-Code ≠ 0. Für hohe Raten `BIBBY_REGISTRATION_LIMIT` der Umgebung
temporär erhöhen (sonst 429). `cleanup` entfernt alle markierten Daten vollständig.
