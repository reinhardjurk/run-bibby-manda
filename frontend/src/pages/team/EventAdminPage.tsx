import { useRef, useState } from 'react';
import { downloadBlob, errorMessage } from '../../api/client';
import { eventsApi } from '../../api/team';
import type { CompetitionIn, EventOut, EventTemplate } from '../../api/types';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { PageHead } from '../../components/EventSelector';
import { Notice } from '../../components/ErrorBox';
import { Loading } from '../../components/Loading';
import { Modal } from '../../components/Modal';
import { useToast } from '../../hooks/useToast';
import { formatDate, formatDateTime } from '../../utils/format';
import { CompetitionEditor, CompetitionModal } from './events/CompetitionEditor';
import { emptyEventForm, EventForm, eventToForm, formToEventIn, formToEventUpdate, type EventFormState } from './events/EventForm';
import { useTeam } from './TeamContext';

function BackgroundUpload({ slug, event, kind, has, onChanged }: { slug: string; event: EventOut; kind: 'certificate' | 'bib'; has: boolean; onChanged: () => void }) {
  const toast = useToast();
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const label = kind === 'certificate' ? 'Urkunden-Hintergrund' : 'Startnummern-Hintergrund';
  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    try {
      await eventsApi.uploadBackground(slug, event.id, kind, file);
      toast.success(`${label} hochgeladen.`);
      setTick((n) => n + 1);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  const clear = async () => {
    if (!window.confirm(`${label} entfernen?`)) return;
    try {
      await eventsApi.update(slug, event.id, { clear_fields: [kind === 'certificate' ? 'certificate_background' : 'bib_background'] });
      toast.success(`${label} entfernt.`);
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };
  return (
    <div className="stack">
      <strong>{label}</strong>
      {has ? (
        <img src={`${eventsApi.backgroundUrl(slug, event.id, kind)}?v=${tick}`} alt={label} className="preview-img" />
      ) : (
        <span className="muted small">Kein Hintergrund (max. 8 MB, wird auf A4@300dpi skaliert).</span>
      )}
      <div className="row">
        <input type="file" accept="image/*" disabled={busy} onChange={(e) => void upload(e.target.files?.[0])} aria-label={`${label} hochladen`} />
        {has && (
          <button type="button" className="btn btn--small" onClick={() => void clear()}>
            Entfernen
          </button>
        )}
      </div>
    </div>
  );
}

function EventDetail({ event }: { event: EventOut }) {
  const { slug, me, reloadEvents } = useTeam();
  const toast = useToast();
  const [form, setForm] = useState<EventFormState>(() => eventToForm(event));
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isAdmin = me.roles.includes('admin');

  const save = async () => {
    setBusy(true);
    try {
      await eventsApi.update(slug, event.id, formToEventUpdate(form, event));
      toast.success('Veranstaltung gespeichert.');
      setForm((f) => ({ ...f, photo_hmac_seed: '' }));
      reloadEvents();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const clearSeed = async () => {
    if (!window.confirm('HMAC-Seed löschen? Bestehende Foto-Links werden ungültig.')) return;
    try {
      await eventsApi.update(slug, event.id, { clear_fields: ['photo_hmac_seed'] });
      toast.success('Seed gelöscht.');
      reloadEvents();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const exportTemplate = async () => {
    try {
      const tpl = await eventsApi.template(slug, event.id);
      const blob = new Blob([JSON.stringify(tpl, null, 2)], { type: 'application/json' });
      downloadBlob(blob, `bibby-template-${event.name.replace(/\s+/g, '_')}.json`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const remove = async () => {
    try {
      await eventsApi.remove(slug, event.id);
      toast.success('Veranstaltung gelöscht.');
      reloadEvents();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <div className="stack stack--lg">
      <div className="row row--between">
        <div className="small muted">
          {event.registration_count} Anmeldungen · Urkunden-Hintergrund: {event.has_certificate_background ? 'ja' : 'nein'} · StNr.-Hintergrund: {event.has_bib_background ? 'ja' : 'nein'}
        </div>
        <div className="row">
          <button type="button" className="btn btn--small" onClick={() => void exportTemplate()}>
            Vorlage exportieren (JSON)
          </button>
          {isAdmin && (
            <button type="button" className="btn btn--small btn--danger" onClick={() => setConfirmDelete(true)}>
              Veranstaltung löschen
            </button>
          )}
        </div>
      </div>
      <EventForm value={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} onSubmit={save} busy={busy} submitLabel="Speichern" seedSet={event.photo_seed_set} onClearSeed={clearSeed} />
      <div className="grid grid--2">
        <BackgroundUpload slug={slug} event={event} kind="certificate" has={event.has_certificate_background} onChanged={reloadEvents} />
        <BackgroundUpload slug={slug} event={event} kind="bib" has={event.has_bib_background} onChanged={reloadEvents} />
      </div>
      <CompetitionEditor slug={slug} event={event} onChanged={reloadEvents} />
      {confirmDelete && (
        <ConfirmDialog
          title="Veranstaltung löschen"
          danger
          confirmLabel="Endgültig löschen"
          requireText={event.name}
          message={
            <>
              <strong>
                {event.name} {event.year}
              </strong>{' '}
              mit allen {event.registration_count} Anmeldungen, Zeiten und Hintergründen unwiderruflich löschen?
            </>
          }
          onConfirm={remove}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}

/** Create dialog – also used after a template import (prefilled, with competitions). */
function CreateEventModal({ initial, competitions: initialComps, onClose }: { initial: EventFormState; competitions: CompetitionIn[]; onClose: () => void }) {
  const { slug, reloadEvents, setSelectedEventId } = useTeam();
  const toast = useToast();
  const [form, setForm] = useState<EventFormState>(initial);
  const [comps, setComps] = useState<CompetitionIn[]>(initialComps);
  const [editIdx, setEditIdx] = useState<number | 'new' | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    try {
      const body = formToEventIn(form);
      const created = comps.length > 0 ? await eventsApi.importTemplate(slug, { ...body, competitions: comps }) : await eventsApi.create(slug, body);
      toast.success('Veranstaltung angelegt.');
      reloadEvents();
      setSelectedEventId(created.id);
      onClose();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Veranstaltung anlegen" onClose={onClose} wide>
      <div className="stack stack--lg">
        <EventForm value={form} onChange={(p) => setForm((f) => ({ ...f, ...p }))} onSubmit={create} onCancel={onClose} busy={busy} submitLabel="Anlegen" />
        <div className="stack">
          <div className="row row--between">
            <h3 style={{ margin: 0 }}>Strecken ({comps.length})</h3>
            <button type="button" className="btn btn--small" onClick={() => setEditIdx('new')}>
              + Strecke
            </button>
          </div>
          {comps.length === 0 && <p className="muted small">Strecken können auch nach dem Anlegen ergänzt werden.</p>}
          {comps.length > 0 && (
            <ul className="capture-list">
              {comps.map((c, i) => (
                <li key={`${c.title_de}-${i}`}>
                  <span>
                    {c.title_de} · {(c.price_adult_cents / 100).toFixed(2)} €
                  </span>
                  <span>
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => setEditIdx(i)}>
                      Bearbeiten
                    </button>
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => setComps((l) => l.filter((_, j) => j !== i))}>
                      Entfernen
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {editIdx !== null && (
        <CompetitionModal
          initial={editIdx === 'new' ? null : (comps[editIdx] ?? null)}
          index={comps.length}
          title={editIdx === 'new' ? 'Strecke hinzufügen' : 'Strecke bearbeiten'}
          onClose={() => setEditIdx(null)}
          onSave={(c) => {
            setComps((l) => (editIdx === 'new' ? [...l, c] : l.map((x, j) => (j === editIdx ? c : x))));
          }}
        />
      )}
    </Modal>
  );
}

/** Tab "Events" (full width): list, create, edit, backgrounds, competitions, template export/import, delete. */
export function EventAdminPage() {
  const { events, eventsLoading, selectedEventId, setSelectedEventId } = useTeam();
  const toast = useToast();
  const [create, setCreate] = useState<{ form: EventFormState; comps: CompetitionIn[] } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const selected = events.find((e) => e.id === selectedEventId) ?? null;

  const importFile = async (file: File | undefined) => {
    if (!file) return;
    try {
      const tpl = JSON.parse(await file.text()) as EventTemplate;
      if (!tpl || typeof tpl.name !== 'string') throw new Error('Keine gültige Bibby-Vorlage.');
      setCreate({
        form: {
          ...emptyEventForm(),
          name: tpl.name,
          tshirt_options: tpl.tshirt_options ?? '',
          tshirt_included: !!tpl.tshirt_included,
          venue_postal_code: tpl.venue_postal_code ?? '',
          bib_start_number: String(tpl.bib_start_number ?? 1),
          certificate_offset_lines: String(tpl.certificate_offset_lines ?? 0),
        },
        comps: Array.isArray(tpl.competitions) ? tpl.competitions : [],
      });
      toast.info('Vorlage geladen – bitte Jahr und Datum ergänzen.');
    } catch (err) {
      toast.error(errorMessage(err, 'Vorlage konnte nicht gelesen werden.'));
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  return (
    <div className="stack">
      <PageHead title="Veranstaltungen">
        <button type="button" className="btn btn--primary" onClick={() => setCreate({ form: emptyEventForm(), comps: [] })}>
          + Veranstaltung
        </button>
        <label className="btn">
          Vorlage importieren
          <input ref={fileRef} type="file" accept="application/json,.json" className="visually-hidden" onChange={(e) => void importFile(e.target.files?.[0])} />
        </label>
      </PageHead>
      {eventsLoading && events.length === 0 && <Loading />}
      {!eventsLoading && events.length === 0 && <Notice kind="info">Noch keine Veranstaltung – legen Sie die erste an oder importieren Sie eine Vorlage.</Notice>}
      {events.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th className="num">Jahr</th>
                <th>Datum</th>
                <th>Anmeldeschluss</th>
                <th className="num">Strecken</th>
                <th className="num">Anmeldungen</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="is-clickable" onClick={() => setSelectedEventId(e.id)} style={e.id === selectedEventId ? { background: 'var(--color-primary-soft)' } : undefined}>
                  <td>
                    <strong>{e.name}</strong>
                  </td>
                  <td className="num">{e.year}</td>
                  <td className="nowrap">{formatDate(e.event_date)}</td>
                  <td className="nowrap">{e.registration_deadline ? formatDateTime(e.registration_deadline) : <span className="muted">offen</span>}</td>
                  <td className="num">{e.competitions.length}</td>
                  <td className="num">{e.registration_count}</td>
                  <td>
                    <button type="button" className="btn btn--small btn--ghost" onClick={() => setSelectedEventId(e.id)}>
                      Bearbeiten
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selected && (
        <section className="card">
          <h2>
            {selected.name} {selected.year}
          </h2>
          <EventDetail key={selected.id + String(selected.photo_seed_set) + String(selected.has_bib_background) + String(selected.has_certificate_background)} event={selected} />
        </section>
      )}
      {create && <CreateEventModal initial={create.form} competitions={create.comps} onClose={() => setCreate(null)} />}
    </div>
  );
}
