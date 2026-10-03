import { useState, type FormEvent } from 'react';
import type { EventIn, EventOut } from '../../../api/types';
import { Checkbox, Field } from '../../../components/Field';
import { fromLocalInput, randomHex, toLocalInput } from '../../../utils/format';

export interface EventFormState {
  name: string;
  year: string;
  event_date: string;
  registration_deadline: string;
  default_start_time: string;
  tshirt_options: string;
  tshirt_included: boolean;
  youth_cutoff_date: string;
  venue_postal_code: string;
  bib_start_number: string;
  certificate_offset_lines: string;
  photo_base_url: string;
  photo_hmac_seed: string;
}

export function emptyEventForm(): EventFormState {
  return {
    name: '',
    year: String(new Date().getFullYear()),
    event_date: '',
    registration_deadline: '',
    default_start_time: '',
    tshirt_options: '',
    tshirt_included: false,
    youth_cutoff_date: '',
    venue_postal_code: '',
    bib_start_number: '1',
    certificate_offset_lines: '0',
    photo_base_url: '',
    photo_hmac_seed: '',
  };
}

export function eventToForm(e: EventOut): EventFormState {
  return {
    name: e.name,
    year: String(e.year),
    event_date: e.event_date ?? '',
    registration_deadline: toLocalInput(e.registration_deadline),
    default_start_time: toLocalInput(e.default_start_time),
    tshirt_options: e.tshirt_options,
    tshirt_included: e.tshirt_included,
    youth_cutoff_date: e.youth_cutoff_date ?? '',
    venue_postal_code: e.venue_postal_code ?? '',
    bib_start_number: String(e.bib_start_number),
    certificate_offset_lines: String(e.certificate_offset_lines),
    photo_base_url: e.photo_base_url ?? '',
    photo_hmac_seed: '',
  };
}

/** Form → EventIn (create/import). Empty optionals become null. */
export function formToEventIn(f: EventFormState): EventIn {
  return {
    name: f.name.trim(),
    year: Number(f.year),
    event_date: f.event_date || null,
    registration_deadline: fromLocalInput(f.registration_deadline),
    default_start_time: fromLocalInput(f.default_start_time),
    tshirt_options: f.tshirt_options,
    tshirt_included: f.tshirt_included,
    youth_cutoff_date: f.youth_cutoff_date || null,
    venue_postal_code: f.venue_postal_code.trim() || null,
    bib_start_number: Number(f.bib_start_number) || 1,
    certificate_offset_lines: Number(f.certificate_offset_lines) || 0,
    photo_base_url: f.photo_base_url.trim() || null,
    photo_hmac_seed: f.photo_hmac_seed.trim() || null,
  };
}

/** Form → EventUpdate: nullable fields that became empty go into `clear_fields`. */
export function formToEventUpdate(f: EventFormState, original: EventOut) {
  const data = formToEventIn(f);
  const clear: string[] = [];
  const body: Record<string, unknown> = {};
  const nullable = ['event_date', 'registration_deadline', 'default_start_time', 'youth_cutoff_date', 'venue_postal_code', 'photo_base_url'] as const;
  for (const k of nullable) {
    const next = data[k];
    const prev = original[k];
    if (next === null && prev !== null) clear.push(k);
    else if (next !== null && next !== prev) body[k] = next;
  }
  if (data.name !== original.name) body['name'] = data.name;
  if (data.year !== original.year) body['year'] = data.year;
  if (data.tshirt_options !== original.tshirt_options) body['tshirt_options'] = data.tshirt_options;
  if (data.tshirt_included !== original.tshirt_included) body['tshirt_included'] = data.tshirt_included;
  if (data.bib_start_number !== original.bib_start_number) body['bib_start_number'] = data.bib_start_number;
  if (data.certificate_offset_lines !== original.certificate_offset_lines) body['certificate_offset_lines'] = data.certificate_offset_lines;
  if (data.photo_hmac_seed) body['photo_hmac_seed'] = data.photo_hmac_seed;
  return { ...body, clear_fields: clear } as import('../../../api/types').EventUpdate;
}

interface Props {
  value: EventFormState;
  onChange: (patch: Partial<EventFormState>) => void;
  onSubmit: () => void | Promise<void>;
  onCancel?: () => void;
  busy?: boolean;
  submitLabel: string;
  /** Existing event: seed field shows set-flag and never the value. */
  seedSet?: boolean;
  onClearSeed?: () => void;
}

export function EventForm({ value, onChange, onSubmit, onCancel, busy, submitLabel, seedSet, onClearSeed }: Props) {
  const [seedVisible, setSeedVisible] = useState(false);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    void onSubmit();
  };
  return (
    <form className="stack stack--lg" onSubmit={submit}>
      <fieldset className="stack">
        <legend>Veranstaltung</legend>
        <div className="grid grid--3">
          <Field label="Name" required>
            {(id) => <input id={id} value={value.name} required maxLength={200} onChange={(e) => onChange({ name: e.target.value })} />}
          </Field>
          <Field label="Jahr" required>
            {(id) => <input id={id} type="number" min={1900} max={2200} value={value.year} required onChange={(e) => onChange({ year: e.target.value })} />}
          </Field>
          <Field label="Datum">{(id) => <input id={id} type="date" value={value.event_date} onChange={(e) => onChange({ event_date: e.target.value })} />}</Field>
          <Field label="Anmeldeschluss" hint="Leer = Online-Anmeldung immer offen.">
            {(id) => <input id={id} type="datetime-local" value={value.registration_deadline} onChange={(e) => onChange({ registration_deadline: e.target.value })} />}
          </Field>
          <Field label="Standard-Startzeit" hint="Wird für neue Strecken ohne eigene Startzeit übernommen.">
            {(id) => <input id={id} type="datetime-local" value={value.default_start_time} onChange={(e) => onChange({ default_start_time: e.target.value })} />}
          </Field>
          <Field label="Jugend-Stichtag" hint="Geburtsdatum ab diesem Tag = Jugendtarif (wenn die Strecke einen hat).">
            {(id) => <input id={id} type="date" value={value.youth_cutoff_date} onChange={(e) => onChange({ youth_cutoff_date: e.target.value })} />}
          </Field>
          <Field label="PLZ Veranstaltungsort" hint="Für die Anreise-Statistik.">
            {(id) => <input id={id} value={value.venue_postal_code} maxLength={10} onChange={(e) => onChange({ venue_postal_code: e.target.value })} />}
          </Field>
          <Field label="Erste Startnummer">
            {(id) => <input id={id} type="number" min={1} value={value.bib_start_number} onChange={(e) => onChange({ bib_start_number: e.target.value })} />}
          </Field>
          <Field label="Urkunde: Zeilenversatz (±30)">
            {(id) => (
              <input id={id} type="number" min={-30} max={30} value={value.certificate_offset_lines} onChange={(e) => onChange({ certificate_offset_lines: e.target.value })} />
            )}
          </Field>
        </div>
        <Field label="T-Shirt-Größen (eine pro Zeile)">
          {(id) => <textarea id={id} rows={4} value={value.tshirt_options} onChange={(e) => onChange({ tshirt_options: e.target.value })} placeholder={'S\nM\nL\nXL'} />}
        </Field>
        <Checkbox label="T-Shirt im Startgeld enthalten" checked={value.tshirt_included} onChange={(v) => onChange({ tshirt_included: v })} />
      </fieldset>

      <fieldset className="stack">
        <legend>Zielfotos</legend>
        <div className="grid grid--2">
          <Field label="Foto-Basis-URL" hint="Pro Startnummer wird ein HMAC-Ordner angehängt: {base}/{hmac}/index.html">
            {(id) => <input id={id} type="url" value={value.photo_base_url} onChange={(e) => onChange({ photo_base_url: e.target.value })} placeholder="https://" />}
          </Field>
          <Field
            label={
              <>
                HMAC-Seed{' '}
                {seedSet ? <span className="badge badge--ok">gesetzt</span> : <span className="badge badge--warn">nicht gesetzt</span>}
              </>
            }
            hint="Wird nach dem Speichern nicht mehr angezeigt. Leer lassen = unverändert."
          >
            {(id) => (
              <div className="row">
                <input
                  id={id}
                  type={seedVisible ? 'text' : 'password'}
                  value={value.photo_hmac_seed}
                  maxLength={128}
                  autoComplete="off"
                  className="mono"
                  onChange={(e) => onChange({ photo_hmac_seed: e.target.value })}
                />
                <button
                  type="button"
                  className="btn btn--small"
                  onClick={() => {
                    onChange({ photo_hmac_seed: randomHex(16) });
                    setSeedVisible(true);
                  }}
                >
                  Zufall erzeugen
                </button>
                <button type="button" className="btn btn--small btn--ghost" onClick={() => setSeedVisible((v) => !v)}>
                  {seedVisible ? 'verbergen' : 'anzeigen'}
                </button>
                {seedSet && onClearSeed && (
                  <button type="button" className="btn btn--small btn--ghost" onClick={onClearSeed}>
                    Seed löschen
                  </button>
                )}
              </div>
            )}
          </Field>
        </div>
      </fieldset>

      <div className="form-actions">
        {onCancel && (
          <button type="button" className="btn btn--ghost" onClick={onCancel} disabled={busy}>
            Abbrechen
          </button>
        )}
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
