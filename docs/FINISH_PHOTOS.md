# Zielfotos

Pro Event werden eine öffentliche S3-Basis-URL und ein geheimer HMAC-Seed hinterlegt (Events-Tab,
„Zufall erzeugen"). Der Ordnername je Startnummer ist `HMAC-SHA256(seed, startnummer)` (hex, 40
Zeichen) – ohne Seed nicht erratbar. Die Verwaltungsseite verlinkt
`{basis-url}/{hash}/index.html`, sobald beides konfiguriert ist.

Das Begleitwerkzeug `backend/tools/finishphotos/cli.py`:

```bash
cd backend && uv sync --extra photos          # pytesseract + boto3; tesseract-ocr muss installiert sein
export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=…
uv run python -m tools.finishphotos.cli --photos ./fotos --seed "$SEED" \
   --bucket bibby-production-finish-photos --prefix stadtlauf-2026 \
   --endpoint https://s3.fr-par.scw.cloud --bib-min 1 --bib-max 1500 --year 2026 \
   --review ./review --dry-run
```

* Zwei OCR-Pässe: Ganzbild und einzeln erkannte helle Nummernkarten; Plausibilitätsfilter
  (Nummernbereich, Jahreszahlen, relative Kartengröße).
* Verkleinerung auf ~1600 px lange Kante, EXIF wird entfernt.
* Upload nach `{prefix}/{hash}/` mit `public-read` je Objekt; der Bucket hat **kein** öffentliches
  Listing. Je Ordner entsteht eine `index.html`-Galerie (noindex).
* Idempotent (unveränderte Objekte werden übersprungen), `--dry-run`, Review-Ordner mit
  `unassigned/`, `ambiguous/` und `plan.json`.
