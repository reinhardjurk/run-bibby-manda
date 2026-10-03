import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { publicApi } from '../../api/public';
import { errorMessage } from '../../api/client';
import type { RegistrationCreated } from '../../api/types';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Loading } from '../../components/Loading';
import { PublicLayout } from '../../components/PublicLayout';
import {
  emptyRegistrationValues,
  RegistrationFormFields,
  toRegistrationPayload,
  type RegistrationFormValues,
} from '../../components/RegistrationFormFields';
import { useAsync } from '../../hooks/useAsync';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useToast } from '../../hooks/useToast';
import { useLang, useT } from '../../i18n';
import { euro, formatDate, formatDateTime } from '../../utils/format';

function SuccessPanel({ result, onAnother }: { result: RegistrationCreated; onAnother: () => void }) {
  const t = useT();
  const [lang] = useLang();
  const manageToken = useMemo(() => {
    try {
      return new URL(result.manage_url).searchParams.get('token');
    } catch {
      return null;
    }
  }, [result.manage_url]);
  const { slug = '' } = useParams();

  useEffect(() => {
    if (result.checkout_url) {
      const id = window.setTimeout(() => {
        window.location.assign(result.checkout_url as string);
      }, 2500);
      return () => window.clearTimeout(id);
    }
  }, [result.checkout_url]);

  return (
    <div className="card success-panel stack">
      <h2>{t('reg.successTitle')}</h2>
      <div>
        <div className="muted">{t('reg.successBib')}</div>
        <div className="bib">{result.bib_number}</div>
      </div>
      <dl className="kv" style={{ textAlign: 'left', justifyContent: 'center' }}>
        <dt>{t('payment.method')}</dt>
        <dd>{t(`payment.${result.payment.method}` as 'payment.on_site')}</dd>
        <dt>{t('payment.amount')}</dt>
        <dd>{euro(result.payment.amount_cents, lang)}</dd>
        {result.payment.mandate_reference && (
          <>
            <dt>{t('payment.mandateReference')}</dt>
            <dd className="mono">{result.payment.mandate_reference}</dd>
          </>
        )}
      </dl>
      <div>
        <div className="muted small">{t('reg.successManage')}</div>
        <code>{result.manage_url}</code>
        <p className="small muted" style={{ marginTop: '0.5rem' }}>
          {t('reg.successManageHint')}
        </p>
      </div>
      {result.checkout_url && (
        <Notice kind="info">
          <span>{t('reg.successRedirect')}</span>
          <a className="btn btn--primary" href={result.checkout_url}>
            {t('reg.successPayNow')}
          </a>
        </Notice>
      )}
      <div className="row" style={{ justifyContent: 'center' }}>
        {manageToken && (
          <Link className="btn" to={`/${slug}/manage?token=${encodeURIComponent(manageToken)}`}>
            {t('reg.openManage')}
          </Link>
        )}
        <button type="button" className="btn btn--ghost" onClick={onAnother}>
          {t('reg.another')}
        </button>
      </div>
    </div>
  );
}

export function RegistrationPage() {
  const { slug = '' } = useParams();
  const t = useT();
  const [lang] = useLang();
  const toast = useToast();
  const info = useAsync(() => publicApi.info(slug), [slug]);
  const [values, setValues] = useState<RegistrationFormValues>(() => emptyRegistrationValues(lang));
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<RegistrationCreated | null>(null);
  useDocumentTitle(t('reg.title'));

  const openEvents = useMemo(() => (info.data?.events ?? []).filter((e) => e.registration_open), [info.data]);
  const closedEvents = useMemo(() => (info.data?.events ?? []).filter((e) => !e.registration_open), [info.data]);

  // Preselect when exactly one event is open.
  useEffect(() => {
    if (openEvents.length === 1 && !values.event_id) {
      setValues((v) => ({ ...v, event_id: openEvents[0]?.id ?? '' }));
    }
  }, [openEvents, values.event_id]);

  const patch = (p: Partial<RegistrationFormValues>) => setValues((v) => ({ ...v, ...p }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!values.payment_method || !values.gender) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await publicApi.register(slug, toRegistrationPayload(values));
      setResult(created);
      window.scrollTo({ top: 0 });
    } catch (err) {
      const msg = errorMessage(err);
      setSubmitError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const reset = () => {
    setResult(null);
    setValues(emptyRegistrationValues(lang));
  };

  const selectedEvent = openEvents.find((e) => e.id === values.event_id);

  return (
    <PublicLayout
      slug={slug}
      orgName={info.data?.organization.name}
      logoUrl={info.data?.logo_url}
      sponsorDisplay={info.data?.sponsor_display}
      title={t('reg.title')}
    >
      {info.loading && <Loading />}
      <ErrorBox message={info.error} onRetry={info.reload} />
      {info.data && result && <SuccessPanel result={result} onAnother={reset} />}
      {info.data && !result && (
        <div className="stack stack--lg">
          {openEvents.length === 0 && (
            <Notice kind="warn">
              <div>
                <strong>{info.data.events.length ? t('reg.closed') : t('reg.noEvents')}</strong>
                {info.data.events.length > 0 && <div className="small">{t('reg.closedHint')}</div>}
              </div>
            </Notice>
          )}
          {openEvents.length > 0 && closedEvents.length > 0 && (
            <p className="small muted">
              {t('reg.closed')}: {closedEvents.map((e) => `${e.name} ${e.year}`).join(', ')}
            </p>
          )}
          {selectedEvent && (
            <div className="card card--flat small">
              <strong>
                {selectedEvent.name} {selectedEvent.year}
              </strong>
              {selectedEvent.event_date && (
                <>
                  {' · '}
                  {t('reg.date')}: {formatDate(selectedEvent.event_date, lang)}
                </>
              )}
              {selectedEvent.registration_deadline && (
                <>
                  {' · '}
                  {t('reg.deadline')}: {formatDateTime(selectedEvent.registration_deadline, lang)}
                </>
              )}
            </div>
          )}
          {openEvents.length > 0 && (
            <form onSubmit={submit} className="stack stack--lg">
              <RegistrationFormFields
                slug={slug}
                values={values}
                onChange={patch}
                events={openEvents}
                paymentMethods={info.data.payment_methods}
                heardOptions={info.data.heard_about_options}
                sepaCreditor={info.data.sepa_creditor}
                disabled={submitting}
              />
              <ErrorBox message={submitError} />
              <div className="form-actions">
                <button type="submit" className="btn btn--primary btn--large" disabled={submitting}>
                  {submitting ? t('reg.submitting') : t('reg.submit')}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </PublicLayout>
  );
}
