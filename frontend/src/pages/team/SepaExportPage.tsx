import { useState } from 'react';
import { downloadBlob, errorMessage } from '../../api/client';
import { sepaApi } from '../../api/team';
import { EventSelector, PageHead } from '../../components/EventSelector';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Checkbox } from '../../components/Field';
import { Loading } from '../../components/Loading';
import { useAsync } from '../../hooks/useAsync';
import { useToast } from '../../hooks/useToast';
import { useT } from '../../i18n';
import { euro } from '../../utils/format';
import { useTeam } from './TeamContext';

/** Tab "SEPA": summary of direct-debit payments and CSV export. */
export function SepaExportPage() {
  const { slug, selectedEventId, selectedEvent } = useTeam();
  const t = useT();
  const toast = useToast();
  const summary = useAsync(() => sepaApi.summary(slug, selectedEventId), [slug, selectedEventId], !!selectedEventId);
  const [includeExported, setIncludeExported] = useState(false);
  const [busy, setBusy] = useState(false);

  const exportCsv = async () => {
    setBusy(true);
    try {
      const res = await sepaApi.exportCsv(slug, selectedEventId, includeExported);
      const rows = res.headers.get('X-Row-Count');
      downloadBlob(res.blob, res.filename ?? `sepa_${selectedEvent?.year ?? ''}_${selectedEvent?.name ?? 'export'}.csv`);
      toast.success(`${rows ?? '?'} Datensätze exportiert.`);
      summary.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <PageHead title="SEPA-Lastschriften">
        <EventSelector />
      </PageHead>
      {!selectedEventId && <Notice kind="info">{t('team.noEvent')}</Notice>}
      {summary.loading && <Loading />}
      <ErrorBox message={summary.error} onRetry={summary.reload} />
      {summary.data && (
        <>
          <div className="grid grid--2">
            <div className="stat">
              <div className="stat__label">Offen (noch nicht exportiert)</div>
              <div className="stat__value">{summary.data.open.count}</div>
              <div className="stat__sub">{euro(summary.data.open.amount_cents)}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Bereits exportiert</div>
              <div className="stat__value">{summary.data.exported.count}</div>
              <div className="stat__sub">{euro(summary.data.exported.amount_cents)}</div>
            </div>
          </div>
          <div className="card stack">
            <dl className="kv">
              <dt>Gläubiger</dt>
              <dd>{summary.data.creditor_name || <span className="muted">nicht gesetzt</span>}</dd>
              <dt>Gläubiger-ID</dt>
              <dd className="mono">{summary.data.creditor_id || <span className="muted">nicht gesetzt</span>}</dd>
            </dl>
            {(!summary.data.creditor_name || !summary.data.creditor_id) && (
              <Notice kind="warn">Gläubigerdaten fehlen – bitte unter Special-Admin → Einstellungen ergänzen.</Notice>
            )}
            <Checkbox label="Bereits exportierte Lastschriften erneut einschließen" checked={includeExported} onChange={setIncludeExported} />
            <div>
              <button
                type="button"
                className="btn btn--primary"
                onClick={exportCsv}
                disabled={busy || (summary.data.open.count === 0 && !includeExported)}
              >
                CSV exportieren
              </button>
            </div>
            <p className="small muted">
              Die CSV (Semikolon-getrennt, UTF-8 mit BOM) enthält Name, Kontoinhaber, IBAN, Mandatsreferenz, Betrag,
              Verwendungszweck, Startnummer und E-Mail. Exportierte Zahlungen werden serverseitig markiert.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
