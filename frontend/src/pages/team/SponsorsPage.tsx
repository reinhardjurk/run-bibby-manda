import { useEffect, useState, type FormEvent } from 'react';
import { errorMessage } from '../../api/client';
import { sponsorsApi } from '../../api/team';
import type { DisplaySettings, SponsorOut } from '../../api/types';
import { PageHead } from '../../components/EventSelector';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Field } from '../../components/Field';
import { Loading } from '../../components/Loading';
import { useAsync } from '../../hooks/useAsync';
import { useToast } from '../../hooks/useToast';
import { useTeam } from './TeamContext';

const TIERS = [1, 2, 3, 4, 5];

function SponsorCard({ s, slug, onChanged }: { s: SponsorOut; slug: string; onChanged: () => void }) {
  const toast = useToast();
  const [tier, setTier] = useState(s.tier);
  const [name, setName] = useState(s.name ?? '');
  const [url, setUrl] = useState(s.url ?? '');
  const [busy, setBusy] = useState(false);
  const dirty = tier !== s.tier || name !== (s.name ?? '') || url !== (s.url ?? '');

  const save = async () => {
    setBusy(true);
    try {
      await sponsorsApi.update(slug, s.id, { tier, name, url });
      toast.success('Sponsor gespeichert.');
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    if (!window.confirm(`Sponsor „${s.name ?? s.id}“ löschen?`)) return;
    try {
      await sponsorsApi.remove(slug, s.id);
      toast.success('Sponsor gelöscht.');
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="card sponsor-card stack">
      <img src={s.image_url} alt={s.name ?? 'Sponsor'} />
      <Field label="Klasse">
        {(id) => (
          <select id={id} value={tier} onChange={(e) => setTier(Number(e.target.value))}>
            {TIERS.map((n) => (
              <option key={n} value={n}>
                Klasse {n}
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Name">{(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
      <Field label="Link (URL)">{(id) => <input id={id} type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" />}</Field>
      <div className="row row--between">
        <button type="button" className="btn btn--small btn--ghost" onClick={() => void remove()}>
          Löschen
        </button>
        <button type="button" className="btn btn--small btn--primary" onClick={() => void save()} disabled={!dirty || busy}>
          Speichern
        </button>
      </div>
    </div>
  );
}

/** Tab "Sponsoren": logo uploads, tiers and public display settings. */
export function SponsorsPage() {
  const { slug } = useTeam();
  const toast = useToast();
  const list = useAsync(() => sponsorsApi.list(slug), [slug]);
  const display = useAsync(() => sponsorsApi.display(slug), [slug]);
  const [file, setFile] = useState<File | null>(null);
  const [tier, setTier] = useState(3);
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [uploading, setUploading] = useState(false);
  const [disp, setDisp] = useState({ mode: 'rotation', seconds: '30', weights: '5,3,2,1,1', bucket: '' });
  const [validation, setValidation] = useState<DisplaySettings['bucket_validation']>(null);
  const [savingDisp, setSavingDisp] = useState(false);

  useEffect(() => {
    if (display.data) {
      setDisp({
        mode: display.data.sponsor_mode || 'rotation',
        seconds: String(display.data.sponsor_marquee_seconds ?? 30),
        weights: display.data.sponsor_tier_weights || '5,3,2,1,1',
        bucket: display.data.sponsor_bucket_url || '',
      });
    }
  }, [display.data]);

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    try {
      await sponsorsApi.upload(slug, file, tier, name, url);
      toast.success('Logo hochgeladen.');
      setFile(null);
      setName('');
      setUrl('');
      (e.target as HTMLFormElement).reset();
      list.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const saveDisplay = async () => {
    setSavingDisp(true);
    setValidation(null);
    try {
      const res = await sponsorsApi.setDisplay(slug, {
        sponsor_mode: disp.mode,
        sponsor_marquee_seconds: Number(disp.seconds),
        sponsor_tier_weights: disp.weights,
        sponsor_bucket_url: disp.bucket,
      });
      display.setData(res);
      setValidation(res.bucket_validation ?? null);
      toast.success('Anzeige-Einstellungen gespeichert.');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSavingDisp(false);
    }
  };

  return (
    <div className="stack stack--lg">
      <PageHead title="Sponsoren" />

      <section className="card stack">
        <h2>Anzeige auf den öffentlichen Seiten</h2>
        {display.loading && !display.data && <Loading />}
        <ErrorBox message={display.error} onRetry={display.reload} />
        <div className="grid grid--2">
          <Field label="Modus" hint="rotation = ein Logo nach dem anderen (Anzeigedauer nach Klassengewicht) · marquee = Laufband">
            {(id) => (
              <select id={id} value={disp.mode} onChange={(e) => setDisp((d) => ({ ...d, mode: e.target.value }))}>
                <option value="rotation">rotation</option>
                <option value="marquee">marquee</option>
              </select>
            )}
          </Field>
          <Field label="Laufband: Dauer eines Durchlaufs (5–300 s)">
            {(id) => <input id={id} type="number" min={5} max={300} value={disp.seconds} onChange={(e) => setDisp((d) => ({ ...d, seconds: e.target.value }))} />}
          </Field>
          <Field label="Klassengewichte (Sekunden für Klasse 1..5)" hint="z. B. 5,3,2,1,1 – Klasse 1 wird 5 s gezeigt, Klasse 3 2 s">
            {(id) => <input id={id} value={disp.weights} onChange={(e) => setDisp((d) => ({ ...d, weights: e.target.value }))} />}
          </Field>
          <Field
            label="S3-Bucket-Basis-URL (optional)"
            hint="Wenn gesetzt, werden Logos aus den Ordnern gold/, silber/, bronze/ des Buckets geladen statt aus den Uploads."
          >
            {(id) => <input id={id} type="url" value={disp.bucket} onChange={(e) => setDisp((d) => ({ ...d, bucket: e.target.value }))} placeholder="https://bucket.s3.region.example/prefix" />}
          </Field>
        </div>
        {validation && (
          <Notice kind="success">
            <div>
              Bucket gelesen: <code>{validation.normalized_url}</code>
              <div className="chip-list" style={{ marginTop: '0.35rem' }}>
                {TIERS.map((n) => (
                  <span key={n} className="badge">
                    Klasse {n}: {validation.found[String(n)] ?? 0}
                  </span>
                ))}
              </div>
            </div>
          </Notice>
        )}
        <div className="form-actions">
          <button type="button" className="btn btn--primary" onClick={() => void saveDisplay()} disabled={savingDisp}>
            Speichern
          </button>
        </div>
      </section>

      <section className="card stack">
        <h2>Logo hochladen</h2>
        <form className="inline-form" onSubmit={(e) => void upload(e)}>
          <Field label="Bilddatei" required>
            {(id) => <input id={id} type="file" accept="image/*" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />}
          </Field>
          <Field label="Klasse" className="field--narrow">
            {(id) => (
              <select id={id} value={tier} onChange={(e) => setTier(Number(e.target.value))}>
                {TIERS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Name">{(id) => <input id={id} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
          <Field label="Link (URL)">{(id) => <input id={id} type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" />}</Field>
          <button type="submit" className="btn btn--primary" disabled={uploading || !file}>
            Hochladen
          </button>
        </form>
        <p className="small muted">Bilder werden serverseitig auf max. 600 px verkleinert und von Metadaten befreit.</p>
      </section>

      <section className="stack">
        <h2>Sponsoren ({list.data?.length ?? 0})</h2>
        {list.loading && !list.data && <Loading />}
        <ErrorBox message={list.error} onRetry={list.reload} />
        {list.data && list.data.length === 0 && <p className="muted">Noch keine Sponsoren hochgeladen.</p>}
        <div className="sponsor-grid">
          {list.data?.map((s) => (
            <SponsorCard key={`${s.id}-${s.tier}-${s.name}-${s.url}`} s={s} slug={slug} onChanged={list.reload} />
          ))}
        </div>
      </section>
    </div>
  );
}
