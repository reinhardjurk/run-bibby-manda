# Testkonzept Bibby Multi-Org

Dieses Dokument beschreibt, **was** in Bibby getestet wird, **auf welcher Ebene** und **wie** die
Tests ausgeführt werden. Es ist die Grundlage für die Abnahme einer Version und für die Pflege
der Testsuiten bei Erweiterungen.

## 1. Ziele

- Jede fachliche Funktion (Anmeldung, Verwaltung, Zeiterfassung, Ergebnisse, Sponsoren,
  Statistik, SEPA, Einstellungen, Plattform) ist durch automatisierte Tests abgedeckt.
- Die Mandantentrennung ist ein **Abnahmekriterium**: kein Test darf Daten einer fremden
  Organisation sehen oder ändern können.
- Die Tests laufen gegen eine **konfigurierbare Organisation** – lokal, auf einer
  Staging-Instanz oder (mit einer eigens dafür angelegten Test-Organisation) auf Produktion.
- Testdaten sind eindeutig markiert und werden nach dem Lauf wieder entfernt.

## 2. Testebenen

| Ebene | Ort | Läuft gegen | Wann |
|---|---|---|---|
| **Unit-Tests** | `backend/tests/unit` | reine Funktionen (Startnummern, Altersklassen, Platzierungen, Staffeln, IBAN, Anreise, Mail-Absender, Konfiguration, Zielfoto-Hashes) | jeder Push (CI) |
| **API-/Integrationstests** | `backend/tests/api` | FastAPI-App in-process mit echter PostgreSQL (Migrationen, RLS), Fake-Mailversand, Fake-SumUp | jeder Push (CI) |
| **Isolationstests** | `backend/tests/api/test_isolation.py` | zwei Organisationen, kreuzweise Zugriffe, Row-Level-Security | jeder Push (CI), Abnahmekriterium |
| **End-to-End (E2E)** | `backend/tools/e2e` | eine **laufende Instanz** über HTTP, konfigurierbare Organisation | vor Releases, nach Deployments, manuell per Workflow |
| **Lasttests** | `backend/tools/loadtest` (siehe `docs/LOADTEST.md`) | laufende Instanz | vor der Saison / bei Infrastrukturänderungen |
| **Sicherheits-Checks** | `.github/workflows/ci.yml` (gitleaks), `.gitleaks.toml`, Pre-Commit | Repository | jeder Push |
| **Frontend** | `frontend` (Typecheck, Lint, Build) | Quellcode | jeder Push (CI) |
| **Smoke-Test** | `.github/workflows/deploy.yml` | frisch deployter Container (`/health`, `/version`) | jedes Deployment |
| **Manuelle Prüfung** | Checkliste in Abschnitt 7 | Browser | vor Releases |

Die Unit- und API-Tests sichern die Logik und laufen schnell und isoliert. Die E2E-Suite prüft
zusätzlich das Zusammenspiel von Deployment, Konfiguration (Secrets, Datenbank, PDF-Rendering,
Cookies/CSRF hinter dem Proxy) und Daten einer realen Organisation.

## 3. Testbereiche und Abdeckung

| Bereich | Geprüft wird | Unit | API | E2E-Modul |
|---|---|---|---|---|
| Basis & Login | Health/Version, httpOnly-Session-Cookie, CSRF-Double-Submit, generische Fehlermeldungen, Logout, Session an Organisation gebunden | – | `test_roles_and_auth` | `test_01_health_auth` |
| Events & Strecken | CRUD, Nummernkreise (Validierung), Vorlagen-Export/-Import ohne Jahresdaten, Hintergrundbilder (Urkunde/Startnummer), write-only Foto-Seed, Löschen nur als Admin mit Kaskade | – | `test_bibs_timing_devices`, `test_registration_flow` | `test_02_events` |
| Online-Anmeldung | Preise (Erwachsene/Jugend), Zahlarten vor Ort / SEPA / SumUp, IBAN-Prüfung und -Maskierung, Mandatsreferenz, Einwilligungen, T-Shirt-Optionen, Dubletten (Name+Geburtsdatum, normalisiert), Team-Autocomplete, Meldeschluss serverseitig, Anmeldebüro nach Meldeschluss, Webhook-Fälschung | `test_bibs`, `test_travel_and_iban` | `test_registration_flow` | `test_03_registration` |
| Startnummern | Sequenz, Nummernkreise pro Strecke, Lücken für Nummernkreise, Advisory-Lock bei paralleler Vergabe, manuelle Umvergabe mit Konflikt | `test_bibs` | `test_bibs_timing_devices` | `test_03`, `test_05` |
| Verwaltungsseite (Teilnehmende) | Anzeige per Token, falscher/fremder Token 404, Änderungen (E-Mail, Team, T-Shirt, Strecke mit Preisfolge), Startnummer unveränderlich, Startnummern-PDF, Urkunde erst nach Zeit, Einfrieren nach Berechnung (409), Zielfoto-Link mit HMAC-Ordner | `test_finishphotos` | `test_registration_flow` | `test_04_manage`, `test_06_timing` |
| Anmeldebüro / Management | Suche (Name, Vor+Nachname, Startnummer), Paging, Statusfilter, Suche per Startnummer, Bezahlt-Markierung, Vollbearbeitung aller Felder, Zahlungsdaten, Identitätsänderung mit Dublettenschutz, Dubletten zusammenführen, Büro-Anmeldung, Startnummern-PDF, Löschen | – | `test_registration_flow` | `test_05_reception` |
| Zeiterfassung | Geräte-Tokens (einmalige Anzeige, Kiosk-URL, Label eindeutig), Kontext, Upload idempotent (Dedup-Schlüssel), Teil-Duplikate, Geräte-Offset, manuelle Erfassung, Bearbeiten/Ignorieren/Löschen, Zusammenfassung, Berechnung (Mittelwert aller Erfassungen minus Start), Plausibilität (Schwelle, Standard aus Einstellungen), interne Ergebnisliste inkl. Personen ohne Veröffentlichung, Reissue/Sperren/Löschen von Geräten | `test_results_logic` | `test_bibs_timing_devices` | `test_06_timing` |
| Ergebnisse & Urkunden | Platz gesamt / Geschlecht / Altersklasse, Übersicht je Strecke × AK × Geschlecht, Einzel-Urkunde, Sammel-PDF mit Filtern und Zähler, ohne Hintergrund, öffentliche Liste nur mit Einwilligung und Zeit, Staffelbildung (genau 3 Mitglieder), Staffelwertung und -platz | `test_results_logic` | `test_bibs_timing_devices` | `test_07_results` |
| Sponsoren | Upload und Normalisierung von Logos, Klassen 1–5, Bearbeiten, Löschen, öffentliche Ausgabe, Anzeigeeinstellungen (Modus, Laufbanddauer, Gewichte) mit Validierung, Bucket-URL-Prüfung | `test_sponsor_bucket` | `test_bibs_timing_devices` | `test_08_sponsors` |
| Statistik | Übersicht, Jüngste/Älteste, Schnellste je Strecke, Teams, Staffeln, Wiederkehrende, Woher-erfahren, T-Shirt-Größen, Anreise-Schätzung nach PLZ-Leitregionen | `test_travel_and_iban` | `test_registration_flow` | `test_09_stats_sepa` |
| SEPA | Zusammenfassung offen/exportiert, CSV mit BOM, entschlüsselte IBAN, Mandatsreferenz, Betragsformat, Export markiert, Wiederholung nur mit `include_exported` | `test_cli_reencrypt` | `test_registration_flow`, `test_isolation` | `test_09_stats_sepa` |
| Einstellungen & Mail | Geheimnisse nie ausgegeben, Live-Mail nur mit Bestätigung, Absender-Lokalteil (Normalisierung, Validierung, feste Domain), Vorlagen, SEPA-Gläubigerdaten, SumUp-Key write-only / löschbar, Logo-Upload | `test_mail_sender` | `test_schema_and_mail` | `test_10_settings_users` |
| Benutzer & Rollen | Anlegen, Validierung (Passwortlänge, Rollen, Dublette), Rollen-Matrix, Rollenänderung, Deaktivieren, Löschen, Selbstaussperrschutz | – | `test_roles_and_auth` | `test_10_settings_users` |
| Plattform (Super-Admin) | getrennter Login, Übersicht, Organisationen anlegen (Slug-Regeln, reservierte Slugs, Dublette), Benutzer der Org, weitere Admins, Passwort-Reset invalidiert Sessions, Organisation betreten/verlassen mit Audit, Sperren (423 öffentlich, Login gesperrt), Löschen mit Slug-Bestätigung | – | `test_platform` | `test_11_platform` |
| Sicherheit & Mandantentrennung | unbekannte Slugs/IDs → 404 (nie 403), fremde Strecke bei Anmeldung, Cross-Org mit zweiter Organisation (Session, Token, Objekt-IDs, auch als Super-Admin im Org-Kontext), CSRF trotz gültiger Session, Rate-Limits | `test_config` | `test_isolation`, `test_roles_and_auth` | `test_12_security` |
| Zielfotos | HMAC-Ordnernamen, CLI-Werkzeug | `test_finishphotos` | – | `test_04_manage` |
| Deployment | Container-Start, Migrationen, Health/Version | – | – | Smoke-Test in `deploy.yml`, `test_01` |

## 4. Die E2E-Suite (`backend/tools/e2e`)

### 4.1 Konfiguration

Die Organisation, gegen die getestet wird, ist vollständig über Umgebungsvariablen konfigurierbar:

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `BIBBY_E2E_BASE_URL` | ja | Basis-URL der Instanz, z. B. `https://www.run-bibby.eu` oder `http://localhost:8000` |
| `BIBBY_E2E_SLUG` | ja | Slug der **Test-Organisation** |
| `BIBBY_E2E_EMAIL` / `BIBBY_E2E_PASSWORD` | ja | ein Benutzer dieser Organisation mit Rolle **admin** |
| `BIBBY_E2E_PLATFORM_EMAIL` / `BIBBY_E2E_PLATFORM_PASSWORD` | nein | Super-Admin; ohne diese Werte werden die Plattform-Tests übersprungen |
| `BIBBY_E2E_SECOND_SLUG` | nein | eine zweite (beliebige, aktive) Organisation für die Cross-Org-Isolationstests |
| `BIBBY_E2E_RATELIMIT=1` | nein | führt zusätzlich den Login-Rate-Limit-Test aus; er verbraucht das Login-Kontingent der eigenen IP (20 Versuche je 5 Minuten), ein direkt folgender Lauf schlägt daher bis zu 5 Minuten lang mit 429 fehl |

Empfehlung: Für Produktion eine eigene Organisation (z. B. `testverein`) ausschließlich für die
Tests verwenden. `python -m tools.e2e.bootstrap` (bzw. `BIBBY_E2E_BOOTSTRAP=1 tools/e2e/run.sh`)
legt sie mit dem Super-Admin-Zugang idempotent an: fehlende Organisation und Org-Admin werden
erstellt, eine gesperrte Organisation reaktiviert, das Admin-Passwort auf `BIBBY_E2E_PASSWORD`
gesetzt; ist `BIBBY_E2E_SECOND_SLUG` gesetzt, entsteht auch die zweite (leere) Organisation.
Der GitHub-Workflow führt diesen Schritt standardmäßig vor der Suite aus. Die Suite legt in der
konfigurierten Organisation Events, Anmeldungen, Geräte, Benutzer und Sponsoren an.

### 4.2 Testdaten, Markierung und Aufräumen

- Alle Events heißen `E2E …`, Geräte-Tokens, Sponsoren und Benutzer tragen das Präfix `E2E`,
  E-Mail-Adressen enden auf `@e2e.example.org`, Teilnehmende heißen `… E2E-…`.
- Vor **und** nach dem Lauf entfernt die Suite alle so markierten Objekte (`cleanup_marked_data`
  in `conftest.py`). Ein abgebrochener Lauf hinterlässt damit keine Altlasten für den nächsten.
- Die Suite setzt den Mailmodus für die Dauer des Laufs auf `off` und stellt anschließend alle
  geänderten Einstellungen (Mail, Absender, Sponsoren-Anzeige, SEPA-Gläubiger, Schwellen) wieder
  her. Ein vorhandenes Logo wird nach dem Logo-Test wieder hochgeladen.
- Ein vorhandener SumUp-Schlüssel wird **nie** überschrieben; der entsprechende Test wird dann
  übersprungen. Ist SumUp konfiguriert, läuft stattdessen der Online-Zahlungs-Test.
- Personen (Teilnehmende) sind organisationsweit und werden vom System absichtlich nicht
  gelöscht (Wiederkehrende). Die Suite verwendet deshalb pro Lauf eindeutige Namen; Reste sind
  an `E2E-` im Nachnamen erkennbar und stören weitere Läufe nicht.
- Es werden keine E-Mails versendet und keine echten Zahlungen ausgelöst.

### 4.3 Aufbau

Die Module sind nummeriert und laufen in dieser Reihenfolge; sie teilen sich ein Event mit drei
Strecken (10 km mit Nummernkreis 100–199, 5 km, Staffel 3×2 km):

```
test_01_health_auth.py      Basis, Login, CSRF, Session-Bindung
test_02_events.py           Events, Strecken, Vorlagen, Hintergründe
test_03_registration.py     Online-Anmeldung, Preise, Zahlarten, Dubletten, Meldeschluss
test_04_manage.py           Verwaltungsseite der Teilnehmenden, PDFs, Zielfoto-Link
test_05_reception.py        Anmeldebüro: Suche, Bezahlt, Vollbearbeitung, Startnummern, Merge
test_06_timing.py           Geräte, idempotenter Upload, Offsets, Berechnung, Plausibilität
test_07_results.py          Platzierungen, Urkunden, öffentliche Ergebnisse, Staffeln
test_08_sponsors.py         Sponsoren und Anzeigeeinstellungen
test_09_stats_sepa.py       Statistik, Anreise, SEPA-Export
test_10_settings_users.py   Einstellungen, Absender, SumUp-Key, Logo, Benutzer und Rollen
test_11_platform.py         Super-Admin (nur mit Plattform-Zugang)
test_12_security.py         404-Verhalten, Cross-Org-Isolation, CSRF, Rate-Limit
```

Öffentliche Anmeldungen sind auf 30 pro Minute und IP begrenzt. Massendaten legt die Suite
deshalb über das Anmeldebüro an; die öffentliche Anmeldung wartet bei einem 429 einmal ab.

### 4.4 Ausführung

Lokal (Backend läuft, z. B. `uvicorn app.main:app --port 8000`):

```bash
cd backend
BIBBY_E2E_BASE_URL=http://localhost:8000 BIBBY_E2E_SLUG=demo \
BIBBY_E2E_EMAIL=admin@example.org BIBBY_E2E_PASSWORD=… \
tools/e2e/run.sh                      # alle Module
tools/e2e/run.sh -k timing            # nur Zeiterfassung
tools/e2e/run.sh tools/e2e/test_03_registration.py -x
```

Gegen eine deployte Instanz identisch mit `BIBBY_E2E_BASE_URL=https://www.run-bibby.eu`. In
GitHub Actions steht der manuelle Workflow **E2E tests** (`.github/workflows/e2e.yml`) zur
Verfügung: Basis-URL, Slug und optional zweiter Slug werden beim Start eingegeben, die
Zugangsdaten kommen aus den Repository-Secrets `E2E_EMAIL`, `E2E_PASSWORD`,
`E2E_PLATFORM_EMAIL`, `E2E_PLATFORM_PASSWORD`. Der JUnit-Bericht wird als Artefakt abgelegt.

Die Suite ist bewusst **nicht** Teil des normalen `pytest`-Laufs (`testpaths = ["tests"]`), weil
sie eine laufende Instanz benötigt.

## 5. Ablauf einer Abnahme

1. CI auf dem Release-Commit grün (gitleaks, ruff, mypy, Unit-/API-Tests inkl. Isolation,
   Frontend-Build, Docker-Build).
2. Deployment auf die Zielumgebung; Smoke-Test des Workflows grün.
3. E2E-Suite gegen die Test-Organisation der Zielumgebung mit `BIBBY_E2E_SECOND_SLUG` und
   Plattform-Zugang: **alle Tests bestanden**, höchstens die dokumentierten Skips
   (SumUp nicht konfiguriert, Rate-Limit nicht aktiviert).
4. Manuelle Checkliste (Abschnitt 7) für die Oberfläche.
5. Vor der Saison zusätzlich Lasttest nach `docs/LOADTEST.md`.

## 6. Nicht automatisiert abgedeckt

- Tatsächliche Mailzustellung (Scaleway TEM, DNS/SPF/DKIM): manuell im Modus `test` an die
  Test-Adresse prüfen.
- Echte SumUp-Zahlungen: lokal und in den API-Tests läuft der Fake-Provider; in Produktion mit
  dem SumUp-Sandbox-Konto einmal durchspielen (Checkout, Webhook, Status „bezahlt“).
- Optik der PDFs (Hintergründe, Versatzzeilen) und der Sponsorenanzeige: Sichtprüfung.
- Browser-Oberfläche: siehe Checkliste; die Suite prüft nur, dass die SPA ausgeliefert wird.
- Offline-Verhalten der Zeiterfassung im Browser (Warteschlange, Wiederholung): manuell mit
  Flugmodus prüfen; die serverseitige Idempotenz ist automatisiert.

## 7. Manuelle Checkliste (Oberfläche)

- Öffentliche Seite der Organisation: Logo, Events, Strecken, Preise, Sprachumschaltung DE/EN.
- Anmeldung im Browser mit jeder Zahlart; Bestätigungsseite zeigt Startnummer und Verwaltungslink.
- Verwaltungslink aus der Mail öffnen, Daten ändern, Startnummer-PDF und (nach dem Lauf)
  Urkunde herunterladen.
- Team-Bereich: Login, Rollen-abhängige Navigation, Anmeldebüro-Suche, Bezahlt-Schalter.
- Zeiterfassung im Kiosk-Modus auf einem Tablet: Erfassen, Offline gehen, weiter erfassen,
  wieder online – keine Doppelungen in der Übersicht.
- Ergebnisse öffentlich und intern, Urkundendruck je Altersklasse.
- Sponsorenanzeige (Rotation und Laufband) auf dem Anzeige-Bildschirm.
- Super-Admin: Organisation anlegen, Admin anlegen, Organisation betreten, Audit einsehen.

## 8. Pflege

- Jede neue Funktion erhält Unit-/API-Tests **und** einen Eintrag in der Bereichsmatrix
  (Abschnitt 3) sowie, wenn sie über HTTP erreichbar ist, einen E2E-Test im passenden Modul.
- Neue Einstellungen, die die Suite verändert, werden in `RESTORABLE_SETTINGS`
  (`conftest.py`) aufgenommen, damit sie nach dem Lauf wiederhergestellt werden.
- Neue Objekttypen mit Testdaten bekommen das Präfix `E2E` und einen Aufräumschritt in
  `_cleanup`.
