# Instructions for an AI model: write test scripts for one single event

You are writing an automated test suite for **one existing running event** on a Bibby
instance. Bibby is a multi-tenant platform for running events: every organization has a slug,
a public participation page and a protected team area. Your tests talk to the HTTP API behind
those pages. Follow these instructions exactly.

## 1. Configuration (everything comes from environment variables)

| Variable | Required | Meaning |
|---|---|---|
| `EVENT_PARTICIPATION_URL` | yes | public page of the organization, e.g. `https://www.run-bibby.eu/laufclub` |
| `EVENT_MANAGEMENT_URL` | yes | team area of the same organization, e.g. `https://www.run-bibby.eu/laufclub/team` |
| `EVENT_NAME` | yes | exact name of the event under test, e.g. `Stadtlauf` (combined with `EVENT_YEAR` if set) |
| `EVENT_YEAR` | no | year of the event, needed when several events share the name |
| `TEAM_EMAIL` / `TEAM_PASSWORD` | yes | a team user of that organization with the role `race_office` (an `admin` works too) |
| `ALLOW_RACE_OPERATIONS` | no | `1` enables the tests that change the event's results (timing upload, computation, SEPA export). Default: off |
| `REQUEST_TIMEOUT` | no | seconds per request, default 60 |
| `LOAD_DEVICES` | no | number of simulated timing devices in the load test, default 10 |
| `LOAD_RECORDS_PER_DEVICE` | no | finish-time records each device uploads, default 200 |
| `LOAD_BATCH_SIZE` | no | records per upload request, default 50 (server maximum 500) |
| `LOAD_P95_MS` | no | acceptance threshold for the 95th-percentile upload latency, default 1500 |

Derive everything else from the two URLs, never hard-code hosts or slugs:

- base URL = scheme + host of `EVENT_PARTICIPATION_URL` (strip the path)
- slug = last non-empty path segment of `EVENT_PARTICIPATION_URL`
- `EVENT_MANAGEMENT_URL` must be `<base>/<slug>/team`; abort with a clear message if its host or
  slug differ from the participation URL. The management URL is only used for this consistency
  check and for the login call; the API routes below are fixed.

Abort with exit code 2 and a one-line explanation when a required variable is missing, the
event is not found, or the user does not have the required role.

## 2. API you will use

All paths are relative to the base URL. Responses are JSON unless stated otherwise.

**Public (no login)**

- `GET /health` → `{"status":"ok"}`; `GET /version` → `{"backend": …, "db_schema": …}`
- `GET /api/public/{slug}/info` → organization, `payment_methods` (subset of `on_site`,
  `sepa_debit`, `sumup`), `heard_about_options`, `events[]` with `id`, `name`, `year`,
  `registration_open`, `tshirt_options`, `competitions[]` (`id`, `title_de`, `title_en`,
  `price_adult_cents`, `price_youth_cents`, `relay_scoring`, `start_time`)
- `GET /api/public/{slug}/events/{event_id}/competitions`
- `GET /api/public/{slug}/team-names?q=…` → list of existing team names
- `POST /api/public/{slug}/registrations` body:
  `{event_id, competition_id, first_name, last_name, birth_date (YYYY-MM-DD), gender ("f"|"m"|"x"),
  email, language ("de"|"en"), team_name?, tshirt_size?, postal_code?, heard_about?,
  consent_data (must be true), consent_publish, payment_method, iban?, account_holder?}`
  → `201 {registration_id, bib_number, manage_url, checkout_url?, payment{method,status,
  amount_cents,iban_masked?,mandate_reference?}}`. Errors: `400` (deadline, consent, IBAN,
  T-shirt size), `409` (same person already registered), `422` (schema), `429` (rate limit:
  30 registrations per minute and IP; wait 65 s once and retry)
- `GET /api/public/{slug}/manage?token=…` → the participant's view (`bib_number`, `frozen`,
  `payment`, `competitions`, `tshirt_options`, `photo_url?`); wrong token → `404`
- `PATCH /api/public/{slug}/manage?token=…` body subset of `{email, competition_id, team_name,
  tshirt_size}`; `409` once a finish time exists (`frozen: true`)
- `GET /api/public/{slug}/manage/bib.pdf?token=…` → PDF; `GET …/manage/certificate.pdf?token=…`
  → PDF or `404` before a time exists
- `GET /api/public/{slug}/results?event_id=…` → published results (only participants with
  `consent_publish` and a time)

**Team (login required)**

- `POST /api/{slug}/auth/login` `{email, password}` → `200 {csrf_token, roles, …}` and an
  httpOnly cookie `bibby_session`. Send the cookie on every call and the header
  `X-CSRF-Token: <csrf_token>` on every POST/PUT/PATCH/DELETE. `GET /api/{slug}/auth/me`,
  `POST /api/{slug}/auth/logout`.
- `GET /api/{slug}/team/events` and `GET /api/{slug}/team/events/{id}` (with `competitions`,
  `registration_deadline`, `default_start_time`)
- `GET /api/{slug}/team/registrations?event_id=…&q=…&status=…&page=…&page_size=…` →
  `{items[], total, page, page_size}`; `GET …/registrations/by-bib/{n}?event_id=…`;
  `GET …/registrations/{id}`; `POST …/registrations` (race office entry, same body as public
  plus optional `status`); `PATCH …/registrations/{id}` (any field, `bib_number` conflict →
  `409`); `POST …/registrations/{id}/mark-paid`; `DELETE …/registrations/{id}` → `204`;
  `GET …/registrations/{id}/bib.pdf`
- `GET /api/{slug}/team/stats?event_id=…`
- Timing devices (team): `GET /api/{slug}/team/timing/devices`; `POST …/timing/devices`
  `{label, time_offset_seconds}` → `201` with the plaintext `token` (shown once) and `kiosk_url`;
  `DELETE …/timing/devices/{id}` → `204`. `GET …/timing/summary?event_id=…` →
  `{records: {valid: n, …}, distinct_bibs}`.
- Device upload (no login, header `X-Device-Token: <token>`): `GET /api/{slug}/timing/context`;
  `POST /api/{slug}/timing/records` `{event_id, records: [{bib_number, absolute_time (ISO 8601),
  dedup_key (8–120 chars, unique per record)}]}` with at most 500 records per request →
  `{inserted, duplicates}`. Re-sending a record with the same `dedup_key` is counted as a
  duplicate and never stored twice.
- Race operations (only with `ALLOW_RACE_OPERATIONS=1`): `POST /api/{slug}/team/timing/records/manual`
  `{event_id, bib_number, absolute_time}`; `GET …/timing/records?event_id=…&bib_number=…`;
  `DELETE …/timing/records/{id}`; `POST …/timing/compute?event_id=…` →
  `{computed, without_start_time, relays_formed}`; `GET …/timing/internal-results?event_id=…`;
  `GET …/results/certificate.pdf?event_id=…&bib_number=…`

Unknown or foreign IDs always answer `404`, never `403`.

## 3. Hard rules for a real event

1. **Never modify, delete or export anything you did not create.** The event, its competitions,
   its existing registrations and the organization's settings are production data.
2. Mark every registration you create: last name starts with `TEST-`, e-mail ends with
   `@test.example.org`, team name (if any) starts with `TEST `. Keep the IDs you create in a
   module-level list and delete them in a session-scoped teardown via
   `DELETE /api/{slug}/team/registrations/{id}`. Also delete leftovers from earlier runs at the
   start: search `q=TEST-` for the event and delete every item whose e-mail matches the marker.
3. Do not call `compute`, the SEPA export, settings endpoints or event edits unless
   `ALLOW_RACE_OPERATIONS=1`. Even then, upload timing records only for bibs you created,
   delete those records again and run `compute` once more at the end so the event's results
   are exactly as before.
4. Use a fixed valid test IBAN (`DE89 3704 0044 0532 0130 00`) for SEPA registrations and
   never a real one. Choose `payment_method` only from `info.payment_methods`; skip tests
   for methods the organization does not offer.
5. Respect the registration deadline: if `registration_open` is false, public registration
   tests must expect `400` and create their data through the race-office endpoint instead.
6. Load tests upload finish times only for bib numbers that no participant of the event has:
   read the highest bib number of the event through the race-office search and use numbers
   from `max_bib + 100000` upwards (the server accepts bibs up to 999999). Delete every
   uploaded record and every device you created afterwards; run `compute` once at the end only
   if you ran it during the test.
7. Never print passwords, tokens or cookies. Assertion messages may include response bodies
   of public endpoints only.

## 4. What to test (one module per block, pytest, in this order)

1. **Reachability and configuration**: health and version; the organization is the one from the
   URL; the event is found by name (and year); it has at least one competition; the team login
   works and `auth/me` lists `race_office` or `admin`; the management URL is consistent.
2. **Public event data**: competitions, prices and T-shirt options from `info` equal those from
   the team endpoint; `registration_open` matches the deadline; `team-names` returns existing
   names for a known prefix.
3. **Competition detection**: read the event's competitions from the team endpoint and the
   public `info` and assert both lists have the same IDs. Store them in a session fixture
   `competitions`. Every test below that depends on a competition is **parametrized over this
   list at collection time** (use `pytest_generate_tests` with the IDs read from the API once,
   or a module-level call that reads the environment), so the suite adapts automatically when
   the organizer adds or removes races. The report must show the race title in each test ID.
   Record for each competition: adult and youth price, `relay_scoring`, bib range
   (`bib_range_start`/`bib_range_end`, may be null) and `start_time`.
4. **Registration across all races**: for **every** competition create one adult registration
   with the first offered payment method and, when a youth price exists, one youth
   registration; assert the amount equals the competition's price, and the bib lies inside the
   competition's bib range when one is configured and outside every configured range
   otherwise. For relay competitions (`relay_scoring`) register three persons with the same
   `TEST `-prefixed team name and assert the team name is returned by `team-names`. Then
   register one person in race A and move them to race B via the manage page: the bib number
   stays, the open payment amount becomes race B's price. Finally attempt a second
   registration of the same person in another race of the same event and assert `409`.
5. **Registration details**: one registration per offered payment method (adult price), one youth
   registration (birth date so that the youth price applies; use the event's `youth_cutoff_date`
   from the team endpoint when present, else age 12), bib number is a positive integer and
   unique across your registrations, `manage_url` contains the token, SEPA response masks the
   IBAN and carries a mandate reference, duplicate person → `409`, missing consent → `400`,
   invalid T-shirt size → `400`, invalid IBAN → `400`, the created registration appears in the
   race-office search by name and by bib.
6. **Manage page**: view with the token; wrong token → `404`; change e-mail, team name, T-shirt
   size and competition (bib number stays, open payment amount follows the new price); bib PDF
   is a PDF (`%PDF` header); certificate → `404` before a time exists.
7. **Race office**: search, paging with `page_size=1`, `by-bib`, detail, mark-paid sets
   `payment.status == "paid"`, editing name and birth date, manual bib re-assignment to a free
   number and conflict with a used one (`409`), race-office registration after the deadline,
   bib PDF, delete → `204` then `404`.
8. **Statistics (read-only)**: `stats` for the event returns `overview.participants >= number of
   your registrations`, one entry in `competitions[]` per detected race, and `travel`.
9. **Race operations** (`ALLOW_RACE_OPERATIONS=1` only): manual timing record for one of your
   bibs, `compute` returns `computed >= 1`, the registration has `finish_seconds`, the manage
   page is `frozen` and the certificate PDF downloads, `internal-results` contains your bib,
   public `results` contains it only if `consent_publish` was true; cleanup as in rule 3.
10. **Load test of finish-time entry** (`ALLOW_RACE_OPERATIONS=1` only, marker `load`): this
    simulates the finish line on race day, where several devices record and upload times at
    the same moment, some of them offline for a while and re-sending.
    - Setup: create `LOAD_DEVICES` device tokens labelled `TEST Load <n>`; assign each device
      its own block of bib numbers per rule 6; generate `LOAD_RECORDS_PER_DEVICE` records per
      device with `absolute_time` spread over a plausible finish window after the earliest
      competition `start_time` and a UUID-based `dedup_key`.
    - Run 1, concurrent upload: every device uploads its records in batches of
      `LOAD_BATCH_SIZE` from its own thread (`concurrent.futures.ThreadPoolExecutor`, one
      worker per device) at the same time. Measure wall-clock per request. Assert every
      response is `200`, the sum of `inserted` equals the number of generated records and
      `duplicates` is 0.
    - Run 2, offline replay: re-send the complete set of batches of half the devices
      concurrently (what a device does after reconnecting). Assert `inserted` is 0 and
      `duplicates` equals the number of re-sent records, and that `summary.records.valid` did
      not grow.
    - Run 3, mixed: each device sends batches that contain 50 % already-sent and 50 % new
      records. Assert the counts match exactly.
    - Correctness after load: `GET …/timing/records?event_id=…&bib_number=…` for a sample of
      ten bibs returns exactly the generated records for that bib with the right timestamps;
      `summary.distinct_bibs` increased by exactly the number of load bibs.
    - Metrics to report (print and write to `load_report.json`): devices, records, batches,
      total duration, throughput in records per second, latency p50/p95/max in ms per run,
      error count. Assert `p95 <= LOAD_P95_MS` and zero errors.
    - Teardown: delete all uploaded records (list per bib with `bib_number=`, then `DELETE`
      each) and all `TEST Load` devices, then assert `summary` equals the value captured before
      the test. Run this teardown even when an assertion failed.
    - Keep the default sizes small enough to finish within a few minutes against a production
      instance; larger runs are configured through the variables above, never hard-coded.

Every test asserts the status code first and then the fields it needs; use `assert r.status_code
== 201, r.text` so failures show the server message.

## 5. Technical conventions

- Python 3.11, `pytest`, `httpx` (sync client), no other dependencies. One file `conftest.py`
  with fixtures `cfg` (parsed environment), `anon` (plain client), `team` (logged-in client with
  CSRF header), `event` (the resolved event dict), `created` (list of registration IDs, cleaned
  up at session end) and a helper `register(payload)` that retries once after a `429`.
- Mark the race-operations tests with `@pytest.mark.race_ops` and the load test with
  `@pytest.mark.load`; skip both when the flag is not set. Mark payment-method tests with the
  method name and skip when not offered.
- Parametrized tests over competitions use the race title as the pytest ID
  (`ids=lambda c: c["title_de"]`) so the report reads "test_adult_price[10 km]".
- Each test must pass on its own and the whole suite must pass twice in a row against the same
  event (idempotent).
- Provide `README.md` with: the variables, how to run (`pytest -ra`), what the suite creates
  and deletes, and what it never touches.
- Output must be lint-clean (`ruff check`, `ruff format`) and type-annotated where practical.

## 6. Deliverables

```
event_tests/
  README.md
  conftest.py
  test_1_setup.py
  test_2_public_event.py
  test_3_competitions.py        detection, parametrization source
  test_4_registration_races.py  registrations across all races, relays, race change
  test_5_registration.py        payment methods, validation, duplicates
  test_6_manage.py
  test_7_race_office.py
  test_8_stats.py
  test_9_race_ops.py
  test_10_load_timing.py        load test of finish-time entry
```

Before you finish, run the suite twice against the configured event with
`ALLOW_RACE_OPERATIONS` unset, report the pass/skip counts, and confirm that the race-office
search for `TEST-` returns zero items afterwards. Then run the load test once with the default
sizes against a non-production instance, include `load_report.json` in the deliverables, and
confirm that no `TEST Load` device and no uploaded record remains.
