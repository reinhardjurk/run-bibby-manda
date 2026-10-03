import { timingTeamApi } from '../../../api/team';
import { ErrorBox } from '../../../components/ErrorBox';
import { Loading } from '../../../components/Loading';
import { useAsync } from '../../../hooks/useAsync';
import { formatSeconds } from '../../../utils/format';

/** Complete internal result list incl. participants without publication consent and relays. */
export function InternalResultsSection({ slug, eventId }: { slug: string; eventId: string }) {
  const res = useAsync(() => timingTeamApi.internalResults(slug, eventId), [slug, eventId]);
  return (
    <div className="stack">
      <div className="row row--end">
        <button type="button" className="btn btn--small" onClick={res.reload}>
          Aktualisieren
        </button>
      </div>
      {res.loading && !res.data && <Loading />}
      <ErrorBox message={res.error} onRetry={res.reload} />
      {res.data?.competitions.map((c) => (
        <section key={c.competition.id}>
          <h3>
            {c.competition.title_de} <span className="badge">{c.rows.length} im Ziel</span>{' '}
            {c.unfinished > 0 && <span className="badge badge--warn">{c.unfinished} ohne Zeit</span>}
          </h3>
          <div className="table-wrap">
            <table className="table--compact">
              <thead>
                <tr>
                  <th className="num">Platz</th>
                  <th className="num">StNr.</th>
                  <th>Name</th>
                  <th>Team</th>
                  <th>AK</th>
                  <th className="num">AK-Pl.</th>
                  <th className="num">Zeit</th>
                  <th>Veröff.</th>
                  {c.competition.relay_scoring && <th className="num">Staffel</th>}
                </tr>
              </thead>
              <tbody>
                {c.rows.map((r) => (
                  <tr key={r.registration_id}>
                    <td className="num">{r.place ?? '–'}</td>
                    <td className="num">{r.bib_number ?? '–'}</td>
                    <td>{r.name}</td>
                    <td>{r.team_name ?? ''}</td>
                    <td>{r.age_class ?? ''}</td>
                    <td className="num">{r.place_age_class ?? ''}</td>
                    <td className="num mono">{r.time}</td>
                    <td>{r.consent_publish ? <span className="badge badge--ok">ja</span> : <span className="badge badge--danger">nein</span>}</td>
                    {c.competition.relay_scoring && (
                      <td className="num">{r.relay_place !== null ? `${r.relay_place}. (${r.relay_time})` : ''}</td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {c.relays.length > 0 && (
            <div className="table-wrap" style={{ marginTop: '0.5rem' }}>
              <table className="table--compact">
                <thead>
                  <tr>
                    <th className="num">Staffel-Platz</th>
                    <th>Team</th>
                    <th className="num">Gewertet</th>
                    <th className="num">Gesamtzeit</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {c.relays.map((rel) => (
                    <tr key={rel.relay_id}>
                      <td className="num">{rel.place ?? '–'}</td>
                      <td>{rel.team_name}</td>
                      <td className="num">{rel.total_scored}</td>
                      <td className="num mono">{formatSeconds(rel.total_seconds)}</td>
                      <td>{rel.complete ? <span className="badge badge--ok">vollständig</span> : <span className="badge badge--warn">unvollständig</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
