# Bibby – Frontend

React 18 + Vite 5 + TypeScript (strict), react-router-dom v6, plain CSS. No UI framework, no state library.
The only extra runtime dependency is `qrcode` (QR codes for device tokens).

## Development

```bash
cd frontend
npm install          # exact versions are pinned; package-lock.json is committed
npm run dev          # http://localhost:5173
```

The dev server proxies `/api`, `/health` and `/version` to the backend at `http://localhost:8000`
(see `vite.config.ts`). Sessions are httpOnly cookies set by the backend; nothing is stored in
localStorage except per-viewer conveniences (language, selected event, timing queue).

## Scripts

| Script              | Purpose                                             |
| ------------------- | --------------------------------------------------- |
| `npm run dev`       | Vite dev server with API proxy                      |
| `npm run build`     | `tsc --noEmit && vite build` → `dist/`              |
| `npm run typecheck` | TypeScript only                                     |
| `npm run lint`      | ESLint (flat config, typescript-eslint, react-hooks) |
| `npm run preview`   | Serve the production build locally                  |

## Environment

| Variable     | Default | Description                                                       |
| ------------ | ------- | ----------------------------------------------------------------- |
| `VITE_BUILD` | `dev`   | Build id shown in the team footer (`Frontend <id> · Backend <sha> · DB <schema>`). Set it in CI, e.g. to the git SHA. |

The build is served same-origin by the backend (`base: '/'`, relative `/api/...` URLs), so no API
base URL needs to be configured.

## Structure

```
src/
  api/          fetch wrapper (CSRF header, device token, error handling) + typed endpoint modules
  components/   shared UI (forms, modal, sponsor bars, event selector, …)
  hooks/        useAsync, useToast, useLocalStorage, useOnline, useTimingQueue
  i18n/         de.ts (lead), en.ts, provider with useT()/useLang()
  pages/
    public/     landing, registration, manage, results, timing kiosk
    team/       login, layout + tabs, reception, certificates, race operations, sponsors, events, stats, SEPA
    platform/   super-admin console
  styles/       global.css (CSS variables, mobile-first)
  utils/        formatting helpers, role checks
```

## Routes

- `/` neutral landing · `/platform` super-admin
- `/:slug/teilnahme` registration · `/:slug/manage?token=` self-service · `/:slug/ergebnisse` results
- `/:slug/timing?device=TOKEN` kiosk timing (device token kept in sessionStorage only)
- `/:slug/team/login`, `/:slug/team/<tab>` with tabs `admin`, `ergebnisdruck`, `zeiterfassung`,
  `special-admin`, `sponsoren`, `events`, `statistiken`, `sepa` (role-gated)

## Conventions

- Mutating requests send `X-CSRF-Token` from the `bibby_csrf` cookie; kiosk mode sends `X-Device-Token`.
- Backend error payloads (`{detail: string}` or pydantic 422 lists) are surfaced in toasts/notices.
- Timing captures are queued in localStorage and synced in idempotent batches (safe to resend).
