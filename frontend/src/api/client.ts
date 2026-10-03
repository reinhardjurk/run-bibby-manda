/**
 * Thin fetch wrapper for the Bibby backend.
 *
 * - Same-origin relative URLs (`/api/...`), cookies always included.
 * - Mutating requests carry the CSRF double-submit header read from the `bibby_csrf` cookie.
 * - Kiosk/device mode sends `X-Device-Token` instead of relying on cookies.
 * - Backend errors (`{detail: string}` or pydantic `{detail: [...]}`) become `ApiError`.
 */

export const CSRF_COOKIE = 'bibby_csrf';
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly payload: unknown;

  constructor(status: number, detail: string, payload?: unknown) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.payload = payload;
  }
}

export function readCookie(name: string): string | null {
  const parts = document.cookie ? document.cookie.split(';') : [];
  for (const part of parts) {
    const [k, ...rest] = part.trim().split('=');
    if (k === name) return decodeURIComponent(rest.join('='));
  }
  return null;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  /** JSON body (serialised) – ignored when `form` is given. */
  body?: unknown;
  /** Multipart form body. */
  form?: FormData;
  /** Query parameters; `undefined`/`null`/'' are skipped. */
  query?: Record<string, string | number | boolean | null | undefined>;
  /** Device token for kiosk mode (sent as `X-Device-Token`). */
  deviceToken?: string | null;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export function buildQuery(query?: RequestOptions['query']): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === '') continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : '';
}

interface ValidationItem {
  loc?: Array<string | number>;
  msg?: string;
}

/** Extracts a human-readable message from a backend error payload. */
export function extractDetail(payload: unknown, fallback: string): string {
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const d = (payload as { detail: unknown }).detail;
    if (typeof d === 'string' && d) return d;
    if (Array.isArray(d)) {
      const msgs = (d as ValidationItem[]).map((it) => {
        const field = (it.loc ?? []).filter((p) => p !== 'body' && p !== 'query').join('.');
        return field ? `${field}: ${it.msg ?? ''}` : (it.msg ?? '');
      });
      const joined = msgs.filter(Boolean).join(' · ');
      if (joined) return joined;
    }
  }
  return fallback;
}

function statusFallback(status: number): string {
  switch (status) {
    case 0:
      return 'Keine Verbindung zum Server.';
    case 401:
      return 'Bitte anmelden.';
    case 403:
      return 'Keine Berechtigung.';
    case 404:
      return 'Nicht gefunden.';
    case 409:
      return 'Konflikt – die Daten wurden zwischenzeitlich geändert.';
    case 422:
      return 'Ungültige Eingabe.';
    case 423:
      return 'Diese Organisation ist derzeit nicht verfügbar.';
    case 429:
      return 'Zu viele Anfragen. Bitte später erneut versuchen.';
    case 503:
      return 'Dienst vorübergehend nicht verfügbar.';
    default:
      return status >= 500 ? 'Interner Fehler.' : `Fehler (${status}).`;
  }
}

async function doFetch(path: string, opts: RequestOptions): Promise<Response> {
  const method = opts.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json, */*', ...opts.headers };
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  if (opts.deviceToken) {
    headers['X-Device-Token'] = opts.deviceToken;
  } else if (MUTATING.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers['X-CSRF-Token'] = csrf;
  }
  let res: Response;
  try {
    res = await fetch(path + buildQuery(opts.query), {
      method,
      headers,
      body,
      credentials: 'include',
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError(0, statusFallback(0));
  }
  if (!res.ok) {
    let payload: unknown = null;
    const text = await res.text();
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = null;
    }
    throw new ApiError(res.status, extractDetail(payload, statusFallback(res.status)), payload);
  }
  return res;
}

/** JSON request. Returns `undefined` (typed as T) for 204 responses. */
export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await doFetch(path, opts);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export interface BlobResult {
  blob: Blob;
  filename: string | null;
  headers: Headers;
}

/** Binary request (PDF/CSV). Cookies are sent automatically. */
export async function apiBlob(path: string, opts: RequestOptions = {}): Promise<BlobResult> {
  const res = await doFetch(path, opts);
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  return { blob, filename: m?.[1] ? decodeURIComponent(m[1]) : null, headers: res.headers };
}

/** Triggers a browser download of a blob (object URL is revoked afterwards). */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Opens a blob in a new tab (fallback: download). */
export function openBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const win = window.open(url, '_blank', 'noopener');
  if (!win) downloadBlob(blob, filename);
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function errorMessage(err: unknown, fallback = 'Unbekannter Fehler.'): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message || fallback;
  return fallback;
}
