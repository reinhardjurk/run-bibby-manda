import { Link } from 'react-router-dom';
import { useT } from '../i18n';

export function NotFoundPage() {
  const t = useT();
  return (
    <div className="landing">
      <h1>404</h1>
      <p>{t('common.notFound')}</p>
      <Link className="btn" to="/">
        Bibby
      </Link>
    </div>
  );
}
