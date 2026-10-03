import { useEffect, useState } from 'react';
import { errorMessage } from '../../api/client';
import { publicApi } from '../../api/public';
import { registrationsApi } from '../../api/team';
import { EventSelector, PageHead } from '../../components/EventSelector';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Loading } from '../../components/Loading';
import { Pagination } from '../../components/Pagination';
import { useAsync } from '../../hooks/useAsync';
import { useToast } from '../../hooks/useToast';
import { useT } from '../../i18n';
import { formatDate, formatSeconds } from '../../utils/format';
import { MergeParticipantsModal, type MergeSelection } from './reception/MergeParticipantsModal';
import { OfficeRegistrationModal } from './reception/OfficeRegistrationModal';
import { RegistrationDetailModal } from './reception/RegistrationDetailModal';
import { PayBadge, RegStatusBadge } from './reception/StatusBadges';
import { useTeam } from './TeamContext';

const PAGE_SIZE = 50;

/** Tab "Admin": race-office reception desk – search, pay, edit, office registration, merge. */
export function ReceptionPage() {
  const { slug, selectedEventId, selectedEvent, reloadEvents } = useTeam();
  const t = useT();
  const toast = useToast();
  const [q, setQ] = useState('');
  const [debounced, setDebounced] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const [officeOpen, setOfficeOpen] = useState(false);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [mergeSel, setMergeSel] = useState<MergeSelection>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(q.trim()), 250);
    return () => window.clearTimeout(id);
  }, [q]);
  useEffect(() => setPage(1), [debounced, status, selectedEventId]);

  const info = useAsync(() => publicApi.info(slug), [slug]);
  const list = useAsync(
    () => registrationsApi.list(slug, { event_id: selectedEventId, q: debounced, status, page, page_size: PAGE_SIZE }),
    [slug, selectedEventId, debounced, status, page],
    !!selectedEventId,
  );

  const markPaid = async (id: string) => {
    setBusyId(id);
    try {
      await registrationsApi.markPaid(slug, id);
      toast.success('Als bezahlt markiert.');
      list.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  const changed = () => {
    list.reload();
    reloadEvents();
  };

  return (
    <div className="stack">
      <PageHead title="Wettkampfbüro">
        <EventSelector />
        <button type="button" className="btn btn--primary" onClick={() => setOfficeOpen(true)} disabled={!selectedEvent}>
          + Nachmeldung
        </button>
        <button type="button" className="btn" onClick={() => setMergeOpen(true)}>
          Teilnehmer zusammenführen
        </button>
      </PageHead>
      {!selectedEventId && <Notice kind="info">{t('team.noEvent')}</Notice>}
      {selectedEventId && (
        <>
          <div className="inline-form">
            <div className="field">
              <label className="field__label" htmlFor="reg-search">
                Suche (Name oder Startnummer)
              </label>
              <input
                id="reg-search"
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="z. B. Müller oder 123"
                autoFocus
              />
            </div>
            <div className="field field--narrow">
              <label className="field__label" htmlFor="reg-status">
                Status
              </label>
              <select id="reg-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">alle</option>
                <option value="confirmed">bestätigt</option>
                <option value="pending">offen</option>
                <option value="cancelled">storniert</option>
              </select>
            </div>
          </div>
          {list.loading && !list.data && <Loading />}
          <ErrorBox message={list.error} onRetry={list.reload} />
          {list.data && (
            <>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th className="num">StNr.</th>
                      <th>Name</th>
                      <th>Geb.</th>
                      <th>Strecke</th>
                      <th>Team</th>
                      <th>Status</th>
                      <th className="num">Zeit</th>
                      <th>Zahlung</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.items.length === 0 && (
                      <tr>
                        <td colSpan={9} className="muted center">
                          {t('common.none')}
                        </td>
                      </tr>
                    )}
                    {list.data.items.map((r) => (
                      <tr key={r.id} className="is-clickable" onClick={() => setOpenId(r.id)}>
                        <td className="num">
                          <strong>{r.bib_number ?? '–'}</strong>
                        </td>
                        <td>
                          {r.last_name}, {r.first_name}
                          <div className="small muted">{r.email}</div>
                        </td>
                        <td className="nowrap">{formatDate(r.birth_date)}</td>
                        <td>{r.competition_title}</td>
                        <td>{r.team_name ?? ''}</td>
                        <td>
                          <RegStatusBadge status={r.status} />
                        </td>
                        <td className="num mono">{formatSeconds(r.finish_seconds)}</td>
                        <td>
                          <PayBadge method={r.payment_method} status={r.payment_status} />
                        </td>
                        <td className="nowrap" onClick={(e) => e.stopPropagation()}>
                          {r.payment_method && r.payment_status !== 'paid' && (
                            <button
                              type="button"
                              className="btn btn--small"
                              disabled={busyId === r.id}
                              onClick={() => void markPaid(r.id)}
                            >
                              Als bezahlt markieren
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={list.data.page} pageSize={list.data.page_size} total={list.data.total} onChange={setPage} />
            </>
          )}
        </>
      )}

      {openId && (
        <RegistrationDetailModal
          slug={slug}
          registrationId={openId}
          event={selectedEvent}
          heardOptions={info.data?.heard_about_options ?? []}
          onClose={() => setOpenId(null)}
          onChanged={changed}
          onPickMerge={(role, id, label) => {
            setMergeSel((s) => ({ ...s, [role]: { id, label } }));
            toast.info(`${role === 'source' ? 'Quelle' : 'Ziel'} gemerkt: ${label}`);
          }}
        />
      )}
      {officeOpen && selectedEvent && (
        <OfficeRegistrationModal slug={slug} event={selectedEvent} onClose={() => setOfficeOpen(false)} onCreated={changed} />
      )}
      {mergeOpen && (
        <MergeParticipantsModal slug={slug} selection={mergeSel} onClose={() => setMergeOpen(false)} onMerged={changed} />
      )}
    </div>
  );
}
