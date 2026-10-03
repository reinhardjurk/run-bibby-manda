# Rotations-Runbook

Alle Secrets liegen ausschließlich in GitHub-Environment-Secrets bzw. OpenTofu-Variablen
(`TF_VAR_*`) und werden als Container-Umgebungsvariablen injiziert. Nichts davon steht im
Repository, im Frontend oder in Logs. Nach jeder Rotation: Deploy-Workflow ausführen, dann
`/health` und `/version` prüfen.

| Secret | Variable | Rotationsschritte | Folgen |
| --- | --- | --- | --- |
| **App-Secret** (HMAC für Session-, Verwaltungs-, Geräte-Tokens) | `BIBBY_APP_SECRET` | 1. Neuen Wert erzeugen (`openssl rand -base64 48`). 2. GitHub-Secret `BIBBY_APP_SECRET` ersetzen. 3. Deploy. | **Alle Sessions, Verwaltungslinks und Geräte-Tokens werden ungültig** (Hashes passen nicht mehr). Teilnehmende brauchen neue Links (Bestätigungsmail erneut auslösen bzw. Wettkampfbüro informieren); Geräte-Tokens im Special-Admin „Neu ausstellen". Nur im Notfall (Leak) rotieren, idealerweise außerhalb der Anmeldephase. |
| **Feldverschlüsselung** (Fernet, IBAN + SumUp-API-Keys) | `BIBBY_FIELD_ENCRYPTION_KEY` | 1. Neuen Key erzeugen: `python -m app.cli generate-fernet-key`. 2. Secret ersetzen, Deploy. 3. **Umschlüsseln** im Container/CI mit dem neuen Key in der Umgebung: `python -m app.cli reencrypt-ibans <ALTER_KEY>`. 4. Alten Key vernichten. | Bis Schritt 3 sind alte IBANs nicht entschlüsselbar: SEPA-Exporte zeigen `IBAN-NICHT-ENTSCHLUESSELBAR` statt zu brechen, Online-Zahlung meldet „nicht verfügbar". Das Kommando ist idempotent und meldet nicht umschlüsselbare Datensätze (Exit-Code ≠ 0). |
| **Datenbank-Zugang** | `BIBBY_DATABASE_URL`, `BIBBY_DATABASE_URL_MIGRATIONS` | 1. In Scaleway neue DB-Rolle/Passwort anlegen (App-Rolle ohne `BYPASSRLS`, Migrationsrolle = Eigentümer). 2. Secrets ersetzen. 3. Deploy (Migrationsschritt prüft die Verbindung). 4. Alte Rolle entfernen. | Kurzer Verbindungsabbruch beim Neustart der Container; keine fachlichen Folgen. |
| **Mail-API-Key** (Transactional Email) | `BIBBY_MAIL_API_KEY` | 1. Neuen API-Key in Scaleway IAM erzeugen (nur TEM-Rechte). 2. Secret ersetzen, Deploy. 3. Testmail: Mailmodus einer Testorganisation auf `test` und eine Anmeldung ausführen. 4. Alten Key löschen. | Fehlende/ungültige Keys führen nur zu geloggten Mailfehlern – Anmeldungen laufen weiter. Betroffene Teilnehmende erhalten den Link über das Wettkampfbüro. |
| **Zahlungsanbieter** (SumUp API-Key + Merchant-Code, pro Organisation) | `org_setting.sumup_api_key` (verschlüsselt) | Org-Admin: Special-Admin → Einstellungen → neuen Key eintragen (Feld ist write-only; „gesetzt" wird angezeigt). Alten Key im SumUp-Dashboard widerrufen. | Offene Checkouts des alten Keys werden nicht mehr verifiziert; betroffene Zahlungen manuell prüfen („Als bezahlt markieren" mit Transaktionscode aus der SumUp-Auszahlung). |
| **Scaleway-Zugang für CI** (`SCW_ACCESS_KEY`/`SCW_SECRET_KEY`) | GitHub-Secrets | Neuen IAM-API-Key mit minimalen Rechten (Registry push, Container, SDB, Object Storage, TEM) erzeugen, Secrets ersetzen, Deploy-Workflow testen, alten Key löschen. | Keine Laufzeitfolgen für die Anwendung. |
| **Super-Admin-Passwort** | – (DB) | `python -m app.cli create-platform-admin <email> <neues-passwort>` (setzt das Passwort eines bestehenden Kontos) oder über ein zweites Super-Admin-Konto. | Bestehende Plattform-Sessions bleiben bis zum Ablauf (72 h) gültig; bei Verdacht zusätzlich das App-Secret rotieren. |
| **Zielfoto-Seed** (pro Event) | `event.photo_hmac_seed` | Im Events-Tab neuen Zufalls-Seed erzeugen, Zielfoto-CLI erneut mit neuem Seed laufen lassen, alte Ordner im Bucket löschen. | Alte Galerie-Links werden ungültig; die Verwaltungsseite verlinkt automatisch die neuen Ordner. |

## Verdacht auf Leak im Git-Verlauf

1. Pipeline bricht durch gitleaks bereits beim Push ab – Secret sofort rotieren (oben), nicht
   erst entfernen.
2. Verlauf bereinigen (z. B. `git filter-repo`), Force-Push mit allen Beteiligten abstimmen.
3. Alle Klone neu aufsetzen; `gitleaks detect --source . --log-opts=--all` lokal ausführen.
