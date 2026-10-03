import { Checkbox, Field } from './Field';
import { TeamNameInput } from './TeamNameInput';
import type { Gender, Language, PaymentMethod, PublicCompetition, PublicEvent } from '../api/types';
import { useLang, useT, type TranslationKey } from '../i18n';
import { euro } from '../utils/format';

export interface RegistrationFormValues {
  event_id: string;
  competition_id: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: Gender | '';
  email: string;
  language: Language;
  team_name: string;
  tshirt_size: string;
  postal_code: string;
  heard_about: string;
  consent_data: boolean;
  consent_publish: boolean;
  payment_method: PaymentMethod | '';
  iban: string;
  account_holder: string;
}

export function emptyRegistrationValues(lang: Language): RegistrationFormValues {
  return {
    event_id: '',
    competition_id: '',
    first_name: '',
    last_name: '',
    birth_date: '',
    gender: '',
    email: '',
    language: lang,
    team_name: '',
    tshirt_size: '',
    postal_code: '',
    heard_about: '',
    consent_data: false,
    consent_publish: false,
    payment_method: '',
    iban: '',
    account_holder: '',
  };
}

export interface PriceInfo {
  cents: number;
  youth: boolean;
}

/** Youth price applies when birth_date >= youth_cutoff_date and the competition has a youth price. */
export function computePrice(
  event: PublicEvent | null | undefined,
  competition: PublicCompetition | null | undefined,
  birthDate: string,
): PriceInfo | null {
  if (!event || !competition) return null;
  const youth =
    !!event.youth_cutoff_date &&
    !!birthDate &&
    birthDate >= event.youth_cutoff_date &&
    competition.price_youth_cents !== null &&
    competition.price_youth_cents !== undefined;
  return { cents: youth ? (competition.price_youth_cents as number) : competition.price_adult_cents, youth };
}

interface Props {
  slug: string;
  values: RegistrationFormValues;
  onChange: (patch: Partial<RegistrationFormValues>) => void;
  events: PublicEvent[];
  paymentMethods: PaymentMethod[];
  heardOptions: string[];
  sepaCreditor: { name: string; creditor_id: string };
  /** Office mode relaxes consent requirements and shows all events (not only open ones). */
  office?: boolean;
  disabled?: boolean;
}

export function RegistrationFormFields({
  slug,
  values,
  onChange,
  events,
  paymentMethods,
  heardOptions,
  sepaCreditor,
  office,
  disabled,
}: Props) {
  const t = useT();
  const [lang] = useLang();
  const event = events.find((e) => e.id === values.event_id) ?? null;
  const competition = event?.competitions.find((c) => c.id === values.competition_id) ?? null;
  const price = computePrice(event, competition, values.birth_date);
  const compTitle = (c: PublicCompetition) => (lang === 'en' ? c.title_en || c.title_de : c.title_de);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="stack stack--lg">
      <fieldset className="stack">
        <legend>{t('reg.competition')}</legend>
        {events.length > 1 && (
          <Field label={t('reg.event')} required>
            {(id) => (
              <select
                id={id}
                value={values.event_id}
                required
                disabled={disabled}
                onChange={(e) => onChange({ event_id: e.target.value, competition_id: '', tshirt_size: '' })}
              >
                <option value="">{t('reg.selectCompetition')}</option>
                {events.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} {e.year}
                  </option>
                ))}
              </select>
            )}
          </Field>
        )}
        <Field label={t('reg.competition')} required>
          {(id) => (
            <select
              id={id}
              value={values.competition_id}
              required
              disabled={disabled || !event}
              onChange={(e) => onChange({ competition_id: e.target.value })}
            >
              <option value="">{t('reg.selectCompetition')}</option>
              {event?.competitions.map((c) => (
                <option key={c.id} value={c.id}>
                  {compTitle(c)}
                  {c.start_time ? ` · ${t('reg.start')} ${new Date(c.start_time).toLocaleTimeString(lang === 'de' ? 'de-DE' : 'en-GB', { hour: '2-digit', minute: '2-digit' })}` : ''}
                  {' · '}
                  {c.price_adult_cents === 0 ? t('common.free') : euro(c.price_adult_cents, lang)}
                </option>
              ))}
            </select>
          )}
        </Field>
        {price && (
          <div className="price-box" aria-live="polite">
            <span>
              {t('reg.price')} <small>({price.youth ? t('reg.priceYouth') : t('reg.priceAdult')})</small>
            </span>
            <span className="price-box__value">{price.cents === 0 ? t('common.free') : euro(price.cents, lang)}</span>
          </div>
        )}
      </fieldset>

      <fieldset className="stack">
        <legend>{t('manage.participant')}</legend>
        <div className="grid grid--2">
          <Field label={t('reg.firstName')} required>
            {(id) => (
              <input
                id={id}
                value={values.first_name}
                required
                maxLength={100}
                autoComplete="given-name"
                disabled={disabled}
                onChange={(e) => onChange({ first_name: e.target.value })}
              />
            )}
          </Field>
          <Field label={t('reg.lastName')} required>
            {(id) => (
              <input
                id={id}
                value={values.last_name}
                required
                maxLength={100}
                autoComplete="family-name"
                disabled={disabled}
                onChange={(e) => onChange({ last_name: e.target.value })}
              />
            )}
          </Field>
          <Field label={t('reg.birthDate')} required>
            {(id) => (
              <input
                id={id}
                type="date"
                value={values.birth_date}
                required
                max={today}
                min="1900-01-01"
                autoComplete="bday"
                disabled={disabled}
                onChange={(e) => onChange({ birth_date: e.target.value })}
              />
            )}
          </Field>
          <Field label={t('reg.gender')} required>
            {(id) => (
              <select
                id={id}
                value={values.gender}
                required
                disabled={disabled}
                onChange={(e) => onChange({ gender: e.target.value as Gender | '' })}
              >
                <option value="">{t('reg.selectCompetition')}</option>
                <option value="f">{t('gender.f')}</option>
                <option value="m">{t('gender.m')}</option>
                <option value="x">{t('gender.x')}</option>
              </select>
            )}
          </Field>
          <Field label={t('reg.email')} required hint={office ? undefined : t('reg.emailHint')}>
            {(id) => (
              <input
                id={id}
                type="email"
                value={values.email}
                required
                maxLength={320}
                autoComplete="email"
                inputMode="email"
                disabled={disabled}
                onChange={(e) => onChange({ email: e.target.value })}
              />
            )}
          </Field>
          <Field label={t('reg.language')}>
            {(id) => (
              <select
                id={id}
                value={values.language}
                disabled={disabled}
                onChange={(e) => onChange({ language: e.target.value as Language })}
              >
                <option value="de">Deutsch</option>
                <option value="en">English</option>
              </select>
            )}
          </Field>
          <Field
            label={
              <>
                {t('reg.team')} <small>({t('common.optional')})</small>
                <span className="info-tip" title={t('reg.teamHint')} role="img" aria-label={t('reg.teamHint')}>
                  i
                </span>
              </>
            }
            hint={competition?.relay_scoring ? t('reg.teamHint') : undefined}
          >
            {(id) => (
              <TeamNameInput
                id={id}
                slug={slug}
                value={values.team_name}
                disabled={disabled}
                onChange={(v) => onChange({ team_name: v })}
              />
            )}
          </Field>
          {event && event.tshirt_options.length > 0 && (
            <Field
              label={
                <>
                  {t('reg.tshirt')}{' '}
                  {event.tshirt_included ? (
                    <span className="badge badge--primary">{t('reg.tshirtIncluded')}</span>
                  ) : (
                    <small>({t('common.optional')})</small>
                  )}
                </>
              }
            >
              {(id) => (
                <select
                  id={id}
                  value={values.tshirt_size}
                  disabled={disabled}
                  onChange={(e) => onChange({ tshirt_size: e.target.value })}
                >
                  <option value="">{event.tshirt_included ? t('reg.selectCompetition') : t('reg.tshirtNone')}</option>
                  {event.tshirt_options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          )}
          <Field
            label={
              <>
                {t('reg.postalCode')} <small>({t('common.optional')})</small>
              </>
            }
            hint={t('reg.postalCodeHint')}
          >
            {(id) => (
              <input
                id={id}
                value={values.postal_code}
                maxLength={10}
                inputMode="numeric"
                autoComplete="postal-code"
                disabled={disabled}
                onChange={(e) => onChange({ postal_code: e.target.value })}
              />
            )}
          </Field>
          <Field
            label={
              <>
                {t('reg.heardAbout')} <small>({t('common.optional')})</small>
              </>
            }
          >
            {(id) => (
              <select
                id={id}
                value={values.heard_about}
                disabled={disabled}
                onChange={(e) => onChange({ heard_about: e.target.value })}
              >
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
      </fieldset>

      <fieldset className="stack">
        <legend>{t('reg.paymentMethod')}</legend>
        <div className="radio-group" role="radiogroup">
          {paymentMethods.map((m) => (
            <label className="radio" key={m}>
              <input
                type="radio"
                name="payment_method"
                value={m}
                required
                checked={values.payment_method === m}
                disabled={disabled}
                onChange={() => onChange({ payment_method: m })}
              />
              <span>
                {t(`payment.${m}` as TranslationKey)}
                {m === 'sumup' && <div className="small muted">{t('payment.sumupHint')}</div>}
              </span>
            </label>
          ))}
        </div>
        {values.payment_method === 'sepa_debit' && (
          <div className="stack">
            <div className="grid grid--2">
              <Field label={t('payment.iban')} required>
                {(id) => (
                  <input
                    id={id}
                    value={values.iban}
                    required
                    autoComplete="off"
                    spellCheck={false}
                    disabled={disabled}
                    onChange={(e) => onChange({ iban: e.target.value.toUpperCase() })}
                    placeholder="DE00 0000 0000 0000 0000 00"
                  />
                )}
              </Field>
              <Field label={t('payment.accountHolder')} required>
                {(id) => (
                  <input
                    id={id}
                    value={values.account_holder}
                    required
                    maxLength={200}
                    autoComplete="name"
                    disabled={disabled}
                    onChange={(e) => onChange({ account_holder: e.target.value })}
                  />
                )}
              </Field>
            </div>
            <div className="notice notice--info small">
              <div>
                <strong>{t('payment.mandate')}</strong>
                <br />
                {t('payment.mandateText', {
                  creditor: sepaCreditor.name || '–',
                  creditorId: sepaCreditor.creditor_id || '–',
                })}
              </div>
            </div>
          </div>
        )}
      </fieldset>

      <fieldset className="stack">
        <legend>Einwilligungen / Consent</legend>
        <Checkbox
          label={t('reg.consentData')}
          checked={values.consent_data}
          required={!office}
          disabled={disabled}
          onChange={(v) => onChange({ consent_data: v })}
        />
        <Checkbox
          label={t('reg.consentPublish')}
          checked={values.consent_publish}
          disabled={disabled}
          onChange={(v) => onChange({ consent_publish: v })}
        />
      </fieldset>
    </div>
  );
}

/** Converts form values into the API payload (empty strings → null for optional fields). */
export function toRegistrationPayload(v: RegistrationFormValues) {
  const opt = (s: string) => (s.trim() ? s.trim() : null);
  return {
    event_id: v.event_id,
    competition_id: v.competition_id,
    first_name: v.first_name.trim(),
    last_name: v.last_name.trim(),
    birth_date: v.birth_date,
    gender: v.gender as Gender,
    email: v.email.trim(),
    language: v.language,
    team_name: opt(v.team_name),
    tshirt_size: opt(v.tshirt_size),
    postal_code: opt(v.postal_code),
    heard_about: opt(v.heard_about),
    consent_data: v.consent_data,
    consent_publish: v.consent_publish,
    payment_method: v.payment_method as PaymentMethod,
    iban: v.payment_method === 'sepa_debit' ? opt(v.iban.replace(/\s+/g, '')) : null,
    account_holder: v.payment_method === 'sepa_debit' ? opt(v.account_holder) : null,
  };
}
