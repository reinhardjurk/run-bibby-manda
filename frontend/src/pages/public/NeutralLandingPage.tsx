import { Link } from 'react-router-dom';
import { LanguageSwitch } from '../../components/LanguageSwitch';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useT } from '../../i18n';

/** Neutral entry page: no list of organizations, only a hint to use the organizer's link. */
export function NeutralLandingPage() {
  const t = useT();
  useDocumentTitle(null);
  return (
    <div className="landing">
      <div className="landing__logo" aria-hidden="true">
        B
      </div>
      <h1>{t('landing.title')}</h1>
      <p>{t('landing.subtitle')}</p>
      <p>{t('landing.hint')}</p>
      <LanguageSwitch />
      <p className="small">
        <Link to="/platform">{t('landing.platform')}</Link>
      </p>
    </div>
  );
}
