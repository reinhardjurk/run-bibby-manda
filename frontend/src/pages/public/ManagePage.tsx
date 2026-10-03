import { useEffect, useState, type FormEvent } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ApiError, errorMessage, openBlob } from '../../api/client';
import { publicApi } from '../../api/public';
import type { ManageUpdate, ManageView } from '../../api/types';
import { ErrorBox, Notice } from '../../components/ErrorBox';
import { Field } from '../../components/Field';
import { Loading } from '../../components/Loading';
import { PublicLayout } from '../../components/PublicLayout';
import { TeamNameInput } from '../../components/TeamNameInput';
import { useAsync } from '../../hooks/useAsync';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useToast } from '../../hooks/useToast';
import { useLang, useT, type TranslationKey } from '../../i18n';
import { euro, formatDate, formatDateTime, formatSeconds } from '../../utils/format';

function PaymentBlock({ view }: { view: ManageView }) {
  const t = useT();
  const [lang] = useLang();
  const p = view.payment;
  return (
    <dl className="kv">
      <dt>{t('payment.method')}</dt>
      <dd>{t(`payment.${p.method}` as TranslationKey)}</dd>
      <dt>{t('payment.status')}</dt>
      <dd>
        <span className={`badge ${p.status === 'paid' ? 'badge--ok' : p.status === 'cancelled' ? 'badge--danger' : 'badge--warn'}`}>
          {t(`payment.status.${p.status}` as TranslationKey)}
        </span>
        {p.paid_at && <small className="muted"> · {formatDateTime(p.paid_at, lang)}</small>}
      </dd>
      <dt>{t('payment.amount')}</dt>
      <dd>{euro(p.amount_cents, lang)}</dd>
      {p.iban_masked && (
        <>
          <dt>{t('payment.iban')}</dt>
          <dd className="mono">{p.iban_masked}</dd>
        </>
      )}
      {p.account_holder && (
        <>
          <dt>{t('payment.accountHolder')}</dt>
          <dd>{p.account_holder}</dd>
        </>
      )}
      {p.mandate_reference && (
        <>
          <dt>{t('payment.mandateReference')}</dt>
          <dd className="mono">{p.mandate_reference}</dd>
        </>
      )}
      {view.mandate_text && (
        <>
          <dt>{t('payment.mandate')}</dt>
          <dd className="small">{view.mandate_text}</dd>
        </>
      )}
      {p.provider_transaction_code && (
        <>
          <dt>{t('payment.transactionCode')}</dt>
          <dd className="mono">{p.provider_transaction_code}</dd>
        </>
      )}
    </dl>
  );
}

export function ManagePage() {
  const { slug = '' } = useParams();
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';
  const t = useT();
  const [lang] = useLang();
  const toast = useToast();
  const info = useAsync(() => publicApi.info(slug), [slug]);
  const view = useAsync(() => publicApi.manage(slug, token), [slug, token], token.length > 0);
  const [form, setForm] = useState({ email: '', competition_id: '', team_name: '', tshirt_size: '' });
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  useDocumentTitle(t('manage.title'));

  useEffect(() => {
    if (view.data) {
      setForm({
        email: view.data.email,
        competition_id: view.data.competition_id,
        team_name: view.data.team_name ?? '',
        tshirt_size: view.data.tshirt_size ?? '',
      });
    }
  }, [view.data]);

  const data = view.data;

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (!data) return;
    const body: ManageUpdate = {};
    if (form.email.trim() !== data.email) body.email = form.email.trim();
    if (form.competition_id !== data.competition_id) body.competition_id = form.competition_id;
    if (form.team_name.trim() !== (data.team_name ?? '')) body.team_name = form.team_name.trim();
    if (form.tshirt_size !== (data.tshirt_size ?? '')) body.tshirt_size = form.tshirt_size;
    if (Object.keys(body).length === 0) {
      toast.info(t('manage.saved'));
      return;
    }
    setSaving(true);
    try {
      const updated = await publicApi.manageUpdate(slug, token, body);
      view.setData(updated);
      toast.success(t('manage.saved'));
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error(t('manage.conflict', { detail: err.detail }));
        view.reload();
      } else {
        toast.error(errorMessage(err));
      }
    } finally {
      setSaving(false);
    }
  };

  const download = async (kind: 'bib' | 'certificate') => {
    setBusy(kind);
    try {
      const res =
        kind === 'bib' ? await publicApi.manageBibPdf(slug, token) : await publicApi.manageCertificatePdf(slug, token);
      const name = kind === 'bib' ? `startnummer-${data?.bib_number ?? ''}.pdf` : `urkunde-${data?.bib_number ?? ''}.pdf`;
      openBlob(res.blob, res.filename ?? name);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const checkout = async () => {
    setBusy('checkout');
    try {
      const res = await publicApi.manageCheckout(slug, token);
      if (res.checkout_url) {
        window.location.assign(res.checkout_url);
      } else {
        toast.success(t('payment.status.paid'));
        view.reload();
      }
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(null);
    }
  };

  const compTitle = (c: { title_de: string; title_en: string }) =>
    lang === 'en' ? c.title_en || c.title_de : c.title_de;

  return (
    <PublicLayout
      slug={slug}
      orgName={info.data?.organization.name}
      logoUrl={info.data?.logo_url}
      sponsorDisplay={info.data?.sponsor_display}
      title={t('manage.title')}
    >
      {!token && <Notice kind="warn">{t('manage.missingToken')}</Notice>}
      {token && view.loading && <Loading />}
      <ErrorBox message={view.error} onRetry={view.reload} />
      {data && (
        <div className="stack stack--lg">
          <div className="card">
            <h2>
              {data.event_name} {data.event_year}
            </h2>
            <dl className="kv">
              <dt>{t('manage.participant')}</dt>
              <dd>
                {data.first_name} {data.last_name}
                <small className="muted">
                  {' '}
                  · {formatDate(data.birth_date, lang)} · {t(`gender.${data.gender}` as TranslationKey)}
                </small>
              </dd>
              <dt>{t('manage.status')}</dt>
              <dd>
                <span className={`badge ${data.status === 'confirmed' ? 'badge--ok' : data.status === 'cancelled' ? 'badge--danger' : 'badge--warn'}`}>
                  {t(`manage.status.${data.status}` as TranslationKey)}
                </span>
              </dd>
              <dt>{t('manage.bib')}</dt>
              <dd>
                <strong style={{ fontSize: '1.3rem' }}>{data.bib_number ?? '–'}</strong>
              </dd>
              <dt>{t('manage.competition')}</dt>
              <dd>{data.competition_title}</dd>
              {data.finish_seconds && (
                <>
                  <dt>{t('manage.finishTime')}</dt>
                  <dd className="mono">{formatSeconds(data.finish_seconds)}</dd>
                </>
              )}
            </dl>
            <div className="row" style={{ marginTop: '0.75rem' }}>
              <button type="button" className="btn" onClick={() => download('bib')} disabled={busy !== null}>
                {t('manage.bibPdf')}
              </button>
              {data.frozen && (
                <button type="button" className="btn" onClick={() => download('certificate')} disabled={busy !== null}>
                  {t('manage.certificatePdf')}
                </button>
              )}
              {data.photo_url && (
                <a className="btn" href={data.photo_url} target="_blank" rel="noopener noreferrer">
                  {t('manage.photos')}
                </a>
              )}
            </div>
          </div>

          <div className="card">
            <h2>{t('manage.payment')}</h2>
            <PaymentBlock view={data} />
            {data.payment.method === 'sumup' && data.payment.status === 'pending' && (
              <div style={{ marginTop: '0.75rem' }}>
                <button type="button" className="btn btn--primary" onClick={checkout} disabled={busy !== null}>
                  {t('manage.payNow')}
                </button>
              </div>
            )}
          </div>

          <form className="card stack" onSubmit={save}>
            <h2>{t('manage.changeTitle')}</h2>
            {data.frozen && <Notice kind="warn">{t('manage.frozen')}</Notice>}
            <div className="grid grid--2">
              <Field label={t('reg.email')} required>
                {(id) => (
                  <input
                    id={id}
                    type="email"
                    value={form.email}
                    required
                    disabled={data.frozen || saving}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  />
                )}
              </Field>
              <Field label={t('reg.competition')}>
                {(id) => (
                  <select
                    id={id}
                    value={form.competition_id}
                    disabled={data.frozen || saving}
                    onChange={(e) => setForm((f) => ({ ...f, competition_id: e.target.value }))}
                  >
                    {data.competitions.map((c) => (
                      <option key={c.id} value={c.id}>
                        {compTitle(c)} · {c.price_adult_cents === 0 ? t('common.free') : euro(c.price_adult_cents, lang)}
                      </option>
                    ))}
                  </select>
                )}
              </Field>
              <Field label={t('reg.team')} hint={t('reg.teamHint')}>
                {(id) => (
                  <TeamNameInput
                    id={id}
                    slug={slug}
                    value={form.team_name}
                    disabled={data.frozen || saving}
                    onChange={(v) => setForm((f) => ({ ...f, team_name: v }))}
                  />
                )}
              </Field>
              {data.tshirt_options.length > 0 && (
                <Field label={t('reg.tshirt')}>
                  {(id) => (
                    <select
                      id={id}
                      value={form.tshirt_size}
                      disabled={data.frozen || saving}
                      onChange={(e) => setForm((f) => ({ ...f, tshirt_size: e.target.value }))}
                    >
                      <option value="">{t('reg.tshirtNone')}</option>
                      {data.tshirt_options.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  )}
                </Field>
              )}
            </div>
            <div className="form-actions">
              <button type="submit" className="btn btn--primary" disabled={data.frozen || saving}>
                {saving ? t('common.saving') : t('common.save')}
              </button>
            </div>
          </form>
        </div>
      )}
    </PublicLayout>
  );
}

