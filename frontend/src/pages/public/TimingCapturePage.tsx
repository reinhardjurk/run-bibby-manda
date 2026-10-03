import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { timingApi } from '../../api/timing';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { LanguageSwitch } from '../../components/LanguageSwitch';
import { Loading } from '../../components/Loading';
import { useAsync } from '../../hooks/useAsync';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useLocalStorage } from '../../hooks/useLocalStorage';
import { useOnline } from '../../hooks/useOnline';
import { useTimingQueue } from '../../hooks/useTimingQueue';
import { useT } from '../../i18n';
import { formatClock } from '../../utils/format';

interface Props {
  /** kiosk = device token from URL/sessionStorage, no login; team = cookie session inside the team layout. */
  mode: 'kiosk' | 'team';
}

function deviceStorageKey(slug: string) {
  return `bibby_device_token_${slug}`;
}

/** Reads the device token from `?device=` (then strips it from the URL) or from sessionStorage. */
function useDeviceToken(slug: string, enabled: boolean): string | null {
  const [params, setParams] = useSearchParams();
  const fromUrl = params.get('device');
  const [token, setToken] = useState<string | null>(() => {
    if (!enabled) return null;
    if (fromUrl) return fromUrl;
    try {
      return sessionStorage.getItem(deviceStorageKey(slug));
    } catch {
      return null;
    }
  });
  useEffect(() => {
    if (!enabled || !fromUrl) return;
    try {
      sessionStorage.setItem(deviceStorageKey(slug), fromUrl);
    } catch {
      /* ignore */
    }
    setToken(fromUrl);
    const next = new URLSearchParams(params);
    next.delete('device');
    setParams(next, { replace: true });
  }, [enabled, fromUrl, params, setParams, slug]);
  return token;
}

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];

export function TimingCapturePage({ mode }: Props) {
  const { slug = '' } = useParams();
  const t = useT();
  const online = useOnline();
  const deviceToken = useDeviceToken(slug, mode === 'kiosk');
  const ctx = useAsync(() => timingApi.context(slug, deviceToken), [slug, deviceToken], mode === 'team' || !!deviceToken);
  const [eventId, setEventId] = useLocalStorage<string>(`bibby_timing_event_${slug}`, '');
  const [input, setInput] = useState('');
  const [flash, setFlash] = useState<string | null>(null);
  useDocumentTitle(t('timing.title'));

  const label = ctx.data?.device ? ctx.data.actor : 'web';
  const queue = useTimingQueue({ slug, deviceToken, label, online });

  const events = useMemo(() => ctx.data?.events ?? [], [ctx.data]);
  useEffect(() => {
    if (events.length > 0 && !events.some((e) => e.id === eventId)) setEventId(events[0]?.id ?? '');
  }, [events, eventId, setEventId]);

  // Physical keyboard support (USB numpad / barcode scanners).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return;
      if (/^\d$/.test(e.key)) setInput((v) => (v.length < 6 ? v + e.key : v));
      else if (e.key === 'Backspace') setInput((v) => v.slice(0, -1));
      else if (e.key === 'Enter') doCapture();
      else if (e.key === 'Escape') setInput('');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const doCapture = () => {
    if (!eventId) return;
    if (!input) {
      setFlash(t('timing.emptyBib'));
      return;
    }
    const bib = Number(input);
    queue.capture(eventId, bib);
    setInput('');
    setFlash(t('timing.captured', { bib }));
    if (navigator.vibrate) navigator.vibrate(30);
    window.setTimeout(() => setFlash(null), 1500);
  };

  if (mode === 'kiosk' && !deviceToken) {
    return (
      <div className="timing">
        <h1>{t('timing.title')}</h1>
        <Notice kind="warn">{t('timing.noDevice')}</Notice>
        <Link to="/">Bibby</Link>
      </div>
    );
  }

  const ctxError =
    ctx.error && mode === 'kiosk' && deviceToken && (ctx.error.includes('Token') || ctx.error.includes('anmelden'))
      ? t('timing.invalidToken')
      : ctx.error;

  return (
    <div className="timing">
      {mode === 'kiosk' && (
        <div className="row row--between">
          <div>
            <h1 style={{ margin: 0 }}>{t('timing.title')}</h1>
            {ctx.data && <div className="small muted">{ctx.data.organization.name}</div>}
          </div>
          <LanguageSwitch />
        </div>
      )}
      {ctx.loading && !ctx.data && <Loading />}
      <ErrorBox message={ctxError} onRetry={ctx.reload} />
      {!ctx.data && !ctx.loading && queue.pendingCount > 0 && (
        <Notice kind="warn">{t('timing.offlineHint')}</Notice>
      )}

      <div className="field">
        <label className="field__label" htmlFor="timing-event">
          {t('timing.event')}
        </label>
        <select id="timing-event" value={eventId} onChange={(e) => setEventId(e.target.value)} disabled={events.length === 0}>
          {events.length === 0 && <option value={eventId}>{eventId ? 'Gespeicherte Veranstaltung (offline)' : '–'}</option>}
          {events.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name} {e.year}
            </option>
          ))}
        </select>
      </div>

      <div className="timing__status">
        <span>
          <span className={`dot ${online ? 'dot--online' : 'dot--offline'}`} aria-hidden="true" />
          {online ? t('common.online') : t('common.offline')}
        </span>
        <span>
          <strong>{queue.pendingCount}</strong> {t('timing.pending')}
        </span>
        <button
          type="button"
          className="btn btn--small"
          onClick={() => void queue.sync()}
          disabled={queue.syncing || queue.pendingCount === 0 || !online}
        >
          {queue.syncing ? t('timing.syncing') : t('timing.syncNow')}
        </button>
      </div>
      {!online && <Notice kind="warn">{t('timing.offlineHint')}</Notice>}
      {queue.lastError && <ErrorBox message={queue.lastError} />}
      {ctx.data && (
        <div className="small muted">
          {t('timing.actor')}: {ctx.data.actor}
          {ctx.data.device && ctx.data.offset_seconds !== 0 && (
            <> · {t('timing.offsetHint', { offset: ctx.data.offset_seconds })}</>
          )}
        </div>
      )}

      <div className="timing__display" aria-live="polite" aria-label={t('timing.bib')}>
        {input}
      </div>
      {flash && <div className="notice notice--success">{flash}</div>}

      <div className="keypad" role="group" aria-label={t('timing.bib')}>
        {KEYS.map((k) => (
          <button type="button" key={k} onClick={() => setInput((v) => (v.length < 6 ? v + k : v))}>
            {k}
          </button>
        ))}
        <button type="button" className="keypad__back" onClick={() => setInput((v) => v.slice(0, -1))} aria-label="Backspace">
          ⌫
        </button>
        <button type="button" onClick={() => setInput((v) => (v.length < 6 ? v + '0' : v))}>
          0
        </button>
        <button type="button" className="keypad__back" onClick={() => setInput('')} aria-label="Clear">
          C
        </button>
        <button type="button" className="keypad__capture" onClick={doCapture} disabled={!eventId}>
          {t('timing.capture')}
        </button>
      </div>

      <section>
        <h2>{t('timing.lastCaptures')}</h2>
        {queue.recent.length === 0 ? (
          <p className="muted small">{t('common.none')}</p>
        ) : (
          <ul className="capture-list">
            {queue.recent.map((r) => (
              <li key={r.dedup_key}>
                <span>
                  <strong>{r.bib_number}</strong>
                </span>
                <span>{formatClock(r.absolute_time, true)}</span>
                <span className={`badge ${r.status === 'synced' ? 'badge--ok' : 'badge--warn'}`}>
                  {r.status === 'synced' ? t('timing.synced') : t('timing.queued')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      {!!queue.lastSyncAt && <div className="small muted">Sync: {formatClock(queue.lastSyncAt)}</div>}
    </div>
  );
}
