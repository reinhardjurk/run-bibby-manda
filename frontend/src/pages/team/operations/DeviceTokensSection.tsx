import { useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { errorMessage } from '../../../api/client';
import { timingTeamApi } from '../../../api/team';
import type { DeviceTokenIssued, DeviceTokenOut } from '../../../api/types';
import { ErrorBox, Notice } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { Modal } from '../../../components/Modal';
import { useAsync } from '../../../hooks/useAsync';
import { useToast } from '../../../hooks/useToast';
import { formatDateTime } from '../../../utils/format';

function IssuedTokenModal({ issued, onClose }: { issued: DeviceTokenIssued; onClose: () => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const toast = useToast();
  useEffect(() => {
    if (canvas.current) {
      QRCode.toCanvas(canvas.current, issued.kiosk_url, { width: 260, margin: 1 }).catch(() => undefined);
    }
  }, [issued.kiosk_url]);
  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Kopiert.');
    } catch {
      toast.error('Kopieren nicht möglich – bitte manuell markieren.');
    }
  };
  return (
    <Modal title={`Geräte-Token · ${issued.label}`} onClose={onClose}>
      <div className="stack">
        <Notice kind="warn">
          Dieser Token wird nur <strong>einmal</strong> angezeigt und kann später nicht erneut abgerufen werden. Bei
          Verlust „Neu ausstellen“ verwenden (der alte Token wird dadurch ungültig).
        </Notice>
        <div className="qr-box">
          <canvas ref={canvas} aria-label="QR-Code mit Kiosk-Link" />
          <div className="small muted">QR-Code mit dem Erfassungsgerät scannen</div>
        </div>
        <Field label="Kiosk-Link">
          {(id) => (
            <div className="row">
              <input id={id} readOnly value={issued.kiosk_url} className="mono" onFocus={(e) => e.target.select()} />
              <button type="button" className="btn" onClick={() => void copy(issued.kiosk_url)}>
                Kopieren
              </button>
            </div>
          )}
        </Field>
        <Field label="Token">
          {(id) => (
            <div className="row">
              <input id={id} readOnly value={issued.token} className="mono" onFocus={(e) => e.target.select()} />
              <button type="button" className="btn" onClick={() => void copy(issued.token)}>
                Kopieren
              </button>
            </div>
          )}
        </Field>
      </div>
    </Modal>
  );
}

/** Device tokens for kiosk timing: create, reissue, toggle, offset, delete. */
export function DeviceTokensSection({ slug }: { slug: string }) {
  const toast = useToast();
  const devices = useAsync(() => timingTeamApi.devices(slug), [slug]);
  const [label, setLabel] = useState('');
  const [offset, setOffset] = useState('0');
  const [busy, setBusy] = useState(false);
  const [issued, setIssued] = useState<DeviceTokenIssued | null>(null);
  const [edit, setEdit] = useState<Record<string, { label: string; offset: string }>>({});

  const create = async () => {
    if (!label.trim()) return;
    setBusy(true);
    try {
      const res = await timingTeamApi.createDevice(slug, label.trim(), Number(offset) || 0);
      setIssued(res);
      setLabel('');
      setOffset('0');
      devices.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const reissue = async (d: DeviceTokenOut) => {
    if (!window.confirm(`Token für „${d.label}“ neu ausstellen? Der bisherige Token wird sofort ungültig.`)) return;
    try {
      setIssued(await timingTeamApi.reissueDevice(slug, d.id));
      devices.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const patch = async (d: DeviceTokenOut, body: { is_active?: boolean; time_offset_seconds?: number; label?: string }) => {
    try {
      await timingTeamApi.updateDevice(slug, d.id, body);
      toast.success('Gespeichert.');
      devices.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const remove = async (d: DeviceTokenOut) => {
    if (!window.confirm(`Geräte-Token „${d.label}“ löschen?`)) return;
    try {
      await timingTeamApi.removeDevice(slug, d.id);
      toast.success('Gelöscht.');
      devices.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="stack">
      <div className="inline-form card card--flat">
        <Field label="Bezeichnung (z. B. „Ziel Handy 1“)">
          {(id) => <input id={id} value={label} maxLength={100} onChange={(e) => setLabel(e.target.value)} />}
        </Field>
        <Field label="Zeitversatz (s)" className="field--narrow">
          {(id) => <input id={id} inputMode="numeric" value={offset} onChange={(e) => setOffset(e.target.value)} />}
        </Field>
        <button type="button" className="btn btn--primary" onClick={create} disabled={busy || !label.trim()}>
          Token erstellen
        </button>
      </div>
      {devices.loading && !devices.data && <Loading />}
      <ErrorBox message={devices.error} onRetry={devices.reload} />
      {devices.data && (
        <div className="table-wrap">
          <table className="table--compact">
            <thead>
              <tr>
                <th>Bezeichnung</th>
                <th className="num">Versatz (s)</th>
                <th>Aktiv</th>
                <th>Zuletzt genutzt</th>
                <th>Angelegt</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {devices.data.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted center">
                    Noch keine Geräte-Token.
                  </td>
                </tr>
              )}
              {devices.data.map((d) => {
                const e = edit[d.id] ?? { label: d.label, offset: String(d.time_offset_seconds) };
                const dirty = e.label !== d.label || Number(e.offset) !== d.time_offset_seconds;
                return (
                  <tr key={d.id}>
                    <td>
                      <input
                        aria-label="Bezeichnung"
                        value={e.label}
                        onChange={(ev) => setEdit((m) => ({ ...m, [d.id]: { ...e, label: ev.target.value } }))}
                        style={{ minWidth: 140 }}
                      />
                    </td>
                    <td className="num">
                      <input
                        aria-label="Zeitversatz"
                        inputMode="numeric"
                        value={e.offset}
                        onChange={(ev) => setEdit((m) => ({ ...m, [d.id]: { ...e, offset: ev.target.value } }))}
                        style={{ width: 80 }}
                      />
                    </td>
                    <td>
                      <label className="checkbox">
                        <input type="checkbox" checked={d.is_active} onChange={(ev) => void patch(d, { is_active: ev.target.checked })} />
                        <span>{d.is_active ? 'aktiv' : 'gesperrt'}</span>
                      </label>
                    </td>
                    <td className="small nowrap">{d.last_used_at ? formatDateTime(d.last_used_at) : '–'}</td>
                    <td className="small nowrap">{formatDateTime(d.created_at)}</td>
                    <td className="nowrap">
                      {dirty && (
                        <button
                          type="button"
                          className="btn btn--small btn--primary"
                          onClick={() => void patch(d, { label: e.label, time_offset_seconds: Number(e.offset) || 0 })}
                        >
                          Speichern
                        </button>
                      )}
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => void reissue(d)}>
                        Neu ausstellen
                      </button>
                      <button type="button" className="btn btn--small btn--ghost" onClick={() => void remove(d)}>
                        Löschen
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {issued && <IssuedTokenModal issued={issued} onClose={() => setIssued(null)} />}
    </div>
  );
}
