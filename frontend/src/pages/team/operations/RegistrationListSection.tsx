import { useEffect, useState } from 'react';
import { registrationsApi } from '../../../api/team';
import { ErrorBox } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { Pagination } from '../../../components/Pagination';
import { useAsync } from '../../../hooks/useAsync';
import { formatDate, formatSeconds } from '../../../utils/format';
import { PayBadge, RegStatusBadge } from '../reception/StatusBadges';

/** Read-only paged registration list for race operations (full editing lives in the Admin tab). */
export function RegistrationListSection({ slug, eventId }: { slug: string; eventId: string }) {
  const [q, setQ] = useState('');
  const [debounced, setDebounced] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 100;
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(q.trim()), 250);
    return () => window.clearTimeout(id);
  }, [q]);
  useEffect(() => setPage(1), [debounced, eventId]);
  const list = useAsync(
    () => registrationsApi.list(slug, { event_id: eventId, q: debounced, page, page_size: pageSize }),
    [slug, eventId, debounced, page],
  );
  return (
    <div className="stack">
      <Field label="Suche (Name oder Startnummer)">{(id) => <input id={id} value={q} onChange={(e) => setQ(e.target.value)} />}</Field>
      {list.loading && !list.data && <Loading />}
      <ErrorBox message={list.error} onRetry={list.reload} />
      {list.data && (
        <>
          <div className="table-wrap">
            <table className="table--compact">
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
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((r) => (
                  <tr key={r.id}>
                    <td className="num">{r.bib_number ?? '–'}</td>
                    <td>
                      {r.last_name}, {r.first_name}
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={list.data.page} pageSize={list.data.page_size} total={list.data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
