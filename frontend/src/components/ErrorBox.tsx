import { useT } from '../i18n';

interface Props {
  message: string | null | undefined;
  onRetry?: () => void;
}

export function ErrorBox({ message, onRetry }: Props) {
  const t = useT();
  if (!message) return null;
  return (
    <div className="notice notice--error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn btn--small btn--ghost" onClick={onRetry}>
          {t('common.retry')}
        </button>
      )}
    </div>
  );
}

export function Notice({
  kind = 'info',
  children,
}: {
  kind?: 'info' | 'warn' | 'success' | 'error';
  children: React.ReactNode;
}) {
  return <div className={`notice notice--${kind}`}>{children}</div>;
}
