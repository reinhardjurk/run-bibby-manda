import { useEffect, useState } from 'react';
import { errorMessage } from '../../../api/client';
import { settingsApi } from '../../../api/team';
import type { SettingsView } from '../../../api/types';
import { ConfirmDialog } from '../../../components/ConfirmDialog';
import { ErrorBox, Notice } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Loading } from '../../../components/Loading';
import { useAsync } from '../../../hooks/useAsync';
import { useToast } from '../../../hooks/useToast';

const TEXT_KEYS = [
  'mail_sender_name',
  'mail_sender_local_part',
  'mail_reply_to',
  'mail_subject_de',
  'mail_subject_en',
  'mail_body_de',
  'mail_body_en',
  'sepa_creditor_name',
  'sepa_creditor_id',
  'sepa_mandate_prefix',
  'sumup_merchant_code',
  'plausibility_threshold_seconds',
] as const;
type TextKey = (typeof TEXT_KEYS)[number];
type Form = Record<TextKey, string> & { mail_mode: string; sumup_api_key: string };

function str(v: string | boolean | undefined): string {
  return typeof v === 'string' ? v : '';
}

function fromView(v: SettingsView): Form {
  const f = { mail_mode: str(v['mail_mode']) || 'off', sumup_api_key: '' } as Form;
  for (const k of TEXT_KEYS) f[k] = str(v[k]);
  return f;
}

/** Organization settings: mail, SEPA creditor, SumUp, plausibility threshold, logo. */
export function SettingsSection({ slug, isAdmin, onSaved }: { slug: string; isAdmin: boolean; onSaved?: (v: SettingsView) => void }) {
  const toast = useToast();
  const view = useAsync(() => settingsApi.get(slug), [slug]);
  const [form, setForm] = useState<Form | null>(null);
  const senderDomain = typeof view.data?.['mail_sender_domain'] === 'string' ? view.data['mail_sender_domain'] : '';
  const [busy, setBusy] = useState(false);
  const [confirmLive, setConfirmLive] = useState(false);
  const [logoTick, setLogoTick] = useState(0);
  const [logoBroken, setLogoBroken] = useState(false);

  useEffect(() => {
    if (view.data) setForm(fromView(view.data));
  }, [view.data]);

  const set = (k: keyof Form, v: string) => setForm((f) => (f ? { ...f, [k]: v } : f));

  const doSave = async (confirmLiveMail: boolean) => {
    if (!form || !view.data) return;
    const values: Record<string, string> = {};
    for (const k of TEXT_KEYS) {
      if (form[k] !== str(view.data[k])) values[k] = form[k];
    }
    if (form.mail_mode !== str(view.data['mail_mode'])) values['mail_mode'] = form.mail_mode;
    if (form.sumup_api_key.trim()) values['sumup_api_key'] = form.sumup_api_key.trim();
    if (Object.keys(values).length === 0) {
      toast.info('Keine Änderungen.');
      return;
    }
    setBusy(true);
    try {
      const updated = await settingsApi.update(slug, { values, confirm_live_mail: confirmLiveMail });
      view.setData(updated);
      setForm(fromView(updated));
      onSaved?.(updated);
      toast.success('Einstellungen gespeichert.');
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
      setConfirmLive(false);
    }
  };

  const save = () => {
    if (!form || !view.data) return;
    if (form.mail_mode === 'live' && str(view.data['mail_mode']) !== 'live') {
      setConfirmLive(true);
      return;
    }
    void doSave(false);
  };

  const clearSumup = async () => {
    if (!window.confirm('SumUp-API-Key wirklich entfernen? Online-Zahlung wird dadurch deaktiviert.')) return;
    try {
      const updated = await settingsApi.clearSecret(slug, 'sumup_api_key');
      view.setData(updated);
      toast.success('API-Key entfernt.');
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const uploadLogo = async (file: File | undefined) => {
    if (!file) return;
    try {
      await settingsApi.uploadLogo(slug, file);
      toast.success('Logo hochgeladen.');
      setLogoBroken(false);
      setLogoTick((n) => n + 1);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const deleteLogo = async () => {
    if (!window.confirm('Logo entfernen?')) return;
    try {
      await settingsApi.deleteLogo(slug);
      toast.success('Logo entfernt.');
      setLogoBroken(true);
      setLogoTick((n) => n + 1);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  if (view.loading && !view.data) return <Loading />;
  if (view.error) return <ErrorBox message={view.error} onRetry={view.reload} />;
  if (!form || !view.data) return null;
  const sumupSet = view.data['sumup_api_key_set'] === true;

  return (
    <div className="stack stack--lg">
      <fieldset className="stack">
        <legend>E-Mail-Versand</legend>
        {!isAdmin && <Notice kind="info">Der Mailmodus kann nur von Org-Admins geändert werden.</Notice>}
        <Field label="Mailmodus" hint="live = echte Empfänger · test = nur an die Test-Adresse der Plattform · off = kein Versand">
          {(id) => (
            <select id={id} value={form.mail_mode} disabled={!isAdmin} onChange={(e) => set('mail_mode', e.target.value)}>
              <option value="off">off</option>
              <option value="test">test</option>
              <option value="live">live</option>
            </select>
          )}
        </Field>
        <div className="grid grid--2">
          <Field label="Absendername">{(id) => <input id={id} value={form.mail_sender_name} onChange={(e) => set('mail_sender_name', e.target.value)} />}</Field>
          <Field
            label="Absenderadresse (No-Reply)"
            hint={`Die Domain ist fest. Leer = noreply-${slug}@${senderDomain}. Antworten an diese Adresse werden nicht zugestellt – nennen Sie im Mailtext eine Kontaktadresse.`}
          >
            {(id) => (
              <div className="input-suffix">
                <input
                  id={id}
                  value={form.mail_sender_local_part}
                  placeholder={`noreply-${slug}`}
                  disabled={!isAdmin}
                  onChange={(e) => set('mail_sender_local_part', e.target.value)}
                />
                <span>@{senderDomain}</span>
              </div>
            )}
          </Field>
          <Field label="Antwort-an (Reply-To)">
            {(id) => <input id={id} type="email" value={form.mail_reply_to} onChange={(e) => set('mail_reply_to', e.target.value)} />}
          </Field>
          <Field label="Betreff (DE)">{(id) => <input id={id} value={form.mail_subject_de} onChange={(e) => set('mail_subject_de', e.target.value)} />}</Field>
          <Field label="Betreff (EN)">{(id) => <input id={id} value={form.mail_subject_en} onChange={(e) => set('mail_subject_en', e.target.value)} />}</Field>
          <Field label="Text (DE)" hint="Platzhalter {link} wird durch den Verwaltungslink ersetzt.">
            {(id) => <textarea id={id} rows={6} value={form.mail_body_de} onChange={(e) => set('mail_body_de', e.target.value)} />}
          </Field>
          <Field label="Text (EN)" hint="Placeholder {link} is replaced by the management link.">
            {(id) => <textarea id={id} rows={6} value={form.mail_body_en} onChange={(e) => set('mail_body_en', e.target.value)} />}
          </Field>
        </div>
      </fieldset>

      <fieldset className="stack">
        <legend>SEPA-Lastschrift</legend>
        <div className="grid grid--3">
          <Field label="Gläubigername">{(id) => <input id={id} value={form.sepa_creditor_name} onChange={(e) => set('sepa_creditor_name', e.target.value)} />}</Field>
          <Field label="Gläubiger-ID">{(id) => <input id={id} value={form.sepa_creditor_id} onChange={(e) => set('sepa_creditor_id', e.target.value)} />}</Field>
          <Field label="Mandatsreferenz-Präfix">
            {(id) => <input id={id} value={form.sepa_mandate_prefix} onChange={(e) => set('sepa_mandate_prefix', e.target.value)} />}
          </Field>
        </div>
      </fieldset>

      <fieldset className="stack">
        <legend>Online-Zahlung (SumUp)</legend>
        <div className="grid grid--2">
          <Field
            label={
              <>
                API-Key{' '}
                {sumupSet ? <span className="badge badge--ok">gesetzt</span> : <span className="badge badge--warn">nicht gesetzt</span>}
              </>
            }
            hint="Wird verschlüsselt gespeichert und nie wieder angezeigt. Leer lassen = unverändert."
          >
            {(id) => (
              <div className="row">
                <input
                  id={id}
                  type="password"
                  autoComplete="new-password"
                  value={form.sumup_api_key}
                  disabled={!isAdmin}
                  onChange={(e) => set('sumup_api_key', e.target.value)}
                  placeholder={sumupSet ? '••••••••' : ''}
                />
                {sumupSet && isAdmin && (
                  <button type="button" className="btn btn--small" onClick={() => void clearSumup()}>
                    Entfernen
                  </button>
                )}
              </div>
            )}
          </Field>
          <Field label="Merchant-Code">
            {(id) => <input id={id} value={form.sumup_merchant_code} disabled={!isAdmin} onChange={(e) => set('sumup_merchant_code', e.target.value)} />}
          </Field>
        </div>
      </fieldset>

      <fieldset className="stack">
        <legend>Zeitnahme</legend>
        <Field label="Plausibilitätsschwelle (Sekunden)" className="field--narrow">
          {(id) => (
            <input id={id} inputMode="decimal" value={form.plausibility_threshold_seconds} onChange={(e) => set('plausibility_threshold_seconds', e.target.value)} />
          )}
        </Field>
      </fieldset>

      <div className="form-actions">
        <button type="button" className="btn btn--primary" onClick={save} disabled={busy}>
          {busy ? 'Wird gespeichert …' : 'Einstellungen speichern'}
        </button>
      </div>

      <fieldset className="stack">
        <legend>Logo</legend>
        <div className="row">
          {!logoBroken && (
            <img
              key={logoTick}
              src={`${settingsApi.logoUrl(slug)}?v=${logoTick}`}
              alt="Aktuelles Logo"
              className="preview-img"
              style={{ maxHeight: 80 }}
              onError={() => setLogoBroken(true)}
            />
          )}
          {logoBroken && <span className="muted small">Kein Logo hinterlegt.</span>}
        </div>
        <div className="row">
          <input type="file" accept="image/*" onChange={(e) => void uploadLogo(e.target.files?.[0])} aria-label="Logo hochladen" />
          {!logoBroken && (
            <button type="button" className="btn btn--small" onClick={() => void deleteLogo()}>
              Logo entfernen
            </button>
          )}
        </div>
      </fieldset>

      {confirmLive && (
        <ConfirmDialog
          title="Mailmodus auf „live“ umschalten"
          confirmLabel="Ja, live schalten"
          danger
          message={
            <>
              Im Modus <strong>live</strong> werden Bestätigungs-E-Mails an echte Teilnehmende versendet. Bitte stellen
              Sie sicher, dass Absender, Betreff und Texte korrekt sind.
            </>
          }
          onConfirm={() => doSave(true)}
          onCancel={() => setConfirmLive(false)}
        />
      )}
    </div>
  );
}
