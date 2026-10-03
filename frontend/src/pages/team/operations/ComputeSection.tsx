import { useState } from 'react';
import { errorMessage } from '../../../api/client';
import { timingTeamApi } from '../../../api/team';
import type { ComputeResult, PlausibilityResult } from '../../../api/types';
import { ErrorBox, Notice } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { useToast } from '../../../hooks/useToast';
import { formatClock } from '../../../utils/format';

/** "Alle Laufzeiten berechnen" + plausibility check. */
export function ComputeSection({
  slug,
  eventId,
  defaultThreshold,
}: {
  slug: string;
  eventId: string;
  defaultThreshold: string;
}) {
  const toast = useToast();
  const [result, setResult] = useState<ComputeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [threshold, setThreshold] = useState(defaultThreshold || '3');
  const [plaus, setPlaus] = useState<PlausibilityResult | null>(null);
  const [plausLoading, setPlausLoading] = useState(false);
  const [plausError, setPlausError] = useState<string | null>(null);

  const compute = async () => {
    if (!window.confirm('Alle Laufzeiten dieser Veranstaltung neu berechnen? Bestehende Zeiten werden überschrieben.')) return;
    setBusy(true);
    try {
      const r = await timingTeamApi.compute(slug, eventId);
      setResult(r);
      toast.success(`${r.computed} Zeiten berechnet.`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const check = async () => {
    setPlausLoading(true);
    setPlausError(null);
    try {
      const n = threshold.trim() === '' ? null : Number(threshold.replace(',', '.'));
      setPlaus(await timingTeamApi.plausibility(slug, eventId, n));
    } catch (err) {
      setPlausError(errorMessage(err));
    } finally {
      setPlausLoading(false);
    }
  };

  return (
    <div className="stack">
      <div className="row">
        <button type="button" className="btn btn--primary" onClick={compute} disabled={busy}>
          {busy ? 'Berechnet …' : 'Alle Laufzeiten berechnen'}
        </button>
        <span className="small muted">
          Berechnet Zielzeiten aus Erfassungen und Startzeiten, bildet Staffeln und friert die Anmeldungen ein.
        </span>
      </div>
      {result && (
        <div className="grid grid--3">
          <div className="stat">
            <div className="stat__label">Berechnet</div>
            <div className="stat__value">{result.computed}</div>
          </div>
          <div className="stat">
            <div className="stat__label">Ohne Startzeit</div>
            <div className="stat__value">{result.without_start_time}</div>
          </div>
          <div className="stat">
            <div className="stat__label">Staffeln gebildet</div>
            <div className="stat__value">{result.relays_formed}</div>
          </div>
        </div>
      )}
      <h3>Plausibilitätsprüfung</h3>
      <div className="inline-form">
        <Field label="Schwelle (Sekunden)" className="field--narrow" hint="Startnummern mit mehreren Erfassungen, deren Abstand die Schwelle überschreitet.">
          {(id) => <input id={id} inputMode="decimal" value={threshold} onChange={(e) => setThreshold(e.target.value)} />}
        </Field>
        <button type="button" className="btn" onClick={check} disabled={plausLoading}>
          Prüfen
        </button>
      </div>
      {plausLoading && <Loading />}
      <ErrorBox message={plausError} />
      {plaus && (
        <>
          {plaus.entries.length === 0 ? (
            <Notice kind="success">Keine Auffälligkeiten (Schwelle {plaus.threshold_seconds} s).</Notice>
          ) : (
            <div className="table-wrap">
              <table className="table--compact">
                <thead>
                  <tr>
                    <th className="num">StNr.</th>
                    <th className="num">Spanne (s)</th>
                    <th>Zeitstempel</th>
                  </tr>
                </thead>
                <tbody>
                  {plaus.entries.map((e) => (
                    <tr key={e.bib_number}>
                      <td className="num">
                        <strong>{e.bib_number}</strong>
                      </td>
                      <td className="num">{e.spread_seconds.toFixed(1)}</td>
                      <td className="mono small">{e.timestamps.map((ts) => formatClock(ts, true)).join(' · ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
