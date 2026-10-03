import { useMemo, useState } from 'react';
import { errorMessage, openBlob } from '../../api/client';
import { resultsApi } from '../../api/team';
import { EventSelector, PageHead } from '../../components/EventSelector';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Checkbox, Field } from '../../components/Field';
import { Loading } from '../../components/Loading';
import { useAsync } from '../../hooks/useAsync';
import { useToast } from '../../hooks/useToast';
import { useT } from '../../i18n';
import { useTeam } from './TeamContext';

const GENDER_LABEL: Record<string, string> = { f: 'weiblich', m: 'männlich', x: 'divers' };

/** Tab "Ergebnisdruck": certificates – single by bib, per age class × competition, whole competition. */
export function CertificatePrintPage() {
  const { slug, selectedEventId } = useTeam();
  const t = useT();
  const toast = useToast();
  const overview = useAsync(() => resultsApi.overview(slug, selectedEventId), [slug, selectedEventId], !!selectedEventId);
  const [background, setBackground] = useState(true);
  const [bib, setBib] = useState('');
  const [compId, setCompId] = useState('');
  const [ageClass, setAgeClass] = useState('');
  const [gender, setGender] = useState('');
  const [busy, setBusy] = useState(false);

  const comp = useMemo(
    () => overview.data?.competitions.find((c) => c.competition.id === compId) ?? overview.data?.competitions[0] ?? null,
    [overview.data, compId],
  );
  const effectiveCompId = comp?.competition.id ?? '';

  // How many certificates the current selection contains.
  const count = useMemo(() => {
    if (!comp) return 0;
    if (!ageClass) {
      if (!gender) return comp.finished;
      return comp.age_classes.reduce((sum, ac) => sum + (ac.counts[gender] ?? 0), 0);
    }
    const ac = comp.age_classes.find((a) => a.age_class === ageClass);
    if (!ac) return 0;
    return gender ? (ac.counts[gender] ?? 0) : ac.total;
  }, [comp, ageClass, gender]);

  const single = async () => {
    const n = Number(bib);
    if (!Number.isInteger(n) || n < 0) {
      toast.error('Bitte eine gültige Startnummer eingeben.');
      return;
    }
    setBusy(true);
    try {
      const res = await resultsApi.certificate(slug, selectedEventId, n, background);
      openBlob(res.blob, `urkunde-${n}.pdf`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const batch = async () => {
    if (!effectiveCompId) return;
    setBusy(true);
    try {
      const res = await resultsApi.certificates(slug, {
        event_id: selectedEventId,
        competition_id: effectiveCompId,
        age_class: ageClass || undefined,
        gender: gender || undefined,
        print_background: background,
      });
      const n = res.headers.get('X-Certificate-Count');
      toast.success(`${n ?? count} Urkunde(n) erzeugt.`);
      openBlob(res.blob, `urkunden-${comp?.competition.title_de ?? ''}${ageClass ? `-${ageClass}` : ''}.pdf`);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <PageHead title="Ergebnisdruck">
        <EventSelector />
      </PageHead>
      {!selectedEventId && <Notice kind="info">{t('team.noEvent')}</Notice>}
      {overview.loading && <Loading />}
      <ErrorBox message={overview.error} onRetry={overview.reload} />
      {overview.data && (
        <>
          <div className="card">
            <Checkbox label="Hintergrund mitdrucken" checked={background} onChange={setBackground} />
            <div className="small muted" style={{ marginTop: '0.25rem' }}>
              Ohne Hintergrund drucken, wenn Urkunden auf vorgedrucktes Papier gehen.
            </div>
          </div>

          <div className="grid grid--2">
            <section className="card stack">
              <h2>Einzelurkunde</h2>
              <div className="inline-form">
                <Field label="Startnummer" className="field--narrow">
                  {(id) => (
                    <input
                      id={id}
                      inputMode="numeric"
                      value={bib}
                      onChange={(e) => setBib(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && void single()}
                    />
                  )}
                </Field>
                <button type="button" className="btn btn--primary" onClick={single} disabled={busy || !bib}>
                  Urkunde (PDF)
                </button>
              </div>
            </section>

            <section className="card stack">
              <h2>Stapeldruck</h2>
              <Field label="Strecke">
                {(id) => (
                  <select
                    id={id}
                    value={effectiveCompId}
                    onChange={(e) => {
                      setCompId(e.target.value);
                      setAgeClass('');
                      setGender('');
                    }}
                  >
                    {overview.data?.competitions.map((c) => (
                      <option key={c.competition.id} value={c.competition.id}>
                        {c.competition.title_de} ({c.finished})
                      </option>
                    ))}
                  </select>
                )}
              </Field>
              <div className="grid grid--2">
                <Field label="Altersklasse">
                  {(id) => (
                    <select id={id} value={ageClass} onChange={(e) => setAgeClass(e.target.value)}>
                      <option value="">gesamte Strecke</option>
                      {comp?.age_classes.map((ac) => (
                        <option key={ac.age_class} value={ac.age_class}>
                          {ac.age_class} ({ac.total})
                        </option>
                      ))}
                    </select>
                  )}
                </Field>
                <Field label="Geschlecht">
                  {(id) => (
                    <select id={id} value={gender} onChange={(e) => setGender(e.target.value)} disabled={!comp?.competition.gender_scoring}>
                      <option value="">alle</option>
                      <option value="f">weiblich</option>
                      <option value="m">männlich</option>
                      <option value="x">divers</option>
                    </select>
                  )}
                </Field>
              </div>
              <div className="row row--between">
                <span>
                  Auswahl enthält <strong>{count}</strong> Urkunde(n)
                </span>
                <button type="button" className="btn btn--primary" onClick={batch} disabled={busy || count === 0}>
                  Stapel (PDF)
                </button>
              </div>
            </section>
          </div>

          <section className="card">
            <h2>Übersicht Altersklassen</h2>
            {overview.data.competitions.length === 0 && <p className="muted">{t('common.none')}</p>}
            <div className="grid grid--2">
              {overview.data.competitions.map((c) => (
                <div key={c.competition.id}>
                  <h3>
                    {c.competition.title_de} <span className="badge">{c.finished} im Ziel</span>
                  </h3>
                  {c.age_classes.length === 0 ? (
                    <p className="muted small">Noch keine Zeiten.</p>
                  ) : (
                    <div className="table-wrap">
                      <table className="table--compact">
                        <thead>
                          <tr>
                            <th>AK</th>
                            {c.competition.gender_scoring && <th className="num">w</th>}
                            {c.competition.gender_scoring && <th className="num">m</th>}
                            {c.competition.gender_scoring && <th className="num">d</th>}
                            <th className="num">gesamt</th>
                            <th></th>
                          </tr>
                        </thead>
                        <tbody>
                          {c.age_classes.map((ac) => (
                            <tr key={ac.age_class}>
                              <td>{ac.age_class}</td>
                              {c.competition.gender_scoring && <td className="num">{ac.counts['f'] ?? 0}</td>}
                              {c.competition.gender_scoring && <td className="num">{ac.counts['m'] ?? 0}</td>}
                              {c.competition.gender_scoring && <td className="num">{ac.counts['x'] ?? 0}</td>}
                              <td className="num">{ac.total}</td>
                              <td>
                                <button
                                  type="button"
                                  className="btn btn--small btn--ghost"
                                  onClick={() => {
                                    setCompId(c.competition.id);
                                    setAgeClass(ac.age_class);
                                    setGender('');
                                  }}
                                >
                                  auswählen
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <p className="small muted" style={{ marginTop: '0.5rem' }}>
              Geschlechter: {Object.entries(GENDER_LABEL).map(([k, v]) => `${k} = ${v}`).join(', ')}
            </p>
          </section>
        </>
      )}
    </div>
  );
}
