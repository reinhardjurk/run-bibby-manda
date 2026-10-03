# Architektur

## Mandantenmodell

* `organization` ist der Mandant (Slug, Name, Status `active|suspended`). **Jede** fachliche
  Tabelle trägt `organization_id` (NOT NULL, FK, Index) – siehe `backend/app/db/models/`.
* Die Organisation wird ausschließlich **serverseitig** aufgelöst:
  * öffentliche Endpoints: aus dem URL-Slug (`get_org_by_slug`),
  * Team-Endpoints: aus der Session, die an genau eine Organisation gebunden ist
    (`get_current_principal` prüft `auth_token.organization_id == org.id`),
  * Geräte-Endpoints: Geräte-Token wird nur innerhalb der Slug-Organisation gesucht.
  Kein Endpoint liest eine `organization_id` aus Body oder Query.
* **Zentrale Scoping-Schicht** `app/core/scoping.py`: `tenant_select(Model, org_id)` und
  `get_tenant_or_404(...)`. Fremde oder erratene IDs liefern **404** (kein Existenz-Orakel).
* Eindeutigkeiten gelten pro Organisation (`UNIQUE(organization_id, email)`,
  `UNIQUE(organization_id, match_key)`, Mandatsreferenz, Geräte-Label); Startnummern pro Event.
* **Row-Level-Security** (Migration `0002`): Policies auf allen Mandantentabellen prüfen
  `organization_id::text = current_setting('app.organization_id', true)`. Die Anwendung setzt
  die Variable pro Request (`set_config`) und löscht sie, bevor die Verbindung in den Pool
  zurückgeht. RLS greift für Rollen ohne `BYPASSRLS`, die die Tabellen nicht besitzen – in
  Produktion verbindet sich die App daher mit einer eigenen, eingeschränkten Rolle, während
  Migrationen (CI-Schritt) mit der Eigentümer-Rolle laufen. Primäre Verteidigung bleibt die
  getestete Scoping-Schicht (`tests/api/test_isolation.py`).
* Gesperrte Organisationen: öffentliche API → 423 (Frontend zeigt neutrale Hinweisseite), Logins
  → 401, bestehende Sessions werden beim Sperren gelöscht, Daten bleiben erhalten.

## Rollen

* **Super-Admin** (`platform_admin`, eigene Session `platform_session`): Organisationen
  anlegen/sperren/löschen, ersten Org-Admin anlegen, Passwörter zurücksetzen, Übersicht,
  Audit-Log. Kann sich nicht selbst löschen; mindestens ein aktives Konto bleibt bestehen.
  **Handeln als Organisation**: `POST /api/platform/organizations/{id}/enter` setzt
  `acting_organization_id` in der Plattform-Session; danach gilt der Super-Admin in genau dieser
  Organisation als Admin. Eintritt, Austritt und **jede schreibende Aktion** werden in `audit_log`
  protokolliert (eigene Transaktion, auch bei Fehlschlag der eigentlichen Aktion).
* **Organisations-RBAC** (`user_role`): `admin` (impliziert alles, verwaltet Benutzer, kein
  Selbstaussperren), `race_office`, `timing`, `sponsor_management`, `sepa`, `viewer`. Prüfung
  serverseitig über `require_roles(...)` an jedem Admin-Endpoint.

## Authentifizierung

* Passwort-Login → zufälliges Token, in der DB nur als HMAC-SHA256 (App-Secret) gespeichert,
  72 h gültig; Transport als **httpOnly, Secure, SameSite=Lax Cookie**. Schreibende Aufrufe
  benötigen den CSRF-Header (`X-CSRF-Token`) passend zum nicht-httpOnly CSRF-Cookie
  (Double-Submit). Keine Tokens in `localStorage`.
* Teilnehmende: persönlicher Verwaltungslink (Token zufällig, nur Hash gespeichert).
* Geräte-Tokens: Header `X-Device-Token`, nur Hash gespeichert, Klartext einmalig bei
  Erzeugung/„Neu ausstellen".
* Generische Login-Fehlermeldung, konstante Antwortzeit (Dummy-bcrypt), Rate-Limits pro IP und
  Konto mit exponentiellem Backoff.

## Anmeldung & Startnummern

Reihenfolge in `registrations/service.create_registration`:

1. Lesen & validieren (Meldeschluss serverseitig, T-Shirt-Option, Einwilligung, IBAN).
2. Bei Online-Zahlung: lesende Transaktion beenden und **Checkout beim Anbieter anlegen** – ohne
   offene Transaktion, ohne Lock. Anbieter nicht erreichbar → 503, nichts gespeichert.
3. Teilnehmer (match_key) finden/anlegen, Anmeldung + Zahlung schreiben; `flush()`.
   `IntegrityError` auf `uq_registration_event_participant` → 409 „bereits angemeldet" (nur
   diese Ausnahme, kein pauschales `except Exception`).
4. **Letzter Schritt**: `pg_advisory_xact_lock(hashtext(event_id))`, Nummer bestimmen
   (`registrations/bibs.py`), einfügen, `commit()` – der Lock wird nur für diese Mikrosekunden
   gehalten, es findet kein externer Aufruf statt.
5. Nach dem Commit: Bestätigungsmail als Background-Task (`mail_mode` live/test/off); Mailfehler
   werden geloggt und lassen die Anmeldung nie scheitern.

Nummernkreise: Strecke mit Kreis → fortlaufend innerhalb (geteilte Kreise zählen gemeinsam),
voll → 409. Ohne Kreis → ab `event.bib_start_number`, alle Kreise des Events werden
übersprungen. Ummeldungen ändern die Nummer nie; das Wettkampfbüro kann manuell umhängen.

## Zahlung (SumUp Hosted Checkout)

Pro Organisation API-Key (Fernet-verschlüsselt in `org_setting`) und Merchant-Code. Status wird
**nur** serverseitig per `GET /checkouts/{id}` verifiziert – beim Laden der Verwaltungsseite und
im Webhook (dessen Payload nur als Hinweis dient). „Jetzt online bezahlen" erzeugt einen frischen
Checkout. In Tests/Lasttests ersetzt `BIBBY_PAYMENT_PROVIDER=fake` den Anbieter.

## Zeiterfassung & Ergebnisse

* Keine Runden. Mehrere Geräte erfassen dieselbe Zielüberquerung; `timing_record` hat
  `UNIQUE(event_id, dedup_key)` → der Offline-Upload (`INSERT … ON CONFLICT DO NOTHING`) ist
  idempotent. Zeit-Offset des Geräts wird beim Eingang angewendet.
* „Alle Laufzeiten berechnen": Zielzeit = Mittelwert aller `valid|manual`-Erfassungen,
  Laufzeit = Zielzeit − Streckenstart; anschließend vollständige Neubildung der Staffeln
  (`results/relays.py`: normalisierter Teamname, genau 3 bestätigte Mitglieder).
* Platzierungen über das gesamte Feld; Veröffentlichung filtert nur die Anzeige. Altersklassen
  `five|one|none`, Geschlechterwertung optional (`results/age_classes.py`).
* PDFs (Startnummer A5 quer, Urkunde A4 hoch, Sammel-PDFs) werden mit WeasyPrint in einem
  eigenen, begrenzten Thread-Pool gerendert (`results/pdf.py`, `BIBBY_PDF_WORKERS`), nie im
  Event-Loop.
* Zielfotos: Ordner = `HMAC-SHA256(seed, startnummer)[:40]`; der Seed verlässt den Server nie.

## Schema & Migrationen

Einzige Quelle der Wahrheit: `backend/alembic/versions`. `0001` legt alle Tabellen mit
`CREATE TABLE IF NOT EXISTS` an (kompatibel mit einer `create_all`-Baseline), `0002` die
RLS-Policies. Der Test `test_migrations_match_models` schlägt bei jeder Drift zwischen
Migrationen und ORM-Modellen fehl. Migrationen laufen **nie** beim Container-Start, sondern als
eigener CI-Schritt vor dem Deploy.

## Fehlerbehandlung & Betrieb

* Fachfehler als `HTTPException` mit deutschen `detail`-Meldungen (`core/errors.py`); erwartete
  Ausnahmen (`IntegrityError`, `PaymentProviderError`, `httpx.HTTPError`) werden gezielt gefangen.
* `ErrorCorsMiddleware`: auch 500er tragen CORS-Header.
* `/health`, `/version` (`{"backend": GIT_SHA, "db_schema": alembic revision}`).
* Rate-Limits: Login (IP + Konto + Backoff), öffentliche Anmeldung, Webhook – konfigurierbar,
  429 mit neutraler Meldung.
