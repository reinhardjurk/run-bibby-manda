import { statsApi } from '../../api/team';
import type { StatsFast, StatsPerson } from '../../api/types';
import { EventSelector, PageHead } from '../../components/EventSelector';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Loading } from '../../components/Loading';
import { useAsync } from '../../hooks/useAsync';
import { useT, type TranslationKey } from '../../i18n';
import { useTeam } from './TeamContext';

function Person({ p }: { p: StatsPerson | null }) {
  if (!p) return <span className="muted">–</span>;
  return (
    <span>
      {p.name} ({p.age}){p.bib_number !== null && <small className="muted"> · #{p.bib_number}</small>}
    </span>
  );
}
function Fast({ p }: { p: StatsFast | null }) {
  if (!p) return <span className="muted">–</span>;
  return (
    <span>
      {p.name} <span className="mono">{p.time}</span>
      {p.bib_number !== null && <small className="muted"> · #{p.bib_number}</small>}
    </span>
  );
}

function Bars({ data, labelFor }: { data: Record<string, number>; labelFor?: (k: string) => string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map((e) => e[1]));
  if (entries.length === 0) return <p className="muted small">Keine Daten.</p>;
  return (
    <div className="bar-chart">
      {entries.map(([k, v]) => (
        <div className="bar-chart__row" key={k}>
          <span>{labelFor ? labelFor(k) : k}</span>
          <span className="bar-chart__bar" style={{ width: `${(v / max) * 100}%` }} aria-hidden="true" />
          <span className="num">{v}</span>
        </div>
      ))}
    </div>
  );
}

/** Tab "Statistiken". */
export function StatsPage() {
  const { slug, selectedEventId } = useTeam();
  const t = useT();
  const stats = useAsync(() => statsApi.get(slug, selectedEventId), [slug, selectedEventId], !!selectedEventId);
  const s = stats.data;

  return (
    <div className="stack">
      <PageHead title="Statistiken">
        <EventSelector />
      </PageHead>
      {!selectedEventId && <Notice kind="info">{t('team.noEvent')}</Notice>}
      {stats.loading && <Loading />}
      <ErrorBox message={stats.error} onRetry={stats.reload} />
      {s && (
        <div className="stack stack--lg">
          <section className="grid grid--4">
            <div className="stat">
              <div className="stat__label">Teilnehmende</div>
              <div className="stat__value">{s.overview.participants}</div>
              <div className="stat__sub">{s.overview.finished} im Ziel</div>
            </div>
            <div className="stat">
              <div className="stat__label">Teams</div>
              <div className="stat__value">{s.overview.teams}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Staffeln</div>
              <div className="stat__value">{s.overview.relays}</div>
              <div className="stat__sub">{s.overview.relays_complete} vollständig</div>
            </div>
            <div className="stat">
              <div className="stat__label">Durchschnittsalter</div>
              <div className="stat__value">{s.overview.average_age ?? '–'}</div>
              <div className="stat__sub">
                Jüngste/r: <Person p={s.overview.youngest} />
                <br />
                Älteste/r: <Person p={s.overview.oldest} />
              </div>
            </div>
          </section>

          <section className="card">
            <h2>Pro Strecke</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Strecke</th>
                    <th className="num">Gemeldet</th>
                    <th className="num">Im Ziel</th>
                    <th>w / m / d</th>
                    <th>Schnellste/r</th>
                    <th>Schnellste Frau</th>
                    <th>Schnellster Mann</th>
                    <th>Jüngste/r</th>
                    <th>Älteste/r</th>
                  </tr>
                </thead>
                <tbody>
                  {s.competitions.map((c) => (
                    <tr key={c.competition.id}>
                      <td>{c.competition.title_de}</td>
                      <td className="num">{c.total}</td>
                      <td className="num">{c.finished}</td>
                      <td className="nowrap">
                        {c.by_gender['f'] ?? 0} / {c.by_gender['m'] ?? 0} / {c.by_gender['x'] ?? 0}
                      </td>
                      <td>
                        <Fast p={c.fastest} />
                      </td>
                      <td>
                        <Fast p={c.fastest_female} />
                      </td>
                      <td>
                        <Fast p={c.fastest_male} />
                      </td>
                      <td>
                        <Person p={c.youngest} />
                      </td>
                      <td>
                        <Person p={c.oldest} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h2>Staffeln</h2>
            {s.relays.length === 0 ? (
              <p className="muted">Keine Staffeln.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th className="num">Platz</th>
                      <th>Team</th>
                      <th>Strecke</th>
                      <th className="num">Mitglieder</th>
                      <th className="num">Zeit</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.relays.map((r, i) => (
                      <tr key={`${r.team_name}-${i}`}>
                        <td className="num">{r.place ?? '–'}</td>
                        <td>{r.team_name}</td>
                        <td>{r.competition}</td>
                        <td className="num">{r.members}</td>
                        <td className="num mono">{r.time || '–'}</td>
                        <td>
                          {r.complete ? (
                            <span className="badge badge--ok">vollständig</span>
                          ) : (
                            <span className="badge badge--warn">unvollständig</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <div className="grid grid--2">
            <section className="card">
              <h2>Anreise (Schätzung)</h2>
              {!s.travel.available && (
                <Notice kind="warn">
                  Für diese Veranstaltung ist keine Veranstaltungs-PLZ hinterlegt – bitte im Event ergänzen.
                </Notice>
              )}
              {s.travel.available && (
                <div className="stack">
                  <div className="small muted">
                    {s.travel.counted} mit PLZ ausgewertet · {s.travel.unknown} ohne/unbekannt
                  </div>
                  <Bars data={s.travel.buckets} labelFor={(k) => `${k} km`} />
                  <dl className="kv">
                    <dt>Ø Entfernung</dt>
                    <dd>{s.travel.average_km !== null ? `${s.travel.average_km} km` : '–'}</dd>
                    <dt>Weiteste Anreise</dt>
                    <dd>
                      {s.travel.farthest_km !== null ? `${s.travel.farthest_km} km` : '–'}
                      {s.travel.farthest_region && <small className="muted"> · {s.travel.farthest_region}</small>}
                    </dd>
                  </dl>
                  {s.travel.top_regions.length > 0 && (
                    <>
                      <h3>Top-Regionen</h3>
                      <Bars
                        data={Object.fromEntries(s.travel.top_regions.map((r) => [`${r.region} ${r.name}`.trim(), r.count]))}
                      />
                    </>
                  )}
                </div>
              )}
            </section>

            <section className="card">
              <h2>Wiederholungstäter/innen</h2>
              <p>
                <strong>{s.regulars.count}</strong> Teilnehmende waren bereits bei anderen Veranstaltungen dabei.
              </p>
              {s.regulars.names.length > 0 && (
                <details>
                  <summary className="small">Namen anzeigen</summary>
                  <div className="chip-list" style={{ marginTop: '0.5rem' }}>
                    {s.regulars.names.map((n) => (
                      <span key={n} className="badge">
                        {n}
                      </span>
                    ))}
                  </div>
                </details>
              )}
            </section>

            <section className="card">
              <h2>Aufmerksam geworden durch</h2>
              <Bars data={s.heard_about} labelFor={(k) => t(`heard.${k}` as TranslationKey)} />
            </section>

            <section className="card">
              <h2>T-Shirt-Größen</h2>
              <Bars data={s.tshirt_sizes} />
            </section>

            <section className="card">
              <h2>Teamnamen ({s.team_names.length})</h2>
              {s.team_names.length === 0 ? (
                <p className="muted">Keine Teams.</p>
              ) : (
                <div className="chip-list">
                  {s.team_names.map((n) => (
                    <span key={n} className="badge">
                      {n}
                    </span>
                  ))}
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
