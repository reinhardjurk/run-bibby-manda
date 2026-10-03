#!/usr/bin/env bash
# Shell test case: seed → registration load → timing load → cleanup. Credentials from env vars.
# Exit code ≠ 0 on any failure. Usage: BIBBY_LOADTEST_BASE_URL=... BIBBY_LOADTEST_SLUG=... \
#   BIBBY_LOADTEST_EMAIL=... BIBBY_LOADTEST_PASSWORD=... tools/loadtest/run_all.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${BIBBY_LOADTEST_BASE_URL:?}" "${BIBBY_LOADTEST_SLUG:?}" "${BIBBY_LOADTEST_EMAIL:?}" "${BIBBY_LOADTEST_PASSWORD:?}"
PY=${PYTHON:-python}
status=0
echo "== seed";               $PY -m tools.loadtest.seed || status=1
echo "== registration load";  $PY -m tools.loadtest.registration_load || status=1
echo "== timing load";        $PY -m tools.loadtest.timing_load || status=1
echo "== cleanup";            $PY -m tools.loadtest.cleanup || status=1
if [ "$status" -ne 0 ]; then echo "LOAD TEST FAILED"; exit 1; fi
echo "LOAD TEST OK"
