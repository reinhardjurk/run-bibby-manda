import { useLang, useT } from '../i18n';

export function LanguageSwitch() {
  const [lang, setLang] = useLang();
  const t = useT();
  return (
    <div className="lang-switch" role="group" aria-label={t('common.language')}>
      <button
        type="button"
        className={lang === 'de' ? 'is-active' : ''}
        onClick={() => setLang('de')}
        aria-pressed={lang === 'de'}
      >
        DE
      </button>
      <button
        type="button"
        className={lang === 'en' ? 'is-active' : ''}
        onClick={() => setLang('en')}
        aria-pressed={lang === 'en'}
      >
        EN
      </button>
    </div>
  );
}
