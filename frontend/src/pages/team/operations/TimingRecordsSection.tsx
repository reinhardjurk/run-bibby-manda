import { useState } from 'react';
import { errorMessage } from '../../../api/client';
import { timingTeamApi } from '../../../api/team';
import type { RecordOut } from '../../../api/types';
import { ErrorBox } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { Modal } from '../../../components/Modal';
import { useAsync } from '../../../hooks/useAsync';
import { useToast } from '../../../hooks/useToast';
import { formatClock, formatDateTime, fromLocalInput, toLocalInput } from '../../../utils/format';

const STATUSES = ['valid', 'ignored', 'duplicate', 'manual'] as const;

function RecordEditModal({
  slug,
  record,
  onClose,
  onSaved,
}: {
  slug: string;
  record: RecordOut;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [bib, setBib] = useState(String(record.bib_number));
  const [time, setTime] = useState(toLocalInput(record.absolute_time));
  const [status, setStatus] = useState(record.status);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const body: { bib_number?: number; absolute_time?: string; status?: string } = {};
      if (Number(bib) !== record.bib_number) body.bib_number = Number(bib);
      const iso = fromLocalInput(time);
      if (iso && Math.abs(new Date(iso).getTime() - new Date(record.absolute_time).getTime()) >= 1000) body.absolute_time = iso;
      if (status !== record.status) body.status = status;
      await timingTeamApi.updateRecord(slug, record.id, body);
      toast.success('Erfassung gespeichert.');
      onSaved();
      onClose();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={`Erfassung bearbeiten · #${record.bib_number}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            Abbrechen
          </button>
          <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
            Speichern
          </button>
        </>
      }
    >
      <div className="stack">
        <Field label="Startnummer">{(id) => <input id={id} inputMode="numeric" value={bib} onChange={(e) => setBib(e.target.value)} />}</Field>
        <Field label="Zeitstempel (lokal)" hint={`Original: ${formatClock(record.absolute_time, true)}`}>
          {(id) => <input id={id} type="datetime-local" step="1" value={time} onChange={(e) => setTime(e.target.value)} />}
        </Field>
        <Field label="Status">
          {(id) => (
            <select id={id} value={status} onChange={(e) => setStatus(e.target.value)}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
    </Modal>
  );
}

/** Timing records of an event (filter by bib), with edit/delete/manual add. */
export function TimingRecordsSection({ slug, eventId }: { slug: string; eventId: string }) {
  const toast = useToast();
  const [bibFilter, setBibFilter] = useState('');
  const [applied, setApplied] = useState<number | null>(null);
  const records = useAsync(() => timingTeamApi.records(slug, eventId, applied, 200), [slug, eventId, applied]);
  const [editing, setEditing] = useState<RecordOut | null>(null);
  const [manualBib, setManualBib] = useState('');
  const [manualTime, setManualTime] = useState(() => toLocalInput(new Date().toISOString()));
  const [busy, setBusy] = useState(false);

  const remove = async (r: RecordOut) => {
    if (!window.confirm(`Erfassung #${r.bib_number} (${formatClock(r.absolute_time)}) löschen?`)) return;
    try {
      await timingTeamApi.removeRecord(slug, r.id);
      toast.success('Gelöscht.');
      records.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const addManual = async () => {
    const n = Number(manualBib);
    const iso = fromLocalInput(manualTime);
    if (!Number.isInteger(n) || n < 0 || !iso) {
      toast.error('Startnummer und Zeit prüfen.');
      return;
    }
    setBusy(true);
    try {
      await timingTeamApi.addManual(slug, eventId, n, iso);
      toast.success('Manuelle Erfassung angelegt.');
      setManualBib('');
      records.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <div className="inline-form">
        <Field label="Startnummer filtern" className="field--narrow">
          {(id) => (
            <input
              id={id}
              inputMode="numeric"
              value={bibFilter}
              onChange={(e) => setBibFilter(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && setApplied(bibFilter ? Number(bibFilter) : null)}
            />
          )}
        </Field>
        <button type="button" className="btn" onClick={() => setApplied(bibFilter ? Number(bibFilter) : null)}>
          Anzeigen
        </button>
        {applied !== null && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setBibFilter('');
              setApplied(null);
            }}
          >
            Filter löschen
          </button>
        )}
      </div>
      <div className="inline-form card card--flat">
        <Field label="Manuell: Startnummer" className="field--narrow">
          {(id) => <input id={id} inputMode="numeric" value={manualBib} onChange={(e) => setManualBib(e.target.value)} />}
        </Field>
        <Field label="Manuell: Zeitpunkt">
          {(id) => <input id={id} type="datetime-local" step="1" value={manualTime} onChange={(e) => setManualTime(e.target.value)} />}
        </Field>
        <button type="button" className="btn btn--primary" onClick={addManual} disabled={busy}>
          Manuell hinzufügen
        </button>
      </div>
      {records.loading && !records.data && <Loading />}
      <ErrorBox message={records.error} onRetry={records.reload} />
      {records.data && (
        <div className="table-wrap">
          <table className="table--compact">
            <thead>
              <tr>
                <th className="num">StNr.</th>
                <th>Zeit</th>
                <th>Quelle</th>
                <th>Status</th>
                <th>Angelegt</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {records.data.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted center">
                    Keine Erfassungen{applied !== null ? ` für #${applied}` : ''}.
                  </td>
                </tr>
              )}
              {records.data.map((r) => (
                <tr key={r.id}>
                  <td className="num">
                    <strong>{r.bib_number}</strong>
                  </td>
                  <td className="mono nowrap">{formatClock(r.absolute_time, true)}</td>
                  <td>{r.source_label ?? '–'}</td>
                  <td>
                    <span className={`badge ${r.status === 'valid' || r.status === 'manual' ? 'badge--ok' : 'badge--warn'}`}>{r.status}</span>
                  </td>
                  <td className="small muted nowrap">{formatDateTime(r.created_at)}</td>
                  <td className="nowrap">
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => setEditing(r)}>
                      Bearbeiten
                    </button>
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => void remove(r)}>
                      Löschen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing && <RecordEditModal slug={slug} record={editing} onClose={() => setEditing(null)} onSaved={records.reload} />}
    </div>
  );
}
