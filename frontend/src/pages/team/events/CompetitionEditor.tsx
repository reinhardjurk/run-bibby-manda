import { useState } from 'react';
import { errorMessage } from '../../../api/client';
import { eventsApi } from '../../../api/team';
import type { AgeClassScheme, CompetitionIn, CompetitionOut, EventOut } from '../../../api/types';
import { Checkbox, Field } from '../../../components/Field';
import { Modal } from '../../../components/Modal';
import { useToast } from '../../../hooks/useToast';
import { euro, euroInput, fromLocalInput, parseEuro, toLocalInput } from '../../../utils/format';

interface CompForm {
  title_de: string;
  title_en: string;
  start_time: string;
  price_adult: string;
  price_youth: string;
  age_class_scheme: AgeClassScheme;
  gender_scoring: boolean;
  relay_scoring: boolean;
  bib_range_start: string;
  bib_range_end: string;
  sort_order: string;
}

function toForm(c: CompetitionIn | null, index: number): CompForm {
  return {
    title_de: c?.title_de ?? '',
    title_en: c?.title_en ?? '',
    start_time: toLocalInput(c?.start_time ?? null),
    price_adult: euroInput(c?.price_adult_cents ?? 0),
    price_youth: c?.price_youth_cents === null || c?.price_youth_cents === undefined ? '' : euroInput(c.price_youth_cents),
    age_class_scheme: c?.age_class_scheme ?? 'five',
    gender_scoring: c?.gender_scoring ?? true,
    relay_scoring: c?.relay_scoring ?? false,
    bib_range_start: c?.bib_range_start === null || c?.bib_range_start === undefined ? '' : String(c.bib_range_start),
    bib_range_end: c?.bib_range_end === null || c?.bib_range_end === undefined ? '' : String(c.bib_range_end),
    sort_order: String(c?.sort_order ?? index),
  };
}

export function formToCompetition(f: CompForm): CompetitionIn | string {
  const adult = parseEuro(f.price_adult);
  if (adult === null) return 'Preis (Erwachsene) ungültig.';
  const youth = f.price_youth.trim() ? parseEuro(f.price_youth) : null;
  if (f.price_youth.trim() && youth === null) return 'Jugendpreis ungültig.';
  if (!f.title_de.trim()) return 'Titel (DE) fehlt.';
  return {
    title_de: f.title_de.trim(),
    title_en: f.title_en.trim(),
    start_time: fromLocalInput(f.start_time),
    price_adult_cents: adult,
    price_youth_cents: youth,
    age_class_scheme: f.age_class_scheme,
    gender_scoring: f.gender_scoring,
    relay_scoring: f.relay_scoring,
    bib_range_start: f.bib_range_start.trim() ? Number(f.bib_range_start) : null,
    bib_range_end: f.bib_range_end.trim() ? Number(f.bib_range_end) : null,
    sort_order: Number(f.sort_order) || 0,
  };
}

export function CompetitionModal({
  initial,
  index,
  title,
  onClose,
  onSave,
}: {
  initial: CompetitionIn | null;
  index: number;
  title: string;
  onClose: () => void;
  onSave: (c: CompetitionIn) => Promise<void> | void;
}) {
  const [f, setF] = useState<CompForm>(() => toForm(initial, index));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (p: Partial<CompForm>) => setF((x) => ({ ...x, ...p }));

  const save = async () => {
    const c = formToCompetition(f);
    if (typeof c === 'string') {
      setError(c);
      return;
    }
    setBusy(true);
    try {
      await onSave(c);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            Abbrechen
          </button>
          <button type="button" className="btn btn--primary" onClick={() => void save()} disabled={busy}>
            Speichern
          </button>
        </>
      }
    >
      <div className="stack">
        <div className="grid grid--2">
          <Field label="Titel (DE)" required>{(id) => <input id={id} value={f.title_de} required maxLength={200} onChange={(e) => set({ title_de: e.target.value })} />}</Field>
          <Field label="Titel (EN)">{(id) => <input id={id} value={f.title_en} maxLength={200} onChange={(e) => set({ title_en: e.target.value })} />}</Field>
          <Field label="Startzeit" hint="Leer = Standard-Startzeit des Events.">
            {(id) => <input id={id} type="datetime-local" value={f.start_time} onChange={(e) => set({ start_time: e.target.value })} />}
          </Field>
          <Field label="Sortierung">{(id) => <input id={id} type="number" value={f.sort_order} onChange={(e) => set({ sort_order: e.target.value })} />}</Field>
          <Field label="Startgeld Erwachsene (€)">
            {(id) => <input id={id} inputMode="decimal" value={f.price_adult} onChange={(e) => set({ price_adult: e.target.value })} />}
          </Field>
          <Field label="Startgeld Jugend (€)" hint="Leer = kein Jugendtarif.">
            {(id) => <input id={id} inputMode="decimal" value={f.price_youth} onChange={(e) => set({ price_youth: e.target.value })} />}
          </Field>
          <Field label="Altersklassen-Schema" hint="five = 5-Jahres-Klassen · one = eine Klasse · none = keine AK-Wertung">
            {(id) => (
              <select id={id} value={f.age_class_scheme} onChange={(e) => set({ age_class_scheme: e.target.value as AgeClassScheme })}>
                <option value="five">five</option>
                <option value="one">one</option>
                <option value="none">none</option>
              </select>
            )}
          </Field>
          <div className="stack" style={{ justifyContent: 'center' }}>
            <Checkbox label="Geschlechterwertung" checked={f.gender_scoring} onChange={(v) => set({ gender_scoring: v })} />
            <Checkbox label="Staffelwertung (3 gleiche Teamnamen = Staffel)" checked={f.relay_scoring} onChange={(v) => set({ relay_scoring: v })} />
          </div>
          <Field label="Startnummern von">{(id) => <input id={id} type="number" min={1} value={f.bib_range_start} onChange={(e) => set({ bib_range_start: e.target.value })} />}</Field>
          <Field label="Startnummern bis">{(id) => <input id={id} type="number" min={1} value={f.bib_range_end} onChange={(e) => set({ bib_range_end: e.target.value })} />}</Field>
        </div>
        {error && <div className="notice notice--error">{error}</div>}
      </div>
    </Modal>
  );
}

/** Competition list of an existing event with CRUD against the API. */
export function CompetitionEditor({ slug, event, onChanged }: { slug: string; event: EventOut; onChanged: () => void }) {
  const toast = useToast();
  const [editing, setEditing] = useState<CompetitionOut | null | 'new'>(null);
  const comps = [...event.competitions].sort((a, b) => a.sort_order - b.sort_order || a.title_de.localeCompare(b.title_de));

  const remove = async (c: CompetitionOut) => {
    if (!window.confirm(`Strecke „${c.title_de}“ löschen?`)) return;
    try {
      await eventsApi.removeCompetition(slug, event.id, c.id);
      toast.success('Strecke gelöscht.');
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="stack">
      <div className="row row--between">
        <h3 style={{ margin: 0 }}>Strecken ({comps.length})</h3>
        <button type="button" className="btn btn--small btn--primary" onClick={() => setEditing('new')}>
          + Strecke
        </button>
      </div>
      <div className="table-wrap">
        <table className="table--compact">
          <thead>
            <tr>
              <th>Titel</th>
              <th>Start</th>
              <th className="num">Erw.</th>
              <th className="num">Jugend</th>
              <th>AK</th>
              <th>Wertung</th>
              <th>StNr.-Bereich</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {comps.length === 0 && (
              <tr>
                <td colSpan={8} className="muted center">
                  Noch keine Strecken.
                </td>
              </tr>
            )}
            {comps.map((c) => (
              <tr key={c.id}>
                <td>
                  {c.title_de}
                  {c.title_en && <div className="small muted">{c.title_en}</div>}
                </td>
                <td className="nowrap">{c.start_time ? new Date(c.start_time).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' }) : '–'}</td>
                <td className="num">{euro(c.price_adult_cents)}</td>
                <td className="num">{c.price_youth_cents === null ? '–' : euro(c.price_youth_cents)}</td>
                <td>{c.age_class_scheme}</td>
                <td className="small">
                  {c.gender_scoring && <span className="badge">w/m</span>} {c.relay_scoring && <span className="badge badge--primary">Staffel</span>}
                </td>
                <td className="nowrap">{c.bib_range_start || c.bib_range_end ? `${c.bib_range_start ?? ''}–${c.bib_range_end ?? ''}` : '–'}</td>
                <td className="nowrap">
                  <button type="button" className="btn btn--small btn--ghost" onClick={() => setEditing(c)}>
                    Bearbeiten
                  </button>
                  <button type="button" className="btn btn--small btn--ghost" onClick={() => void remove(c)}>
                    Löschen
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing !== null && (
        <CompetitionModal
          initial={editing === 'new' ? null : editing}
          index={comps.length}
          title={editing === 'new' ? 'Strecke anlegen' : `Strecke bearbeiten · ${editing.title_de}`}
          onClose={() => setEditing(null)}
          onSave={async (c) => {
            if (editing === 'new') await eventsApi.addCompetition(slug, event.id, c);
            else if (editing) await eventsApi.updateCompetition(slug, event.id, editing.id, c);
            toast.success('Strecke gespeichert.');
            onChanged();
          }}
        />
      )}
    </div>
  );
}
