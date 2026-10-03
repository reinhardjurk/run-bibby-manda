import { useT, type TranslationKey } from '../../../i18n';

export function RegStatusBadge({ status }: { status: string }) {
  const t = useT();
  const cls = status === 'confirmed' ? 'badge--ok' : status === 'cancelled' ? 'badge--danger' : 'badge--warn';
  return <span className={`badge ${cls}`}>{t(`manage.status.${status}` as TranslationKey)}</span>;
}

export function PayBadge({ method, status }: { method: string | null; status: string | null }) {
  const t = useT();
  if (!method) return <span className="muted">–</span>;
  const cls = status === 'paid' ? 'badge--ok' : status === 'cancelled' ? 'badge--danger' : 'badge--warn';
  const short: Record<string, string> = { on_site: 'Bar', sepa_debit: 'SEPA', sumup: 'Online' };
  return (
    <span className="nowrap">
      {short[method] ?? method}{' '}
      <span className={`badge ${cls}`}>{status ? t(`payment.status.${status}` as TranslationKey) : '–'}</span>
    </span>
  );
}
