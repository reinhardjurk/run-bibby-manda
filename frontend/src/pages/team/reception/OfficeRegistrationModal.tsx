import { useState, type FormEvent } from 'react';
import { errorMessage } from '../../../api/client';
import { publicApi } from '../../../api/public';
import { registrationsApi } from '../../../api/team';
import type { EventOut, RegistrationCreated } from '../../../api/types';
import { ErrorBox, Notice } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { Modal } from '../../../components/Modal';
import {
  emptyRegistrationValues,
  RegistrationFormFields,
  toRegistrationPayload,
  type RegistrationFormValues,
} from '../../../components/RegistrationFormFields';
import { useAsync } from '../../../hooks/useAsync';
import { useToast } from '../../../hooks/useToast';
import { useT } from '../../../i18n';
import { toPublicEvent } from './eventAdapter';

interface Props {
  slug: string;
  event: EventOut;
  onClose: () => void;
  onCreated: () => void;
}

/** Office (race-office) registration: same body as the public form plus a status field; no deadline check. */
export function OfficeRegistrationModal({ slug, event, onClose, onCreated }: Props) {
  const t = useT();
  const toast = useToast();
  const info = useAsync(() => publicApi.info(slug), [slug]);
  const [values, setValues] = useState<RegistrationFormValues>(() => ({
    ...emptyRegistrationValues('de'),
    event_id: event.id,
    consent_data: true,
    payment_method: 'on_site',
  }));
  const [status, setStatus] = useState<'pending' | 'confirmed'>('confirmed');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<RegistrationCreated | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!values.gender || !values.payment_method) return;
    setBusy(true);
    setError(null);
    try {
      const res = await registrationsApi.create(slug, { ...toRegistrationPayload(values), status });
      setCreated(res);
      toast.success(`Anmeldung angelegt – Startnummer ${res.bib_number}`);
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const again = () => {
    setCreated(null);
    setValues({ ...emptyRegistrationValues('de'), event_id: event.id, consent_data: true, payment_method: 'on_site' });
  };

  return (
    <Modal title={`Nachmeldung · ${event.name} ${event.year}`} onClose={onClose} wide>
      {info.loading && <Loading />}
      <ErrorBox message={info.error} onRetry={info.reload} />
      {created && (
        <div className="stack">
          <Notice kind="success">
            <div>
              <strong>Startnummer {created.bib_number}</strong>
              <div className="small">
                Verwaltungslink: <code>{created.manage_url}</code>
              </div>
              {created.payment.mandate_reference && (
                <div className="small">
                  Mandatsreferenz: <code>{created.payment.mandate_reference}</code>
                </div>
              )}
            </div>
          </Notice>
          <div className="row row--end">
            <button type="button" className="btn" onClick={again}>
              Weitere Nachmeldung
            </button>
            <button type="button" className="btn btn--primary" onClick={onClose}>
              {t('common.close')}
            </button>
          </div>
        </div>
      )}
      {info.data && !created && (
        <form className="stack stack--lg" onSubmit={submit}>
          <RegistrationFormFields
            slug={slug}
            values={values}
            onChange={(p) => setValues((v) => ({ ...v, ...p }))}
            events={[toPublicEvent(event)]}
            paymentMethods={info.data.payment_methods}
            heardOptions={info.data.heard_about_options}
            sepaCreditor={info.data.sepa_creditor}
            office
            disabled={busy}
          />
          <Field label="Status der Anmeldung">
            {(id) => (
              <select id={id} value={status} onChange={(e) => setStatus(e.target.value as 'pending' | 'confirmed')}>
                <option value="confirmed">bestätigt</option>
                <option value="pending">offen</option>
              </select>
            )}
          </Field>
          <ErrorBox message={error} />
          <div className="form-actions">
            <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
              {t('common.cancel')}
            </button>
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {busy ? t('common.saving') : 'Anmeldung anlegen'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
