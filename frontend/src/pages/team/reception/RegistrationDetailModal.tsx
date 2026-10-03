import { useEffect, useState } from 'react';
import { errorMessage, openBlob } from '../../../api/client';
import { registrationsApi } from '../../../api/team';
import type {
  EventOut,
  Gender,
  Language,
  PaymentMethod,
  PaymentStatus,
  RegistrationAdminUpdate,
  RegistrationDetail,
  RegistrationStatus,
} from '../../../api/types';
import { ConfirmDialog } from '../../../components/ConfirmDialog';
import { ErrorBox } from '../../../components/ErrorBox';
import { Checkbox, Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { Modal } from '../../../components/Modal';
import { useAsync } from '../../../hooks/useAsync';
import { useToast } from '../../../hooks/useToast';
import { useT, type TranslationKey } from '../../../i18n';
import { euroInput, formatDateTime, formatSeconds, parseEuro, parseSeconds } from '../../../utils/format';

interface Props {
  slug: string;
  registrationId: string;
  event: EventOut | null;
  heardOptions: string[];
  onClose: () => void;
  onChanged: () => void;
  onPickMerge?: (role: 'source' | 'target', participantId: string, label: string) => void;
}

interface FormState {
  status: RegistrationStatus;
  bib_number: string;
  competition_id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: Gender;
  email: string;
  language: Language;
  team_name: string;
  tshirt_size: string;
  postal_code: string;
  heard_about: string;
  consent_data: boolean;
  consent_publish: boolean;
  finish: string;
  clear_finish: boolean;
  payment_method: PaymentMethod | '';
  payment_status: PaymentStatus | '';
  amount: string;
  account_holder: string;
  iban: string;
}

function fromDetail(d: RegistrationDetail): FormState {
  return {
    status: d.status as RegistrationStatus,
    bib_number: d.bib_number === null ? '' : String(d.bib_number),
    competition_id: d.competition_id,
    first_name: d.first_name,
    last_name: d.last_name,
    birth_date: d.birth_date,
    gender: d.gender as Gender,
    email: d.email,
    language: d.language as Language,
    team_name: d.team_name ?? '',
    tshirt_size: d.tshirt_size ?? '',
    postal_code: d.postal_code ?? '',
    heard_about: d.heard_about ?? '',
    consent_data: d.consent_data,
    consent_publish: d.consent_publish,
    finish: d.finish_seconds ? formatSeconds(d.finish_seconds) : '',
    clear_finish: false,
    payment_method: (d.payment_method as PaymentMethod | null) ?? '',
    payment_status: (d.payment_status as PaymentStatus | null) ?? '',
    amount: euroInput(d.amount_cents),
    account_holder: d.payment?.account_holder ?? '',
    iban: '',
  };
}

/** Builds the PATCH body with only the changed fields. */
function diff(d: RegistrationDetail, f: FormState): RegistrationAdminUpdate | string {
  const body: RegistrationAdminUpdate = {};
  const opt = (s: string) => (s.trim() ? s.trim() : null);
  if (f.status !== d.status) body.status = f.status;
  if (f.bib_number.trim() && Number(f.bib_number) !== d.bib_number) {
    const n = Number(f.bib_number);
    if (!Number.isInteger(n) || n < 1) return 'Startnummer muss eine positive ganze Zahl sein.';
    body.bib_number = n;
  }
  if (f.competition_id !== d.competition_id) body.competition_id = f.competition_id;
  if (f.first_name.trim() !== d.first_name) body.first_name = f.first_name.trim();
  if (f.last_name.trim() !== d.last_name) body.last_name = f.last_name.trim();
  if (f.birth_date !== d.birth_date) body.birth_date = f.birth_date;
  if (f.gender !== d.gender) body.gender = f.gender;
  if (f.email.trim() !== d.email) body.email = f.email.trim();
  if (f.language !== d.language) body.language = f.language;
  if (opt(f.team_name) !== (d.team_name ?? null)) body.team_name = opt(f.team_name);
  if (opt(f.tshirt_size) !== (d.tshirt_size ?? null)) body.tshirt_size = opt(f.tshirt_size);
  if (opt(f.postal_code) !== (d.postal_code ?? null)) body.postal_code = opt(f.postal_code);
  if (opt(f.heard_about) !== (d.heard_about ?? null)) body.heard_about = opt(f.heard_about);
  if (f.consent_data !== d.consent_data) body.consent_data = f.consent_data;
  if (f.consent_publish !== d.consent_publish) body.consent_publish = f.consent_publish;
  if (f.clear_finish) {
    body.clear_finish = true;
  } else if (f.finish.trim() && f.finish.trim() !== formatSeconds(d.finish_seconds)) {
    const secs = parseSeconds(f.finish);
    if (secs === null) return 'Zielzeit bitte als h:mm:ss, mm:ss oder Sekunden eingeben.';
    body.finish_seconds = secs;
  }
  if (f.payment_method && f.payment_method !== d.payment_method) body.payment_method = f.payment_method;
  if (f.payment_status && f.payment_status !== d.payment_status) body.payment_status = f.payment_status;
  if (f.amount.trim() !== euroInput(d.amount_cents)) {
    const cents = parseEuro(f.amount);
    if (cents === null) return 'Betrag ungültig.';
    body.amount_cents = cents;
  }
  if (f.account_holder.trim() !== (d.payment?.account_holder ?? '')) body.account_holder = opt(f.account_holder);
  if (f.iban.trim()) body.iban = f.iban.replace(/\s+/g, '');
  return body;
}

export function RegistrationDetailModal({
  slug,
  registrationId,
  event,
  heardOptions,
  onClose,
  onChanged,
  onPickMerge,
}: Props) {
  const t = useT();
  const toast = useToast();
  const detail = useAsync(() => registrationsApi.get(slug, registrationId), [slug, registrationId]);
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (detail.data) setForm(fromDetail(detail.data));
  }, [detail.data]);

  const d = detail.data;
  const set = (p: Partial<FormState>) => setForm((f) => (f ? { ...f, ...p } : f));
  const competitions = event?.competitions ?? [];
  const tshirts = (event?.tshirt_options ?? '')
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);

  const save = async () => {
    if (!d || !form) return;
    const body = diff(d, form);
    if (typeof body === 'string') {
      setError(body);
      return;
    }
    if (Object.keys(body).length === 0) {
      toast.info('Keine Änderungen.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await registrationsApi.update(slug, d.id, body);
      detail.setData(updated);
      toast.success('Gespeichert.');
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const markPaid = async () => {
    if (!d) return;
    setSaving(true);
    try {
      const updated = await registrationsApi.markPaid(slug, d.id);
      detail.setData(updated);
      toast.success('Als bezahlt markiert.');
      onChanged();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const bibPdf = async () => {
    if (!d) return;
    try {
      const res = await registrationsApi.bibPdf(slug, d.id);
      openBlob(res.blob, res.filename ?? `startnummer-${d.bib_number ?? ''}.pdf`);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const remove = async () => {
    if (!d) return;
    try {
      await registrationsApi.remove(slug, d.id);
      toast.success('Anmeldung gelöscht.');
      onChanged();
      onClose();
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <Modal
      title={d ? `${d.first_name} ${d.last_name} · StNr. ${d.bib_number ?? '–'}` : 'Anmeldung'}
      onClose={onClose}
      wide
      footer={
        d && (
          <>
            <button type="button" className="btn btn--ghost" onClick={() => setConfirmDelete(true)} disabled={saving}>
              {t('common.delete')}
            </button>
            <button type="button" className="btn" onClick={bibPdf} disabled={saving}>
              Startnummer-PDF
            </button>
            {d.payment && d.payment_status !== 'paid' && (
              <button type="button" className="btn" onClick={markPaid} disabled={saving}>
                Als bezahlt markieren
              </button>
            )}
            <button type="button" className="btn btn--primary" onClick={save} disabled={saving}>
              {saving ? t('common.saving') : t('common.save')}
            </button>
          </>
        )
      }
    >
      {detail.loading && <Loading />}
      <ErrorBox message={detail.error} onRetry={detail.reload} />
      {d && form && (
        <div className="stack">
          <div className="row small muted">
            <span>Angelegt: {formatDateTime(d.created_at)}</span>
            <span>
              Teilnehmer-ID: <code>{d.participant_id}</code>
            </span>
            {d.relay_id && <span className="badge badge--primary">Staffel</span>}
            {onPickMerge && (
              <>
                <button
                  type="button"
                  className="btn btn--small btn--ghost"
                  onClick={() => onPickMerge('source', d.participant_id, `${d.first_name} ${d.last_name}`)}
                >
                  → Merge-Quelle
                </button>
                <button
                  type="button"
                  className="btn btn--small btn--ghost"
                  onClick={() => onPickMerge('target', d.participant_id, `${d.first_name} ${d.last_name}`)}
                >
                  → Merge-Ziel
                </button>
              </>
            )}
          </div>

          <fieldset>
            <legend>Anmeldung</legend>
            <div className="grid grid--3">
              <Field label="Status">
                {(id) => (
                  <select id={id} value={form.status} onChange={(e) => set({ status: e.target.value as RegistrationStatus })}>
                    <option value="pending">offen</option>
                    <option value="confirmed">bestätigt</option>
                    <option value="cancelled">storniert</option>
                  </select>
                )}
              </Field>
              <Field label="Startnummer">
                {(id) => (
                  <input id={id} inputMode="numeric" value={form.bib_number} onChange={(e) => set({ bib_number: e.target.value })} />
                )}
              </Field>
              <Field label="Strecke">
                {(id) => (
                  <select id={id} value={form.competition_id} onChange={(e) => set({ competition_id: e.target.value })}>
                    {!competitions.some((c) => c.id === form.competition_id) && (
                      <option value={form.competition_id}>{d.competition_title}</option>
                    )}
                    {competitions.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title_de}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
              <Field label="Zielzeit (h:mm:ss)">
                {(id) => (
                  <input
                    id={id}
                    value={form.finish}
                    placeholder="–"
                    disabled={form.clear_finish}
                    onChange={(e) => set({ finish: e.target.value })}
                  />
                )}
              </Field>
              <div className="field" style={{ justifyContent: 'flex-end' }}>
                <Checkbox label="Zielzeit löschen" checked={form.clear_finish} onChange={(v) => set({ clear_finish: v })} />
              </div>
            </div>
          </fieldset>

          <fieldset>
            <legend>Person</legend>
            <div className="grid grid--3">
              <Field label="Vorname">{(id) => <input id={id} value={form.first_name} onChange={(e) => set({ first_name: e.target.value })} />}</Field>
              <Field label="Nachname">{(id) => <input id={id} value={form.last_name} onChange={(e) => set({ last_name: e.target.value })} />}</Field>
              <Field label="Geburtsdatum">
                {(id) => <input id={id} type="date" value={form.birth_date} onChange={(e) => set({ birth_date: e.target.value })} />}
              </Field>
              <Field label="Geschlecht">
                {(id) => (
                  <select id={id} value={form.gender} onChange={(e) => set({ gender: e.target.value as Gender })}>
                    <option value="f">weiblich</option>
                    <option value="m">männlich</option>
                    <option value="x">divers</option>
                  </select>
                )}
              </Field>
              <Field label="E-Mail">{(id) => <input id={id} type="email" value={form.email} onChange={(e) => set({ email: e.target.value })} />}</Field>
              <Field label="Sprache">
                {(id) => (
                  <select id={id} value={form.language} onChange={(e) => set({ language: e.target.value as Language })}>
                    <option value="de">Deutsch</option>
                    <option value="en">English</option>
                  </select>
                )}
              </Field>
              <Field label="Team">{(id) => <input id={id} value={form.team_name} onChange={(e) => set({ team_name: e.target.value })} />}</Field>
              <Field label="T-Shirt">
                {(id) =>
                  tshirts.length > 0 ? (
                    <select id={id} value={form.tshirt_size} onChange={(e) => set({ tshirt_size: e.target.value })}>
                      <option value="">–</option>
                      {!tshirts.includes(form.tshirt_size) && form.tshirt_size && (
                        <option value={form.tshirt_size}>{form.tshirt_size}</option>
                      )}
                      {tshirts.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input id={id} value={form.tshirt_size} onChange={(e) => set({ tshirt_size: e.target.value })} />
                  )
                }
              </Field>
              <Field label="PLZ (freiwillig)">
                {(id) => <input id={id} value={form.postal_code} maxLength={10} onChange={(e) => set({ postal_code: e.target.value })} />}
              </Field>
              <Field label="Aufmerksam geworden durch (freiwillig)">
                {(id) => (
                  <select id={id} value={form.heard_about} onChange={(e) => set({ heard_about: e.target.value })}>
                    <option value="">–</option>
                    {heardOptions.map((o) => (
                      <option key={o} value={o}>
                        {t(`heard.${o}` as TranslationKey)}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
            </div>
            <div className="stack" style={{ marginTop: '0.75rem' }}>
              <Checkbox label="Einwilligung Datenverarbeitung" checked={form.consent_data} onChange={(v) => set({ consent_data: v })} />
              <Checkbox label="Einwilligung Veröffentlichung" checked={form.consent_publish} onChange={(v) => set({ consent_publish: v })} />
            </div>
          </fieldset>

          <fieldset>
            <legend>Zahlung</legend>
            <div className="grid grid--3">
              <Field label="Zahlungsart">
                {(id) => (
                  <select id={id} value={form.payment_method} onChange={(e) => set({ payment_method: e.target.value as PaymentMethod })}>
                    <option value="">–</option>
                    <option value="on_site">Barzahlung</option>
                    <option value="sepa_debit">SEPA-Lastschrift</option>
                    <option value="sumup">Online-Zahlung</option>
                  </select>
                )}
              </Field>
              <Field label="Zahlungsstatus">
                {(id) => (
                  <select id={id} value={form.payment_status} onChange={(e) => set({ payment_status: e.target.value as PaymentStatus })}>
                    <option value="">–</option>
                    <option value="pending">offen</option>
                    <option value="paid">bezahlt</option>
                    <option value="cancelled">storniert</option>
                  </select>
                )}
              </Field>
              <Field label="Betrag (€)">
                {(id) => <input id={id} inputMode="decimal" value={form.amount} onChange={(e) => set({ amount: e.target.value })} />}
              </Field>
              <Field label="Kontoinhaber/in">
                {(id) => <input id={id} value={form.account_holder} onChange={(e) => set({ account_holder: e.target.value })} />}
              </Field>
              <Field label="IBAN" hint={d.payment?.iban_masked ? `Gespeichert: ${d.payment.iban_masked} – nur zum Ändern neu eingeben` : 'Keine IBAN gespeichert'}>
                {(id) => <input id={id} value={form.iban} autoComplete="off" onChange={(e) => set({ iban: e.target.value.toUpperCase() })} />}
              </Field>
            </div>
            {d.payment && (
              <dl className="kv small" style={{ marginTop: '0.75rem' }}>
                {d.payment.mandate_reference && (
                  <>
                    <dt>Mandatsreferenz</dt>
                    <dd className="mono">{d.payment.mandate_reference}</dd>
                  </>
                )}
                {d.payment.provider_transaction_code && (
                  <>
                    <dt>Transaktionscode</dt>
                    <dd className="mono">{d.payment.provider_transaction_code}</dd>
                  </>
                )}
                {d.payment.paid_at && (
                  <>
                    <dt>Bezahlt am</dt>
                    <dd>{formatDateTime(d.payment.paid_at)}</dd>
                  </>
                )}
                {d.payment.sepa_exported_at && (
                  <>
                    <dt>SEPA exportiert</dt>
                    <dd>{formatDateTime(d.payment.sepa_exported_at)}</dd>
                  </>
                )}
              </dl>
            )}
          </fieldset>
          <ErrorBox message={error} />
        </div>
      )}
      {confirmDelete && d && (
        <ConfirmDialog
          title="Anmeldung löschen"
          danger
          confirmLabel="Löschen"
          message={`Anmeldung von ${d.first_name} ${d.last_name} (StNr. ${d.bib_number ?? '–'}) unwiderruflich löschen?`}
          onConfirm={remove}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </Modal>
  );
}
