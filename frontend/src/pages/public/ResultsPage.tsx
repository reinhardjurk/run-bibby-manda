import { useParams, useSearchParams } from 'react-router-dom';
import { publicApi } from '../../api/public';
import type { PublicCompetition, ResultRow } from '../../api/types';
import { ErrorBox } from '../../components/ErrorBox';
import { Loading } from '../../components/Loading';
import { PublicLayout } from '../../components/PublicLayout';
import { useAsync } from '../../hooks/useAsync';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useLang, useT } from '../../i18n';

function CompetitionTable({ competition, rows }: { competition: PublicCompetition; rows: ResultRow[] }) {
  const t = useT();
  const [lang] = useLang();
  const title = lang === 'en' ? competition.title_en || competition.title_de : competition.title_de;
  const hasRelay = competition.relay_scoring && rows.some((r) => r.relay_place !== null || r.relay_time);
  const hasAgeClass = rows.some((r) => r.age_class);
  return (
    <section>
      <h2>
        {title} <span className="badge">{rows.length}</span>
      </h2>
      {rows.length === 0 ? (
        <p className="muted">{t('results.noRows')}</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="num">{t('results.place')}</th>
                <th className="num">{t('results.bib')}</th>
                <th>{t('results.name')}</th>
                <th>{t('results.team')}</th>
                {hasAgeClass && <th>{t('results.ageClass')}</th>}
                {hasAgeClass && <th className="num">{t('results.agePlace')}</th>}
                <th className="num">{t('results.time')}</th>
                {hasRelay && <th className="num">{t('results.relayPlace')}</th>}
                {hasRelay && <th className="num">{t('results.relayTime')}</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.bib_number ?? i}-${i}`}>
                  <td className="num">{r.place ?? '–'}</td>
                  <td className="num">{r.bib_number ?? '–'}</td>
                  <td>{r.name}</td>
                  <td>{r.team_name ?? ''}</td>
                  {hasAgeClass && <td>{r.age_class ?? ''}</td>}
                  {hasAgeClass && <td className="num">{r.place_age_class ?? ''}</td>}
                  <td className="num mono">{r.time}</td>
                  {hasRelay && <td className="num">{r.relay_place ?? ''}</td>}
                  {hasRelay && <td className="num mono">{r.relay_time}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function ResultsPage() {
  const { slug = '' } = useParams();
  const t = useT();
  const [params, setParams] = useSearchParams();
  const eventId = params.get('event_id');
  const info = useAsync(() => publicApi.info(slug), [slug]);
  const results = useAsync(() => publicApi.results(slug, eventId), [slug, eventId]);
  useDocumentTitle(t('results.title'));

  return (
    <PublicLayout
      slug={slug}
      orgName={info.data?.organization.name}
      logoUrl={info.data?.logo_url}
      sponsorDisplay={info.data?.sponsor_display}
      title={t('results.title')}
    >
      {results.loading && <Loading />}
      <ErrorBox message={results.error} onRetry={results.reload} />
      {results.data && (
        <div className="stack stack--lg">
          {results.data.events.length > 1 && (
            <div className="field" style={{ maxWidth: 420 }}>
              <label className="field__label" htmlFor="results-event">
                {t('results.event')}
              </label>
              <select
                id="results-event"
                value={results.data.event?.id ?? ''}
                onChange={(e) => setParams(e.target.value ? { event_id: e.target.value } : {})}
              >
                {results.data.events.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} {e.year}
                  </option>
                ))}
              </select>
            </div>
          )}
          {!results.data.event && <p className="muted">{t('results.noEvents')}</p>}
          {results.data.event && (
            <>
              <h2 style={{ marginBottom: 0 }}>
                {results.data.event.name} {results.data.event.year}
              </h2>
              <p className="small muted">{t('results.hint')}</p>
              {results.data.competitions.map((c) => (
                <CompetitionTable key={c.competition.id} competition={c.competition} rows={c.rows} />
              ))}
            </>
          )}
        </div>
      )}
    </PublicLayout>
  );
}
