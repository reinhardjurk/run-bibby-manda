#!/usr/bin/env bash
# Runs the end-to-end suite against a deployed Bibby instance.
#
#   BIBBY_E2E_BASE_URL=https://www.run-bibby.eu BIBBY_E2E_SLUG=testverein \
#   BIBBY_E2E_EMAIL=admin@testverein.de BIBBY_E2E_PASSWORD=... tools/e2e/run.sh [pytest args]
#
# Optional: BIBBY_E2E_PLATFORM_EMAIL/PASSWORD, BIBBY_E2E_SECOND_SLUG, BIBBY_E2E_RATELIMIT=1
#           BIBBY_E2E_BOOTSTRAP=1 creates/repairs the test organization first (needs the platform login)
set -euo pipefail
cd "$(dirname "$0")/../.."
for v in BIBBY_E2E_BASE_URL BIBBY_E2E_SLUG BIBBY_E2E_EMAIL BIBBY_E2E_PASSWORD; do
  if [ -z "${!v:-}" ]; then echo "missing $v" >&2; exit 2; fi
done
PY=${PYTHON:-python}
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; fi
if [ "${BIBBY_E2E_BOOTSTRAP:-0}" = "1" ]; then "$PY" -m tools.e2e.bootstrap; fi
exec "$PY" -m pytest tools/e2e -p no:cacheprovider -ra "$@"
